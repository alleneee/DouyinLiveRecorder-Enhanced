# Session ID 恢复修复说明

## 问题描述

**日期**: 2025-01-24

**问题**: 应用重启后(发版/网络问题),正在录制的直播会生成新的 `session_id`,导致分片通知的 `live_id` 不连续

### 问题场景

```
1. 直播正在录制中
   - session_id: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
   - 分片: seg0, seg1, seg2 已录制

2. 应用重启(发版/网络问题)

3. 重启后继续录制
   - ❌ 旧逻辑: 生成新的 session_id: abcd1234-5678-90ef-ghij-klmnopqrstuv
   - ❌ 分片: seg3, seg4 使用新的 session_id
   - ❌ 分片通知的 live_id 不连续,无法关联到同一个直播

4. 期望行为
   - ✅ 保留原有 session_id: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
   - ✅ 分片: seg3, seg4 继续使用相同的 session_id
   - ✅ 所有分片的 live_id 一致,可以正确关联
```

---

## 根本原因

### 1. **缺少恢复逻辑**

应用启动时(`app/main.py:14-71`):
- ✅ 恢复了监听任务(`start_monitor`)
- ❌ **没有恢复录制任务**
- ❌ **没有检查 `record_status=RECORDING` 的房间**

### 2. **Session 信息丢失风险**

数据库中虽然保存了 `current_session_id` 和 `current_session_started_at`:
- ✅ 监听逻辑(751-759行)会优先使用已有的 session_id
- ⚠️ 但如果重启时直播已结束,会清空这些信息
- ⚠️ 下次开播会生成新的 session_id

---

## 修复方案

### 1. **添加录制恢复方法** (`recording_manager.py:344-426`)

```python
def recover_interrupted_recordings(self):
    """
    应用重启后,恢复中断的录制任务

    检查数据库中所有 record_status=RECORDING 的房间,
    保留原有的 session_id 并重新启动录制任务
    """
    # 查询所有正在录制的房间
    recording_rooms = db.query(LiveRoom).filter(
        LiveRoom.record_status == RecordStatus.RECORDING
    ).all()

    for room in recording_rooms:
        # 验证 session 信息完整性
        if not room.current_session_id or not room.current_session_started_at:
            # 信息缺失,重置为 IDLE
            room.record_status = RecordStatus.IDLE
            continue

        # 检查直播状态
        is_live = self._check_live_status(room)

        if not is_live:
            # 直播已结束,清理会话
            self._stop_recording(db, room)
            continue

        # 直播仍在进行,恢复录制 (保留原有 session_id)
        logger.info(f"🔄 恢复录制任务: session={room.current_session_id[:8]}")
        self._start_recording(db, room)  # 会使用现有的 session_id
```

**关键点**:
- ✅ 保留 `current_session_id` 和 `current_session_started_at`
- ✅ 验证直播仍在进行
- ✅ 重新启动录制任务,使用原有 session

### 2. **应用启动时调用恢复** (`app/main.py:54-63`)

```python
# 恢复监听任务
for room in enabled_rooms:
    await loop.run_in_executor(
        None,
        recording_manager.start_monitor,
        room.id
    )

# ✅ 恢复中断的录制任务（必须在监听任务恢复后执行）
logger.info("检查并恢复中断的录制任务...")
await loop.run_in_executor(
    None,
    recording_manager.recover_interrupted_recordings
)
```

**执行顺序**:
1. 先恢复监听任务
2. 再恢复录制任务
3. 避免竞争条件

---

## 修复后的行为

### 场景1: 直播仍在进行,应用重启

```
重启前:
- session_id: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
- session_started_at: 2025-10-24 10:08:02
- record_status: RECORDING
- 分片: seg0, seg1, seg2

重启后:
1. 应用启动
2. recover_interrupted_recordings() 检测到 room.record_status=RECORDING
3. 验证 session 信息完整: ✅
4. 检查直播状态: is_live=True ✅
5. 恢复录制任务,保留原 session_id

继续录制:
- session_id: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60  ← 相同
- session_started_at: 2025-10-24 10:08:02  ← 相同
- record_status: RECORDING
- 分片: seg3, seg4, seg5  ← 连续
```

### 场景2: 直播已结束,应用重启

```
重启前:
- session_id: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
- record_status: RECORDING

重启后:
1. 应用启动
2. recover_interrupted_recordings() 检测到 room.record_status=RECORDING
3. 检查直播状态: is_live=False ❌
4. 清理会话: current_session_id=None, record_status=IDLE
5. 不恢复录制任务
```

### 场景3: Session 信息缺失

```
重启前:
- session_id: NULL  ← 异常情况
- record_status: RECORDING

重启后:
1. 应用启动
2. recover_interrupted_recordings() 检测到 room.record_status=RECORDING
3. 验证 session 信息: session_id 缺失 ❌
4. 重置状态: record_status=IDLE
5. 跳过恢复
```

---

## 验证方法

### 1. **模拟重启测试**

```bash
# 步骤1: 启动直播录制
curl -X POST "http://localhost:8000/rooms/1/start"

# 步骤2: 等待录制几个分片
sleep 30

# 步骤3: 记录当前 session_id
mysql -e "SELECT current_session_id, record_status FROM live_rooms WHERE id=1"

# 步骤4: 重启应用
kill -9 <pid>
./start_api.sh

# 步骤5: 验证 session_id 是否保留
mysql -e "SELECT current_session_id, record_status FROM live_rooms WHERE id=1"

# 步骤6: 检查新分片的 session_id
mysql -e "SELECT session_id FROM video_segments WHERE room_id=1 ORDER BY id DESC LIMIT 3"
```

**期望结果**:
- 重启前后 `current_session_id` **相同**
- 新分片的 `session_id` 与旧分片**相同**
- 分片通知的 `live_id` **连续**

### 2. **查看启动日志**

```bash
tail -f logs/app.log | grep "恢复录制任务"
```

**期望输出**:
```
📋 发现 1 个中断的录制任务,开始恢复...
[抖音 | 83436154836 | 6ae8cf2b] 检查直播状态...
[抖音 | 83436154836 | 6ae8cf2b] 🔄 恢复录制任务...
[抖音 | 83436154836 | 6ae8cf2b]   Session ID: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
[抖音 | 83436154836 | 6ae8cf2b]   开始时间: 2025-10-24 10:08:02
[抖音 | 83436154836 | 6ae8cf2b] ✅ 录制任务恢复成功
✅ 录制任务恢复完成
```

---

## 技术细节

### Session 生命周期

```
1. 开播检测 (monitor_worker:748-764)
   ↓
2. 生成/复用 session_id
   - current_session_id = room.current_session_id or uuid4()
   - 优先使用已有的,无则生成新的
   ↓
3. 启动录制 (_start_recording:716-746)
   - record_status = RECORDING
   - 提交录制任务到线程池
   ↓
4. 录制进行中 (_recording_worker)
   - 持续录制,生成分片
   - 所有分片使用相同 session_id
   ↓
5. 下播检测 (monitor_worker:765-767)
   ↓
6. 停止录制 (_stop_recording:748-825)
   - current_session_id = None
   - current_session_started_at = None
   - record_status = IDLE
```

### 重启恢复流程

```
应用启动 (app/main.py:lifespan)
   ↓
恢复监听任务 (34-50行)
   - start_monitor() 所有 is_enabled=True 的房间
   ↓
恢复录制任务 (54-63行)  ← 新增
   - recover_interrupted_recordings()
   - 检查 record_status=RECORDING 的房间
   - 保留 session_id,重启录制
   ↓
正常运行
```

---

## 影响分析

### 用户影响

**改进前**:
- ❌ 重启后同一直播的分片 `session_id` 不连续
- ❌ 分片通知的 `live_id` 变化,无法正确关联
- ❌ 用户需要手动处理分片关联问题

**改进后**:
- ✅ 重启后保留原 `session_id`
- ✅ 所有分片的 `live_id` 一致
- ✅ 分片通知可以正确关联到同一直播

### 技术影响

**优点**:
- ✅ Session 连续性得到保证
- ✅ 分片通知数据一致性提升
- ✅ 符合直播录制的业务语义

**注意事项**:
- ⚠️ 恢复逻辑会检查直播状态,如果已结束会清理 session
- ⚠️ Session 信息缺失时会重置状态,避免脏数据

---

## 测试场景

### 1. **正常重启**
- 直播正在进行
- 应用重启
- 期望: session_id 保留,录制继续

### 2. **直播结束后重启**
- 直播已结束,但状态未更新
- 应用重启
- 期望: 清理 session,状态重置为 IDLE

### 3. **异常数据**
- record_status=RECORDING,但 session_id=NULL
- 应用重启
- 期望: 重置状态,跳过恢复

### 4. **并发场景**
- 重启时,监听线程检测到开播
- 恢复逻辑同时执行
- 期望: 无竞争条件,session_id 一致

---

## 版本历史

### v1.2.0 (2025-01-24) - Session 恢复修复
- ✅ 添加 `recover_interrupted_recordings()` 方法
- ✅ 应用启动时自动恢复中断的录制任务
- ✅ 保留原有 session_id 和 session_started_at
- ✅ 验证直播状态,避免恢复已结束的直播

---

**更新日期**: 2025-01-24
**作者**: Claude Code SuperClaude
