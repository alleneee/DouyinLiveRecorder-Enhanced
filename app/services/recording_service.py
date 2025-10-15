"""录制服务层实现（简化版）。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.room import RoomORM


class RecordingService:
    """录制服务 """
    
    def __init__(self, session: Session):
        self._session = session
    
    def start_recording(self, room_id: int, file_path: str | None = None) -> RoomORM:
        """启动录制"""
        room = self._session.get(RoomORM, room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")
        
        if room.recording_status == "recording":
            logger.warning(f"房间 {room_id} 已在录制中")
            return room
        
        room.recording_status = "recording"
        room.recording_started_at = datetime.now(timezone.utc)
        room.last_error = None  # 清除之前的错误
        
        self._session.commit()
        logger.info(f"✅ 录制已启动: room_id={room_id}, url={room.url}")
        return room
    
    def stop_recording(self, room_id: int, *, error_message: str | None = None) -> RoomORM:
        """停止录制"""
        room = self._session.get(RoomORM, room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")
        
        if error_message:
            room.recording_status = "error"
            room.last_error = error_message
            room.error_count += 1
            logger.error(f"❌ 录制错误: room_id={room_id}, error={error_message}")
        else:
            room.recording_status = "idle"
            room.last_recording_at = datetime.now(timezone.utc)
            logger.info(f"✅ 录制已停止: room_id={room_id}")
        
        room.recording_started_at = None
        
        self._session.commit()
        return room
    
    def is_recording(self, room_id: int) -> bool:
        """检查是否正在录制"""
        room = self._session.get(RoomORM, room_id)
        return room.recording_status == "recording" if room else False
    
    def get_recording_rooms(self) -> list[RoomORM]:
        """获取所有正在录制的房间"""
        stmt = select(RoomORM).where(RoomORM.recording_status == "recording")
        return list(self._session.execute(stmt).scalars().all())
    
    def increment_segment(self, room_id: int, segment_size: int) -> None:
        """增加分段统计"""
        room = self._session.get(RoomORM, room_id)
        if room:
            room.total_segments += 1
            room.total_size_bytes += segment_size
            self._session.commit()
            logger.debug(f"📊 更新统计: room_id={room_id}, segments={room.total_segments}, size={room.total_size_bytes}")


__all__ = ["RecordingService"]
