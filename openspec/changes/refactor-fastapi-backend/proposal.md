## Why
- 现有脚本式结构难以扩展对外服务，缺少统一 API 与数据库持久层。
- 用户请求基于 FastAPI + SQLAlchemy + Alembic 的推荐目录架构以支持后续维护与部署。
- 需要将房间管理与录制控制能力统一到 Web 服务和数据库模型中。

## What Changes
- 引入 `app/` 目录结构（`api/`, `core/`, `db/`, `models/`, `schemas/`, `services/`) 并迁移现有录制上下文。
- 配置 MySQL 5.7 兼容的 SQLAlchemy 会话工厂与 Alembic 迁移脚手架。
- 建模 `rooms`、`recordings` 数据表，提供增删改查与录制指令领域方法。
- 暴露 FastAPI 路由用于房间管理（列表、创建、更新、禁用）与录制控制（触发录制、停止、查询状态）。
- 保留原有录制调度逻辑，通过服务层适配数据库与实时状态。

## Impact
- 新增依赖：`fastapi`、`uvicorn`、`sqlalchemy`、`alembic`、`pydantic-settings`、MySQL 驱动（如 `aiomysql`）。
- 需要新建环境变量或配置文件以提供数据库连接字符串。
- 需要编写 Alembic 初始迁移并更新文档与部署指引。
- 后续 CLI 或脚本入口需重定向到新的 FastAPI 应用或保留兼容层。
