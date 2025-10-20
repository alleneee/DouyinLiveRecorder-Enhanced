# API 路由变更通知

## 📅 变更时间
2025-10-17 13:26

## 🔄 变更内容

### 创建直播间端点路径修改

**原端点**: `POST /api/live-rooms`  
**新端点**: `POST /api/live-rooms/createLiveRoom`

---

## 📝 变更详情

### 修改代码
```python
# 修改前（RESTful 风格）
@router.post(
    "",
    response_model=LiveRoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增监控直播间",
    description="创建新的直播间监控，自动启动持续监听线程"
)

# 修改后（RPC 风格）
@router.post(
    "createLiveRoom",
    response_model=LiveRoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增监控直播间",
    description="创建新的直播间监控，自动启动持续监听线程"
)
```

### 影响范围

✅ **功能不变**: 创建直播间的功能和参数完全一致  
✅ **响应格式不变**: 返回数据结构保持一致  
⚠️ **URL变更**: 需要更新客户端请求地址  

---

## 🔀 API 风格对比

### RESTful 风格（修改前）

**特点**:
- ✅ 符合 REST 规范
- ✅ 使用 HTTP 方法表达操作（POST = 创建）
- ✅ 资源导向：`/api/live-rooms` 表示直播间集合
- ✅ 路径简洁

**示例**:
```bash
# 创建
POST /api/live-rooms

# 获取列表
GET /api/live-rooms

# 获取单个
GET /api/live-rooms/{id}

# 更新
PUT /api/live-rooms/{id}

# 删除
DELETE /api/live-rooms/{id}
```

### RPC 风格（修改后）

**特点**:
- ✅ 动作明确：URL 包含动词 `createLiveRoom`
- ✅ 语义直观：一看就知道是创建操作
- ✅ 适合复杂业务场景
- ⚠️ 路径较长

**示例**:
```bash
# 创建（更明确）
POST /api/live-rooms/createLiveRoom

# 其他端点保持不变
GET /api/live-rooms/status
POST /api/live-rooms/{id}/activate
POST /api/live-rooms/{id}/stop
```

---

## 📊 新旧对比表

| 项目 | 修改前 | 修改后 |
|------|--------|--------|
| **端点** | `POST /api/live-rooms` | `POST /api/live-rooms/createLiveRoom` |
| **风格** | RESTful | RPC |
| **路径长度** | 短 | 中等 |
| **语义明确度** | 需要结合 HTTP 方法 | URL 自解释 |
| **符合规范** | REST 标准 | 自定义风格 |

---

## 🔧 迁移指南

### 1. 更新 curl 命令

**旧命令**:
```bash
curl -X POST "http://localhost:8000/api/live-rooms" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470",
    "streamer_name": "主播名称"
  }'
```

**新命令**:
```bash
curl -X POST "http://localhost:8000/api/live-rooms/createLiveRoom" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/745964462470",
    "streamer_name": "主播名称"
  }'
```

### 2. 更新 JavaScript/TypeScript

**旧代码**:
```javascript
const response = await fetch('http://localhost:8000/api/live-rooms', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://live.douyin.com/745964462470',
    streamer_name: '主播名称'
  })
});
```

**新代码**:
```javascript
const response = await fetch('http://localhost:8000/api/live-rooms/createLiveRoom', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://live.douyin.com/745964462470',
    streamer_name: '主播名称'
  })
});
```

### 3. 更新 Python Requests

**旧代码**:
```python
import requests

response = requests.post(
    'http://localhost:8000/api/live-rooms',
    json={
        'url': 'https://live.douyin.com/745964462470',
        'streamer_name': '主播名称'
    }
)
```

**新代码**:
```python
import requests

response = requests.post(
    'http://localhost:8000/api/live-rooms/createLiveRoom',
    json={
        'url': 'https://live.douyin.com/745964462470',
        'streamer_name': '主播名称'
    }
)
```

---

## ✅ 已更新的文档

以下文档已同步更新为新端点：

1. ✅ `/docs/API_CURL_EXAMPLES_COMPLETE.md` - 完整 cURL 示例
2. ✅ 所有平台示例（抖音、B站、虎牙、快手）
3. ✅ 高级用法中的批量添加脚本

---

## 🎯 其他端点（未变更）

以下端点保持不变，无需更新：

| 端点 | 说明 | 状态 |
|------|------|------|
| `DELETE /api/live-rooms/{room_id}` | 删除直播间 | ✅ 不变 |
| `GET /api/live-rooms/status` | 查看所有状态 | ✅ 不变 |
| `GET /api/live-rooms/{room_id}/status` | 查看单个状态 | ✅ 不变 |
| `POST /api/live-rooms/{room_id}/activate` | 激活录制 | ✅ 不变 |
| `POST /api/live-rooms/{room_id}/stop` | 停止录制 | ✅ 不变 |
| `GET /api/live-rooms/monitor/status` | 查看监听器 | ✅ 不变 |
| `POST /api/live-rooms/check-live-status` | 检测直播 | ✅ 不变 |

---

## 💡 建议

### 推荐做法

1. **统一风格**: 建议整个API保持一致的设计风格
   - 要么全部使用 RESTful 风格
   - 要么全部使用 RPC 风格

2. **向后兼容**: 如果有现有客户端，考虑：
   - 同时支持新旧两个端点（过渡期）
   - 在旧端点返回 `301 Moved Permanently` 重定向
   - 提供迁移公告和时间表

3. **文档更新**: 确保所有相关文档同步更新
   - ✅ API 文档
   - ✅ Postman Collection
   - ✅ SDK 示例
   - ✅ 集成测试

---

## 🤔 设计考虑

### 何时使用 RESTful 风格

适合场景：
- ✅ 标准 CRUD 操作
- ✅ 资源导向的 API
- ✅ 需要符合 REST 规范
- ✅ API 对外开放（第三方集成）

### 何时使用 RPC 风格

适合场景：
- ✅ 复杂业务操作（不是简单的 CRUD）
- ✅ 需要明确的动作语义
- ✅ 内部 API（团队内使用）
- ✅ 操作名称比资源更重要

---

## 📞 联系方式

如有疑问或需要帮助，请联系：
- 文档位置: `/docs`
- API 文档: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

**变更记录**:
- 2025-10-17 13:26 - 创建直播间端点路径变更
- 2025-10-17 13:26 - 更新相关文档

**变更人**: 系统管理员  
**影响级别**: 🟡 中等（需要客户端更新）
