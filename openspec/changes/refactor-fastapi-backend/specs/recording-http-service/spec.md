## ADDED Requirements
### Requirement: FastAPI Application Layout
系统 MUST 采用 FastAPI 推荐目录结构，并集中在 `app/` 目录内暴露可导入的 `FastAPI` 实例。

#### Scenario: Module Tree Created
- **WHEN** 工程初始化 FastAPI 服务
- **THEN** 目录包含 `app/main.py`, `app/api/routers`, `app/core`, `app/db`, `app/models`, `app/schemas`, `app/services`
- **AND** `uvicorn app.main:app` 可直接启动应用

### Requirement: Room Management API
系统 MUST 提供 REST 接口以管理房间资源，操作结果同步到数据库和录制注册表。

#### Scenario: List Rooms
- **WHEN** 客户端调用 `GET /rooms`
- **THEN** 服务返回分页房间列表，字段包含 `id`, `url`, `quality`, `nickname`, `status`, 时间戳

#### Scenario: Create Room
- **WHEN** 客户端发送有效负载到 `POST /rooms`
- **THEN** 服务校验并写入数据库
- **AND** 触发注册表加载新房间并返回 201 响应

#### Scenario: Update Room
- **WHEN** 客户端调用 `PATCH /rooms/{id}` 更新清晰度、昵称或状态
- **THEN** 数据库与注册表同步最新状态

#### Scenario: Disable Room
- **WHEN** 客户端调用 `DELETE /rooms/{id}` 或 `POST /rooms/{id}/disable`
- **THEN** 服务将房间状态标记为 `disabled` 并停止对应录制线程

### Requirement: Recording Control API
系统 MUST 暴露录制控制接口，以协调 `RecordingSupervisor` 的启动与停止。

#### Scenario: Start Recording
- **WHEN** 客户端调用 `POST /recordings/{room_id}/start`
- **THEN** 服务通过 Supervisor 启动录制线程，并返回当前状态

#### Scenario: Stop Recording
- **WHEN** 客户端调用 `POST /recordings/{room_id}/stop`
- **THEN** 服务停止线程并持久化录制结束时间

#### Scenario: Recording Status Query
- **WHEN** 客户端调用 `GET /recordings/{room_id}`
- **THEN** 服务返回数据库中最新的录制状态与文件信息

### Requirement: Database Migration Support
系统 MUST 使用 Alembic 管理 MySQL 5.7 数据结构，并保持迁移脚本与模型同步。

#### Scenario: Initial Migration Created
- **WHEN** 运行 `alembic upgrade head`
- **THEN** 创建 `rooms` 与 `recordings` 表，包含外键、索引与时间戳列

#### Scenario: Autogenerate Configured
- **WHEN** 执行 `alembic revision --autogenerate`
- **THEN** Alembic 能够读取 SQLAlchemy 元数据并生成增量迁移文件
