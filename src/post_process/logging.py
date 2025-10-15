"""为后处理流程提供专用日志辅助。"""

from __future__ import annotations

from src.logger import (
    log_post_process_debug,
    log_post_process_error,
    log_post_process_key,
    logger,
)

__all__ = ["log_post_process", "logger"]


def log_post_process(message: str, level: str = "info") -> None:
    """将后处理日志转发到共享日志器的代理函数。"""

    normalized = level.lower()
    if normalized == "error":
        log_post_process_error(message)
    elif normalized == "debug":
        log_post_process_debug(message)
    else:
        log_post_process_key(message)
