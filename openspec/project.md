# 项目上下文

## 项目目标
Douyin Live Recorder 专注于多平台直播录制与后处理：
- 统一管理直播间数据，支持按 URL、清晰度、主播信息等维度维护房间。
- 通过事件驱动的调度器协调录制线程，提供分段录制与持续录制两套模式。
- 在录制结束后触发转码、OSS 上传、消息推送等流程，满足生产部署需求。

## 技术栈
- **语言与运行时**：Python 3.12+，asyncio 并发模型。
- **Web/API**：FastAPI、Uvicorn，REST 风格接口供外部控制。
- **数据存储**：MySQL 5.7+（默认），支持 SQLite 作为本地开发数据库，使用 SQLAlchemy 2.x 与 Alembic。
- **录制工具链**：FFmpeg、oss2（Aliyun OSS SDK）、requests/httpx。
- **环境管理**：uv（pip 加速器）、pyproject.toml、.env 配置。
- **测试**：pytest、pytest-asyncio、手工验证脚本（OSS/FFmpeg 流程）。

## 项目规范

### 代码风格
- 遵循 PEP 8，Black 行宽 88，并配合 isort/ruff（如启用）保持导入顺序。
- 函数与变量使用 `snake_case`，ORM 模型、Pydantic 模型与服务类使用 `PascalCase`。
- 提倡完整类型注解与 docstring，异步 API 需标注返回值与异常说明。
- 所有变更需最小化影响，避免无关重构并保持中文注释/日志清晰。

### 架构模式
- `RecordingApplication` 组合仓库、注册中心与监督器，负责运行时装配。
- `RoomRepository` 负责配置与数据库同步，`RoomRegistry` 管理内存状态与事件广播。
- `RecordingSupervisor` 监听房间事件并直接调度原生工作线程。
- 新功能优先在 `app/core/recording` 实现，并持续清理 legacy 依赖。

### 测试策略
- 使用 pytest 组织单元测试与集成测试，测试文件结构与源码保持一致。
- 对录制调度、仓库同步等关键逻辑编写回归测试；OSS/FFmpeg 流程因依赖外部服务，采用脚本化手工验证并在 README 中说明步骤。
- 计划中的 CI 需至少运行 `pytest -q` 与关键静态检查，避免引入网络依赖。

### Git 工作流
- 主分支 `main` 存放稳定版本，特性开发使用独立分支并通过 PR 合并。
- 提交信息遵循 Conventional Commits（如 `feat:`, `fix:`, `perf:`），PR 描述需包含问题背景、解决方案与测试结果。
- 涉及配置或脚本变更，需在 PR 中列出影响范围与回滚策略。

## 领域背景
- 支持多平台直播录制（抖音、TikTok、快手等），需要维护各自的 Cookie、代理与解析策略。
- 录制结果可按清晰度、主播、时间等规则组织，并支持转码、分段与推送需求。
- 在保留旧版 INI/JSON 配置兼容性的同时，逐步迁移至数据库驱动与 API 控制模式。

## 关键约束
- 禁止将真实的 Cookie、AccessKey、Webhook 等敏感信息写入仓库或日志。
- 部分平台需要代理访问，在 CI 或无代理环境下需使用 mock/跳过策略。
- 旧版 legacy 组件仍在生产环境运行，迁移需确保行为等价并提供回退方案。
- 录制依赖 FFmpeg，需要在部署环境预先安装并验证可用性。

## 外部依赖
- 第三方直播平台（抖音、TikTok、快手等）：通过页面解析或非公开 API 获取流信息。
- 媒体处理：FFmpeg 命令行工具。
- 存储与推送：阿里云 OSS（oss2 SDK）、钉钉/Telegram 等消息渠道。
- 数据库与缓存：MySQL（生产）与 SQLite（开发），可结合 Redis 等组件扩展任务队列。
