# 录制架构 – 变更：retire-legacy-recorder

## MODIFIED Requirements

### Requirement: Event-Driven Recording Supervisor
调度器 MUST 仅依赖现代工作器工厂管理录制线程。
#### Scenario: Start Recording On Room Added
- **GIVEN** 注册服务广播房间新增事件
- **WHEN** 调度器创建录制线程
- **THEN** 线程 MUST 由原生录制工作器工厂启动，而非调用 LegacyRecorder

#### Scenario: Stop Recording On Room Disabled
- **GIVEN** 房间被禁用或移除
- **WHEN** 调度器停止对应线程
- **THEN** 工作线程 MUST 通过原生管道释放资源，不得回落到 legacy 适配层

## ADDED Requirements

### Requirement: Native Worker Runtime
运行时 MUST 提供无需 legacy 适配层的原生工作器执行环境。
#### Scenario: Worker Factory Selection
- **GIVEN** 录制运行时需要为房间选择工作器
- **WHEN** 根据房间配置判断分段或连续录制
- **THEN** 系统 MUST 直接使用 `RecordingWorker` 或分段工作器生成线程，配置来源于现代上下文服务

#### Scenario: Environment Integration Without Legacy Adapter
- **GIVEN** 工作器需要访问 Cookie、代理及存储配置
- **WHEN** 运行时为工作器注入依赖
- **THEN** 数据 MUST 由现代配置/服务层提供，LegacyRecorder 及其环境包装器不得成为必经路径
