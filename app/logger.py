"""FastAPI应用日志配置
适用于uvicorn运行环境的日志系统
支持supervisor和直接运行两种模式
"""
import sys
import os
from pathlib import Path
from loguru import logger

# 移除默认handler
logger.remove()

# 获取项目根目录(app的父目录)
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

# 确保日志目录存在
LOGS_DIR.mkdir(exist_ok=True)

# 控制台输出格式
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<level>{message}</level>"
)

# 文件输出格式
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{message}"
)

# 检测是否在supervisor环境下运行
# supervisor会设置SUPERVISOR_ENABLED环境变量,或者检查进程名
IS_SUPERVISOR = os.getenv("SUPERVISOR_ENABLED", "false").lower() == "true"

# 1. 控制台输出 - 仅在非supervisor环境下启用
# supervisor会捕获stdout/stderr,所以不需要重复输出
if not IS_SUPERVISOR:
    logger.add(
        sink=sys.stderr,
        format=CONSOLE_FORMAT,
        level="INFO",
        colorize=True,
        enqueue=True
    )

# 2. 统一日志文件 - 完整链路追踪
logger.add(
    sink=str(LOGS_DIR / "recorder.log"),
    format=FILE_FORMAT,
    level="INFO",
    rotation="10 MB",  # 每10MB轮转
    retention="7 days",  # 保留7天
    encoding="utf-8",
    enqueue=True,
    backtrace=True,  # 记录异常堆栈
    diagnose=True    # 记录详细诊断信息
)

# 3. 错误日志文件 - 单独记录错误便于快速排查
logger.add(
    sink=str(LOGS_DIR / "error.log"),
    format=FILE_FORMAT,
    level="ERROR",
    rotation="5 MB",
    retention="30 days",  # 错误日志保留更长时间
    encoding="utf-8",
    enqueue=True,
    backtrace=True,
    diagnose=True
)

# 导出配置好的logger
__all__ = ["logger"]
