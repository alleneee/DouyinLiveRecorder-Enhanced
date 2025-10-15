"""适配旧版 `main.start_record` 的包装器。"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.recording.environment import RecordingEnvironment
from app.core.recording.context import RecordingContext
from app.core.recording.models import Room


@dataclass(slots=True)
class LegacyRecorder:
    env: RecordingEnvironment
    context: RecordingContext

    def __post_init__(self) -> None:
        # 注意：旧版 main.py 已被删除，不再需要配置全局变量
        # 新架构直接使用 RecordingWorker
        pass


    def record(self, room: Room, *, stop_event: threading.Event | None = None) -> None:
        """使用新的模块化组件进行录制。"""
        try:
            # 尝试使用新的录制工作器
            from app.core.platforms.legacy_adapter import LegacyPlatformHandler
            from app.core.recording.worker import RecordingWorker, RecordingConfig
            
            # 创建平台处理器
            handler = LegacyPlatformHandler(
                proxy_addr=self.env.options.proxy_addr if self.env.options.use_proxy else None,
                cookies_map=self._build_cookies_map(),
                global_proxy=bool(self.env.options.proxy_addr),
            )
            
            # 创建录制配置
            config = RecordingConfig(
                video_save_path=str(self.env.options.video_save_path),
                video_save_type=self.env.options.video_save_type,
                loop_interval=self.env.options.loop_interval,
                split_time=self.env.options.split_time,
                split_video_by_time=self.env.options.split_video_by_time,
                enable_https=self.env.options.enable_https_recording,
                converts_to_mp4=self.env.options.converts_to_mp4,
                delete_origin_file=self.env.options.delete_origin_file,
                folder_by_author=self.env.options.folder_by_author,
                folder_by_time=self.env.options.folder_by_time,
                clean_emoji=self.env.options.clean_emoji,
            )
            
            # 创建工作器并运行
            worker = RecordingWorker(
                room=room,
                platform_handler=handler,
                config=config,
                stop_event=stop_event,
            )
            
            # 运行异步录制循环
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(worker.run())
            finally:
                loop.close()
                
        except Exception as e:
            # 如果新架构失败，记录错误
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"录制失败: {e}", exc_info=True)
            raise
    
    def _build_cookies_map(self) -> dict[str, str]:
        """构建 Cookie 映射。"""
        parser = self.env.parser
        cookies = {}
        
        if not parser.has_section("Cookie"):
            return cookies
        
        cookie_keys = {
            "抖音cookie": "dy_cookie",
            "快手cookie": "ks_cookie",
            "tiktok_cookie": "tiktok_cookie",
            "虎牙cookie": "hy_cookie",
            "斗鱼cookie": "douyu_cookie",
            "B站cookie": "bili_cookie",
            "小红书cookie": "xhs_cookie",
        }
        
        for ini_key, map_key in cookie_keys.items():
            value = parser.get("Cookie", ini_key, fallback="")
            if value:
                cookies[map_key] = value
        
        return cookies


__all__ = ["LegacyRecorder"]
