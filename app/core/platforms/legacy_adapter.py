"""适配旧版 spider/stream 模块的通用平台处理器。"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.legacy import spider, stream
from app.legacy.utils import logger

from .base import PlatformHandler, StreamInfo


class LegacyPlatformHandler(PlatformHandler):
    """适配旧版录制逻辑的通用平台处理器。
    
    这个类作为过渡方案，将所有平台处理逻辑委托给现有的 spider 和 stream 模块。
    """
    
    def __init__(
        self,
        *,
        proxy_addr: Optional[str] = None,
        cookies_map: Optional[dict[str, str]] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
        global_proxy: bool = False,
        account_credentials: Optional[dict[str, dict]] = None,
    ):
        super().__init__(proxy_addr=proxy_addr, semaphore=semaphore)
        self.cookies_map = cookies_map or {}
        self.global_proxy = global_proxy
        self.account_credentials = account_credentials or {}
    
    @property
    def platform_name(self) -> str:
        return "通用平台"
    
    def can_handle(self, url: str) -> bool:
        """所有 URL 都可以处理（作为兜底）。"""
        return True
    
    async def get_stream_info(
        self,
        url: str,
        quality: str = "OD",
    ) -> StreamInfo | None:
        """调用旧版 spider/stream 获取直播流信息。"""
        try:
            port_info = await self._fetch_platform_stream(url, quality)
            
            if not port_info:
                return None
            
            # 解析返回的数据
            if isinstance(port_info, list) and len(port_info) >= 3:
                return StreamInfo(
                    real_url=port_info[0],
                    is_live=True,
                    anchor_name=port_info[1],
                    title=port_info[2] if len(port_info) > 2 else "",
                    quality=quality,
                    extra={"raw": port_info},
                )
            elif isinstance(port_info, dict):
                # 检查多种可能的 URL 字段
                real_url = (
                    port_info.get("record_url") or 
                    port_info.get("m3u8_url") or 
                    port_info.get("flv_url") or 
                    port_info.get("real_url") or 
                    ""
                )
                # 检查 is_live 字段或根据 URL 判断
                is_live = port_info.get("is_live", bool(real_url))
                
                return StreamInfo(
                    real_url=real_url,
                    is_live=is_live,
                    anchor_name=port_info.get("anchor_name", ""),
                    title=port_info.get("title", ""),
                    quality=quality,
                    extra=port_info,
                )
            
            return None
            
        except Exception as e:
            logger.error(f"获取流信息失败: {url}, 错误: {e}")
            return None
    
    async def _fetch_platform_stream(self, url: str, quality: str) -> list | dict | None:
        """根据 URL 判断平台并调用对应的获取方法。
        
        这个方法复用了 main.py 中的平台判断逻辑。
        """
        proxy = self.proxy_addr
        
        async with self.semaphore:
            # 抖音
            if "douyin.com/" in url:
                cookie = self.cookies_map.get("dy_cookie", "")
                if "v.douyin.com" not in url and "/user/" not in url:
                    json_data = await spider.get_douyin_stream_data(
                        url=url, proxy_addr=proxy, cookies=cookie
                    )
                else:
                    json_data = await spider.get_douyin_app_stream_data(
                        url=url, proxy_addr=proxy, cookies=cookie
                    )
                return await stream.get_douyin_stream_url(json_data, quality)
            
            # TikTok
            elif "tiktok.com/" in url:
                if not (self.global_proxy or proxy):
                    logger.error("TikTok 需要代理")
                    return None
                cookie = self.cookies_map.get("tiktok_cookie", "")
                json_data = await spider.get_tiktok_stream_data(
                    url=url, proxy_addr=proxy, cookies=cookie
                )
                return await stream.get_tiktok_stream_url(json_data, quality)
            
            # 快手
            elif "kuaishou.com/" in url:
                cookie = self.cookies_map.get("ks_cookie", "")
                json_data = await spider.get_kuaishou_stream_data(
                    url=url, proxy_addr=proxy, cookies=cookie
                )
                return await stream.get_kuaishou_stream_url(json_data, quality)
            
            # 虎牙
            elif "huya.com/" in url:
                cookie = self.cookies_map.get("hy_cookie", "")
                if quality not in ["OD", "BD", "UHD"]:
                    json_data = await spider.get_huya_stream_data(
                        url=url, proxy_addr=proxy, cookies=cookie
                    )
                    return await stream.get_huya_stream_url(json_data, quality)
                else:
                    return await spider.get_huya_app_stream_url(
                        url=url, proxy_addr=proxy, cookies=cookie
                    )
            
            # 斗鱼
            elif "douyu.com/" in url:
                cookie = self.cookies_map.get("douyu_cookie", "")
                json_data = await spider.get_douyu_info_data(
                    url=url, proxy_addr=proxy, cookies=cookie
                )
                return await stream.get_douyu_stream_url(
                    json_data, video_quality=quality, cookies=cookie, proxy_addr=proxy
                )
            
            # B站
            elif "bilibili.com/" in url:
                cookie = self.cookies_map.get("bili_cookie", "")
                json_data = await spider.get_bilibili_room_info(
                    url=url, proxy_addr=proxy, cookies=cookie
                )
                return await stream.get_bilibili_stream_url(
                    json_data, video_quality=quality, cookies=cookie, proxy_addr=proxy
                )
            
            # 小红书
            elif "xhslink.com/" in url or "xiaohongshu.com/" in url:
                cookie = self.cookies_map.get("xhs_cookie", "")
                return await spider.get_xhs_stream_url(url, proxy_addr=proxy, cookies=cookie)
            
            # 其他平台可以继续扩展...
            
        return None


__all__ = ["LegacyPlatformHandler"]
