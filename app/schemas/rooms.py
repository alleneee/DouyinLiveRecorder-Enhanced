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
    pass


class RoomUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=512)
    nickname: str | None = Field(default=None, max_length=255)
    quality: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)
    comment: str | None = Field(default=None, max_length=1024)


class RoomRead(RoomBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


__all__ = ["RoomCreate", "RoomRead", "RoomUpdate"]
