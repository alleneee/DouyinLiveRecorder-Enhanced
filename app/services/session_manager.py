"""录制会话管理器 - 纯数据库版本（无Redis依赖）"""
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
import uuid

from sqlalchemy import select, func
from app.database_async import AsyncSessionLocal
from app.models.live_room import LiveRoom
from app.models.video_segment import VideoSegment, SegmentStatus
from app.config import settings


class RecordingSession:
    """录制会话
    
    核心思路：
    1. 所有状态存储在数据库（live_rooms + video_segments）
    2. 需要时从数据库查询恢复
    3. 分片时间基于第一个分片的开始时间 + 分片索引计算
    """
    
    def __init__(
        self,
        room_id: int,
        session_id: str,
        session_started_at: datetime
    ):
        self.room_id = room_id
        self.session_id = session_id
        self.session_started_at = session_started_at
    
    async def get_next_segment_info(self) -> dict:
        """获取下一个分片信息
        
        从数据库查询当前最大分片索引，计算下一个分片的信息
        
        Returns:
            {
                'segment_index': int,           # 分片索引
                'is_first': bool,               # 是否第一个分片
                'segment_started_at': datetime  # 分片开始时间
            }
        """
        async with AsyncSessionLocal() as db:
            # 查询当前最大分片索引
            result = await db.execute(
                select(func.max(VideoSegment.segment_index))
                .where(
                    VideoSegment.room_id == self.room_id,
                    VideoSegment.session_id == self.session_id
                )
            )
            max_index = result.scalar()
            
            # 计算下一个分片索引
            next_index = 1 if max_index is None else max_index + 1
            is_first = (next_index == 1)
            
            # 计算分片开始时间
            if is_first:
                # 第一个分片：使用会话开始时间
                segment_started_at = self.session_started_at
            else:
                # 后续分片：基于第一个分片的开始时间 + (索引-1) * 分段时长
                # 这样即使进程重启，也能准确计算出每个分片的开始时间
                segment_started_at = self.session_started_at + timedelta(
                    seconds=(next_index - 1) * settings.segment_duration
                )
            
            logger.info(
                f"计算分片信息: room_id={self.room_id}, "
                f"segment_index={next_index}, "
                f"is_first={is_first}, "
                f"started_at={segment_started_at}"
            )
            
            return {
                'segment_index': next_index,
                'is_first': is_first,
                'segment_started_at': segment_started_at
            }
    
    async def create_segment_record(
        self,
        segment_index: int,
        segment_started_at: datetime,
        streamer_name: str,
        platform: str
    ) -> VideoSegment:
        """创建分片记录
        
        Args:
            segment_index: 分片索引
            segment_started_at: 分片开始时间
            streamer_name: 主播名称
            platform: 平台名称
            
        Returns:
            创建的VideoSegment对象
        """
        async with AsyncSessionLocal() as db:
            segment = VideoSegment(
                room_id=self.room_id,
                session_id=self.session_id,
                streamer_name=streamer_name,
                platform=platform,
                segment_index=segment_index,
                segment_started_at=segment_started_at,
                segment_ended_at=None,  # 录制中，暂时为空
                duration=None,  # 录制中，暂时为空
                status=SegmentStatus.RECORDING
            )
            
            db.add(segment)
            await db.commit()
            await db.refresh(segment)
            
            logger.info(
                f"分片记录创建: segment_id={segment.id}, "
                f"index={segment_index}, "
                f"started_at={segment_started_at}"
            )
            
            return segment
    
    async def complete_segment(
        self,
        segment_id: int,
        segment_ended_at: Optional[datetime] = None
    ):
        """完成分片录制
        
        Args:
            segment_id: 分片ID
            segment_ended_at: 分片结束时间（默认使用当前时间）
        """
        if segment_ended_at is None:
            segment_ended_at = datetime.now()
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VideoSegment).where(VideoSegment.id == segment_id)
            )
            segment = result.scalar_one_or_none()
            
            if not segment:
                logger.error(f"分片不存在: segment_id={segment_id}")
                return
            
            # 更新结束时间和时长
            segment.segment_ended_at = segment_ended_at
            
            if segment.segment_started_at:
                duration = (segment_ended_at - segment.segment_started_at).total_seconds()
                segment.duration = int(duration)
            
            segment.status = SegmentStatus.COMPLETED
            segment.completed_at = datetime.now()
            
            await db.commit()
            
            logger.info(
                f"分片录制完成: segment_id={segment_id}, "
                f"index={segment.segment_index}, "
                f"duration={segment.duration}秒"
            )
    
    async def end_session(self):
        """结束录制会话
        
        更新所有分片的session_ended_at，清空live_rooms的当前会话
        """
        session_ended_at = datetime.now()
        
        async with AsyncSessionLocal() as db:
            # 更新所有分片的session_ended_at
            await db.execute(
                VideoSegment.__table__.update()
                .where(VideoSegment.session_id == self.session_id)
                .values(session_ended_at=session_ended_at)
            )
            
            # 清空live_rooms的当前会话
            result = await db.execute(
                select(LiveRoom).where(LiveRoom.id == self.room_id)
            )
            room = result.scalar_one_or_none()
            if room:
                room.current_session_id = None
                room.current_session_started_at = None
            
            await db.commit()
        
        logger.info(
            f"会话结束: session_id={self.session_id}, "
            f"ended_at={session_ended_at}"
        )
    
    @classmethod
    async def create_new(cls, room_id: int) -> 'RecordingSession':
        """创建新会话
        
        Args:
            room_id: 直播间ID
            
        Returns:
            新创建的RecordingSession对象
        """
        session_id = str(uuid.uuid4())
        session_started_at = datetime.now()
        
        # 更新数据库
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(LiveRoom).where(LiveRoom.id == room_id)
            )
            room = result.scalar_one_or_none()
            
            if room:
                room.current_session_id = session_id
                room.current_session_started_at = session_started_at
                await db.commit()
        
        logger.info(
            f"新会话创建: room_id={room_id}, "
            f"session_id={session_id}, "
            f"started_at={session_started_at}"
        )
        
        return cls(
            room_id=room_id,
            session_id=session_id,
            session_started_at=session_started_at
        )
    
    @classmethod
    async def recover(cls, room_id: int) -> Optional['RecordingSession']:
        """从数据库恢复会话
        
        Args:
            room_id: 直播间ID
            
        Returns:
            恢复的RecordingSession对象，如果无法恢复返回None
        """
        async with AsyncSessionLocal() as db:
            # 从live_rooms获取当前会话ID
            result = await db.execute(
                select(LiveRoom).where(LiveRoom.id == room_id)
            )
            room = result.scalar_one_or_none()
            
            if not room or not room.current_session_id:
                logger.warning(f"无法恢复会话: room_id={room_id}, 没有活跃会话")
                return None
            
            session_id = room.current_session_id
            session_started_at = room.current_session_started_at
            
            logger.info(
                f"从数据库恢复会话: room_id={room_id}, "
                f"session_id={session_id}"
            )
            
            return cls(
                room_id=room_id,
                session_id=session_id,
                session_started_at=session_started_at
            )


class SessionManager:
    """会话管理器（全局单例）
    
    管理所有活跃的录制会话，支持进程重启后恢复
    """
    
    def __init__(self):
        self.active_sessions = {}  # {room_id: RecordingSession}
    
    async def get_or_create_session(self, room_id: int) -> RecordingSession:
        """获取或创建会话
        
        优先从内存获取，然后尝试从数据库恢复，最后创建新会话
        
        Args:
            room_id: 直播间ID
            
        Returns:
            RecordingSession对象
        """
        # 1. 从内存获取
        if room_id in self.active_sessions:
            logger.debug(f"从内存获取会话: room_id={room_id}")
            return self.active_sessions[room_id]
        
        # 2. 尝试从数据库恢复
        session = await RecordingSession.recover(room_id)
        if session:
            self.active_sessions[room_id] = session
            logger.info(f"会话已恢复: room_id={room_id}")
            return session
        
        # 3. 创建新会话
        session = await RecordingSession.create_new(room_id)
        self.active_sessions[room_id] = session
        logger.info(f"新会话已创建: room_id={room_id}")
        return session
    
    async def end_session(self, room_id: int):
        """结束会话
        
        Args:
            room_id: 直播间ID
        """
        session = self.active_sessions.get(room_id)
        if session:
            await session.end_session()
            del self.active_sessions[room_id]
            logger.info(f"会话已结束并移除: room_id={room_id}")
        else:
            logger.warning(f"会话不存在: room_id={room_id}")
    
    def get_session(self, room_id: int) -> Optional[RecordingSession]:
        """获取会话（仅从内存）
        
        Args:
            room_id: 直播间ID
            
        Returns:
            RecordingSession对象或None
        """
        return self.active_sessions.get(room_id)
    
    def get_active_sessions(self) -> dict:
        """获取所有活跃会话信息
        
        Returns:
            {room_id: session_info}
        """
        return {
            room_id: {
                'session_id': session.session_id,
                'started_at': session.session_started_at.isoformat()
            }
            for room_id, session in self.active_sessions.items()
        }


# 全局单例
session_manager = SessionManager()
