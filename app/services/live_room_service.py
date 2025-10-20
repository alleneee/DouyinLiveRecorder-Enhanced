"""直播间业务逻辑服务层"""
import re
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.logger import logger
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.schemas.live_room import LiveRoomCreate


# 平台映射常量
PLATFORM_MAP: Dict[str, str] = {
    'douyin.com': '抖音',
    'tiktok.com': 'TikTok',
    'kuaishou.com': '快手',
    'huya.com': '虎牙',
    'douyu.com': '斗鱼',
    'bilibili.com': 'B站',
    'xiaohongshu.com': '小红书',
    'yy.com': 'YY',
    'bigo.tv': 'Bigo',
    'twitch.tv': 'TwitchTV',
    'youtube.com': 'Youtube',
}


class LiveRoomService:
    """直播间业务服务类
    
    负责处理直播间相关的业务逻辑：
    - URL解析（平台识别、房间ID提取）
    - 直播间创建、更新、删除
    - 数据验证
    """
    
    @staticmethod
    def extract_platform_from_url(url: str) -> str:
        """从直播间URL提取平台名称
        
        根据URL中的域名关键字识别直播平台。
        
        Args:
            url: 直播间URL
            
        Returns:
            平台名称（中文），如果无法识别则返回"未知平台"
        """
        for domain, platform in PLATFORM_MAP.items():
            if domain in url:
                return platform
        return '未知平台'
    
    @staticmethod
    def extract_room_id_from_url(url: str) -> Optional[str]:
        """从直播间URL提取平台房间ID
        
        支持多种平台的URL格式提取房间ID。
        
        Args:
            url: 直播间URL
            
        Returns:
            房间ID字符串，提取失败返回None
            
        """
        # 抖音：https://live.douyin.com/296728101980
        if 'douyin.com' in url:
            match = re.search(r'live\.douyin\.com/(\d+)', url)
            return match.group(1) if match else None
        
        # TikTok：https://www.tiktok.com/@username/live
        if 'tiktok.com' in url:
            match = re.search(r'@([^/]+)/live', url)
            return match.group(1) if match else None
        
        # 快手：https://live.kuaishou.com/u/username
        if 'kuaishou.com' in url:
            match = re.search(r'/u/([^/?]+)', url)
            return match.group(1) if match else None
        
        # 虎牙：https://www.huya.com/123456
        if 'huya.com' in url:
            match = re.search(r'huya\.com/([^/?]+)', url)
            return match.group(1) if match else None
        
        # 斗鱼：https://www.douyu.com/123456
        if 'douyu.com' in url:
            match = re.search(r'douyu\.com/([^/?]+)', url)
            return match.group(1) if match else None
        
        # B站：https://live.bilibili.com/12345
        if 'bilibili.com' in url:
            match = re.search(r'live\.bilibili\.com/(\d+)', url)
            return match.group(1) if match else None
        
        # 小红书：https://www.xiaohongshu.com/user/profile/xxx/live
        if 'xiaohongshu.com' in url:
            match = re.search(r'/profile/([^/]+)', url)
            return match.group(1) if match else None
        
        # YY：https://www.yy.com/123456
        if 'yy.com' in url:
            match = re.search(r'yy\.com/(\d+)', url)
            return match.group(1) if match else None
        
        # Bigo：https://www.bigo.tv/cn/123456
        if 'bigo.tv' in url:
            match = re.search(r'bigo\.tv/[^/]+/([^/?]+)', url)
            return match.group(1) if match else None
        
        # Twitch：https://www.twitch.tv/username
        if 'twitch.tv' in url:
            match = re.search(r'twitch\.tv/([^/?]+)', url)
            return match.group(1) if match else None
        
        # YouTube：https://www.youtube.com/watch?v=xxxxx
        if 'youtube.com' in url:
            match = re.search(r'[?&]v=([^&]+)', url)
            return match.group(1) if match else None
        
        return None
    
    @staticmethod
    async def check_url_exists(db: AsyncSession, url: str) -> Optional[LiveRoom]:
        """检查URL是否已存在
        
        Args:
            db: 异步数据库会话
            url: 直播间URL
            
        Returns:
            如果存在返回LiveRoom对象，否则返回None
        """
        result = await db.execute(
            select(LiveRoom).where(LiveRoom.url == url)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_room_by_url(db: AsyncSession, url: str) -> Optional[LiveRoom]:
        """通过URL查询直播间
        
        Args:
            db: 异步数据库会话
            url: 直播间URL
            
        Returns:
            LiveRoom对象，如果不存在返回None
        """
        result = await db.execute(
            select(LiveRoom).where(LiveRoom.url == url)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_room_by_platform_room_id(
        db: AsyncSession,
        platform: str,
        platform_room_id: str
    ) -> Optional[LiveRoom]:
        """通过平台和平台房间ID查询直播间
        
        Args:
            db: 异步数据库会话
            platform: 平台名称
            platform_room_id: 平台房间ID
            
        Returns:
            LiveRoom对象，如果不存在返回None
        """
        result = await db.execute(
            select(LiveRoom).where(
                LiveRoom.platform == platform,
                LiveRoom.platform_room_id == platform_room_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_room_by_url_parsed(db: AsyncSession, url: str) -> Optional[LiveRoom]:
        """通过URL解析后查询直播间
        
        先从URL提取平台和房间ID，然后通过这两个字段查询。
        这种方式比直接URL查询更灵活（URL可能有参数变化）。
        
        Args:
            db: 异步数据库会话
            url: 直播间URL
            
        Returns:
            LiveRoom对象，如果不存在返回None
        """
        platform = LiveRoomService.extract_platform_from_url(url)
        platform_room_id = LiveRoomService.extract_room_id_from_url(url)
        
        if not platform_room_id:
            # 如果无法提取房间ID，回退到URL精确匹配
            return await LiveRoomService.get_room_by_url(db, url)
        
        return await LiveRoomService.get_room_by_platform_room_id(
            db, platform, platform_room_id
        )
    
    @staticmethod
    async def create_live_room(
        db: AsyncSession,
        room_data: LiveRoomCreate
    ) -> LiveRoom:
        """创建直播间
        
        处理完整的创建流程：
        1. 提取平台信息
        2. 提取房间ID
        3. 创建数据库记录
        
        Args:
            db: 异步数据库会话
            room_data: 直播间创建数据
            
        Returns:
            创建的LiveRoom对象
        """
        # 提取平台和房间ID
        platform = LiveRoomService.extract_platform_from_url(room_data.url)
        platform_room_id = LiveRoomService.extract_room_id_from_url(room_data.url)
        
        # 创建直播间记录
        db_room = LiveRoom(
            url=room_data.url,
            platform=platform,
            platform_room_id=platform_room_id,
            quality=room_data.quality or "原画",
            streamer_name=room_data.streamer_name,
            is_enabled=room_data.is_enabled if room_data.is_enabled is not None else True,
            auto_record=room_data.auto_record if room_data.auto_record is not None else True,
            remark=room_data.remark,
            record_status=RecordStatus.IDLE,
            live_status=LiveStatus.UNKNOWN,
            current_session_id=room_data.session_id
        )
        
        db.add(db_room)
        await db.commit()
        await db.refresh(db_room)
        
        logger.info(
            "创建直播间成功",
            extra={
                "room_id": db_room.id,
                "platform": platform,
                "platform_room_id": platform_room_id,
                "url": room_data.url,
                "enabled": db_room.is_enabled
            }
        )
        
        return db_room


# 创建单例实例
live_room_service = LiveRoomService()
