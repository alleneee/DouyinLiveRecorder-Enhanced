"""平台处理器基类和数据模型。"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class StreamInfo:
    """直播流信息。"""
    
    real_url: str
    """实际播放地址"""
    
    is_live: bool = False
    """是否正在直播"""
    
    anchor_name: str = ""
    """主播名称"""
    
    title: str = ""
    """直播间标题"""
    
    quality: str = ""
    """画质"""
    
    extra: dict[str, Any] | None = None
    """额外信息"""


class PlatformHandler(ABC):
    """平台处理器抽象基类。"""
    
    def __init__(
        self,
        *,
        proxy_addr: Optional[str] = None,
        cookies: Optional[str] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ):
        self.proxy_addr = proxy_addr
        self.cookies = cookies
        self.semaphore = semaphore or asyncio.Semaphore(10)
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称。"""
        pass
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断是否可以处理该 URL。"""
        pass
    
    @abstractmethod
    async def get_stream_info(
        self,
        url: str,
        quality: str = "OD",
    ) -> StreamInfo | None:
        """获取直播流信息。
        
        Args:
            url: 直播间 URL
            quality: 画质代码 (OD/BD/UHD/HD/SD/LD)
        
        Returns:
            StreamInfo 或 None（如果未开播或获取失败）
        """
        pass


__all__ = ["PlatformHandler", "StreamInfo"]
