"""平台处理器抽象层。"""

from .base import PlatformHandler, StreamInfo
from .registry import PlatformRegistry, get_platform_handler

__all__ = ["PlatformHandler", "StreamInfo", "PlatformRegistry", "get_platform_handler"]
