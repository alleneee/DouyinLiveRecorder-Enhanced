# 通知时机说明 - 队列化上传后的变更

## 📌 问题背景

使用上传队列后，视频和音频上传变为异步并行处理，必须确保**只有在视频和音频都上传成功后**才发送通知，避免：
- ❌ 通知过早发送（文件还未上传完成）
- ❌ 通知重复发送（视频和音频回调都触发通知）
- ❌ 并发竞态条件（两个回调同时检查状态）

---

## 🔄 处理流程对比

### 之前的流程（直接上传）

```
分片创建
   ↓
格式转换 (TS → MP4)
   ↓
音频抽取 (MP4 → MP3)
   ↓
[并行上传]
   ├─ 视频上传 ─┐
   └─ 音频上传 ─┤
                ↓
          上传完成
                ↓
          发送通知  ← ⚠️ 问题：可能在未上传完就发送
                ↓
          清理文件
```

### 优化后的流程（队列化上传）

```
分片创建
   ↓
格式转换 (TS → MP4)
   ↓
音频抽取 (MP4 → MP3)
   ↓
[提交到上传队列]
   ├─ 视频任务 → 队列 → 工作线程1 → 上传 → 回调1 ─┐
   └─ 音频任务 → 队列 → 工作线程2 → 上传 → 回调2 ─┤
                                                    ↓
                                    [_check_and_finalize_upload]
                                         (带数据库行锁)
                                                    ↓
                                        检查：视频 + 音频都完成？
                                                    ↓
                                            ┌───────┴────────┐
                                           NO               YES
                                            ↓                ↓
                                    等待另一个完成    更新状态为UPLOADED
                                                            ↓
                                                    ✅ 发送通知（只一次）
                                                            ↓
                                                    更新session统计
                                                            ↓
                                                    清理本地文件
```

---

## 🔒 关键实现：线程安全的检查逻辑

### 核心方法：`_check_and_finalize_upload`

```python
def _check_and_finalize_upload(self, db: Session, segment_id: int, ...):
    """检查并完成上传流程（线程安全，只通知一次）"""
    
    # 1️⃣ 数据库行锁 - 防止并发冲突
    video_segment = db.query(VideoSegment).filter(
        VideoSegment.id == segment_id
    ).with_for_update().first()  # ← SELECT ... FOR UPDATE
    
    # 2️⃣ 幂等性检查 - 防止重复处理
    if video_segment.status == SegmentStatus.UPLOADED:
        return  # 已处理过，直接返回
    
    # 3️⃣ 检查两个文件是否都上传完成
    has_video = bool(video_segment.oss_video_url)
    has_audio = bool(video_segment.oss_audio_url)
    
    if not (has_video and has_audio):
        # 还有文件未完成，释放锁并等待
        db.commit()
        return
    
    # 4️⃣ 两个文件都完成，更新状态
    video_segment.status = SegmentStatus.UPLOADED
    db.commit()
    
    # 5️⃣ 发送通知（只执行一次）
    segment_notifier.send_notification_sync(db, segment_id)
    
    # 6️⃣ 清理本地文件
    self._cleanup_temp_files(...)
```

---

## 📊 时序图

### 场景：视频先完成，音频后完成

```
时间轴 →

视频上传完成 (t1)                    音频上传完成 (t2)
     ↓                                      ↓
回调：_on_video_upload_complete    回调：_on_audio_upload_complete
     ↓                                      ↓
保存 oss_video_url                  保存 oss_audio_url
     ↓                                      ↓
_check_and_finalize_upload          _check_and_finalize_upload
     ↓                                      ↓
加行锁 (FOR UPDATE)                 ⏳ 等待行锁...
     ↓                                      ↓
检查：video=✅ audio=❌              加行锁 (FOR UPDATE)
     ↓                                      ↓
等待音频完成                        检查：video=✅ audio=✅
释放锁 →                                   ↓
                                   状态更新为UPLOADED
                                           ↓
                                   ✅ 发送通知
                                           ↓
                                   清理文件
                                   释放锁 →
```

---

## ⚠️ 重要机制说明

### 1. 数据库行锁（SELECT FOR UPDATE）

```sql
-- 加锁查询，防止并发修改
SELECT * FROM video_segments WHERE id = 123 FOR UPDATE;
```

**作用**：
- ✅ 确保同一时刻只有一个线程能修改记录
- ✅ 后到达的回调会等待锁释放
- ✅ 避免"两个回调都认为自己是最后一个"的竞态

**示例场景**：
```
线程1（视频）：获取锁 → 检查(video=✅, audio=❌) → 释放锁
线程2（音频）：等待锁 → 获取锁 → 检查(video=✅, audio=✅) → 发送通知 → 释放锁
```

### 2. 幂等性检查

```python
if video_segment.status == SegmentStatus.UPLOADED:
    return  # 已处理，跳过
```

**作用**：
- ✅ 防止通知重复发送
- ✅ 处理异常情况（如回调被重试）
- ✅ 保证最多发送一次通知

### 3. 独立数据库会话

```python
def _on_video_upload_complete(...):
    db_callback = SessionLocal()  # ← 新会话
    try:
        # 处理逻辑
    finally:
        db_callback.close()
```

**作用**：
- ✅ 回调在不同线程执行，需要独立会话
- ✅ 避免线程间会话冲突
- ✅ 自动管理事务生命周期

---

## 🎯 通知时机保证

### ✅ 正确的通知时机

| 场景 | 视频状态 | 音频状态 | 是否通知 | 说明 |
|-----|---------|---------|---------|------|
| 视频完成 | ✅ | ❌ | ❌ | 等待音频 |
| 音频完成 | ❌ | ✅ | ❌ | 等待视频 |
| **两者都完成** | **✅** | **✅** | **✅** | **发送通知** |
| 已发送过通知 | ✅ | ✅ | ❌ | 幂等性保护 |

### ✅ 通知发送条件（AND逻辑）

```python
可以发送通知 = (
    video_segment.oss_video_url != None AND
    video_segment.oss_audio_url != None AND
    video_segment.status != SegmentStatus.UPLOADED  # 未发送过
)
```

---

## 🔍 异常场景处理

### 场景1：视频上传失败

```
视频上传失败
     ↓
状态标记为 FAILED
     ↓
❌ 不发送通知
     ↓
保留本地文件（便于重试）
```

### 场景2：音频上传失败

```
音频上传失败
     ↓
状态标记为 FAILED
     ↓
❌ 不发送通知
     ↓
保留本地文件（便于重试）
```

### 场景3：通知发送失败

```
两个文件都上传成功
     ↓
状态更新为 UPLOADED ✅
     ↓
发送通知失败 ❌
     ↓
日志记录错误
     ↓
⚠️ 状态已更新，可通过日志补发通知
```

---

## 📝 日志追踪

### 关键日志输出

```log
# 1. 任务提交
[抖音 | 12345 | abc123 | seg5] 上传任务已提交到队列, priority=5, queue_size=23

# 2. 视频上传完成
[抖音 | 12345 | abc123 | seg5] 视频URL已保存: live-recorder/prod/抖音/12345/20251023/5/video.mp4

# 3. 第一次检查（视频先完成）
[抖音 | 12345 | abc123 | seg5] 等待其他文件上传完成 (video=True, audio=False)

# 4. 音频上传完成
[抖音 | 12345 | abc123 | seg5] 音频URL已保存: live-recorder/prod/抖音/12345/20251023/5/audio.mp3

# 5. 第二次检查（都完成）
[抖音 | 12345 | abc123 | seg5] 🎉 分片上传完成，准备发送通知

# 6. 通知发送
[抖音 | 12345 | abc123 | seg5] ✅ 分片通知已发送

# 7. 文件清理
[抖音 | 12345 | abc123 | seg5] ✅ 本地文件已清理: TS: seg5.ts, MP4: seg5.mp4, MP3: seg5.mp3
```

---

## 🚀 优势总结

### 1. 准确性 ✅
- **保证**：通知只在视频和音频都上传成功后发送
- **避免**：过早通知导致下游系统获取不到文件

### 2. 可靠性 ✅
- **保证**：通知最多发送一次（幂等性）
- **避免**：重复通知导致下游系统重复处理

### 3. 并发安全 ✅
- **保证**：数据库行锁防止竞态条件
- **避免**：两个线程同时修改状态

### 4. 可追溯性 ✅
- **保证**：详细的日志记录每个步骤
- **便于**：问题排查和性能分析

---

## 🎯 最佳实践

### ✅ DO（推荐）
1. 始终在回调中使用独立的数据库会话
2. 使用行锁保护关键状态检查
3. 记录详细的状态变更日志
4. 实现幂等性检查防止重复操作

### ❌ DON'T（禁止）
1. ❌ 不要在单个文件上传完成后立即发送通知
2. ❌ 不要在没有锁保护的情况下并发修改状态
3. ❌ 不要假设回调的执行顺序
4. ❌ 不要跨线程共享数据库会话

---

**生成时间**: 2025-10-23  
**相关文件**: `app/services/recording_manager.py`, `app/services/upload_queue_manager.py`
