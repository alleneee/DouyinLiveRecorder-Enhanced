#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
URL解析工具

提取直播间URL中的平台和房间ID信息
"""

from typing import Optional, Tuple
from urllib.parse import urlparse
import re


class URLParser:
    """URL解析器 - 提取平台和房间ID"""

    # 平台URL模式映射
    PLATFORM_PATTERNS = {
        '抖音': [
            (r'live\.douyin\.com/(\d+)', 'douyin'),
            (r'v\.douyin\.com/(\w+)', 'douyin'),
        ],
        '快手': [
            (r'live\.kuaishou\.com/u/([^/\?]+)', 'kuaishou'),
        ],
        'B站': [
            (r'live\.bilibili\.com/(\d+)', 'bilibili'),
        ],
        '斗鱼': [
            (r'douyu\.com/([^/\?]+)', 'douyu'),
        ],
        '虎牙': [
            (r'huya\.com/([^/\?]+)', 'huya'),
        ],
        'YY': [
            (r'yy\.com/(\d+)', 'yy'),
        ],
        '小红书': [
            (r'xiaohongshu\.com/user/profile/(\w+)', 'xiaohongshu'),
            (r'xhslink\.com/(\w+)', 'xiaohongshu'),
        ],
        'TikTok': [
            (r'tiktok\.com/@([^/\?]+)', 'tiktok'),
        ],
        'Bigo': [
            (r'bigo\.tv/([^/\?]+)', 'bigo'),
            (r'slink\.bigovideo\.tv/(\w+)', 'bigo'),
        ],
    }

    @classmethod
    def parse_url(cls, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析直播间URL,提取平台和房间ID

        Args:
            url: 直播间URL

        Returns:
            (platform, room_id) 元组
            - platform: 平台名称(如: douyin, bilibili, kuaishou等)
            - room_id: 平台房间ID

        Examples:
            >>> parse_url('https://live.douyin.com/745964462470')
            ('douyin', '745964462470')

            >>> parse_url('https://live.bilibili.com/21852')
            ('bilibili', '21852')
        """
        if not url:
            return None, None

        # 遍历所有平台模式
        for platform_name, patterns in cls.PLATFORM_PATTERNS.items():
            for pattern, platform_key in patterns:
                match = re.search(pattern, url)
                if match:
                    room_id = match.group(1)
                    return platform_key, room_id

        return None, None

    @classmethod
    def extract_platform_from_url(cls, url: str) -> Optional[str]:
        """
        仅提取平台名称

        Args:
            url: 直播间URL

        Returns:
            平台名称或None
        """
        platform, _ = cls.parse_url(url)
        return platform

    @classmethod
    def extract_room_id_from_url(cls, url: str) -> Optional[str]:
        """
        仅提取房间ID

        Args:
            url: 直播间URL

        Returns:
            房间ID或None
        """
        _, room_id = cls.parse_url(url)
        return room_id

    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """
        检查URL是否为有效的直播间URL

        Args:
            url: 待检查的URL

        Returns:
            是否为有效的直播间URL
        """
        platform, room_id = cls.parse_url(url)
        return platform is not None and room_id is not None


# 便捷函数
def parse_live_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    解析直播间URL的便捷函数

    Args:
        url: 直播间URL

    Returns:
        (platform, room_id) 元组
    """
    return URLParser.parse_url(url)
