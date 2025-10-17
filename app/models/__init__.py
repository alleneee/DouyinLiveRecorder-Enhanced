"""数据库模型 - 2表设计"""
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.models.video_segment import VideoSegment, SegmentStatus

__all__ = [
    "LiveRoom",
    "RecordStatus",
    "LiveStatus", 
    "VideoSegment",
    "SegmentStatus"
]
