# 上传队列和通知机制测试指南

## 📋 测试覆盖范围

### 核心功能验证
- ✅ Callback正确触发（成功/失败）
- ✅ 视频+音频都完成后才发送通知
- ✅ 通知只发送一次（幂等性）
- ✅ 并发安全（数据库行锁）
- ✅ 失败自动重试机制
- ✅ 队列FIFO顺序

---

## 🚀 快速开始

### 方式1：手动测试（推荐新手）

```bash
# 进入项目目录
cd /Users/niko/DouyinLiveRecorder

# 激活环境
pyenv shell 3.12.11

# 运行手动测试
python tests/manual_test_upload_callback.py
```

**预期输出**：
```
🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪
上传队列回调机制手动测试
🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪

============================================================
测试1：验证callback是否被触发
============================================================

📤 提交任务: /var/folders/.../test_xxx.txt
任务提交: 成功

⏳ 等待上传完成...

✅ Callback被触发！
  - success: True
  - result: {'key': 'live-recorder/test/20251023/test_xxx.txt', ...}
  - error: None

✅ 测试通过 - Callback被成功触发

============================================================
测试结果汇总
============================================================
✅ 通过 - 基础Callback触发
✅ 通过 - 通知时机顺序
✅ 通过 - 并发Callback
✅ 通过 - 失败Callback

总计: 4/4 通过

🎉 所有测试通过！
```

### 方式2：Pytest单元测试（推荐开发者）

```bash
# 安装pytest（如果还没有）
pip install pytest pytest-mock

# 运行所有测试
pytest tests/test_upload_queue_notification.py -v

# 运行特定测试
pytest tests/test_upload_queue_notification.py::TestUploadQueueManager::test_callback_triggered_on_success -v

# 显示详细输出
pytest tests/test_upload_queue_notification.py -v -s

# 只运行集成测试
pytest tests/test_upload_queue_notification.py -v -m integration
```

**预期输出**：
```
tests/test_upload_queue_notification.py::TestUploadQueueManager::test_manager_start_stop PASSED [ 10%]
tests/test_upload_queue_notification.py::TestUploadQueueManager::test_callback_triggered_on_success PASSED [ 20%]
tests/test_upload_queue_notification.py::TestUploadQueueManager::test_callback_triggered_on_failure PASSED [ 30%]
tests/test_upload_queue_notification.py::TestUploadQueueManager::test_retry_mechanism PASSED [ 40%]
tests/test_upload_queue_notification.py::TestUploadQueueManager::test_concurrent_tasks PASSED [ 50%]
tests/test_upload_queue_notification.py::TestNotificationTiming::test_notification_after_both_complete PASSED [ 60%]
tests/test_upload_queue_notification.py::TestNotificationTiming::test_notification_idempotency PASSED [ 70%]
tests/test_upload_queue_notification.py::TestNotificationTiming::test_concurrent_finalize_race_condition PASSED [ 80%]
tests/test_upload_queue_notification.py::TestIntegrationFlow::test_full_upload_notification_flow PASSED [ 90%]

======================== 9 passed in 15.32s =========================
```

---

## 📊 测试详解

### 测试类1：UploadQueueManager

#### test_manager_start_stop
- **目的**：验证队列管理器正常启动和停止
- **验证点**：
  - `running` 状态正确
  - 工作线程数量正确
  - 优雅关闭

#### test_callback_triggered_on_success
- **目的**：验证上传成功时callback被触发
- **关键点**：
  - Mock `oss_uploader.upload_file`
  - Callback收到正确的结果
  - `success=True`

#### test_callback_triggered_on_failure
- **目的**：验证上传失败时callback被触发
- **关键点**：
  - Mock抛出异常
  - Callback收到错误信息
  - `success=False`

#### test_retry_mechanism
- **目的**：验证失败自动重试
- **关键点**：
  - 前2次失败，第3次成功
  - 只调用一次最终callback
  - 重试次数统计正确

#### test_concurrent_tasks
- **目的**：验证并发任务处理
- **关键点**：
  - 同时提交10个任务
  - 所有callback都被触发
  - 无丢失或重复

---

### 测试类2：NotificationTiming

#### test_notification_after_both_complete
- **目的**：验证通知时机（核心测试）
- **流程**：
  1. 只上传视频 → 不发送通知
  2. 再上传音频 → 发送通知
- **验证点**：
  - 视频完成后：`oss_video_url`已保存，状态仍为UPLOADING
  - 音频完成后：`oss_audio_url`已保存，状态变为UPLOADED
  - 通知只在最后发送一次

#### test_notification_idempotency
- **目的**：验证通知幂等性
- **场景**：分片已经是UPLOADED状态
- **验证点**：再次调用不会重复发送通知

#### test_concurrent_finalize_race_condition
- **目的**：验证并发竞态条件下的数据库行锁
- **场景**：两个线程同时调用`_check_and_finalize_upload`
- **验证点**：通知只发送一次（行锁保护）

---

### 测试类3：IntegrationFlow

#### test_full_upload_notification_flow
- **目的**：端到端集成测试
- **完整流程**：
  1. 创建分片记录
  2. 触发上传流程
  3. 格式转换 + 音频抽取
  4. 提交到上传队列
  5. 队列处理上传
  6. 触发callback
  7. 检查并发送通知
  8. 清理本地文件
- **验证点**：
  - 最终状态为UPLOADED
  - 视频和音频URL都已保存
  - 通知被发送

---

## 🔍 调试技巧

### 查看详细日志

```bash
# 运行时查看日志
tail -f logs/app.log | grep -E "callback|通知|上传"
```

**关键日志**：
```
[抖音 | 12345 | abc123 | seg0] 执行上传完成回调     ← Callback触发
[抖音 | 12345 | abc123 | seg0] 视频URL已保存        ← 保存URL
[抖音 | 12345 | abc123 | seg0] 音频URL已保存        ← 保存URL
[抖音 | 12345 | abc123 | seg0] 🎉 分片上传完成     ← 都完成
[抖音 | 12345 | abc123 | seg0] ✅ 分片通知已发送   ← 通知发送
[抖音 | 12345 | abc123 | seg0] ✅ 本地文件已清理   ← 清理文件
```

### 数据库检查

```sql
-- 查看分片状态
SELECT id, status, oss_video_url, oss_audio_url, error_message
FROM video_segments
ORDER BY id DESC
LIMIT 10;

-- 应该看到：
-- status = 'UPLOADED'
-- oss_video_url IS NOT NULL
-- oss_audio_url IS NOT NULL
```

### Python调试

```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用日志
logger.debug(f"变量值: video_path={video_path}, segment_id={segment_id}")
```

---

## ⚠️ 常见问题

### Q1: Callback没有被触发

**排查步骤**：
1. 检查队列是否启动
   ```python
   from app.services.upload_queue_manager import upload_queue_manager
   print(upload_queue_manager.running)  # 应该是True
   ```

2. 检查任务是否提交成功
   ```python
   submitted = upload_queue_manager.submit(task)
   print(submitted)  # 应该是True
   ```

3. 查看worker线程日志
   ```bash
   grep "UploadWorker" logs/app.log
   ```

### Q2: 通知发送了两次

**可能原因**：
- 并发竞态条件未处理
- 幂等性检查失效

**验证**：
```sql
-- 查看分片状态
SELECT status FROM video_segments WHERE id = 123;
-- 应该只有一条 status='UPLOADED' 的记录
```

**修复**：确保`_check_and_finalize_upload`中使用了`with_for_update()`行锁

### Q3: 通知没有发送

**可能原因**：
- 视频或音频上传失败
- 状态检查逻辑错误

**排查**：
```sql
-- 检查URL是否都已保存
SELECT oss_video_url, oss_audio_url, status
FROM video_segments
WHERE id = 123;

-- 应该看到：
-- oss_video_url: 'live-recorder/...'
-- oss_audio_url: 'live-recorder/...'
-- status: 'UPLOADED'
```

### Q4: 队列一直满

**排查**：
```python
from app.services.upload_queue_manager import upload_queue_manager
stats = upload_queue_manager.get_stats()
print(f"队列长度: {stats['current_queue_size']}/{upload_queue_manager.max_queue_size}")
print(f"失败数: {stats['total_failed']}")
```

**解决**：
- 增大队列大小：`OSS_UPLOAD_QUEUE_SIZE=1000`
- 增加工作线程：`OSS_UPLOAD_WORKERS=20`
- 检查是否有任务一直失败重试

---

## 📈 性能基准

### 单个任务处理时间

| 阶段 | 耗时 | 说明 |
|-----|------|------|
| 格式转换（TS→MP4） | 2-5秒 | 取决于视频大小 |
| 音频抽取 | 0.5-1秒 | 通常很快 |
| 小文件上传（<50MB） | 1-3秒 | 简单上传 |
| 大文件上传（>50MB） | 5-15秒 | 分片上传 |
| Callback执行 | <0.1秒 | 数据库更新 |
| **总计** | **8-24秒** | 端到端 |

### 并发性能

| 并发数 | 队列长度 | 工作线程 | 预期QPS |
|--------|----------|----------|---------|
| 10直播间 | 100 | 10 | 2-3/s |
| 50直播间 | 500 | 15 | 8-10/s |
| 100直播间 | 1000 | 20 | 15-20/s |

---

## ✅ 验收标准

运行测试后，所有以下条件都应满足：

1. ✅ 所有pytest测试通过
2. ✅ 手动测试显示 "🎉 所有测试通过！"
3. ✅ 日志中看到 "执行上传完成回调"
4. ✅ 日志中看到 "🎉 分片上传完成，准备发送通知"
5. ✅ 日志中看到 "✅ 分片通知已发送"
6. ✅ 数据库中分片状态为 UPLOADED
7. ✅ 本地临时文件被清理

---

## 🔧 持续集成

### GitHub Actions配置示例

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-mock
      
      - name: Run tests
        run: |
          pytest tests/test_upload_queue_notification.py -v
```

---

**最后更新**: 2025-10-23  
**维护者**: DouyinLiveRecorder Team
