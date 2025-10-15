# -*- coding: utf-8 -*-

import os
import sys
import configparser
from datetime import datetime
from pathlib import Path
from loguru import logger
from typing import Optional


class LoggerManager:
    """统一日志管理器 - 简化的Loguru配置和使用接口"""

    def __init__(self, config_file: Optional[str] = None):
        self.script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
        self.config = self._load_config(config_file)
        self._setup_logger()

    def _load_config(self, config_file: Optional[str]) -> dict:
        """加载日志配置"""
        default_config = {
            'retention_days': 7,
            'max_file_size': '10 MB',
            'debug_mode': False,  # 新增debug模式配置
            'file_format': '{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}'
        }

        if config_file and os.path.exists(config_file):
            try:
                config = configparser.ConfigParser()
                config.read(config_file, encoding='utf-8-sig')
                if config.has_section('日志设置'):
                    section = config['日志设置']
                    # 安全地获取布尔值
                    debug_mode_str = section.get('debug模式', '否')
                    debug_mode = debug_mode_str.lower() in ['是', 'true', '1', 'yes']

                    default_config.update({
                        'retention_days': section.getint('日志保留天数', 7),
                        'max_file_size': section.get('最大文件大小', '10 MB'),
                        'debug_mode': debug_mode
                    })
            except Exception as e:
                print(f"加载日志配置失败，使用默认配置: {e}")

        return default_config

    def _get_log_dir(self):
        """获取当前日期的日志目录"""
        current_date = datetime.now().strftime('%Y-%m-%d')
        log_dir = os.path.join(self.script_path, 'logs', current_date)
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def _setup_logger(self):
        """设置日志器 - 极简配置，只保留app.log"""
        # 移除默认处理器
        logger.remove()

        log_dir = self._get_log_dir()

        # 控制台输出 - 只用于关键错误信息
        logger.add(
            sys.stderr,
            level="ERROR",  # 控制台只显示错误
            format="<red>[ERROR]</red> {message}",
            colorize=True,
            enqueue=True
        )

        # 根据debug模式决定日志级别
        log_level = "DEBUG" if self.config.get('debug_mode', False) else "INFO"

        # 唯一的应用日志文件 - 包含所有后处理日志
        logger.add(
            os.path.join(log_dir, "app.log"),
            level=log_level,
            format=self.config['file_format'],
            rotation="1 day",  # 按天轮转
            retention=f"{self.config['retention_days']} days",
            encoding='utf-8',
            enqueue=True,
            filter=lambda record: record["level"].name in (["INFO", "ERROR", "DEBUG"] if self.config.get('debug_mode', False) else ["INFO", "ERROR"])
        )

    def is_debug_mode(self):
        """检查是否为debug模式"""
        return self.config.get('debug_mode', False)


# 创建全局日志管理器实例
script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
config_file = os.path.join(script_path, 'config', 'config.ini')
_logger_manager = LoggerManager(config_file)

# 简化的日志接口 - 只记录关键信息到app.log
def log_key_info(message: str):
    """记录关键信息到app.log"""
    logger.info(message)

def log_error(message: str):
    """记录错误信息到app.log，同时显示在控制台"""
    logger.error(message)

def log_post_process_key(message: str):
    """记录后处理关键节点信息到app.log"""
    logger.info(f"[后处理] {message}")

def log_post_process_error(message: str):
    """记录后处理错误信息到app.log"""
    logger.error(f"[后处理] {message}")

def log_post_process_debug(message: str):
    """记录后处理详细信息（仅在debug模式下）"""
    logger.debug(f"[后处理] {message}")

def log_post_process(message: str, level: str = "info"):
    """兼容性函数 - 后处理日志记录"""
    if level.lower() == "error":
        log_post_process_error(message)
    elif level.lower() == "debug":
        log_post_process_debug(message)
    else:
        log_post_process_key(message)

# 控制台输出函数 - 不记录到日志文件
def console_print(message: str, level: str = "info"):
    """控制台输出，不记录到日志文件"""
    if level.lower() == "error":
        print(f"[ERROR] {message}")
    elif level.lower() == "warning":
        print(f"[WARNING] {message}")
    elif level.lower() == "status":
        print(f"[STATUS] {message}")
    else:
        print(message)

def console_status(message: str):
    """控制台状态信息输出 - 用于实时监控显示"""
    print(message)

def console_error(message: str):
    """控制台错误信息输出"""
    print(f"[ERROR] {message}")

def console_warning(message: str):
    """控制台警告信息输出"""
    print(f"[WARNING] {message}")

# 自动异常捕获装饰器
def catch_exceptions(func):
    """自动捕获异常的装饰器"""
    return logger.catch(func)

# 兼容性接口 - 保持向后兼容
status_logger = logger
post_process_logger = logger


# 兼容性函数 - 保持向后兼容
def log_info(message: str):
    """兼容性函数 - 建议使用 log_key_info 或 console_print"""
    log_key_info(message)

def log_warning(message: str):
    """兼容性函数 - 建议使用 console_warning"""
    console_warning(message)

def log_debug(message: str):
    """兼容性函数 - 调试信息不再记录到文件"""
    console_print(f"[DEBUG] {message}")

def log_status(message: str):
    """兼容性函数 - 建议使用 console_status"""
    console_status(message)

# 导出主要函数
__all__ = [
    'logger', 'log_key_info', 'log_error',
    'log_post_process', 'log_post_process_key', 'log_post_process_error', 'log_post_process_debug',
    'console_print', 'console_status', 'console_error', 'console_warning',
    'log_info', 'log_warning', 'log_debug', 'log_status',  # 兼容性函数
    'catch_exceptions', 'status_logger', 'post_process_logger', '_logger_manager'
]
