"""直播间模型 - 2表设计版本（简化）"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class RecordStatus(str, enum.Enum):
    """录制状态"""
    PENDING = "pending"  # 待录制
    RECORDING = "recording"  # 录制中
    FINISHED = "finished"  # 录制结束
    ERROR = "error"  # 错误
    STOPPED = "stopped"  # 已停止


class LiveStatus(str, enum.Enum):
    """直播状态"""
    UNKNOWN = "unknown"
    LIVE = "live"
    OFFLINE = "offline"


class LiveRoom(Base):
    """直播间表 - 简化版
    
    只保留核心字段：
    - 基础信息：URL、平台、主播名等
    - 录制配置：画质、是否启用等
    - 当前状态：直播状态、录制状态
    """
    __tablename__ = "live_rooms"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 基础信息
    url = Column(String(512), nullable=False, unique=True, comment="直播间URL")
    platform = Column(String(50), nullable=False, index=True, comment="平台名称")
    platform_room_id = Column(String(100), comment="平台房间ID")
    streamer_name = Column(String(100), index=True, comment="主播名称")
    room_title = Column(String(255), comment="直播间标题")
    
    # 录制配置
    quality = Column(String(20), default="原画", comment="录制质量")
    is_enabled = Column(Boolean, default=False, index=True, comment="是否启用监控")
    auto_record = Column(Boolean, default=False, comment="是否自动录制")
    
    # 当前直播状态（使用String类型避免枚举验证问题）
    live_status = Column(String(20), default="unlive", index=True, comment="直播状态 unlive/live")
    record_status = Column(String(20), default="pending", index=True, comment="录制状态 pending/recording/finished/error/stopped")
    
    # 当前会话信息（用于追踪正在录制的会话）
    current_session_id = Column(String(36), index=True, comment="当前录制会话ID")
    current_session_started_at = Column(DateTime, comment="当前会话开始时间")
    current_session_ended_at = Column(DateTime, comment="当前会话结束时间")
    total_segment = Column(Integer, default=0, comment="会话完成后的总分片数")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    remark = Column(Text, comment="备注")

    def __repr__(self):
        return f"<LiveRoom(id={self.id}, platform={self.platform}, streamer={self.streamer_name})>"
