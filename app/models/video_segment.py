"""视频分段 ORM 模型。"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Index
from sqlalchemy.sql import func

from app.db.base import Base


class VideoSegmentORM(Base):
    """视频分段记录表（每20分钟一段）。"""
    
    __tablename__ = "video_segments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_url = Column(String(500), nullable=False, comment="直播间 URL")
    anchor_name = Column(String(100), nullable=False, comment="主播名称")
    segment_index = Column(Integer, nullable=False, comment="分段序号（从1开始）")
    local_path = Column(String(500), nullable=False, comment="本地文件路径")
    file_size = Column(BigInteger, nullable=False, comment="文件大小（字节）")
    duration_seconds = Column(Integer, nullable=True, comment="视频时长（秒）")
    oss_key = Column(String(500), nullable=True, comment="OSS 对象键")
    oss_url = Column(Text, nullable=True, comment="OSS 访问 URL")
    upload_status = Column(
        String(20), 
        nullable=False, 
        default="pending",
        comment="上传状态: pending/uploading/success/failed"
    )
    upload_time = Column(DateTime, nullable=True, comment="上传完成时间")
    start_time = Column(DateTime, nullable=False, comment="录制开始时间")
    end_time = Column(DateTime, nullable=False, comment="录制结束时间")
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
        Index('idx_anchor_name', 'anchor_name'),
        Index('idx_start_time', 'start_time'),
        Index('idx_upload_status', 'upload_status'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )


__all__ = ["VideoSegmentORM"]
