"""统一的日志配置模块 - 整合loguru和标准logging。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


class LoggingConfig:
    """统一日志配置管理器。"""
    
    _initialized = False
    
    @classmethod
    def setup(
        cls,
        *,
        log_dir: Optional[Path] = None,
        log_level: str = "INFO",
        enable_console: bool = True,
        enable_file: bool = True,
        debug_mode: bool = False,
    ) -> None:
        """配置全局日志系统。
        
        Args:
            log_dir: 日志文件目录，None则使用默认位置
            log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
            enable_console: 是否启用控制台输出
            enable_file: 是否启用文件输出
            debug_mode: 是否启用调试模式
        """
        if cls._initialized:
            logger.warning("日志系统已初始化，跳过重复配置")
            return
        
        # 移除loguru默认处理器
        logger.remove()
        
        # 确定日志级别
        level = "DEBUG" if debug_mode else log_level
        
        # 配置控制台输出
        if enable_console:
            logger.add(
                sys.stderr,
                level=level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                       "<level>{level: <8}</level> | "
                       "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                       "<level>{message}</level>",
                colorize=True,
                enqueue=True,
            )
        
        # 配置文件输出
        if enable_file:
            if log_dir is None:
                log_dir = Path(__file__).resolve().parents[2] / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 应用日志
            logger.add(
                log_dir / "app_{time:YYYY-MM-DD}.log",
                level=level,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="00:00",
                retention="7 days",
                compression="zip",
                encoding="utf-8",
                enqueue=True,
            )
            
            # 错误日志（单独文件）
            logger.add(
                log_dir / "error_{time:YYYY-MM-DD}.log",
                level="ERROR",
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="00:00",
                retention="30 days",
                compression="zip",
                encoding="utf-8",
                enqueue=True,
            )
        
        # 配置标准logging到loguru的拦截
        cls._intercept_standard_logging()
        
        cls._initialized = True
        logger.info("日志系统初始化完成，级别={}", level)
    
    @staticmethod
    def _intercept_standard_logging() -> None:
        """拦截标准logging输出到loguru。"""
        
        class InterceptHandler(logging.Handler):
            """将标准logging重定向到loguru的处理器。"""
            
            def emit(self, record: logging.LogRecord) -> None:
                # 获取对应的loguru级别
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno
                
                # 查找调用者
                frame, depth = logging.currentframe(), 2
                while frame and frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1
                
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, record.getMessage()
                )
        
        # 配置根logger
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
        
        # 抑制一些过于啰嗦的第三方库日志
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logger:
        """获取logger实例（兼容性方法）。
        
        Args:
            name: logger名称，None则使用调用者模块
            
        Returns:
            loguru logger实例
        """
        if not cls._initialized:
            cls.setup()
        
        if name:
            return logger.bind(name=name)
        return logger


# 便捷函数
def setup_logging(**kwargs) -> None:
    """设置日志系统的便捷函数。"""
    LoggingConfig.setup(**kwargs)


def get_logger(name: Optional[str] = None):
    """获取logger的便捷函数。"""
    return LoggingConfig.get_logger(name)


__all__ = ["LoggingConfig", "setup_logging", "get_logger", "logger"]
