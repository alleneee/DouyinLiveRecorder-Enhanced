# 日志体系重构更新日志

## 版本: v2.0 (2025-10-15)

### 重大变更

#### ✨ 新增功能

1. **统一日志配置模块** (`app/core/logging_config.py`)
   - 整合 loguru 和标准 logging
   - 自动拦截标准 logging 到 loguru
   - 支持控制台和文件双输出
   - 智能日志轮转和压缩

2. **全中文日志输出**
   - 所有业务日志使用中文描述
   - 提升可读性和调试效率
   - 统一日志格式和风格

3. **完善的日志覆盖**
   - 核心录制模块全覆盖
   - 数据库操作日志
   - 启动/停止流程日志
   - 错误和异常日志

#### 📝 修改的文件

**新增文件：**
- `app/core/logging_config.py` - 统一日志配置模块
- `docs/logging_system.md` - 日志系统文档
- `docs/logging_changelog.md` - 更新日志

**修改文件：**
- `app/runtime.py` - 添加日志初始化和中文日志
- `app/main.py` - 应用启动/关闭日志中文化
- `app/core/recording/app.py` - 录制应用生命周期日志
- `app/core/recording/supervisor.py` - 调度器和工作线程日志
- `app/core/recording/service.py` - 房间管理服务日志
- `app/services/recording_service.py` - 录制服务数据库操作日志

#### 🔧 配置变更

**日志文件结构：**
```
logs/
└── YYYY-MM-DD/
    ├── app_YYYY-MM-DD.log        # 应用日志（新）
    └── error_YYYY-MM-DD.log      # 错误日志（新）
```

**保留策略：**
- 应用日志：7天
- 错误日志：30天
- 自动压缩为 .zip 格式

#### 📊 日志级别覆盖

| 模块 | DEBUG | INFO | WARNING | ERROR |
|------|-------|------|---------|-------|
| runtime | ✓ | ✓ | ✓ | ✓ |
| recording.app | ✓ | ✓ | - | ✓ |
| recording.supervisor | ✓ | ✓ | ✓ | ✓ |
| recording.service | ✓ | ✓ | ✓ | ✓ |
| recording_service | ✓ | ✓ | - | ✓ |

### 兼容性

#### ✅ 向后兼容

- 旧版 `app/legacy/logger.py` 继续可用
- 现有日志调用无需修改
- 标准 logging 自动桥接

#### ⚠️ 废弃警告

以下函数建议迁移到新系统：
- `log_key_info()` → `logger.info()`
- `log_error()` → `logger.error()`
- `log_debug()` → `logger.debug()`

### 性能优化

1. **异步日志队列**
   - 所有日志使用 `enqueue=True`
   - 避免阻塞主线程

2. **智能过滤**
   - 抑制第三方库冗余日志
   - urllib3、httpx、httpcore 设置为 WARNING 级别

3. **自动压缩**
   - 旧日志文件自动 zip 压缩
   - 节省磁盘空间

### 使用示例

#### 基本用法

```python
from loguru import logger

# 信息日志
logger.info("开始录制直播间: {}", room_name)

# 调试日志
logger.debug("获取到流地址: {}", stream_url)

# 警告日志
logger.warning("直播间 {} 连接超时，重试中", room_id)

# 错误日志
logger.error("录制失败: {}", error_message)

# 异常日志（自动记录堆栈）
try:
    process_video()
except Exception:
    logger.exception("视频处理异常")
```

#### 配置调试模式

```python
from app.core.logging_config import setup_logging

setup_logging(
    log_level="DEBUG",
    debug_mode=True,
    enable_console=True,
    enable_file=True,
)
```

### 迁移指南

#### 步骤 1: 导入新 logger

```python
# 旧版
from app.legacy.logger import log_key_info, log_error

# 新版
from loguru import logger
```

#### 步骤 2: 替换函数调用

```python
# 旧版
log_key_info("开始处理任务")
log_error("处理失败")

# 新版
logger.info("开始处理任务")
logger.error("处理失败")
```

#### 步骤 3: 使用结构化参数

```python
# 旧版
log_key_info(f"录制完成: {filename}")

# 新版
logger.info("录制完成: {}", filename)
```

### 已知问题

暂无

### 下一步计划

1. 为更多模块补充日志
   - API 路由层
   - 平台适配器
   - 后处理模块
   - 消息推送模块

2. 添加日志分析工具
   - 日志统计脚本
   - 错误告警机制

3. 性能监控日志
   - 录制性能指标
   - 资源使用情况

### 贡献者

- 日志系统重构: Cascade AI Assistant
- 文档编写: Cascade AI Assistant

---

**发布日期**: 2025-10-15  
**版本**: v2.0  
**标签**: logging, refactor, chinese-logs
