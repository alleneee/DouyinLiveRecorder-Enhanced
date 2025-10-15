## Overview
本设计说明如何将现有录制逻辑迁移到 FastAPI 推荐目录结构，并接入 SQLAlchemy/Alembic。

## Architecture
- `app/main.py` 暴露 FastAPI 实例，加载 API 路由、生命周期钩子。
- `app/core/config.py` 使用 `pydantic-settings` 读取数据库、日志、录制参数。
- `app/db/session.py` 建立异步 SQLAlchemy 引擎（`mysql+aiomysql://`），提供依赖注入的 `AsyncSession`。
- `app/models/*.py` 定义 ORM：`RoomORM` 与 `RecordingORM`，包含软删除/状态字段。
- `app/schemas/rooms.py` 等定义 Pydantic 入参/出参模型，用于请求验证。
- `app/services/room_service.py` 封装房间 CRUD、状态同步到 `RoomRegistry`。
- `app/services/recording_service.py` 调用现有 `RecordingSupervisor` 触发录制、收敛状态。
- `app/api/routers/rooms.py`、`recordings.py` 提供 REST 路由；统一挂载到 `app/api/router.py`。
- Alembic `env.py` 注入 SQLAlchemy 元数据并读取应用配置，首个迁移创建 `rooms` 与 `recordings`。

## Integration Strategy
- 继续复用 `src/recording` 下的上下文、Supervisor 与 worker factory。
- 启动 FastAPI 时构造 `RecordingApplication`，将仓库适配至数据库：
  - 实现 `DatabaseRoomRepository` 作为 `RoomRepository` 新后端，读取/写入 MySQL。
  - 提供同步任务保持文件配置可选导出，满足旧流程。
- 服务层在数据库事务成功后更新 `RoomRegistry`，保持内存状态与线程调度一致。
- 录制控制 API 经由服务层调用 `RecordingSupervisor` 的 `start_recording`、`stop_recording` 等（新增封装）。

## Data Model Notes
- `rooms`：`id`、`platform`、`room_identity`、`nickname`、`quality`、`status`、`created_at`、`updated_at`、`comment`。
- `recordings`：`id`、`room_id` 外键、`started_at`、`stopped_at`、`status`、`file_path`、`error_message`。
- 使用 `ENUM` 或 `VARCHAR` 存储状态，确保兼容 MySQL 5.7。

## Operations
- `uvicorn app.main:app` 作为入口，同时保留旧 `main.py` 触发方式。
- Alembic 迁移命令：`alembic init`, `alembic revision --autogenerate`, `alembic upgrade head`。
- 文档更新：说明如何配置 `DATABASE_URL`、如何运行迁移与启动服务。
