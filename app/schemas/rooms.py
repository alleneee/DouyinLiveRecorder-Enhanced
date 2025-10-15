"""房间相关 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RoomBase(BaseModel):
    url: str = Field(..., max_length=512)
    nickname: str = Field("", max_length=255)
    quality: str = Field("原画", max_length=32)
    status: str = Field("active", max_length=32)
    comment: str | None = Field(default=None, max_length=1024)


class RoomCreate(RoomBase):
    # 录制配置
    enable_segment_recording: bool = Field(True, description="启用分段录制")
    segment_duration: int = Field(60, description="分段时长（秒）")
    video_save_type: str = Field("TS", description="视频格式")
    run_post_process: bool = Field(True, description="是否执行后处理")


class RoomUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=512)
    nickname: str | None = Field(default=None, max_length=255)
    quality: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)
    comment: str | None = Field(default=None, max_length=1024)


class RoomRead(RoomBase):
    id: int
    enable_segment_recording: bool = True
    segment_duration: int = 1200
    video_save_type: str = "TS"
    run_post_process: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RoomList(BaseModel):
    items: list["RoomRead"]
    total: int
    limit: int
    offset: int


__all__ = ["RoomCreate", "RoomRead", "RoomUpdate", "RoomList"]
