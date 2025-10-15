<!-- OPENSPEC:START -->
# OpenSpec 使用说明

以下说明是给在本项目中工作的 AI 助手使用的。

当请求中出现以下情况时，请务必打开 @/openspec/AGENTS.md 文件：

- 提及规划或提案（例如：proposal、spec、change、plan 等词）

- 引入新功能、重大变更、架构调整，或涉及性能 / 安全性的大型工作

- 请求内容存在歧义，需要在编写代码前查阅权威规范

通过阅读 @/openspec/AGENTS.md，你将了解：

- 如何创建和应用变更提案（proposal）

- 规范（spec）的格式与约定

- 项目的结构与工作指南

请保留此受管区块，以便执行 openspec update 时自动刷新说明内容。

<!-- OPENSPEC:END -->

# Repository Guidelines

## 项目结构与模块组织

Douyin Live Recorder 聚焦多平台直播录制与后处理，涵盖房间管理、分段/持续录制及录制后转码、上传、推送等生产流程，并兼容旧版 INI/JSON 配置模式。
项目当前支持抖音、TikTok、快手等平台，需针对各自 Cookie、代理策略与解析方式维护配置，保证旧版组件平滑过渡。

- **运行时与数据层**：Python 3.12+（`asyncio` 并发）、FastAPI + Uvicorn、SQLAlchemy 2.x + Alembic；MySQL 5.7+ 为生产数据库，SQLite 适用于本地开发。
- **录制工具链**：FFmpeg、Aliyun OSS SDK (`oss2`)、`requests/httpx` 等为录制、上传与通知流程提供支撑。
- **配置与依赖管理**：使用 `uv`、`pyproject.toml` 与 `.env` 管理环境、依赖与敏感配置。
- **核心组件职责**：`RecordingApplication` 装配仓库、注册中心与监督器；`RoomRepository` 同步配置与数据库；`RoomRegistry` 管理内存状态与事件；`RecordingSupervisor` 监听房间事件并调度原生录制工作器。
- **legacy 迁移策略**：`app/legacy/` 仍在生产环境使用，新功能优先落在 `app/core/recording`，迁移需确保行为等价并保留回退方案。
- **`app/`**：FastAPI 服务与核心业务所在，`core/recording/` 负责监督器与录制工作器，`services/` 处理数据库事务，`runtime.py` 负责运行时启动。
- **`app/legacy/`**：旧版 spider/stream 兼容层，仅在扩展传统平台解析时修改。
- **`config/` 与 `backup_config/`**：INI 配置与备份，`URL_config.ini` 是默认房间清单，修改后同步备份。
- **`downloads/` 与 `logs/`**：录制文件与日志输出目录，不要提交生成内容。
- **`tests/` 与 `tests/verify_*.py`**：Pytest 单元测试及流程脚本，新增功能时保持对应覆盖。
- **`openspec/`**：录制体系规范，进行架构调整前务必阅读。

## 构建、测试与开发命令

- `uv venv && source .venv/bin/activate`：创建并启用虚拟环境，统一使用 `uv`。
- `uv pip install -r requirements.txt`：安装依赖，受限场景可追加 `--system`。
- `uvicorn app.main:app --reload --port 8009`：本地启动 API，便于联调。
- `pytest -q`：运行核心测试；如需手动校验 OSS，可配合 `tests/verify_oss_flow.py`。

## 编码风格与命名规范

- 遵循 PEP 8，Black 配置行宽 88；必要时同时运行 `black` 与 `isort` 保持格式。
- 保持完整类型注解与 docstring，异步 API 需明确返回值与异常说明。
- 函数与变量使用 `snake_case`，ORM 模型与 Pydantic 模型采用帕斯卡命名。
- 变更遵循最小化原则，尊重现有模块边界，非必要不重命名。
- 遵循 KISS 原则，非必要不要过度设计。
- 在开发中遵循 SOLID 原则。

## 测试指南

- 统一使用 Pytest，测试文件与源码结构一一对应（示例：`tests/recording/test_*`）。
- 修改监督器、工作器或仓库持久化逻辑时，保持回归覆盖并记录关键场景。
- 计划中的 CI 至少运行 `pytest -q` 与关键静态检查，避免引入外部网络依赖。
- 涉及 OSS/FFmpeg 的流程优先复用现有脚本，并在 PR 中说明前置条件与手工验证步骤。

## 提交与拉取请求规范

- 主分支 `main` 存放稳定版本，特性开发使用独立分支并通过 PR 合并。
- 提交信息推荐使用 Conventional Commits（如 `feat: 添加抖音H265解析`），简洁说明目的。
- PR 需关联相关议题、说明配置变更，并附测试结果（`pytest` 输出或人工验证日志）。
- 调整 `SegmentRecordingWorker` 或 OSS 上传配置时，记录变更前后的行为差异，并提供回滚方案。

## 安全与配置提示

- OSS 密钥、直播 Cookie 等敏感信息禁止入库，统一放置在 `.env` 并在日志中脱敏。
- 修改 `config/*.ini` 时在 PR 中阐明原因，确保有据可查。
- 部分平台需代理访问，在 CI 或无代理环境下需使用 mock 或跳过策略。
- 录制链路依赖 FFmpeg，部署前需确认工具已安装并通过验证。

## Python 专项规范

- 使用 Python 语言迭代本项目时，需遵循 `/Users/niko/Downloads/python-pro.md`《Python Pro》文档中列明的现代化实践。
- 优先采用 Python 3.12+ 特性，结合 `uv`、`ruff`、`pytest`、`pydantic` 与 FastAPI；新增工具须确认与文档要求一致。
- 编写代码时保持完整类型注解、详尽异常处理与 docstring，测试覆盖率目标 ≥90%，必要时补充 `pytest` fixture 或属性测试。
- 涉及性能、异步或资源消耗的改动，应参照文档建议开展 profiling、异步优化或缓存策略，并在 PR 中说明验证方法与收益。
- 非必要不创建md文档进行说明
