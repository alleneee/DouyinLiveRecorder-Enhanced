## MODIFIED Requirements
### Requirement: Room Repository Abstraction
仓库 MUST 支持可插拔的持久层，实现文件与数据库（MySQL 5.7）双后端，并保持统一的 `Room` 数据模型。

#### Scenario: Load Rooms From Database Backend
- **GIVEN** 提供 MySQL 连接配置
- **WHEN** 仓库初始化并加载房间
- **THEN** 返回与文件后端一致的 `Room` 集合
- **AND** 每个房间包含状态、清晰度、昵称与时间戳

#### Scenario: Persist Database Changes
- **WHEN** 服务层对房间进行增删改或状态变更
- **THEN** 仓库写入 MySQL 并更新 `updated_at`
- **AND** 成功后触发与内存注册表同步事件
