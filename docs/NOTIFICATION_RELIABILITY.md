# 分片通知可靠性说明

## 快速修复版本 (v1.1 - 2025-01-24)

### 改进内容

本次更新移除了原有的 **Fire-and-Forget** 模式,改为**同步验证响应**模式,确保通知发送的可靠性。

---

## 核心改进

### ✅ 1. HTTP 状态码验证

**改进前**:
```python
# 发送后立即返回,不检查响应
requests.post(...)
# 静默处理结果,不记录日志
```

**改进后**:
```python
response = requests.post(...)
if 200 <= response.status_code < 300:
    logger.info("✅ 分片通知发送成功")
    return True
else:
    logger.error(f"❌ HTTP {response.status_code}: {response.text}")
    return False
```

---

### ✅ 2. 详细错误分类

**网络超时**:
```
❌ 分片通知超时:
  超时时间: 30秒
  请检查网络连接或增加timeout配置
```

**连接失败**:
```
❌ 分片通知连接失败:
  错误信息: Connection refused
  请检查URL是否正确: http://example.com/webhook
```

**HTTP错误**:
```
❌ 分片通知发送失败:
  HTTP状态: 500
  响应内容: {"error": "Internal Server Error"}
  请检查接收端服务是否正常
```

---

### ✅ 3. 完整响应日志

**成功响应 (JSON)**:
```
✅ 分片通知发送成功:
  HTTP状态: 200
  响应内容: {
    "code": 0,
    "message": "success",
    "data": {...}
  }
```

**成功响应 (文本)**:
```
✅ 分片通知发送成功:
  HTTP状态: 200
  响应内容: OK
```

---

## 接收端要求

### 必须满足

1. **返回 HTTP 200-299 状态码**
   - ✅ 200 OK
   - ✅ 201 Created
   - ✅ 204 No Content
   - ❌ 4xx 客户端错误
   - ❌ 5xx 服务端错误

2. **30秒内完成响应**
   - 超过30秒会触发超时错误
   - 建议异步处理耗时操作,快速响应

### 推荐格式

```json
{
  "code": 0,
  "message": "success"
}
```

---

## 故障排查

### 问题1: 日志显示超时

**原因**:
- 接收端处理时间过长 (>30秒)
- 网络延迟严重

**解决方案**:
```python
# 接收端: 快速响应 + 异步处理
@app.post("/webhook/segment")
async def receive_notification(data: dict):
    # 立即返回200
    background_tasks.add_task(process_segment, data)
    return {"code": 0, "message": "accepted"}
```

---

### 问题2: 日志显示连接失败

**原因**:
- URL配置错误
- 接收端服务未启动
- 防火墙阻止连接

**检查方法**:
```bash
# 测试连接
curl -X POST http://your-api.com/webhook/segment \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

---

### 问题3: 日志显示HTTP 4xx/5xx

**原因**:
- 接收端数据验证失败 (400)
- 接收端业务逻辑错误 (500)

**解决方案**:
1. 检查接收端日志
2. 验证请求数据格式
3. 使用webhook.site测试数据结构

---

## 未来规划

### 阶段2: 状态跟踪 (计划中)

```sql
-- 数据库字段扩展
ALTER TABLE video_segments ADD COLUMN notification_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE video_segments ADD COLUMN notification_attempts INT DEFAULT 0;
ALTER TABLE video_segments ADD COLUMN notification_last_attempt_at DATETIME;
ALTER TABLE video_segments ADD COLUMN notification_error TEXT;
```

### 阶段3: 重试机制 (计划中)

```python
class NotificationRetryWorker:
    """后台重试队列"""
    retry_delays = [10, 30, 60, 300, 600]  # 指数退避
    max_attempts = 5
```

---

## 配置选项

### 当前可配置项

```env
# .env
SEGMENT_NOTIFICATION_BASE_URL=http://your-api.com  # 基础URL
```

### 未来可配置项 (待实现)

```env
SEGMENT_NOTIFICATION_MAX_RETRY=5              # 最大重试次数
SEGMENT_NOTIFICATION_TIMEOUT=30               # 超时时间(秒)
SEGMENT_NOTIFICATION_REQUIRE_CONFIRMATION=true  # 是否要求业务层确认
```

---

## 测试建议

### 1. 使用 webhook.site 测试

```bash
# 访问 https://webhook.site/
# 复制 Unique URL
# 配置到 .env

SEGMENT_NOTIFICATION_BASE_URL=https://webhook.site/your-unique-id
```

### 2. 本地 Mock 服务器

```python
# test_webhook_server.py
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.post("/shard/plan")
async def receive_notification(data: dict):
    print(f"收到通知: {data}")
    return {"code": 0, "message": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
```

```bash
# 启动测试服务器
python test_webhook_server.py

# 配置
SEGMENT_NOTIFICATION_BASE_URL=http://localhost:8888
```

---

## 版本历史

### v1.1 (2025-01-24) - 快速修复
- ✅ 移除 Fire-and-Forget 模式
- ✅ 添加 HTTP 状态码验证
- ✅ 详细错误分类和日志
- ✅ 完整响应内容记录

### v1.0 (2025-01-17) - 初始版本
- ✅ 基础通知功能
- ❌ Fire-and-Forget 模式(已废弃)

---

**更新日期**: 2025-01-24
**作者**: Claude Code SuperClaude
