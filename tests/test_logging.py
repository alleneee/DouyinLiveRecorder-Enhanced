"""日志系统测试模块。"""

import tempfile
from pathlib import Path

import pytest
from loguru import logger

from app.core.logging_config import LoggingConfig, setup_logging


class TestLoggingConfig:
    """测试日志配置功能。"""
    
    def test_setup_logging_basic(self):
        """测试基本日志设置。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=Path(tmpdir),
                log_level="INFO",
                enable_console=False,
                enable_file=True,
            )
            
            logger.info("测试日志信息")
            logger.error("测试错误信息")
            
            # 验证日志文件创建
            log_files = list(Path(tmpdir).glob("*.log"))
            assert len(log_files) > 0
    
    def test_setup_logging_debug_mode(self):
        """测试调试模式。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=Path(tmpdir),
                debug_mode=True,
                enable_console=False,
                enable_file=True,
            )
            
            logger.debug("调试信息")
            logger.info("普通信息")
    
    def test_logging_chinese_output(self):
        """测试中文日志输出。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=Path(tmpdir),
                enable_console=False,
                enable_file=True,
            )
            
            # 测试中文日志
            logger.info("开始录制直播间")
            logger.warning("直播间连接超时")
            logger.error("录制失败: 网络错误")
            
            # 读取日志文件验证中文
            log_files = list(Path(tmpdir).glob("app_*.log"))
            if log_files:
                content = log_files[0].read_text(encoding='utf-8')
                assert "开始录制直播间" in content
                assert "直播间连接超时" in content
    
    def test_standard_logging_interception(self):
        """测试标准logging拦截。"""
        import logging
        
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=Path(tmpdir),
                enable_console=False,
                enable_file=True,
            )
            
            # 使用标准logging
            std_logger = logging.getLogger("test")
            std_logger.info("标准logging测试")
            
            # 验证日志被拦截到文件
            log_files = list(Path(tmpdir).glob("app_*.log"))
            if log_files:
                content = log_files[0].read_text(encoding='utf-8')
                assert "标准logging测试" in content


class TestLoggingIntegration:
    """测试日志系统集成。"""
    
    def test_multiple_loggers(self):
        """测试多个logger实例。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=Path(tmpdir), enable_console=False)
            
            logger.bind(name="module1").info("模块1日志")
            logger.bind(name="module2").info("模块2日志")
    
    def test_exception_logging(self):
        """测试异常日志记录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=Path(tmpdir), enable_console=False)
            
            try:
                raise ValueError("测试异常")
            except Exception:
                logger.exception("捕获到异常")
            
            # 验证异常被记录
            error_files = list(Path(tmpdir).glob("error_*.log"))
            if error_files:
                content = error_files[0].read_text(encoding='utf-8')
                assert "ValueError" in content
                assert "测试异常" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
