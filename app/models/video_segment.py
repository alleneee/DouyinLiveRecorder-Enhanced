"""视频分片模型 
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base
import enum


class SegmentStatus(str, enum.Enum):
    """分片状态"""
    RECORDING = "recording"
    COMPLETED = "completed"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"


class VideoSegment(Base):
    """视频分片表 - 包含详细的录制信息和视频元数据"""
    __tablename__ = "video_segments"
    __table_args__ = (
        Index('idx_platform_room_session', 'platform', 'platform_room_id', 'session_id'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="直播间ID"
    )

    # 直播平台信息（便于独立查询，无需JOIN）
    platform = Column(String(50), nullable=False, index=True, comment="直播平台（冗余字段）")
    platform_room_id = Column(String(100), index=True, comment="平台房间ID（冗余字段）")

    # 会话标识（用于区分同一直播间的多次开播）
    session_id = Column(String(36), nullable=False, index=True, comment="录制会话ID（UUID）")

    # 录制信息
    segment_index = Column(Integer, comment="切片索引（同一会话内的序号）")
    
    # 分片时间信息（相对时间，格式：HH:MM:SS）
    # 存储相对于录制开始的时间，例如：
    # seg0: started_at="00:00:00", ended_at="00:20:00"
    # seg1: started_at="00:20:00", ended_at="00:40:00"
    segment_started_at = Column(String(20), comment="分片相对开始时间(HH:MM:SS格式)")
    segment_ended_at = Column(String(20), comment="分片相对结束时间(HH:MM:SS格式)")
    duration = Column(Integer, comment="分片实际时长(秒)，可能小于配置的segment_duration")
    
    # OSS相对路径(不包含域名,只存储key)
    # 示例: live-recorder/prod/抖音/296728101980/20251021/48/video.ts
    # 前端访问时需拼接: https://{bucket}.{endpoint}/{oss_video_url}
    oss_video_url = Column(String(1024), comment="OSS视频相对路径(key,不含域名)")
    oss_audio_url = Column(String(1024), comment="OSS音频相对路径(key,不含域名,mp3格式)")
    
    # 状态和错误（使用String类型避免枚举验证问题）
    status = Column(
        String(20),
        default="recording",
        index=True,
        comment="文件状态"
    )
    error_message = Column(Text, comment="错误信息")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    completed_at = Column(DateTime, comment="录制完成时间")

    def __repr__(self):
        return f"<VideoSegment(id={self.id}, session={self.session_id}, index={self.segment_index})>"
