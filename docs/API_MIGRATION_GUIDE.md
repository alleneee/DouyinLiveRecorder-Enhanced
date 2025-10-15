# API 迁移指南

## 📋 概述

已将旧的 `recordings.py` API 迁移到新的 `recording_v2.py`，并统一为 `recording` 路由。

## 🔄 API 路径变更

### 旧路径（已废弃）

```
POST /api/recordings/{room_id}/start
POST /api/recordings/{room_id}/stop
GET  /api/recordings/{room_id}
```

### 新路径（推荐使用）

```
POST /api/recording/start
POST /api/recording/stop
GET  /api/recording/status
```

## 📝 主要变更

### 1. 启动录制接口

#### 旧接口
```bash
POST /api/recordings/{room_id}/start
{
  "force": false
}
```

#### 新接口
```bash
POST /api/recording/start
{
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "quality": "OD",
  "video_save_type": "TS",
  "converts_to_mp4": false,
  "folder_by_author": true,
  
  "enable_segment_recording": true,
  "segment_duration": 1200,
  
  "oss_enabled": true,
  "oss_upload_immediately": false,
  "oss_delete_after_upload": false,
  
  "run_post_process": true,
  "generate_m3u8": true,
  "extract_audio": true,
  
  "push_on_start": true,
  "push_on_stop": true
}
```

**优势**：
- ✅ 不需要预先创建 room
- ✅ 支持更多配置选项
- ✅ 支持分段录制/连续录制切换
- ✅ 支持 OSS 配置覆盖

### 2. 停止录制接口

#### 旧接口
```bash
POST /api/recordings/{room_id}/stop
```

#### 新接口
```bash
POST /api/recording/stop?url=https://live.douyin.com/296728101980
```

**变更**：
- 使用 URL 参数而不是 room_id
- 更直观的接口设计

### 3. 查询状态接口

#### 旧接口
```bash
GET /api/recordings/{room_id}
```

#### 新接口
```bash
GET /api/recording/status
```

**返回示例**：
```json
[
  {
    "status": "running",
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "message": "录制中"
  }
]
```

## 🎯 迁移步骤

### 步骤 1：更新 API 端点

将所有 API 调用从旧路径更新到新路径：

```python
# 旧代码
response = requests.post(
    f"http://localhost:8009/api/recordings/{room_id}/start",
    json={"force": False}
)

# 新代码
response = requests.post(
    "http://localhost:8009/api/recording/start",
    json={
        "url": "https://live.douyin.com/296728101980",
        "nickname": "央视网财经",
        "enable_segment_recording": True
    }
)
```

### 步骤 2：更新请求参数

新接口需要提供完整的录制配置：

```python
# 最小配置
payload = {
    "url": "https://live.douyin.com/xxx",
    "nickname": "主播名"
}

# 完整配置
payload = {
    "url": "https://live.douyin.com/xxx",
    "nickname": "主播名",
    "quality": "OD",
    "enable_segment_recording": True,
    "segment_duration": 1200,
    "oss_enabled": True
}
```

### 步骤 3：更新停止录制调用

```python
# 旧代码
response = requests.post(
    f"http://localhost:8009/api/recordings/{room_id}/stop"
)

# 新代码
response = requests.post(
    "http://localhost:8009/api/recording/stop",
    params={"url": "https://live.douyin.com/xxx"}
)
```

## 📊 功能对比

| 功能 | 旧接口 | 新接口 |
|------|--------|--------|
| 启动录制 | ✅ | ✅ |
| 停止录制 | ✅ | ✅ |
| 查询状态 | ✅ | ✅ |
| 分段录制 | ❌ | ✅ |
| OSS 配置 | ❌ | ✅ |
| 后处理配置 | ❌ | ✅ |
| 推送配置 | ❌ | ✅ |
| 数据库记录 | 部分 | ✅ 完整 |

## 🔧 兼容性说明

### 已移除的功能

1. **Room 管理**：不再需要预先创建 room
2. **room_id 参数**：使用 URL 直接标识直播间
3. **force 参数**：自动检测重复录制

### 新增的功能

1. **录制模式选择**：分段录制 vs 连续录制
2. **配置覆盖**：可以覆盖全局配置
3. **任务记录**：完整的数据库记录
4. **视频分段记录**：每20分钟一条记录

## 🎨 示例代码

### Python 客户端

```python
import requests

class RecordingClient:
    def __init__(self, base_url="http://localhost:8009"):
        self.base_url = base_url
    
    def start_recording(self, url: str, nickname: str, **kwargs):
        """启动录制。"""
        payload = {
            "url": url,
            "nickname": nickname,
            **kwargs
        }
        response = requests.post(
            f"{self.base_url}/api/recording/start",
            json=payload
        )
        return response.json()
    
    def stop_recording(self, url: str):
        """停止录制。"""
        response = requests.post(
            f"{self.base_url}/api/recording/stop",
            params={"url": url}
        )
        return response.json()
    
    def get_status(self):
        """获取所有录制状态。"""
        response = requests.get(
            f"{self.base_url}/api/recording/status"
        )
        return response.json()

# 使用示例
client = RecordingClient()

# 启动分段录制
client.start_recording(
    url="https://live.douyin.com/296728101980",
    nickname="央视网财经",
    enable_segment_recording=True,
    oss_enabled=True
)

# 停止录制
client.stop_recording("https://live.douyin.com/296728101980")

# 查询状态
status = client.get_status()
print(status)
```

### cURL 示例

```bash
# 启动录制
curl -X POST "http://localhost:8009/api/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "enable_segment_recording": true
  }'

# 停止录制
curl -X POST "http://localhost:8009/api/recording/stop?url=https://live.douyin.com/296728101980"

# 查询状态
curl -X GET "http://localhost:8009/api/recording/status"
```

## 🐛 常见问题

### Q1: 旧接口还能用吗？

**A**: 已移除旧接口，请尽快迁移到新接口。

### Q2: 如何获取 room_id？

**A**: 新接口不再使用 room_id，直接使用直播间 URL。

### Q3: 如何实现旧接口的 force 参数？

**A**: 新接口自动检测重复录制，无需 force 参数。如果已在录制，会返回 "running" 状态。

### Q4: 数据库表结构变了吗？

**A**: 新增了 `recording_tasks` 表，保留了原有的 `rooms` 和 `recordings` 表。

## 📚 相关文档

- [API 请求示例](API_REQUEST_EXAMPLES.md)
- [录制模式指南](RECORDING_MODES_GUIDE.md)
- [分段录制指南](SEGMENT_RECORDING_GUIDE.md)
- [Swagger 文档](http://localhost:8009/docs)

## 🎉 总结

✅ **新接口优势**：
- 更简洁的 API 设计
- 更强大的功能支持
- 更完整的数据记录
- 更灵活的配置选项

🔄 **迁移建议**：
- 尽快更新到新接口
- 使用新的请求参数格式
- 利用新功能提升录制体验
