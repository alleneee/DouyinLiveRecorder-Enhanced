"""服务模块"""
from app.services.recording_manager import recording_manager
from app.services.oss_uploader import oss_uploader

__all__ = ["recording_manager", "oss_uploader"]
