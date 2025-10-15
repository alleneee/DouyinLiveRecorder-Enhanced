"""录制任务 ORM 模型。"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.sql import func

from app.db.base import Base


class RecordingTaskORM(Base):
    """录制任务表。"""
    
    __tablename__ = "recording_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_url = Column(String(500), nullable=False, comment="直播间 URL")
    nickname = Column(String(100), nullable=False, comment="主播昵称")
    quality = Column(String(20), nullable=False, server_default="OD", comment="画质代码")
    enable_segment_recording = Column(Boolean, nullable=False, server_default='1', comment="启用分段录制")
    segment_duration = Column(Integer, nullable=False, server_default='1200', comment="分段时长（秒）")
    video_save_type = Column(String(20), nullable=False, server_default="TS", comment="视频保存格式")
    oss_enabled = Column(Boolean, nullable=True, comment="是否启用OSS上传")
    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
        comment="任务状态: pending/running/stopped/error"
    )
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    stopped_at = Column(DateTime, nullable=True, comment="停止时间")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )
    
    __table_args__ = (
        Index('idx_room_url', 'room_url'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )


__all__ = ["RecordingTaskORM"]
