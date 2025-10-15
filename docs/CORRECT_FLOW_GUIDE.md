# 正确的录制流程指南

## 📋 正确流程概述

```
1. 创建房间（落表）
   POST /api/rooms
   → 保存直播间信息和录制配置到数据库
   
2. 启动录制
   POST /api/recording/start
   → 基于房间ID启动录制
   
3. 停止录制  
   POST /api/recording/stop
   → 基于房间ID停止录制
```

## 🎯 为什么这样设计？

### ❌ 错误流程（之前的设计）
```
直接启动录制 → 传入所有配置参数 → 录制
```

**问题**：
- 每次启动都要传大量参数
- 配置无法持久化
- 无法统一管理直播间

### ✅ 正确流程（当前设计）
```
创建房间（配置持久化） → 启动录制（简单） → 停止录制（简单）
```

**优势**：
- 配置一次，多次使用
- 统一管理所有直播间
- 接口简洁清晰
- 支持批量操作

## 📝 详细步骤

### 步骤 1: 创建房间（保存到数据库）

**接口**: `POST /api/rooms`

**请求参数**:
```json
{
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "quality": "OD",
  "status": "active",
  "comment": "测试直播间",
  
  "enable_segment_recording": true,
  "segment_duration": 60,
  "video_save_type": "TS",
  "oss_enabled": false,
  "run_post_process": true
}
```

**响应**:
```json
{
  "id": 1,
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "quality": "OD",
  "status": "active",
  "enable_segment_recording": true,
  "segment_duration": 60,
  "video_save_type": "TS",
  "oss_enabled": false,
  "run_post_process": true,
  "created_at": "2025-01-15T13:30:00",
  "updated_at": "2025-01-15T13:30:00"
}
```

**数据库变化**:
```sql
-- rooms 表新增一条记录
INSERT INTO rooms (url, nickname, enable_segment_recording, segment_duration, ...)
VALUES ('https://live.douyin.com/296728101980', '央视网财经', 1, 60, ...);
```

### 步骤 2: 查询房间列表

**接口**: `GET /api/rooms`

**响应**:
```json
{
  "items": [
    {
      "id": 1,
      "url": "https://live.douyin.com/296728101980",
      "nickname": "央视网财经",
      "enable_segment_recording": true,
      "segment_duration": 60,
      "status": "active"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 步骤 3: 启动录制（基于房间ID）

**接口**: `POST /api/recording/start`

**请求参数**:
```json
{
  "room_id": 1
}
```

**响应**:
```json
{
  "status": "started",
  "room_id": 1,
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "message": "录制已启动"
}
```

**内部流程**:
1. 根据 `room_id=1` 查询 rooms 表
2. 获取房间的录制配置（enable_segment_recording, segment_duration 等）
3. 创建录制任务，保存到 recording_tasks 表
4. 启动录制工作器（SegmentRecordingWorker 或 ContinuousRecordingWorker）

### 步骤 4: 检查录制状态

**接口**: `GET /api/recording/status`

**响应**:
```json
[
  {
    "status": "running",
    "room_id": 1,
    "url": "https://live.douyin.com/296728101980",
    "nickname": "央视网财经",
    "message": "录制中"
  }
]
```

### 步骤 5: 停止录制（基于房间ID）

**接口**: `POST /api/recording/stop`

**请求参数**:
```json
{
  "room_id": 1
}
```

**响应**:
```json
{
  "status": "stopped",
  "room_id": 1,
  "url": "https://live.douyin.com/296728101980",
  "nickname": "央视网财经",
  "message": "录制已停止"
}
```

## 🔄 数据流转

```
用户创建房间
    ↓
rooms 表（持久化配置）
    ├─ id: 1
    ├─ url: https://...
    ├─ nickname: 央视网财经
    ├─ enable_segment_recording: 1
    └─ segment_duration: 60
    ↓
用户启动录制（room_id=1）
    ↓
读取 rooms 表配置 → 创建 recording_tasks 记录
    ↓
启动录制工作器
    ↓
每分钟保存一个视频分段 → video_segments 表
    ├─ segment_index: 1
    ├─ segment_index: 2
    └─ segment_index: 3
    ↓
用户停止录制（room_id=1）
    ↓
更新 recording_tasks 状态
```

## 💡 使用场景

### 场景 1: 定期录制（推荐）

```bash
# 1. 创建房间（只需一次）
curl -X POST "http://localhost:8009/api/rooms" \
  -d '{
    "url": "https://live.douyin.com/xxx",
    "nickname": "主播A",
    "enable_segment_recording": true,
    "segment_duration": 60
  }'
# → 返回 room_id: 1

# 2. 每天定时启动录制
curl -X POST "http://localhost:8009/api/recording/start" \
  -d '{"room_id": 1}'

# 3. 录制一段时间后停止
curl -X POST "http://localhost:8009/api/recording/stop" \
  -d '{"room_id": 1}'

# 可以反复执行步骤2-3，无需重复创建房间
```

### 场景 2: 批量管理

```bash
# 1. 批量创建多个房间
for url in url1 url2 url3; do
  curl -X POST "http://localhost:8009/api/rooms" \
    -d "{\"url\": \"$url\", ...}"
done

# 2. 查询所有房间
curl "http://localhost:8009/api/rooms"

# 3. 批量启动录制
for room_id in 1 2 3; do
  curl -X POST "http://localhost:8009/api/recording/start" \
    -d "{\"room_id\": $room_id}"
done
```

### 场景 3: 更新配置

```bash
# 1. 更新房间配置
curl -X PATCH "http://localhost:8009/api/rooms/1" \
  -d '{
    "segment_duration": 120,
    "oss_enabled": true
  }'

# 2. 下次启动录制时会使用新配置
curl -X POST "http://localhost:8009/api/recording/start" \
  -d '{"room_id": 1}'
```

## 📊 数据库表关系

```
rooms（房间表）
├─ id (主键)
├─ url（直播间URL）
├─ nickname（主播昵称）
├─ enable_segment_recording（录制模式）
├─ segment_duration（分段时长）
└─ ...

recording_tasks（录制任务表）
├─ id (主键)
├─ room_url（关联 rooms.url）
├─ status（任务状态）
└─ ...

video_segments（视频分段表）
├─ id (主键)
├─ room_url（关联 rooms.url）
├─ segment_index（分段序号）
└─ ...
```

## 🎨 完整测试示例

```bash
# 运行自动化测试
cd /Users/niko/DouyinLiveRecorder
python tests/test_correct_flow.py
```

测试会自动执行：
1. ✅ 创建房间
2. ✅ 查询房间列表
3. ✅ 启动录制
4. ✅ 检查状态
5. ✅ 等待3分钟（生成3个分段）
6. ✅ 停止录制
7. ✅ 验证数据库
8. ✅ 验证文件

## 🔍 对比总结

| 操作 | 旧流程 | 新流程（正确） |
|------|--------|---------------|
| **创建直播间** | ❌ 无此步骤 | ✅ POST /api/rooms |
| **启动录制** | 传入所有配置 | 只传 room_id |
| **停止录制** | 传 URL | 只传 room_id |
| **配置持久化** | ❌ 不持久化 | ✅ 保存到数据库 |
| **批量管理** | ❌ 困难 | ✅ 容易 |
| **接口复杂度** | 高 | 低 |

## 🎉 总结

✅ **正确流程的优势**：
1. 配置一次，多次使用
2. 统一管理所有直播间
3. 接口简洁，易于使用
4. 支持批量操作
5. 配置可追溯

✅ **核心理念**：
- 房间是配置的载体
- 录制是基于房间的操作
- 分离配置和操作，提高灵活性
