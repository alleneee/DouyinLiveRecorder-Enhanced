# DouyinLiveRecorder API - 完整 cURL 请求示例

本文档提供 `live_rooms.py` 中所有 API 端点的 cURL 请求示例。

**基础URL**: `http://localhost:8000`

**Content-Type**: `application/json`

---

## 📋 目录

1. [新增监控直播间](#1-新增监控直播间)
2. [删除监控直播间](#2-删除监控直播间)
3. [查看所有直播间状态](#3-查看所有直播间状态)
4. [查看单个直播间状态](#4-查看单个直播间状态)
5. [激活录制](#5-激活录制)
6. [停止录制](#6-停止录制)
7. [查看监听器状态](#7-查看监听器状态)
8. [检测直播状态](#8-检测直播状态)

---

## 1. 新增监控直播间

**端点**: `POST /api/live-rooms/createLiveRoom`

**描述**: 创建新的直播间监控，自动启动持续监听线程

### 请求示例

#### 基础请求（最小参数）
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470",
    "streamer_name": "主播名称"
  }'
```

#### 完整请求（所有参数）
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470",
    "streamer_name": "某某主播",
    "quality": "原画",
    "is_enabled": true,
    "auto_record": true,
    "remark": "这是我最喜欢的主播"
  }'
```

#### 不同平台示例

**抖音**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470",
    "streamer_name": "抖音主播"
  }'
```

**B站**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.bilibili.com/123456",
    "streamer_name": "B站主播",
    "quality": "蓝光"
  }'
```

**虎牙**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.huya.com/123456",
    "streamer_name": "虎牙主播",
    "quality": "超清"
  }'
```

**快手**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.kuaishou.com/u/xxxxx",
    "streamer_name": "快手主播"
  }'
```

### 响应示例

```json
{
  "id": 1,
  "url": "https://live.douyin.com/745964462470",
  "platform": "抖音",
  "streamer_name": "某某主播",
  "quality": "原画",
  "is_enabled": true,
  "auto_record": true,
  "record_status": "idle",
  "live_status": "unknown",
  "remark": "这是我最喜欢的主播",
  "created_at": "2025-10-17T13:20:00",
  "updated_at": "2025-10-17T13:20:00"
}
```

### 错误响应

**400 - URL已存在**
```json
{
  "detail": {
    "error": "room_already_exists",
    "message": "该直播间URL已存在",
    "existing_room_id": 1
  }
}
```

---

## 2. 删除监控直播间

**端点**: `DELETE /api/live-rooms/{room_id}`

**描述**: 删除指定的直播间监控并停止相关线程

### 请求示例

```bash
curl -X DELETE "http://localhost:8000/api/live-rooms/1"
```

### 响应示例

**成功**: 返回 `204 No Content`（无响应体）

### 错误响应

**404 - 直播间不存在**
```json
{
  "detail": "直播间不存在"
}
```

---

## 3. 查看所有直播间状态

**端点**: `GET /api/live-rooms/status`

**描述**: 获取所有监控中的直播间状态列表

### 请求示例

```bash
curl -X GET "http://localhost:8000/api/live-rooms/status"
```

### 响应示例

```json
{
  "rooms": [
    {
      "id": 1,
      "url": "https://live.douyin.com/745964462470",
      "platform": "抖音",
      "streamer_name": "主播A",
      "quality": "原画",
      "is_enabled": true,
      "auto_record": true,
      "record_status": "recording",
      "live_status": "online",
      "remark": null,
      "created_at": "2025-10-17T10:00:00",
      "updated_at": "2025-10-17T13:20:00"
    },
    {
      "id": 2,
      "url": "https://live.bilibili.com/123456",
      "platform": "B站",
      "streamer_name": "主播B",
      "quality": "蓝光",
      "is_enabled": true,
      "auto_record": true,
      "record_status": "idle",
      "live_status": "offline",
      "remark": "B站UP主",
      "created_at": "2025-10-17T11:00:00",
      "updated_at": "2025-10-17T13:15:00"
    }
  ],
  "total": 2
}
```

---

## 4. 查看单个直播间状态

**端点**: `GET /api/live-rooms/{room_id}/status`

**描述**: 获取指定直播间的详细状态信息

### 请求示例

```bash
curl -X GET "http://localhost:8000/api/live-rooms/1/status"
```

### 响应示例

```json
{
  "id": 1,
  "url": "https://live.douyin.com/745964462470",
  "platform": "抖音",
  "streamer_name": "某某主播",
  "quality": "原画",
  "is_enabled": true,
  "auto_record": true,
  "record_status": "recording",
  "live_status": "online",
  "remark": "这是我最喜欢的主播",
  "created_at": "2025-10-17T10:00:00",
  "updated_at": "2025-10-17T13:20:00"
}
```

### 错误响应

**404 - 直播间不存在**
```json
{
  "detail": "直播间不存在"
}
```

---

## 5. 激活录制

**端点**: `POST /api/live-rooms/activate`

**描述**: 手动激活录制功能，使用外部提供的 session_id 进行跨系统日志追踪

**重要**: 此 API 需要提供外部 session_id，允许调用方使用自己的业务 ID 进行录制追踪

### 请求示例

#### 基础请求
```bash
curl -X POST "http://localhost:8000/api/live-rooms/activate" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980",
    "session_id": "20250117-001-douyin-296728101980"
  }'
```

#### 不同 session_id 格式示例

**业务ID格式（推荐）**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/activate" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470",
    "session_id": "ORDER-2025-001-DY745964462470"
  }'
```

**时间戳格式**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/activate" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.bilibili.com/123456",
    "session_id": "20250117-143000-bilibili-123456"
  }'
```

**自定义追踪格式**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/activate" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.huya.com/123456",
    "session_id": "PROD-2025Q1-HUYA-123456-REC01"
  }'
```

### 响应示例

```json
{
  "success": true,
  "message": "录制已激活",
  "session_id": "20250117-001-douyin-296728101980"
}
```

### 错误响应

**400 - 直播间URL不存在**
```json
{
  "detail": "该URL对应的直播间不存在，请先使用 createLiveRoom 添加监控"
}
```

**400 - 录制已在进行中**
```json
{
  "detail": "该直播间的录制已在进行中"
}
```

**400 - 缺少必填参数**
```json
{
  "detail": [
    {
      "loc": ["body", "session_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Session ID 设计建议

为了实现最佳的跨系统追踪体验，建议 session_id 包含以下信息：

- **日期**: 便于按日期归档和查询（如 `20250117`）
- **序号**: 同一天的多次录制区分（如 `001`）
- **平台**: 平台标识（如 `douyin`, `bilibili`）
- **房间号**: 直播间标识（如 `296728101980`）

示例格式: `20250117-001-douyin-296728101980`

---

## 6. 停止录制

**端点**: `POST /api/live-rooms/stop`

**描述**: 手动停止指定直播间的录制任务

### 请求示例

#### 基础请求
```bash
curl -X POST "http://localhost:8000/api/live-rooms/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/296728101980"
  }'
```

#### 不同平台示例

**抖音**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470"
  }'
```

**B站**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.bilibili.com/123456"
  }'
```

**虎牙**
```bash
curl -X POST "http://localhost:8000/api/live-rooms/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.huya.com/123456"
  }'
```

### 响应示例

```json
{
  "success": true
}
```

### 错误响应

**404 - 直播间不存在**
```json
{
  "detail": {
    "error": "room_not_found",
    "message": "直播间不存在，请先创建监控",
    "url": "https://live.douyin.com/296728101980",
    "platform": "抖音",
    "platform_room_id": "296728101980"
  }
}
```

**400 - 没有正在进行的录制**
```json
{
  "detail": {
    "error": "not_recording",
    "message": "没有正在进行的录制",
    "platform": "抖音",
    "platform_room_id": "296728101980",
    "current_status": "idle",
    "url": "https://live.douyin.com/296728101980"
  }
}
```

---

## 7. 查看监听器状态

**端点**: `GET /api/live-rooms/monitor/status`

**描述**: 获取系统监听线程和录制线程的运行状态

### 请求示例

```bash
curl -X GET "http://localhost:8000/api/live-rooms/monitor/status"
```

### 响应示例

```json
{
  "monitor_threads": {
    "1": {
      "room_id": 1,
      "platform": "抖音",
      "url": "https://live.douyin.com/745964462470",
      "is_alive": true,
      "status": "监听中"
    },
    "2": {
      "room_id": 2,
      "platform": "B站",
      "url": "https://live.bilibili.com/123456",
      "is_alive": true,
      "status": "监听中"
    }
  },
  "recording_threads": {
    "1": {
      "room_id": 1,
      "platform": "抖音",
      "url": "https://live.douyin.com/745964462470",
      "is_alive": true,
      "status": "录制中"
    }
  },
  "total_monitors": 2,
  "total_recordings": 1
}
```

---

## 8. 检测直播状态

**端点**: `POST /api/live-rooms/check-live-status`

**描述**: 快速检测指定直播间是否正在直播（支持50+平台，无需预先添加）

### 请求示例

#### 抖音
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470"
  }'
```

#### B站
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.bilibili.com/123456"
  }'
```

#### 虎牙
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.huya.com/123456"
  }'
```

#### 快手
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.kuaishou.com/u/xxxxx"
  }'
```

#### 斗鱼
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.douyu.com/123456"
  }'
```

#### 小红书
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.xiaohongshu.com/live/xxxxx"
  }'
```

#### TikTok
```bash
curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.tiktok.com/@username/live"
  }'
```

### 响应示例

**正在直播**
```json
{
  "is_live": true
}
```

**未在直播**
```json
{
  "is_live": false
}
```

### 错误响应

**500 - 检测失败**
```json
{
  "detail": "检测直播状态失败: [错误详情]"
}
```

---

## 🔧 高级用法

### 1. 批量添加直播间

```bash
#!/bin/bash

# 直播间列表
ROOMS=(
  "https://live.douyin.com/745964462470|抖音主播A"
  "https://live.bilibili.com/123456|B站主播B"
  "https://www.huya.com/123456|虎牙主播C"
)

# 循环添加
for room in "${ROOMS[@]}"; do
  IFS='|' read -r url name <<< "$room"
  curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$url\", \"streamer_name\": \"$name\"}"
  echo ""
done
```

### 2. 批量检测直播状态

```bash
#!/bin/bash

# URL列表
URLS=(
  "https://live.douyin.com/745964462470"
  "https://live.bilibili.com/123456"
  "https://www.huya.com/123456"
)

# 循环检测
for url in "${URLS[@]}"; do
  echo "检测: $url"
  curl -X POST "http://localhost:8000/api/live-rooms/check-live-status" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"$url\"}"
  echo ""
done
```

### 3. 监控直播间状态变化

```bash
#!/bin/bash

# 持续监控
while true; do
  clear
  echo "=== 直播间状态 ==="
  curl -s "http://localhost:8000/api/live-rooms/status" | jq '.'
  sleep 30
done
```

### 4. 美化JSON输出

使用 `jq` 工具美化输出：

```bash
curl -s "http://localhost:8000/api/live-rooms/status" | jq '.'
```

或者使用 Python：

```bash
curl -s "http://localhost:8000/api/live-rooms/status" | python3 -m json.tool
```

---

## 📝 请求参数说明

### LiveRoomCreate 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| url | string | ✅ | - | 直播间URL |
| streamer_name | string | ✅ | - | 主播名称 |
| quality | string | ❌ | "原画" | 录制质量（原画/蓝光/超清/高清/标清/流畅） |
| is_enabled | boolean | ❌ | true | 是否启用监控 |
| auto_record | boolean | ❌ | true | 是否自动录制 |
| remark | string | ❌ | null | 备注信息 |

### 录制质量选项

- `原画` - 最高画质
- `蓝光` - 蓝光画质
- `超清` - 超清画质
- `高清` - 高清画质
- `标清` - 标清画质
- `流畅` - 流畅画质

---

## 🎯 支持的平台

✅ 抖音 (Douyin)  
✅ TikTok  
✅ 快手 (Kuaishou)  
✅ B站 (Bilibili)  
✅ 虎牙 (Huya)  
✅ 斗鱼 (Douyu)  
✅ YY直播  
✅ 小红书 (Xiaohongshu)  
✅ Bigo Live  
✅ 更多 50+ 平台...

---

## 🔍 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 204 | 删除成功（无内容） |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 📚 相关文档

- [API 文档](http://localhost:8000/docs) - Swagger UI
- [ReDoc 文档](http://localhost:8000/redoc) - ReDoc UI
- [Postman Collection](/docs/DouyinLiveRecorder_API.postman_collection.json)

---

**最后更新**: 2025-10-17
**API 版本**: v1.3
**基础URL**: http://localhost:8000

**重要变更 v1.3**:

- ✨ 激活录制 API 现在需要提供外部 `session_id` 参数
- 🔄 激活和停止录制 API 改为使用 URL 而非 room_id
- 📝 支持自定义 session_id 格式,便于跨系统追踪
