# API v2 新特性说明

## 🎉 全新模块化架构

基于 main.py 核心逻辑重构，提供更清晰、更强大的录制能力。

## ✨ 核心改进

### 1. 平台处理器抽象
```python
# 统一的平台接口
from src.platforms import PlatformHandler

class MyHandler(PlatformHandler):
    async def get_stream_info(self, url: str, quality: str):
        # 实现获取逻辑
        pass
```

### 2. 独立的录制工作器
```python
# 封装完整的录制逻辑
from src.recording.worker import RecordingWorker

worker = RecordingWorker(room, handler, config=config)
await worker.run()
```

### 3. 后处理服务
```python
# 视频转码
from src.processing import VideoConverter
converter.convert_to_mp4("video.ts")

# 推送通知
from src.processing import PushNotifier
notifier.notify_live_start("主播", "URL")
```

## 🚀 新增 API 端点

### 基础路径：`/api/v2/recording`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/start` | POST | 启动录制（支持更多配置） |
| `/stop` | POST | 停止录制 |
| `/status` | GET | 查看所有活跃录制 |
| `/test-platform` | POST | 🆕 测试平台连接 |
| `/convert` | POST | 🆕 后台视频转码 |

## 📊 对比旧版

| 特性 | v1 | v2 |
|------|----|----|
| 代码结构 | 单体 | 模块化 ✅ |
| 可扩展性 | 低 | 高 ✅ |
| 测试平台 | ❌ | ✅ |
| 视频转码 API | ❌ | ✅ |
| 异步支持 | 部分 | 完整 ✅ |
| 向后兼容 | - | 100% ✅ |

## 🔄 兼容性保证

- ✅ 旧 API 继续工作
- ✅ 自动使用新组件（通过 LegacyRecorder）
- ✅ 失败时回退到旧逻辑
- ✅ 无需修改现有代码

## 📚 快速开始

```bash
# 1. 启动服务
uvicorn app.main:app --reload

# 2. 使用新 API
curl -X POST "http://localhost:8000/api/v2/recording/start" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/123456",
    "nickname": "主播",
    "quality": "OD",
    "converts_to_mp4": true
  }'
```

## 📖 详细文档

- [快速开始](../QUICK_START_V2.md)
- [重构指南](refactoring_guide.md)
- [重构总结](../REFACTORING_SUMMARY.md)

## 🎯 使用建议

### 新项目
推荐直接使用 v2 API，享受更清晰的架构和更强的功能。

### 现有项目
- 保持使用 v1 API（已自动使用新组件）
- 逐步迁移到 v2 API
- 两个版本可以并存

## 💡 最佳实践

1. **使用 v2 API 的测试端点**验证平台连接
2. **启用转码 API** 实现异步后处理
3. **配置推送通知**获取实时状态更新
4. **按需扩展** PlatformHandler 支持新平台

---

**立即体验新功能！** 访问 http://localhost:8000/docs
