"""视频分片schemas - 简化版"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VideoSegmentResponse(BaseModel):
    """视频分片响应 - 只包含核心元数据"""
    id: int
    room_id: int

    # 会话标识
    session_id: str

    # 录制信息
    streamer_name: Optional[str]
    platform: Optional[str]
    segment_index: Optional[int]

    # 分片时间信息
    segment_started_at: Optional[datetime]
    segment_ended_at: Optional[datetime]
    duration: Optional[int]

    # OSS地址
    oss_video_url: Optional[str]
    oss_audio_url: Optional[str]

    # 状态
    status: str
    error_message: Optional[str]

    # 时间戳
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class VideoSegmentListResponse(BaseModel):
    """视频分片列表响应"""
    total: int
    page: int
    page_size: int
    items: list[VideoSegmentResponse]


class SessionSegmentsResponse(BaseModel):
    """某个会话的所有分片概览"""
    session_id: str
    session_started_at: datetime
    session_ended_at: Optional[datetime]
    room_id: int
    streamer_name: Optional[str]
    platform: Optional[str]
    total_segments: int
    segments: list[VideoSegmentResponse]

    class Config:
        from_attributes = True
