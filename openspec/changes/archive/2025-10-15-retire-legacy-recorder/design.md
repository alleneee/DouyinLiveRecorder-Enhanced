# 设计：原生录制运行时

## 当前状态
- `bootstrap_runtime` 通过 `legacy_worker_factory` 将 `RecordingApplication` 绑定到 `_worker_entry`，并在其中实例化 `LegacyRecorder`。
- `LegacyRecorder.record` 会创建新的 asyncio 事件循环，将调用代理到 `RecordingWorker`，并从 `RecordingEnvironment` 重建 Cookie 与配置。
- 因此运行时同时维护应用层与 legacy 适配层两个维度，二者都要追踪环境、Cookie 以及录制生命周期。

## 目标架构
- `RecordingApplication` 应直接接收原生工作器工厂，可创建 `SegmentRecordingWorker`、`ContinuousRecordingWorker` 或统一的 `RecordingWorker`。
- 房间元数据、配置与 Cookie 通过现代服务（`RecordingContext`、仓库及环境加载器）提供，无需 `LegacyRecorder`。
- 启停语义仍由监督器掌控，但任何线程都不再调用 legacy 代码路径。

## 关键改动
1. **运行时启动**
   - 移除 `LegacyRecorder` 的创建及相关环境状态。
   - 提供根据房间信息选择工作器（分段或连续）的工厂函数，复用现有服务层与配置。

2. **配置处理**
   - 将 Cookie 解析、代理配置与录制选项折叠为可复用工具，可视情况重构 `RecordingEnvironment` 或迁移到 `RecordingContext`。
   - 确保工作器接收结构化配置对象，而非直接读取 legacy INI 文件。

3. **监督器与工作器契约**
   - 更新 `_worker_entry`（或其替代实现），在受控事件循环中运行异步工作器，并向 `RecordingService` 回报生命周期事件。
   - 通过 `stop_event` 实现优雅停机，不再依赖 `LegacyRecorder`。

4. **废弃清理**
   - 将 legacy 适配模块标记为未使用（删除或隔离），并更新导入，确保 `app/runtime.py` 不再引用它们。

## 风险与缓解
- **风险**：工作器可能仍依赖 legacy 配置语义。*缓解*：在完全迁移前提供适配函数，将 `RecordingEnvironment` 数据转换为新配置。
- **风险**：移除 legacy 可能影响依赖自定义 Cookie 的平台。*缓解*：保留 Cookie 获取逻辑，但从新流水线调用。
- **风险**：线程与异步交互可能回归。*缓解*：为监督器启停与工作器取消编写测试，并复用现有手工脚本验证。

## 备选方案
- 保留 `LegacyRecorder` 但缩小范围：已拒绝，因为双重代理仍存在，阻碍后续演进。
- 立即重写各平台数据抓取：暂缓，本次变更专注移除运行时代码桥接，平台统一可在后续开展。
