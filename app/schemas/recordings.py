"""录制相关 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RecordingRead(BaseModel):
    id: int
    room_id: int
    status: str
    file_path: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecordingStart(BaseModel):
    force: bool = Field(default=False)


class RecordingStop(BaseModel):
    reason: str | None = None


__all__ = ["RecordingRead", "RecordingStart", "RecordingStop"]
