# Recording Architecture Overview

## Core Components

- **RoomRepository**: 提供线程安全的 `URL_config.ini` 读写封装，支持房间新增、更新、禁用与注释，同时保证写入原子性。
- **RoomRegistry**: 维护内存中的房间集合并广播生命周期事件，供调度与外部模块订阅。
- **RecordingSupervisor**: 监听注册服务事件并启动/停止录制线程，可通过工厂函数适配现有 `start_record` 逻辑。
- **RoomService**: 协调仓库与注册表，提供去重、批量同步以及常用增删改操作。
- **LegacyRoomAdapter**: 为旧版流程提供兼容接口，输出原有的元组与注释列表，同时利用仓库服务确保数据一致。
- **FilePollingWatcher / RoomCommandInterface**: 作为可插拔控制通道，实现文件轮询热更新与命令行管理。

## Initialization

`RecordingApplication` 负责装配上述组件：

1. 创建 `RoomRepository`、`RoomRegistry` 与 `RoomService` 并完成引导。
2. 启动 `RecordingSupervisor`，并可选启用文件监听或 CLI 控制通道。
3. 通过 `set_context` 暴露运行时上下文，便于现有代码渐进集成。

当前主循环已通过 `RoomService` 读取配置并执行去重、过滤与自动补全逻辑，逐步替换原有基于文件的解析流程。

## Testing

- 新增 `tests/recording/test_recording_components.py` 覆盖仓库解析、增删改、去重逻辑及遗留适配器输出。
- 测试使用标准库 `unittest`，可通过 `python3 -m unittest tests.recording.test_recording_components` 执行。

## 下一步

- 将 `main.py` 的配置解析与热更新逻辑迁移到 `RoomService`/`LegacyRoomAdapter`。
- 逐步用事件驱动调度替换全局列表与直接线程管理。
- 扩展控制通道（如 CLI / HTTP）以支持运行期动态增删房间。
- 将 `RoomCommandInterface` 集成到主流程或独立入口，提供基础命令管理。
