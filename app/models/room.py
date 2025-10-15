"""Room ORM 模型定义。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoomORM(Base):
    """房间元数据表。"""

    __tablename__ = "rooms"
    __table_args__ = (Index("ix_rooms_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    quality: Mapped[str] = mapped_column(String(32), nullable=False, default="原画")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 录制配置
    enable_segment_recording: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")
    segment_duration: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1200")
    video_save_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="TS")
    run_post_process: Mapped[bool] = mapped_column(Integer, nullable=False, server_default="1")
    
    # 当前录制状态
    recording_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="idle")
    recording_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # 统计信息
    total_segments: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_recording_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # 错误信息
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


__all__ = ["RoomORM"]
