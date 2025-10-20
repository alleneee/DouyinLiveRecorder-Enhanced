# 分片通知功能实现说明

## 📦 实现内容

本次更新实现了**分片上传完成自动通知**功能,在每个视频分片上传到OSS后,自动向配置的外部API发送通知。

## 🎯 功能特性

### ✅ 核心功能
- **自动触发**: 分片上传完成后自动发送通知
- **完整信息**: 包含直播间、视频、分片的完整数据
- **灵活配置**: 通过环境变量配置通知URL
- **容错设计**: 通知失败不影响录制流程
- **时间格式**: 支持相对于直播开始的绝对时间格式

### 📋 通知数据结构

```json
{
  "live_info": {
    "live_url": "直播间URL",
    "live_name": "主播名称"
  },
  "sub_video_info": {
    "video_url": "视频OSS地址",
    "audio_url": "音频OSS地址",
    "duration": 60,
    "absolute_start_time": "00:00:00:000",
    "absolute_end_time": "00:01:00:000",
    "serial_num": 0
  },
  "video_shard_info": []
}
```

## 📁 新增文件

```
app/
├── schemas/
│   └── segment_notification.py      # Pydantic数据模型
└── services/
    └── segment_notifier.py          # 通知服务核心实现

docs/
└── SEGMENT_NOTIFICATION.md          # 详细文档

test_segment_notification.py         # 测试脚本
SEGMENT_NOTIFICATION_README.md       # 本文件
```

## 🔧 修改文件

### 1. `app/services/recording_manager.py`
在 `_upload_video_and_audio()` 方法中的上传完成后添加了通知发送逻辑:

```python
# 步骤4: 发送分片完成通知
try:
    from app.services.segment_notifier import segment_notifier
    segment_notifier.send_notification_sync(db, segment_id)
except Exception as notify_error:
    logger.error(f"{log_ctx} 发送分片通知失败: {notify_error}", exc_info=True)
    # 通知失败不影响主流程
```

**位置**: 第494-500行 (在数据库更新之后,删除本地文件之前)

### 2. `app/config.py`
添加了新的配置项:

```python
# 分片通知配置
segment_notification_url: str = Field("", description="分片上传完成后通知的目标URL(留空则不发送通知)")
```

**位置**: Settings类中,OSS配置之后

### 3. `.env`
添加了配置说明:

```env
# ==================== 分片通知配置 ====================
# 分片上传完成后通知的目标URL(留空则不发送通知)
SEGMENT_NOTIFICATION_URL=
```

**位置**: 文件末尾

## 🚀 快速开始

### 1. 配置通知URL

编辑 `.env` 文件:

```env
SEGMENT_NOTIFICATION_URL=http://your-api.com/webhook/segment
```

### 2. 重启应用

```bash
# 如果使用systemd
sudo systemctl restart douyinlive

# 或直接运行
python main.py
```

### 3. 测试功能

```bash
python test_segment_notification.py
```

## 📊 工作流程

```
录制完成 → 抽取音频 → 上传OSS → 更新数据库 → 🔔 发送通知 → 删除本地文件
```

**触发条件**:
1. ✅ 配置了 `SEGMENT_NOTIFICATION_URL`
2. ✅ 分片状态为 `UPLOADED`
3. ✅ 视频和音频URL都存在

## 🔍 详细文档

完整的使用说明、API文档、常见问题请参考:
- **[详细文档](docs/SEGMENT_NOTIFICATION.md)**

包含内容:
- 配置方法
- 请求格式说明
- 时间格式详解
- 接收端实现示例
- 错误处理说明
- 测试方法
- 常见问题解答

## 💡 设计亮点

### 1. 数据完整性
- 包含直播间URL和名称
- 提供视频和音频的OSS地址
- 计算相对于直播开始的绝对时间
- 分片序号从0开始,便于排序

### 2. 时间处理
```python
def format_absolute_time(self, delta_seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS:mmm 格式"""
    hours = int(delta_seconds // 3600)
    minutes = int((delta_seconds % 3600) // 60)
    seconds = int(delta_seconds % 60)
    milliseconds = int((delta_seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
```

**示例**:
- 直播开始: `00:00:00:000`
- 1分钟后: `00:01:00:000`
- 1小时30分45.5秒后: `01:30:45:500`

### 3. 容错设计
- 通知失败不影响录制
- 通知失败会记录日志
- 支持配置为空(禁用通知)
- 超时时间可配置

### 4. 扩展性
- `video_shard_info` 预留用于未来标签功能
- 数据模型使用Pydantic,易于验证和序列化
- 支持同步和异步两种发送方式

## 🧪 测试验证

### 方法1: 使用测试脚本
```bash
python test_segment_notification.py
```

输出示例:
```
🚀 分片通知功能测试脚本

✅ 测试数据创建成功:
   直播间ID: 1
   分片ID: 1

============================================================
测试分片通知功能
============================================================

📋 步骤1: 构建通知数据...
✅ 通知数据构建成功!

📦 通知数据预览:
{
  "live_info": {
    "live_url": "https://live.douyin.com/745964462470",
    "live_name": "测试主播"
  },
  "sub_video_info": {
    "video_url": "https://oss.example.com/videos/test_segment_0.ts",
    "audio_url": "https://oss.example.com/audios/test_segment_0.mp3",
    "duration": 60,
    "absolute_start_time": "00:00:00:000",
    "absolute_end_time": "00:01:00:000",
    "serial_num": 0
  },
  "video_shard_info": []
}

📤 步骤2: 发送通知...
⚠️  通知服务未启用(SEGMENT_NOTIFICATION_URL未配置)

============================================================

🧹 测试数据已清理
```

### 方法2: 使用 webhook.site
1. 访问 https://webhook.site/
2. 复制URL
3. 配置到 `.env`
4. 进行实际录制
5. 在网站上查看收到的请求

### 方法3: 本地Mock服务器
参考 [详细文档](docs/SEGMENT_NOTIFICATION.md) 中的Mock服务器示例

## 📝 代码示例

### 接收端实现 (FastAPI)

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class SegmentNotification(BaseModel):
    live_info: dict
    sub_video_info: dict
    video_shard_info: list

@app.post("/webhook/segment")
async def receive_notification(data: SegmentNotification):
    # 处理通知
    print(f"收到分片: {data.sub_video_info['serial_num']}")
    return {"status": "success"}
```

## ⚠️ 注意事项

### 1. 性能考虑
- 默认超时30秒
- 通知在独立线程中执行,不阻塞录制
- 通知失败不影响后续分片

### 2. 安全建议
- 接收端应验证请求来源
- 建议使用HTTPS
- 可以添加认证token(需自行扩展)

### 3. 数据一致性
- 接收端应实现幂等性处理
- 建议使用 `live_url` + `serial_num` 作为唯一标识
- 可能需要处理重复通知的情况

## 🔄 工作流程图

```
┌─────────────────┐
│  FFmpeg录制完成  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  创建分片记录    │ (status: COMPLETED)
│  VideoSegment   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   抽取音频      │ (audio_extractor.extract_audio)
│   MP3 128k      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 并行上传到OSS    │ (ThreadPoolExecutor)
│ 视频 + 音频      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  回写OSS URL    │ (status: UPLOADED)
│  video_url      │
│  audio_url      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 🔔 发送通知      │ ← 新增功能
│ POST请求        │
│ 30秒超时        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  删除本地文件    │
│  TS + MP3       │
└─────────────────┘
```

## 🎓 学习资源

### 相关技术
- **Pydantic**: 数据验证和序列化
- **httpx**: 现代异步HTTP客户端
- **FastAPI**: 接收端实现推荐框架

### 扩展阅读
- [Pydantic文档](https://docs.pydantic.dev/)
- [httpx文档](https://www.python-httpx.org/)
- [Webhook最佳实践](https://webhooks.fyi/)

## 📞 支持

如有问题,请:
1. 查看 [详细文档](docs/SEGMENT_NOTIFICATION.md)
2. 检查日志文件 `logs/*.log`
3. 使用测试脚本验证
4. 提交Issue时附带完整日志

## 📄 许可证

遵循项目原有许可证。

---

**实现日期**: 2025-01-17
**版本**: v1.0.0
**作者**: Claude Code SuperClaude
