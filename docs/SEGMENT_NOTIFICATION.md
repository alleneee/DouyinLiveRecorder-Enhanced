# 分片通知功能文档

## 功能概述

分片通知功能会在每个视频分片上传到OSS完成后,自动向配置的外部API发送包含直播信息、视频信息和分片信息的HTTP POST请求。

## 配置方法

### 1. 在 `.env` 文件中配置通知URL

```env
# ==================== 分片通知配置 ====================
# 分片上传完成后通知的目标URL(留空则不发送通知)
SEGMENT_NOTIFICATION_URL=http://your-api.com/webhook/segment
```

**注意**:
- 如果不配置此项或留空,则不会发送通知
- URL必须是完整的HTTP/HTTPS地址
- 支持自定义端口,例如: `http://localhost:3000/api/webhook`

### 2. 重启应用

修改配置后需要重启应用才能生效。

## 请求格式

### HTTP 请求

- **方法**: `POST`
- **Content-Type**: `application/json`
- **超时时间**: 30秒(默认)

### 响应要求

**接收端必须返回HTTP 200-299状态码**,否则发送方会认为通知失败并记录错误日志。

**推荐响应格式**:
```json
{
  "code": 0,
  "message": "success"
}
```

**失败响应示例**:
- HTTP 4xx: 客户端错误(数据格式不正确等)
- HTTP 5xx: 服务端错误(处理失败等)

**注意**:
- ✅ 发送方会验证HTTP状态码和响应内容
- ✅ 响应body会完整记录到日志中
- ❌ 响应失败会详细记录错误原因

### 请求体结构

```json
{
  "live_info": {
    "live_url": "https://live.douyin.com/745964462470",
    "live_name": "测试主播"
  },
  "sub_video_info": {
    "video_url": "https://oss.example.com/videos/segment_0.ts",
    "audio_url": "https://oss.example.com/audios/segment_0.mp3",
    "duration": 60,
    "absolute_start_time": "00:00:00:000",
    "absolute_end_time": "00:01:00:000",
    "serial_num": 0
  },
  "video_shard_info": []
}
```

### 字段说明

#### live_info (直播间信息)

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| live_url | string | 直播间URL | `https://live.douyin.com/745964462470` |
| live_name | string | 直播间名称/主播名 | `测试主播` |

#### sub_video_info (子视频信息)

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| video_url | string | 视频OSS地址 | `https://oss.example.com/videos/segment_0.ts` |
| audio_url | string | 音频OSS地址 | `https://oss.example.com/audios/segment_0.mp3` |
| duration | integer | 视频时长(秒) | `60` |
| absolute_start_time | string | 相对于直播开始的起始时间(HH:MM:SS:mmm) | `00:00:00:000` |
| absolute_end_time | string | 相对于直播开始的结束时间(HH:MM:SS:mmm) | `00:01:00:000` |
| serial_num | integer | 分片序号(从0开始) | `0` |

#### video_shard_info (视频分片信息)

当前版本为空数组,预留用于未来扩展标签功能。

将来可能包含的字段:
```json
[
  {
    "start_time": "00:00:00:000",
    "end_time": "00:01:00:000",
    "tag": ["精彩瞬间", "高能"],
    "serial_num": 0
  }
]
```

## 时间格式说明

### 绝对时间格式

`absolute_start_time` 和 `absolute_end_time` 使用格式: `HH:MM:SS:mmm`

- `HH`: 小时 (00-23)
- `MM`: 分钟 (00-59)
- `SS`: 秒 (00-59)
- `mmm`: 毫秒 (000-999)

### 时间计算示例

假设直播在 `14:00:00` 开始录制:

| 实际时间 | 相对时间 | 说明 |
|---------|---------|------|
| 14:00:00.000 | 00:00:00:000 | 第1个分片开始 |
| 14:01:00.000 | 00:01:00:000 | 第1个分片结束 |
| 14:01:00.000 | 00:01:00:000 | 第2个分片开始 |
| 14:02:00.000 | 00:02:00:000 | 第2个分片结束 |
| 15:30:45.500 | 01:30:45:500 | 第91个分片中间某时刻 |

## 触发时机

通知会在以下条件**全部满足**时触发:

1. ✅ 视频分片录制完成
2. ✅ 音频成功抽取
3. ✅ 视频和音频都已上传到OSS
4. ✅ 数据库状态更新为 `UPLOADED`
5. ✅ 配置了 `SEGMENT_NOTIFICATION_URL`

## 工作流程

```
┌─────────────────┐
│  FFmpeg录制完成  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建分片记录    │ (status: COMPLETED)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   抽取音频      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 并行上传OSS     │
│ (视频 + 音频)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  更新数据库     │ (status: UPLOADED)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 🔔 发送通知     │ ← 这里触发
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  删除本地文件   │
└─────────────────┘
```

## 错误处理

### 通知失败不影响录制

即使通知发送失败,也**不会**影响:
- ✅ 视频录制流程
- ✅ OSS上传流程
- ✅ 数据库记录
- ✅ 下一个分片的录制

### 日志记录

所有通知相关的操作都会记录在日志中:

**成功日志**:
```
[INFO] 分片通知发送成功: segment_id=123, status=200, url=http://...
```

**失败日志**:
```
[ERROR] 分片通知发送失败(HTTP错误): segment_id=123, error=..., url=http://...
```

## 接收端实现建议

### 1. 端点示例 (FastAPI)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

class LiveInfo(BaseModel):
    live_url: str
    live_name: str

class SubVideoInfo(BaseModel):
    video_url: str
    audio_url: str
    duration: int
    absolute_start_time: str
    absolute_end_time: str
    serial_num: int

class VideoShardInfo(BaseModel):
    start_time: str
    end_time: str
    tag: List[str]
    serial_num: int

class SegmentNotification(BaseModel):
    live_info: LiveInfo
    sub_video_info: SubVideoInfo
    video_shard_info: List[VideoShardInfo]

@app.post("/webhook/segment")
async def receive_segment_notification(data: SegmentNotification):
    """接收分片通知"""
    try:
        # 处理通知数据
        print(f"收到分片通知: {data.live_info.live_name} - 分片 {data.sub_video_info.serial_num}")

        # 你的业务逻辑
        # - 存储到数据库
        # - 触发后续处理
        # - 发送消息通知

        return {"status": "success", "message": "通知已接收"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. 端点示例 (Express.js)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/webhook/segment', (req, res) => {
    try {
        const { live_info, sub_video_info, video_shard_info } = req.body;

        console.log(`收到分片通知: ${live_info.live_name} - 分片 ${sub_video_info.serial_num}`);

        // 你的业务逻辑

        res.json({ status: 'success', message: '通知已接收' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.listen(3000, () => {
    console.log('Webhook服务运行在 http://localhost:3000');
});
```

### 3. 响应格式

建议返回标准的JSON响应:

**成功响应 (200 OK)**:
```json
{
  "status": "success",
  "message": "通知已接收"
}
```

**失败响应 (4xx/5xx)**:
```json
{
  "status": "error",
  "message": "错误描述"
}
```

## 测试方法

### 1. 使用测试脚本

项目提供了测试脚本 `test_segment_notification.py`:

```bash
python test_segment_notification.py
```

该脚本会:
1. 创建测试直播间和分片数据
2. 构建通知数据并打印预览
3. 如果配置了URL,会尝试发送通知
4. 自动清理测试数据

### 2. 使用 webhook.site 测试

1. 访问 https://webhook.site/
2. 复制生成的唯一URL
3. 在 `.env` 中配置:
   ```env
   SEGMENT_NOTIFICATION_URL=https://webhook.site/你的唯一ID
   ```
4. 进行实际录制
5. 在 webhook.site 查看收到的请求

### 3. 使用本地Mock服务器

```python
# mock_webhook.py
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook/segment', methods=['POST'])
def webhook():
    data = request.json
    print("=" * 60)
    print("收到分片通知:")
    print(f"直播间: {data['live_info']['live_name']}")
    print(f"分片序号: {data['sub_video_info']['serial_num']}")
    print(f"视频URL: {data['sub_video_info']['video_url']}")
    print("=" * 60)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(port=3000)
```

运行:
```bash
pip install flask
python mock_webhook.py
```

配置:
```env
SEGMENT_NOTIFICATION_URL=http://localhost:3000/webhook/segment
```

## 性能考虑

### 1. 超时设置

默认超时30秒。如果接收端处理耗时,可以在代码中调整:

```python
# app/services/segment_notifier.py
segment_notifier = SegmentNotifier(timeout=60)  # 60秒超时
```

### 2. 重试机制

当前版本**不支持自动重试**。如果通知很重要,建议接收端实现:
- 幂等性处理
- 消息队列缓冲
- 数据库记录用于对账

### 3. 异步处理

通知发送是在上传完成后的线程中同步执行的,不会阻塞主录制流程。

## 常见问题

### Q1: 通知没有发送?

**检查清单**:
- [ ] `.env` 中配置了 `SEGMENT_NOTIFICATION_URL`
- [ ] URL格式正确(包含 http:// 或 https://)
- [ ] 应用已重启
- [ ] 分片已经上传完成(状态为UPLOADED)
- [ ] 查看日志确认是否有错误信息

### Q2: 接收端收不到通知?

**可能原因**:
- 接收端服务未运行
- 防火墙阻止了请求
- URL配置错误
- 接收端处理超时(>30秒)

**调试方法**:
```bash
# 测试接收端是否可访问
curl -X POST http://your-api.com/webhook/segment \
  -H "Content-Type: application/json" \
  -d '{"test": "connection"}'
```

### Q3: 如何处理重复通知?

如果由于网络原因可能收到重复通知,建议接收端:

1. **使用唯一标识**: 根据 `live_url` + `serial_num` 判断重复
2. **幂等性设计**: 相同数据多次处理结果一致
3. **数据库约束**: 添加唯一索引防止重复插入

示例:
```python
# 使用复合键判断
unique_key = f"{live_url}:{serial_num}"
if redis.exists(unique_key):
    return {"status": "duplicate"}
redis.setex(unique_key, 3600, "1")  # 1小时过期
```

### Q4: 如何调整通知内容?

如需自定义通知内容,修改:
```python
# app/services/segment_notifier.py - build_notification_data()
```

### Q5: 如何禁用通知?

两种方法:
1. 在 `.env` 中将 `SEGMENT_NOTIFICATION_URL` 设为空
2. 直接删除或注释掉该配置项

## 架构说明

### 核心文件

```
app/
├── schemas/
│   └── segment_notification.py    # 数据模型定义
├── services/
│   ├── segment_notifier.py        # 通知服务实现
│   └── recording_manager.py       # 录制管理器(集成通知)
└── config.py                       # 配置类(添加notification_url)
```

### 数据流

```
VideoSegment (数据库)
    ↓
segment_notifier.build_notification_data()
    ↓
SegmentNotificationRequest (Pydantic模型)
    ↓
httpx.post() (HTTP请求)
    ↓
外部API接收端
```

## 更新日志

### v1.0.0 (2025-01-17)
- ✨ 初始版本
- ✅ 支持分片上传完成后自动通知
- ✅ 包含直播间、视频、分片完整信息
- ✅ 可配置通知URL
- ✅ 通知失败不影响录制流程
- ✅ 完整的日志记录

## 技术支持

如遇问题,请提供:
1. 日志文件 (logs/*.log)
2. 配置文件 (.env,隐藏敏感信息)
3. 错误信息截图
4. 系统环境 (Python版本, OS版本)
