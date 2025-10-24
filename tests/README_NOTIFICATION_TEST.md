# 分片通知测试指南

## 快速开始

### 1. 配置通知URL

在 `.env` 文件中配置接收端URL:

```env
SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com
```

**推荐测试方式**:

#### 方式A: 使用 webhook.site (最简单)
```bash
1. 访问 https://webhook.site/
2. 复制 "Your unique URL" (例如: https://webhook.site/abc123...)
3. 配置到 .env:
   SEGMENT_NOTIFICATION_BASE_URL=https://webhook.site/abc123
```

#### 方式B: 使用你的真实API
```env
SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com
```

---

### 2. 运行测试

```bash
# 进入项目目录
cd /Users/niko/DouyinLiveRecorder

# 运行真实环境测试
python tests/test_real_notification.py
```

---

## 测试内容

### 自动测试的分片

脚本会测试数据库中的以下分片:

| 分片ID | 索引 | 时长 | 时间范围 |
|--------|------|------|----------|
| 352 | 0 | 300秒 | 00:00:00 → 00:05:00 |
| 353 | 1 | 300秒 | 00:05:00 → 00:10:00 |
| 354 | 2 | 300秒 | 00:10:00 → 00:15:00 |
| 355 | 3 | 300秒 | 00:15:00 → 00:20:00 |

---

## 预期输出

### ✅ 成功场景

```
🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔
分片通知真实环境测试
🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔🔔

⚙️  配置检查:
  数据库: localhost:3306/douyinlive
  通知URL: http://your-api.com/shard/plan

📋 测试计划:
  分片ID: [352, 353, 354, 355]

是否继续测试? (输入 y 继续, 其他键取消)
>>> y

================================================================================
测试分片 ID: 352
================================================================================

📦 分片信息:
  平台: 抖音
  房间: 83436154836
  主播: xxx
  Session: 6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60
  索引: 0
  状态: uploaded
  时长: 300秒
  时间: 00:00:00 → 00:05:00

📁 OSS文件:
  视频: live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.MP4
  音频: live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.mp3

🔍 构建通知数据...

📋 通知数据:
{
  "live_info": {
    "live_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
    "live_url": "https://live.douyin.com/83436154836",
    "live_name": "主播名"
  },
  "sub_video_info": {
    "video_url": "live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.MP4",
    "audio_url": "live-recorder/test/抖音/83436154836/20251024/0/20251024_100802_seg000.mp3",
    "duration": 300,
    "absolute_start_time": "2025-10-24T10:08:02",
    "absolute_end_time": "2025-10-24T10:13:02",
    "serial_num": 0,
    "last_segment_flag": false
  }
}

📤 发送通知到: http://your-api.com/shard/plan
⏳ 等待响应...

[抖音 | 83436154836 | 6ae8cf2b | seg0] ✅ 分片通知发送成功:
  HTTP状态: 200
  响应内容: {
    "code": 0,
    "message": "success"
  }

✅ 通知发送成功!

[后续分片测试...]

================================================================================
📊 批量测试结果:
================================================================================
✅ 成功 - 分片 #352
✅ 成功 - 分片 #353
✅ 成功 - 分片 #354
✅ 成功 - 分片 #355

总计: 4/4 成功

🎉 所有测试通过!
```

---

### ❌ 失败场景示例

#### 场景1: 连接失败

```
📤 发送通知到: http://invalid-url.com/shard/plan
⏳ 等待响应...

[抖音 | 83436154836 | 6ae8cf2b | seg0] ❌ 分片通知连接失败:
  错误信息: Failed to establish a new connection
  请检查URL是否正确: http://invalid-url.com/shard/plan

❌ 通知发送失败
```

#### 场景2: HTTP错误

```
[抖音 | 83436154836 | 6ae8cf2b | seg0] ❌ 分片通知发送失败:
  HTTP状态: 500
  响应内容: {"error": "Internal Server Error"}
  请检查接收端服务是否正常

❌ 通知发送失败
```

#### 场景3: 超时

```
[抖音 | 83436154836 | 6ae8cf2b | seg0] ❌ 分片通知超时:
  超时时间: 30秒
  请检查网络连接或增加timeout配置

❌ 通知发送失败
```

---

## 验证方法

### 使用 webhook.site

1. 打开 https://webhook.site/your-unique-id
2. 运行测试后,在网站上查看:
   - 请求时间
   - 请求Headers
   - 请求Body (JSON格式)
   - 响应状态

### 使用真实API

检查你的API日志,应该能看到:

```json
{
  "live_info": {
    "live_id": "6ae8cf2b-7d06-41f7-8922-ffe6a09ebb60",
    "live_url": "https://live.douyin.com/83436154836",
    "live_name": "主播名"
  },
  "sub_video_info": {
    "video_url": "live-recorder/test/抖音/...",
    "audio_url": "live-recorder/test/抖音/...",
    "duration": 300,
    "absolute_start_time": "2025-10-24T10:08:02",
    "absolute_end_time": "2025-10-24T10:13:02",
    "serial_num": 0,
    "last_segment_flag": false
  }
}
```

---

## 常见问题

### Q1: 提示 "未配置 SEGMENT_NOTIFICATION_BASE_URL"

**解决方案**:
```bash
# 编辑 .env 文件
nano .env

# 添加配置
SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com

# 重新运行测试
python tests/test_real_notification.py
```

---

### Q2: 提示 "数据库中找不到 segment_id=xxx"

**原因**: 数据库中没有对应的分片数据

**解决方案**:
1. 检查数据库中是否有数据:
   ```sql
   SELECT id, segment_index, status FROM video_segments
   WHERE id IN (352, 353, 354, 355);
   ```

2. 如果没有数据,修改脚本中的 `test_segment_ids`:
   ```python
   # 使用你的实际segment_id
   test_segment_ids = [你的ID1, 你的ID2, ...]
   ```

---

### Q3: 提示 "分片状态不是 'uploaded'"

**原因**: 分片还未上传到OSS

**解决方案**:
- 等待分片上传完成
- 或选择状态为 'uploaded' 的分片进行测试

---

### Q4: 接收端收到请求但返回错误

**检查清单**:
1. 接收端是否正确处理JSON数据
2. 是否返回 200-299 状态码
3. 响应body格式是否正确

**推荐接收端实现**:
```python
@app.post("/shard/plan")
async def receive_notification(data: dict):
    # 处理逻辑...
    return {"code": 0, "message": "success"}
```

---

## 进阶测试

### 测试单个分片

修改 `main()` 函数:

```python
# 只测试一个分片
test_segment_ids = [352]
```

### 测试更多分片

```python
# 测试更多分片
test_segment_ids = [352, 353, 354, 355, 356, 357, ...]
```

### 修改超时时间

如果网络慢,可以增加超时:

```python
# 在脚本开头添加
from app.services.segment_notifier import segment_notifier
segment_notifier.timeout = 60  # 增加到60秒
```

---

## 其他测试脚本

### Mock服务器测试 (可选)

如果想本地测试,可以使用Mock服务器:

```bash
# 终端1: 启动Mock服务器
python tests/mock_notification_server.py

# 终端2: 配置并测试
# .env 中配置: SEGMENT_NOTIFICATION_BASE_URL=http://localhost:8888
python tests/test_real_notification.py
```

---

**最后更新**: 2025-01-24
**作者**: Claude Code SuperClaude
