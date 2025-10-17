"""Pydantic schemas - 2表设计"""
from app.schemas.live_room import (
    LiveRoomBase,
    LiveRoomCreate,
    LiveRoomUpdate,
    LiveRoomResponse,
    LiveRoomListResponse,
    SessionStatsResponse
)
from app.schemas.video_segment import (
    VideoSegmentResponse,
    VideoSegmentListResponse,
    SessionSegmentsResponse
)
from app.schemas.common import PaginatedResponse

__all__ = [
    "LiveRoomBase",
    "LiveRoomCreate",
    "LiveRoomUpdate",
    "LiveRoomResponse",
    "LiveRoomListResponse",
    "SessionStatsResponse",
    "VideoSegmentResponse",
    "VideoSegmentListResponse",
    "SessionSegmentsResponse",
    "PaginatedResponse"
]
