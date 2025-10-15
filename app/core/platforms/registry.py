"""平台处理器注册表。"""

from __future__ import annotations

import threading
from typing import Optional

from .base import PlatformHandler


class PlatformRegistry:
    """平台处理器注册表（单例）。"""
    
    _instance: Optional[PlatformRegistry] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> PlatformRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._handlers: list[PlatformHandler] = []
        return cls._instance
    
    def register(self, handler: PlatformHandler) -> None:
        """注册平台处理器。"""
        if handler not in self._handlers:
            self._handlers.append(handler)
    
    def get_handler(self, url: str) -> PlatformHandler | None:
        """根据 URL 获取对应的平台处理器。"""
        for handler in self._handlers:
            if handler.can_handle(url):
                return handler
        return None
    
    def clear(self) -> None:
        """清空所有注册的处理器。"""
        self._handlers.clear()


def get_platform_handler(url: str) -> PlatformHandler | None:
    """便捷函数：获取平台处理器。"""
    registry = PlatformRegistry()
    return registry.get_handler(url)


__all__ = ["PlatformRegistry", "get_platform_handler"]
