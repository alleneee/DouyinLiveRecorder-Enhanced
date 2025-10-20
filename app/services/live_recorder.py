"""直播录制工具类 - 封装main.py的录制逻辑供API系统复用

采用策略模式设计，每个平台都是独立的处理策略，符合开闭原则。
"""
import asyncio
import sys
import os
from typing import Dict, Optional, List
from abc import ABC, abstractmethod

# 将src添加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src import spider, stream
from src.utils import logger


class PlatformStrategy(ABC):
    """平台处理策略基类（策略模式）
    
    每个平台实现自己的处理逻辑，保持单一职责。
    """
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称"""
        pass
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断是否能处理该URL"""
        pass
    
    @abstractmethod
    async def get_stream_info(self, url: str, quality: str, proxy_addr: Optional[str], cookies: Dict) -> Dict:
        """获取直播流信息
        
        Returns:
            {
                'is_live': bool,
                'platform': str,
                'stream_url': str,
                'anchor_name': str,
                'title': str
            }
        """
        pass
    
    def _get_quality_code(self, quality_zh: str) -> str:
        """将中文画质转换为代码（通用方法）"""
        quality_map = {
            '原画': 'OD',
            '蓝光': 'BD',
            '超清': 'UHD',
            '高清': 'HD',
            '标清': 'SD',
            '流畅': 'LD'
        }
        return quality_map.get(quality_zh, 'OD')
    
    def _create_empty_result(self) -> Dict:
        """创建空结果（默认值）"""
        return {
            'is_live': False,
            'platform': self.platform_name,
            'stream_url': '',
            'anchor_name': '',
            'title': ''
        }


class DouyinStrategy(PlatformStrategy):
    """抖音平台处理策略"""
    
    @property
    def platform_name(self) -> str:
        return '抖音'
    
    def can_handle(self, url: str) -> bool:
        return 'douyin.com/' in url
    
    async def get_stream_info(self, url: str, quality: str, proxy_addr: Optional[str], cookies: Dict) -> Dict:
        result = self._create_empty_result()

        # 根据URL类型选择不同的spider函数
        if 'v.douyin.com' not in url and '/user/' not in url:
            json_data = await spider.get_douyin_stream_data(
                url=url,
                proxy_addr=proxy_addr,
                cookies=cookies.get('douyin')
            )
        else:
            json_data = await spider.get_douyin_app_stream_data(
                url=url,
                proxy_addr=proxy_addr,
                cookies=cookies.get('douyin')
            )

        # 抖音使用 status 字段判断直播状态
        # status: 2 = 正在直播, 4 = 未开播
        status = json_data.get('status', 4)
        result['is_live'] = (status == 2)
        result['anchor_name'] = json_data.get('anchor_name', '')
        result['title'] = json_data.get('title', '')

        if result['is_live']:
            quality_code = self._get_quality_code(quality)
            port_info = await stream.get_douyin_stream_url(
                json_data, quality_code, proxy_addr
            )
            result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')

        return result


class HuyaStrategy(PlatformStrategy):
    """虎牙平台处理策略"""
    
    @property
    def platform_name(self) -> str:
        return '虎牙'
    
    def can_handle(self, url: str) -> bool:
        return 'huya.com/' in url
    
    async def get_stream_info(self, url: str, quality: str, proxy_addr: Optional[str], cookies: Dict) -> Dict:
        result = self._create_empty_result()
        quality_code = self._get_quality_code(quality)
        
        # 根据画质选择不同的API
        if quality_code not in ['OD', 'BD', 'UHD']:
            json_data = await spider.get_huya_stream_data(
                url=url,
                proxy_addr=proxy_addr,
                cookies=cookies.get('huya')
            )
            port_info = await stream.get_huya_stream_url(json_data, quality_code)
        else:
            port_info = await spider.get_huya_app_stream_url(
                url=url,
                proxy_addr=proxy_addr,
                cookies=cookies.get('huya')
            )
        
        result['is_live'] = port_info.get('is_live', False)
        result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
        
        return result


class StandardPlatformStrategy(PlatformStrategy):
    """标准平台处理策略（适用于大多数平台）
    
    通过配置化的方式处理标准流程的平台。
    """
    
    def __init__(self, name: str, domain: str, spider_func, stream_func=None, use_quality=True):
        self._name = name
        self._domain = domain
        self._spider_func = spider_func
        self._stream_func = stream_func
        self._use_quality = use_quality
    
    @property
    def platform_name(self) -> str:
        return self._name
    
    def can_handle(self, url: str) -> bool:
        return self._domain in url
    
    async def get_stream_info(self, url: str, quality: str, proxy_addr: Optional[str], cookies: Dict) -> Dict:
        result = self._create_empty_result()
        
        # 获取平台数据
        json_data = await self._spider_func(
            url=url,
            proxy_addr=proxy_addr,
            cookies=cookies.get(self._name.lower())
        )
        
        # 提取基础信息
        result['is_live'] = json_data.get('is_live', False)
        result['anchor_name'] = json_data.get('anchor_name', '')
        result['title'] = json_data.get('title', '')
        
        # 如果正在直播且有stream函数，获取流地址
        if result['is_live'] and self._stream_func:
            quality_code = self._get_quality_code(quality) if self._use_quality else None
            
            if self._use_quality:
                port_info = await self._stream_func(
                    json_data, quality_code, proxy_addr
                )
            else:
                port_info = json_data
                
            result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
        elif result['is_live'] and not self._stream_func:
            # spider函数直接返回流地址的情况
            result['stream_url'] = json_data.get('flv_url') or json_data.get('m3u8_url', '')
        
        return result


class PlatformStrategyFactory:
    """平台策略工厂（工厂模式）
    
    负责创建和管理所有平台策略实例。
    """
    
    def __init__(self):
        self._strategies: List[PlatformStrategy] = []
        self._register_all_strategies()
    
    def _register_all_strategies(self):
        """注册所有平台策略"""
        # 特殊平台策略
        self._strategies.append(DouyinStrategy())
        self._strategies.append(HuyaStrategy())
        
        # 标准平台策略
        self._strategies.extend([
            StandardPlatformStrategy('TikTok', 'tiktok.com/', spider.get_tiktok_stream_data, stream.get_tiktok_stream_url),
            StandardPlatformStrategy('快手', 'kuaishou.com/', spider.get_kuaishou_stream_data, stream.get_kuaishou_stream_url),
            StandardPlatformStrategy('B站', 'bilibili.com/', spider.get_bilibili_room_info, stream.get_bilibili_stream_url),
            StandardPlatformStrategy('斗鱼', 'douyu.com/', spider.get_douyu_info_data, stream.get_douyu_stream_url),
            StandardPlatformStrategy('YY', 'yy.com/', spider.get_yy_stream_data, stream.get_yy_stream_url),
            StandardPlatformStrategy('小红书', 'xiaohongshu.com/', spider.get_xhs_stream_url, None, use_quality=False),
            StandardPlatformStrategy('小红书', 'xhslink.com/', spider.get_xhs_stream_url, None, use_quality=False),
            StandardPlatformStrategy('Bigo', 'bigo.tv/', spider.get_bigo_stream_url, None, use_quality=False),
            StandardPlatformStrategy('Bigo', 'slink.bigovideo.tv/', spider.get_bigo_stream_url, None, use_quality=False),
        ])
    
    def get_strategy(self, url: str) -> Optional[PlatformStrategy]:
        """根据URL获取对应的平台策略
        
        Args:
            url: 直播间URL
            
        Returns:
            匹配的平台策略，如果没有匹配则返回None
        """
        for strategy in self._strategies:
            if strategy.can_handle(url):
                return strategy
        return None
    

class LiveRecorder:
    """直播录制器 - 使用策略模式处理多平台
    
    通过策略工厂获取对应平台的处理策略，符合SOLID原则。
    """
    
    def __init__(self, proxy_addr: Optional[str] = None, cookies: Optional[Dict] = None):
        self.proxy_addr = proxy_addr
        self.cookies = cookies or {}
        self._strategy_factory = PlatformStrategyFactory()
    
    
    async def get_live_stream_info(self, url: str, quality: str = "原画") -> Dict:
        """获取直播流信息（策略模式）
        
        使用策略工厂自动选择对应平台的处理策略。
        
        Args:
            url: 直播间URL
            quality: 录制质量
            
        Returns:
            {
                'is_live': bool,
                'platform': str,
                'stream_url': str,
                'anchor_name': str,
                'title': str
            }
        """
        try:
            # 从工厂获取对应的平台策略
            strategy = self._strategy_factory.get_strategy(url)
            
            if not strategy:
                logger.warning(f"未找到匹配的平台策略: {url}")
                return {
                    'is_live': False,
                    'platform': '未知平台',
                    'stream_url': '',
                    'anchor_name': '',
                    'title': ''
                }
            
            # 使用策略处理
            return await strategy.get_stream_info(url, quality, self.proxy_addr, self.cookies)
            
        except Exception as e:
            logger.error(f"获取直播流信息失败: {url}, error={e}")
            return {
                'is_live': False,
                'platform': '未知平台',
                'stream_url': '',
                'anchor_name': '',
                'title': ''
            }
    
    async def check_live_status(self, url: str) -> bool:
        """快速检查直播状态（不获取流地址）
        
        Args:
            url: 直播间URL
            
        Returns:
            是否正在直播
        """
        info = await self.get_live_stream_info(url)
        return info['is_live']
