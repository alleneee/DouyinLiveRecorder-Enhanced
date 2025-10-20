"""
视频分片通知数据模型
用于在分片上传完成后发送给外部API
"""
from typing import List
from pydantic import BaseModel, Field


class LiveInfo(BaseModel):
    """直播间信息"""
    live_id: str = Field(..., description="session_id")
    live_url: str = Field(..., description="直播间URL")
    live_name: str = Field(..., description="直播间名称/主播名")


class SubVideoInfo(BaseModel):
    """子视频信息"""
    video_url: str = Field("", description="视频OSS地址")
    audio_url: str = Field("", description="音频OSS地址")
    duration: int = Field(..., description="视频时长(单位:秒)")
    absolute_start_time: str = Field(..., description="分片开始时间(ISO格式)")
    absolute_end_time: str = Field(..., description="分片结束时间(ISO格式)")
    serial_num: int = Field(..., description="视频序号")


class VideoShardInfo(BaseModel):
    """视频分片信息(用于未来标签功能扩展)"""
    start_time: str = Field(..., description="开始时间(HH:MM:SS:mmm)")
    end_time: str = Field(..., description="结束时间(HH:MM:SS:mmm)")
    tag: List[str] = Field(default_factory=list, description="标签列表")
    serial_num: int = Field(..., description="视频分片序号")


class SegmentNotificationRequest(BaseModel):
    """分片通知请求体"""
    live_info: LiveInfo
    sub_video_info: SubVideoInfo

    class Config:
        json_schema_extra = {
            "example": {
                "live_info": {
                    "live_url": "https://live.douyin.com/745964462470",
                    "live_name": "测试主播"
                },
                "sub_video_info": {
                    "video_url": "https://oss.example.com/videos/segment_0.ts",
                    "audio_url": "https://oss.example.com/audios/segment_0.mp3",
                    "duration": 60,
                    "absolute_start_time": "2025-01-20T10:30:00",
                    "absolute_end_time": "2025-01-20T10:31:00",
                    "serial_num": 0
                }
            }
        }
