# 日志体系重构文档

## 概述

DouyinLiveRecorder 项目的日志系统已重构为统一的中文日志输出体系，整合了 loguru 和标准 logging 库。

## 架构设计

### 核心模块

**`app/core/logging_config.py`** - 统一日志配置模块
- `LoggingConfig` 类：管理全局日志配置
- `setup_logging()` 函数：便捷初始化入口
- `get_logger()` 函数：获取 logger 实例

### 日志级别

- **DEBUG**: 详细的调试信息
- **INFO**: 关键业务流程信息（默认）
- **WARNING**: 警告信息
- **ERROR**: 错误信息

### 日志输出

1. **控制台输出**
   - 彩色格式化输出
   - 显示时间、级别、模块、函数、行号

2. **文件输出**
   - **app_{日期}.log**: 应用日志（INFO级别以上）
   - **error_{日期}.log**: 错误日志（ERROR级别以上）
   - 自动按天轮转
   - 压缩归档（zip格式）
   - 保留期：应用日志7天，错误日志30天

## 已添加日志的模块

### 核心录制模块

#### `app/core/recording/app.py`
- 录制应用初始化
- 启动/停止流程
- 组件加载状态

#### `app/core/recording/supervisor.py`
- 调度器启动/停止
- 工作线程管理
- 房间事件处理

#### `app/core/recording/service.py`
- 房间配置加载
- 房间增删改查操作
- 房间启用/禁用

#### `app/services/recording_service.py`
- 录制开始/停止标记
- 数据库操作
- 录制失败记录

#### `app/runtime.py`
- 运行时启动/关闭
- 工作线程入口
- 旧版录制器集成

#### `app/main.py`
- FastAPI 应用启动/关闭

## 使用方法

### 1. 在新模块中使用

```python
from loguru import logger

# 记录信息
logger.info("开始处理任务")
logger.debug("调试信息: {}", data)
logger.warning("警告: 配置项缺失")
logger.error("错误: 文件不存在")
logger.exception("异常信息")  # 自动记录堆栈
```

### 2. 标准 logging 自动桥接

标准 logging 的输出会自动重定向到 loguru：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("这条日志会自动转到loguru")  # 自动转换
```

### 3. 配置调试模式

```python
from app.core.logging_config import setup_logging

setup_logging(
    log_level="DEBUG",      # 设置为DEBUG级别
    debug_mode=True,        # 启用调试模式
    enable_console=True,    # 启用控制台
    enable_file=True,       # 启用文件输出
)
```

## 日志示例

### 启动流程日志

```
2025-10-15 14:26:00.123 | INFO     | app.runtime:bootstrap_runtime:40 - 正在启动录制运行时
2025-10-15 14:26:00.125 | INFO     | app.core.recording.app:__init__:30 - 正在初始化录制应用
2025-10-15 14:26:00.126 | INFO     | app.core.recording.service:bootstrap:59 - 正在加载房间配置
2025-10-15 14:26:00.130 | INFO     | app.core.recording.service:bootstrap:64 - 已加载 5 个房间配置
2025-10-15 14:26:00.131 | INFO     | app.core.recording.supervisor:start:50 - 正在启动录制调度器
2025-10-15 14:26:00.132 | INFO     | app.core.recording.supervisor:start:58 - 启动时发现 3 个活跃房间
```

### 录制流程日志

```
2025-10-15 14:26:05.100 | INFO     | app.core.recording.supervisor:_ensure_worker:119 - 为房间启动新工作线程: douyin/user123 (https://live.douyin.com/123)
2025-10-15 14:26:05.102 | INFO     | app.runtime:_worker_entry:100 - 房间 douyin/user123 的录制工作线程已启动
2025-10-15 14:26:05.200 | INFO     | app.services.recording_service:mark_started:38 - 标记房间 1 开始录制
```

### 错误日志

```
2025-10-15 14:30:00.500 | ERROR    | app.runtime:_worker_entry:103 - 房间 douyin/user123 的录制工作线程失败
Traceback (most recent call last):
  File "/app/runtime.py", line 101, in _worker_entry
    recorder.record(room, stop_event=stop_event)
  ...
```

## 日志文件位置

```
DouyinLiveRecorder/
└── logs/
    ├── 2025-10-15/
    │   ├── app_2025-10-15.log       # 应用日志
    │   └── error_2025-10-15.log     # 错误日志
    └── 2025-10-14/
        ├── app_2025-10-14.log.zip   # 已压缩的旧日志
        └── error_2025-10-14.log.zip
```

## 最佳实践

1. **使用中文描述业务逻辑**
   ```python
   logger.info("开始录制直播间: {}", room_name)
   # 而不是: logger.info("Start recording room: {}", room_name)
   ```

2. **关键节点必须记录**
   - 服务启动/停止
   - 任务开始/结束
   - 状态变更
   - 错误发生

3. **使用合适的日志级别**
   - DEBUG: 开发调试信息
   - INFO: 业务流程节点
   - WARNING: 可恢复的异常情况
   - ERROR: 错误和异常

4. **结构化日志参数**
   ```python
   # 推荐
   logger.info("录制完成: 时长={}秒, 大小={}MB", duration, size)
   
   # 避免
   logger.info(f"录制完成: 时长={duration}秒, 大小={size}MB")
   ```

5. **异常处理**
   ```python
   try:
       process_recording()
   except Exception as e:
       logger.exception("录制处理失败")  # 自动记录堆栈
       raise
   ```

## 迁移指南

### 从旧版日志系统迁移

旧版使用 `app/legacy/logger.py` 的代码可以保持兼容，但建议逐步迁移：

```python
# 旧版
from app.legacy.logger import log_key_info, log_error
log_key_info("开始处理")
log_error("处理失败")

# 新版（推荐）
from loguru import logger
logger.info("开始处理")
logger.error("处理失败")
```

## 配置选项

可通过环境变量或配置文件调整日志行为：

- `LOG_LEVEL`: 日志级别（DEBUG/INFO/WARNING/ERROR）
- `LOG_DIR`: 日志文件目录
- `DEBUG_MODE`: 是否启用调试模式
- `CONSOLE_OUTPUT`: 是否启用控制台输出

## 性能考虑

- 使用异步队列（enqueue=True）避免阻塞
- 日志文件自动轮转和压缩
- 过滤第三方库的冗余日志

## 故障排查

1. **日志文件未生成**
   - 检查 logs 目录权限
   - 确认 setup_logging() 已调用

2. **日志级别不正确**
   - 检查 debug_mode 配置
   - 确认 log_level 参数

3. **第三方库日志过多**
   - 已自动抑制 urllib3、httpx、httpcore 等库的DEBUG日志
