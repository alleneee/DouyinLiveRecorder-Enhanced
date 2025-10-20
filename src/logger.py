# -*- coding: utf-8 -*-

import os
import sys
from loguru import logger

logger.remove()

custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> - <level>{message}</level>"

logger.add(
    sink=sys.stderr,
    format=custom_format,
    level="INFO",  # 控制台输出INFO及以上级别
    colorize=True,
    enqueue=True
)

script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]

# 统一的日志文件,包含所有级别的日志,便于完整链路追踪
logger.add(
    f"{script_path}/logs/recorder.log",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
    serialize=False,
    enqueue=True,
    retention=7,  # 保留7天
    rotation="10 MB",  # 每10MB轮转一次
    encoding='utf-8'
)
