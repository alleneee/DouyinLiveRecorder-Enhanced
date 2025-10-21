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

    # 平台URL模式映射 - 返回中文平台名称以匹配数据库存储
    PLATFORM_PATTERNS = {
        '抖音': [
            (r'live\.douyin\.com/(\d+)', '抖音'),
            (r'v\.douyin\.com/(\w+)', '抖音'),
        ],
        '快手': [
            (r'live\.kuaishou\.com/u/([^/\?]+)', '快手'),
        ],
        'B站': [
            (r'live\.bilibili\.com/(\d+)', 'B站'),
        ],
        '斗鱼': [
            (r'douyu\.com/([^/\?]+)', '斗鱼'),
        ],
        '虎牙': [
            (r'huya\.com/([^/\?]+)', '虎牙'),
        ],
        'YY': [
            (r'yy\.com/(\d+)', 'YY'),
        ],
        '小红书': [
            (r'xiaohongshu\.com/user/profile/(\w+)', '小红书'),
            (r'xhslink\.com/[^/]*?/(\w+)', '小红书'),  # 短链格式: xhslink.com/a/xxx
        ],
        'TikTok': [
            (r'tiktok\.com/@([^/\?]+)', 'TikTok'),
            (r'vm\.tiktok\.com/(\w+)', 'TikTok'),
        ],
        'Bigo': [
            (r'bigo\.tv/([^?\s]+)', 'Bigo'),  # 匹配完整路径,包含斜杠
            (r'slink\.bigovideo\.tv/(\w+)', 'Bigo'),
        ],
        'Blued': [
            (r'blued\.cn/live/(\w+)', 'Blued'),
        ],
        'AfreecaTV': [
            (r'play\.afreecatv\.com/([^/\?]+)', 'AfreecaTV'),
            (r'afreecatv\.com/([^/\?]+)', 'AfreecaTV'),
            (r'soop\.tv/([^/\?]+)', 'AfreecaTV'),  # 原AfreecaTV现SOOP
        ],
        '千度热播': [
            (r'qiandurebo\.com/web/video\.php\?roomnumber=(\d+)', '千度热播'),
        ],
        '网易CC': [
            (r'cc\.163\.com/([^/\?]+)', '网易CC'),
        ],
        'PandaTV': [
            (r'panda\.tv/([^/\?]+)', 'PandaTV'),
        ],
        '猫耳FM': [
            (r'fm\.missevan\.com/live/(\d+)', '猫耳FM'),
        ],
        'Look直播': [
            (r'look\.163\.com/live/room/(\d+)', 'Look直播'),
        ],
        'WinkTV': [
            (r'winktv\.co\.kr/live/play/(\w+)', 'WinkTV'),
        ],
        'FlexTV': [
            (r'flextv\.co\.kr/channels/(\d+)', 'FlexTV'),
            (r'ttinglive\.com/broadcast/(\w+)', 'FlexTV'),  # 原Flextv现TTingLive
        ],
        'PopkonTV': [
            (r'popkontv\.com/(\w+)', 'PopkonTV'),
        ],
        'TwitCasting': [
            (r'twitcasting\.tv/([^/\?]+)', 'TwitCasting'),
        ],
        '百度直播': [
            (r'live\.baidu\.com/(\w+)', '百度直播'),
        ],
        '微博直播': [
            (r'weibo\.com/l/wblive/p/show/(\w+)', '微博直播'),
        ],
        '酷狗直播': [
            (r'fanxing\.kugou\.com/(\d+)', '酷狗直播'),
        ],
        'TwitchTV': [
            (r'twitch\.tv/([^/\?]+)', 'TwitchTV'),
        ],
        'LiveMe': [
            (r'liveme\.com/live\.html\?videoid=(\w+)', 'LiveMe'),
        ],
        '花椒直播': [
            (r'huajiao\.com/l/(\d+)', '花椒直播'),
        ],
        '流星直播': [
            (r'liuxing\.com/(\w+)', '流星直播'),
        ],
        'ShowRoom': [
            (r'showroom-live\.com/r/(\w+)', 'ShowRoom'),
        ],
        'Acfun': [
            (r'live\.acfun\.cn/live/(\d+)', 'Acfun'),
        ],
        '映客直播': [
            (r'inke\.cn/live\.html\?uid=(\d+)', '映客直播'),
        ],
        '知乎直播': [
            (r'zhihu\.com/theater/(\d+)', '知乎直播'),
        ],
        'CHZZK': [
            (r'chzzk\.naver\.com/live/(\w+)', 'CHZZK'),
        ],
        '17Live': [
            (r'17\.live/live/(\d+)', '17Live'),
        ],
        '六间房': [
            (r'6\.cn/show/(\w+)', '六间房'),
        ],
        'Shopee': [
            (r'shopee\..*?/live/(\w+)', 'Shopee'),
        ],
        'YouTube': [
            (r'youtube\.com/watch\?v=([^&\?]+)', 'YouTube'),
            (r'youtu\.be/([^/\?]+)', 'YouTube'),
            (r'youtube\.com/live/([^/\?]+)', 'YouTube'),
        ],
        '淘宝直播': [
            (r'taobao\.com.*?liveId=(\d+)', '淘宝直播'),
        ],
        '京东直播': [
            (r'jd\.com.*?id=(\d+)', '京东直播'),
        ],
        'Faceit': [
            (r'faceit\.com/.*?/room/([^/\?]+)', 'Faceit'),
        ],
        'Picarto': [
            (r'picarto\.tv/([^/\?]+)', 'Picarto'),
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
            - platform: 平台中文名称(如: 抖音, B站, 快手等)
            - room_id: 平台房间ID

        Examples:
            >>> parse_url('https://live.douyin.com/745964462470')
            ('抖音', '745964462470')

            >>> parse_url('https://live.bilibili.com/21852')
            ('B站', '21852')
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
