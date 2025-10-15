# 快速开始：使用新的模块化录制 API

## 🚀 启动服务

```bash
# 1. 激活虚拟环境（使用 uv）
uv sync

# 2. 启动 FastAPI 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 API 端点

访问 API 文档：http://localhost:8000/docs

### 1. 启动录制

```bash
curl -X POST "http://localhost:8000/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/123456",
    "nickname": "主播昵称",
    "quality": "OD",
    "video_save_type": "TS",
    "converts_to_mp4": true,
    "folder_by_author": true
  }'
```

**参数说明**：
- `url`: 直播间 URL（必填）
- `nickname`: 主播昵称（必填）
- `quality`: 画质代码，可选值：
  - `OD` - 原画
  - `BD` - 蓝光
  - `UHD` - 超清
  - `HD` - 高清
  - `SD` - 标清
  - `LD` - 流畅
- `video_save_type`: 保存格式，可选值：
  - `TS` - TS 视频格式
  - `MP3音频` - MP3 音频
  - `M4A音频` - M4A 音频
- `converts_to_mp4`: 是否转换为 MP4（默认 false）
- `folder_by_author`: 按作者分文件夹（默认 true）

**响应示例**：
```json
{
  "status": "started",
  "url": "https://live.douyin.com/123456",
  "nickname": "主播昵称",
  "message": "录制已启动"
}
```

### 2. 停止录制

```bash
curl -X POST "http://localhost:8000/api/v2/recording/stop?url=https://live.douyin.com/123456"
```

**响应示例**：
```json
{
  "status": "stopped",
  "url": "https://live.douyin.com/123456",
  "nickname": "主播昵称",
  "message": "录制已停止"
}
```

### 3. 查看录制状态

```bash
curl -X GET "http://localhost:8000/api/v2/recording/status"
```

**响应示例**：
```json
[
  {
    "status": "running",
    "url": "https://live.douyin.com/123456",
    "nickname": "主播昵称",
    "message": null
  }
]
```

### 4. 测试平台连接

```bash
curl -X POST "http://localhost:8000/api/v2/recording/test-platform" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/123456",
    "quality": "OD"
  }'
```

**响应示例**：
```json
{
  "platform": "通用平台",
  "is_live": true,
  "real_url": "https://stream.example.com/live.m3u8",
  "anchor_name": "主播昵称",
  "title": "直播标题",
  "quality": "OD"
}
```

### 5. 视频转码

```bash
curl -X POST "http://localhost:8000/api/v2/recording/convert?file_path=/path/to/video.ts&to_h264=false"
```

**响应示例**：
```json
{
  "status": "converting",
  "source": "/path/to/video.ts",
  "message": "转换任务已启动"
}
```

## 💡 Python 代码示例

### 示例 1：启动录制

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v2/recording/start",
    json={
        "url": "https://live.douyin.com/123456",
        "nickname": "主播昵称",
        "quality": "OD",
        "video_save_type": "TS",
        "converts_to_mp4": True,
    }
)

print(response.json())
```

### 示例 2：直接使用模块

```python
import asyncio
from src.recording.worker import RecordingWorker, RecordingConfig
from src.platforms.legacy_adapter import LegacyPlatformHandler
from src.recording.models import Room

async def main():
    # 创建配置
    config = RecordingConfig(
        video_save_path="downloads",
        video_save_type="TS",
        loop_interval=60,
        converts_to_mp4=True,
    )
    
    # 创建平台处理器
    handler = LegacyPlatformHandler(
        cookies_map={
            "dy_cookie": "your_cookie_here",
        }
    )
    
    # 创建房间对象
    room = Room(
        identity="room_001",
        url="https://live.douyin.com/123456",
        nickname="主播昵称",
        quality="OD",
    )
    
    # 创建并运行工作器
    worker = RecordingWorker(
        room=room,
        platform_handler=handler,
        config=config,
    )
    
    await worker.run()

# 运行
asyncio.run(main())
```

### 示例 3：视频转码

```python
from src.processing import VideoConverter

converter = VideoConverter(
    convert_to_h264=False,  # 不重新编码
    delete_origin=True,     # 删除原文件
)

# 转换为 MP4
mp4_path = converter.convert_to_mp4("recording.ts")
print(f"转换完成: {mp4_path}")

# 视频分段（每小时一段）
segments = converter.segment_video("long_video.mp4", segment_time=3600)
print(f"生成 {len(segments)} 个分段")
```

### 示例 4：推送通知

```python
from src.processing import PushNotifier

notifier = PushNotifier(
    enabled_channels=["微信", "钉钉"],
    title="直播通知",
    begin_template="{anchor_name} 开始直播了！{live_url}",
    end_template="{anchor_name} 的直播结束了，时长 {duration}",
    xizhi_api_url="your_api_url",
    dingtalk_api_url="your_api_url",
    dingtalk_secret="your_secret",
)

# 通知开播
notifier.notify_live_start("主播名", "https://live.example.com/123")

# 通知结束
notifier.notify_live_end(
    "主播名",
    "https://live.example.com/123",
    duration="2小时30分",
    file_path="/downloads/recording.mp4"
)
```

## 🔧 配置说明

### Cookie 配置

编辑 `config/config.ini` 文件中的 Cookie 部分：

```ini
[Cookie]
抖音cookie = your_douyin_cookie
快手cookie = your_kuaishou_cookie
B站cookie = your_bilibili_cookie
# ... 其他平台
```

### 录制配置

主要配置项在 `RecordingConfig` 中：

```python
config = RecordingConfig(
    video_save_path="downloads",        # 保存路径
    video_save_type="TS",               # 视频格式
    loop_interval=60,                   # 检测间隔（秒）
    split_time=3600,                    # 分段时长（秒）
    split_video_by_time=False,          # 是否分段
    enable_https=True,                  # 启用 HTTPS
    converts_to_mp4=False,              # 转换为 MP4
    delete_origin_file=True,            # 删除原文件
    folder_by_author=True,              # 按作者分文件夹
    folder_by_time=False,               # 按时间分文件夹
    clean_emoji=True,                   # 清理 emoji
)
```

## 🆚 新旧 API 对比

| 功能 | v1 API | v2 API (新) |
|------|--------|-------------|
| 基础路径 | `/api/recordings` | `/api/v2/recording` |
| 启动录制 | ✅ | ✅ 更灵活的配置 |
| 停止录制 | ✅ | ✅ |
| 状态查询 | ✅ | ✅ |
| 测试平台 | ❌ | ✅ 新增 |
| 视频转码 | ❌ | ✅ 新增 |
| 模块化 | ❌ | ✅ 完全模块化 |

## 📖 详细文档

- [完整重构指南](docs/refactoring_guide.md)
- [重构总结](REFACTORING_SUMMARY.md)
- [API 文档](http://localhost:8000/docs)

## ❓ 常见问题

### Q: 新 API 和旧 API 有什么区别？
A: 新 API 基于模块化架构，代码更清晰，功能更强大，但接口参数基本一致。

### Q: 可以同时使用新旧 API 吗？
A: 可以，两套 API 可以并存，互不干扰。

### Q: 录制的文件保存在哪里？
A: 默认保存在 `downloads/` 目录，可以通过配置修改。

### Q: 如何配置 Cookie？
A: 编辑 `config/config.ini` 文件的 `[Cookie]` 部分。

### Q: 出错时如何调试？
A: 查看日志文件或使用 `/api/v2/recording/test-platform` 端点测试平台连接。

## 🐛 问题反馈

如果遇到问题，请：
1. 检查日志输出
2. 查看 API 文档：http://localhost:8000/docs
3. 参考详细文档：[docs/refactoring_guide.md](docs/refactoring_guide.md)

---

**开始愉快地使用新的模块化录制系统吧！** 🎉
