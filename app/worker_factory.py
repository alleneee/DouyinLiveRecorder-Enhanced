"""原生录制工作器所需的配置辅助函数。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from app.core.config import settings
from app.core.platforms.legacy_adapter import LegacyPlatformHandler
from app.core.recording.continuous_worker import ContinuousConfig
from app.core.recording.segment_worker import SegmentConfig
from app.models.room import RoomORM
from app.recording.environment import RecordingEnvironment


_COOKIE_KEY_MAP: Dict[str, str] = {
    "抖音cookie": "dy_cookie",
    "快手cookie": "ks_cookie",
    "tiktok_cookie": "tiktok_cookie",
    "虎牙cookie": "hy_cookie",
    "斗鱼cookie": "douyu_cookie",
    "B站cookie": "bili_cookie",
    "小红书cookie": "xhs_cookie",
}


def build_platform_handler(env: RecordingEnvironment) -> LegacyPlatformHandler:
    """根据运行时环境创建平台处理器。"""

    proxy_addr = env.options.proxy_addr if env.options.use_proxy else None
    cookies_map = build_cookies_map(env)
    return LegacyPlatformHandler(
        proxy_addr=proxy_addr,
        cookies_map=cookies_map,
        global_proxy=bool(proxy_addr),
    )


def build_cookies_map(env: RecordingEnvironment) -> dict[str, str]:
    """构造 Cookie 映射，以供平台处理器使用。"""

    cookies: dict[str, str] = {}

    # 优先读取通用键
    for key, value in env.cookies.items():
        normalized = key.strip()
        if value:
            cookies[normalized] = value

    # 兼容旧版中文配置键
    for ini_key, alias in _COOKIE_KEY_MAP.items():
        value = env.parser.get("Cookie", ini_key, fallback="")
        if value:
            cookies[alias] = value

    return {key: value for key, value in cookies.items() if value}


def build_segment_config(*, env: RecordingEnvironment, room: RoomORM) -> SegmentConfig:
    """根据环境与房间配置生成分段录制参数。"""

    video_save_path = env.options.video_save_path
    return SegmentConfig(
        segment_duration=room.segment_duration,
        video_save_path=str(video_save_path if isinstance(video_save_path, Path) else Path(video_save_path)),
        video_save_type=(room.video_save_type or env.options.video_save_type).upper(),
        folder_by_author=env.options.folder_by_author,
        oss_enabled=settings.oss_enabled,  # 直接使用全局配置
        oss_access_key_id=settings.oss_access_key_id,
        oss_access_key_secret=settings.oss_access_key_secret,
        oss_endpoint=settings.oss_endpoint,
        oss_bucket_name=settings.oss_bucket_name,
    )


def build_continuous_config(*, env: RecordingEnvironment, room: RoomORM) -> ContinuousConfig:
    """根据环境与房间配置生成连续录制参数。"""

    video_save_path = env.options.video_save_path
    converts_to_mp4 = room.run_post_process or env.options.converts_to_mp4
    return ContinuousConfig(
        video_save_path=str(video_save_path if isinstance(video_save_path, Path) else Path(video_save_path)),
        video_save_type=(room.video_save_type or env.options.video_save_type).upper(),
        folder_by_author=env.options.folder_by_author,
        converts_to_mp4=converts_to_mp4,
        delete_origin_file=env.options.delete_origin_file,
    )


__all__ = [
    "build_platform_handler",
    "build_cookies_map",
    "build_segment_config",
    "build_continuous_config",
]
