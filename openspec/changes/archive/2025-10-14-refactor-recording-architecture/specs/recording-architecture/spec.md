## ADDED Requirements

### Requirement: Room Repository Abstraction
系统 MUST 提供房间仓库 `RoomRepository`，封装对 `URL_config.ini` 的解析与持久化，并允许后续替换为其他后端。

#### Scenario: Load Rooms From File
- **GIVEN** 默认配置目录存在 `URL_config.ini`
- **WHEN** 仓库加载配置
- **THEN** 返回标准化的 `Room` 集合，包含清晰度、URL、昵称、状态与时间戳
- **AND** 对异常行生成注释信息供后续写回

#### Scenario: Persist Repository Changes
- **GIVEN** 仓库内房间集合发生增删或状态变更
- **WHEN** 调用保存接口
- **THEN** `URL_config.ini` 被原子化写回，包含最新注释与禁用信息
- **AND** 写入过程对并发访问加锁

### Requirement: Room Registry Service
系统 MUST 暴露内存态的 `RoomRegistry`，负责房间生命周期管理与状态事件分发。

#### Scenario: Publish Room Lifecycle Events
- **WHEN** 房间被添加、移除或禁用
- **THEN** 注册服务向订阅者广播对应事件
- **AND** 事件包含房间标识与最新状态

#### Scenario: Thread-Safe Room Access
- **WHEN** 多个录制线程查询或更新房间状态
- **THEN** 注册服务保证线程安全并返回最新的 `Room` 数据

### Requirement: Event-Driven Recording Supervisor
录制调度 MUST 依赖 `RecordingSupervisor` 监听房间事件，启动或停止录制线程。

#### Scenario: Start Recording On Room Added
- **GIVEN** 注册服务广播房间新增事件
- **WHEN** 调度器接收事件
- **THEN** 启动对应录制线程并使用 `Room` 数据作为参数

#### Scenario: Stop Recording On Room Disabled
- **WHEN** 房间被禁用或移除
- **THEN** 调度器停止对应线程并释放资源

### Requirement: Pluggable Control Channels
系统 MUST 提供至少一种运行期控制通道以增删房间，并将文件监听作为兼容方案。

#### Scenario: CLI Command Adds Room
- **WHEN** 通过命令行接口调用“添加房间”
- **THEN** 注册服务更新内存集合并触发新增事件
- **AND** 仓库在下一次保存时持久化变动

### Requirement: Unified Room Metadata
系统 MUST 以 `Room` 数据类统一描述房间信息，并贯穿仓库、注册服务与录制线程。

#### Scenario: Room Metadata Propagates Across Modules
- **WHEN** 仓库输出房间数据
- **THEN** 注册服务与录制线程获得同一 `Room` 实例或副本
- **AND** 禁用或状态更新通过 `Room` 字段同步回仓库
