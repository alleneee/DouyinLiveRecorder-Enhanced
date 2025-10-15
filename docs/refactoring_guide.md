# Main.py 重构指南

## 概述

本文档说明了 `main.py` 核心方法的重构，以及如何与 FastAPI 实现集成使用。

## 架构改进

### 重构前（旧架构）
```
main.py (2173 行)
├── start_record() - 核心录制函数（1000+ 行）
├── check_subprocess() - FFmpeg 进程管理
├── 50+ 平台的硬编码判断逻辑
└── 各种工具函数混杂在一起
```

### 重构后（新架构）
```
src/
├── platforms/              # 平台处理器抽象层
│   ├── base.py            # 基类和接口
│   ├── registry.py        # 平台注册表
│   └── legacy_adapter.py  # 适配旧版 spider/stream
│
├── recording/
│   ├── worker.py          # 录制工作器
│   ├── models.py          # 数据模型
│   ├── supervisor.py      # 录制调度器
│   └── ...
│
└── processing/            # 后处理服务
    ├── converter.py       # 视频转码
    └── notifier.py        # 推送通知
```

## 核心组件

### 1. PlatformHandler（平台处理器）

抽象基类，定义了平台处理器的接口：

```python
from src.platforms import PlatformHandler, StreamInfo

class MyPlatformHandler(PlatformHandler):
    @property
    def platform_name(self) -> str:
        return "我的平台"
    
    def can_handle(self, url: str) -> bool:
        return "myplatform.com" in url
    
    async def get_stream_info(self, url: str, quality: str = "OD") -> StreamInfo | None:
        # 获取直播流信息
        return StreamInfo(
            real_url="https://stream.url/live.m3u8",
            is_live=True,
            anchor_name="主播名",
            title="直播标题",
            quality=quality,
        )
```

### 2. RecordingWorker（录制工作器）

封装单个直播间的完整录制逻辑：

```python
from src.recording.worker import RecordingWorker, RecordingConfig
from src.platforms.legacy_adapter import LegacyPlatformHandler
from src.recording.models import Room

# 创建配置
config = RecordingConfig(
    video_save_path="downloads",
    video_save_type="TS",
    loop_interval=60,
    converts_to_mp4=True,
)

# 创建平台处理器
handler = LegacyPlatformHandler(
    cookies_map={"dy_cookie": "your_cookie"},
)

# 创建房间对象
room = Room(
    identity="room_001",
    url="https://live.douyin.com/123456",
    nickname="主播昵称",
    quality="OD",
)

# 创建并运行工作器
import asyncio
worker = RecordingWorker(
    room=room,
    platform_handler=handler,
    config=config,
)
asyncio.run(worker.run())
```

### 3. VideoConverter（视频转码）

```python
from src.processing import VideoConverter

converter = VideoConverter(
    convert_to_h264=False,
    delete_origin=True,
)

# 转换为 MP4
mp4_path = converter.convert_to_mp4("recording.ts")

# 视频分段
segments = converter.segment_video("long_video.mp4", segment_time=3600)
```

### 4. PushNotifier（推送通知）

```python
from src.processing import PushNotifier

notifier = PushNotifier(
    enabled_channels=["微信", "钉钉"],
    title="直播通知",
    xizhi_api_url="your_api_url",
)

# 通知开播
notifier.notify_live_start("主播名", "直播URL")

# 通知结束
notifier.notify_live_end("主播名", "直播URL", duration="2小时", file_path="/path/to/video.mp4")
```

## FastAPI 集成

### 方式 1：通过现有的 LegacyRecorder

`app/recording/legacy_adapter.py` 已经集成了新的模块化组件：

```python
from app.runtime import ensure_runtime

# 确保运行时已初始化
context = ensure_runtime()

# 添加房间（会自动使用新的录制工作器）
context.service.add_room(
    identity="room_001",
    url="https://live.douyin.com/123456",
    nickname="主播",
    quality="OD",
)
```

### 方式 2：直接使用新组件

创建自定义 API 端点：

```python
# app/api/routers/recording_v2.py
from fastapi import APIRouter, BackgroundTasks
from src.platforms.legacy_adapter import LegacyPlatformHandler
from src.recording.worker import RecordingWorker, RecordingConfig
from src.recording.models import Room

router = APIRouter(prefix="/v2/recording", tags=["recording-v2"])

@router.post("/start")
async def start_recording(
    url: str,
    nickname: str,
    quality: str = "OD",
    background_tasks: BackgroundTasks = None,
):
    """启动录制（使用新架构）。"""
    
    # 创建配置
    config = RecordingConfig(
        video_save_path="downloads",
        video_save_type="TS",
        converts_to_mp4=True,
    )
    
    # 创建平台处理器
    handler = LegacyPlatformHandler()
    
    # 创建房间
    room = Room(
        identity=url,
        url=url,
        nickname=nickname,
        quality=quality,
    )
    
    # 创建工作器
    worker = RecordingWorker(
        room=room,
        platform_handler=handler,
        config=config,
    )
    
    # 在后台任务中运行
    import asyncio
    background_tasks.add_task(lambda: asyncio.run(worker.run()))
    
    return {"status": "started", "url": url}
```

## 优势

### 1. 模块化设计
- 每个组件职责单一，易于理解和维护
- 可独立测试各个模块

### 2. 可扩展性
- 添加新平台只需实现 `PlatformHandler` 接口
- 后处理逻辑可独立扩展

### 3. 向后兼容
- 通过 `LegacyPlatformHandler` 适配器，保持与旧代码的兼容
- 现有功能不受影响

### 4. FastAPI 友好
- 异步设计，原生支持 FastAPI
- 易于创建 REST API 端点

## 迁移路径

### 阶段 1：当前状态（已完成）
- ✅ 创建新的模块化组件
- ✅ 保持与旧代码的兼容性
- ✅ 通过 `LegacyRecorder` 自动使用新组件

### 阶段 2：逐步迁移（进行中）
- 🔄 创建新的 API 端点使用新架构
- 🔄 编写单元测试
- 🔄 性能测试和优化

### 阶段 3：完全迁移（规划中）
- 📋 将所有平台实现为独立的 Handler
- 📋 移除对旧 `main.py` 的依赖
- 📋 优化性能和资源使用

## 测试

### 单元测试示例

```python
import pytest
from src.platforms import StreamInfo
from src.recording.worker import RecordingConfig

def test_recording_config():
    config = RecordingConfig(
        video_save_path="test_downloads",
        video_save_type="TS",
    )
    assert config.video_save_path == "test_downloads"
    assert config.video_save_type == "TS"

@pytest.mark.asyncio
async def test_stream_info():
    info = StreamInfo(
        real_url="https://example.com/stream.m3u8",
        is_live=True,
        anchor_name="测试主播",
        title="测试直播",
        quality="OD",
    )
    assert info.is_live is True
    assert info.anchor_name == "测试主播"
```

## 常见问题

### Q: 旧代码还能用吗？
A: 能。`LegacyRecorder` 自动使用新组件，无需修改现有代码。

### Q: 如何添加新平台支持？
A: 实现 `PlatformHandler` 接口，注册到 `PlatformRegistry`。

### Q: 性能有改善吗？
A: 新架构使用异步设计，理论上性能更好。具体需要基准测试。

### Q: 如何回滚到旧版本？
A: 在 `legacy_adapter.py` 的 `record()` 方法中，有 `except ImportError` 分支会自动回退。

## 贡献指南

如果你想扩展新架构：

1. **添加平台支持**：在 `src/platforms/` 创建新的 Handler
2. **增强后处理**：在 `src/processing/` 添加新服务
3. **优化工作器**：改进 `RecordingWorker` 的逻辑
4. **编写测试**：确保新功能有测试覆盖

## 相关文档

- [FastAPI 后端重构提案](../openspec/changes/refactor-fastapi-backend/proposal.md)
- [录制架构规范](../openspec/specs/recording-architecture/spec.md)
- [API 文档](./api_documentation.md)
