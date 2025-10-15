"""房间服务层实现。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import RoomORM
from app.schemas.rooms import RoomCreate, RoomRead, RoomUpdate
from src.recording.models import Room, RoomQuality, RoomStatus


class RoomService:
    """封装房间数据库操作并与领域模型互转。"""

    def __init__(self, session: Session):
        self._session = session

    # ----------------------------
    # 查询接口
    # ----------------------------
    def list_rooms(self) -> list[RoomRead]:
        rooms = self._session.scalars(select(RoomORM).order_by(RoomORM.created_at.desc())).all()
        return [RoomRead.model_validate(room) for room in rooms]

    def get_room(self, room_id: int) -> RoomRead:
        room = self._require_room(room_id)
        return RoomRead.model_validate(room)

    def get_room_orm(self, room_id: int) -> RoomORM:
        return self._require_room(room_id)

    def get_room_domain(self, room_id: int) -> Room:
        room = self._require_room(room_id)
        return self._to_domain(room)

    def get_room_by_url(self, url: str) -> RoomRead:
        room = self._session.scalar(select(RoomORM).where(RoomORM.url == self._normalize_url(url)))
        if not room:
            raise ValueError("Room not found")
        return RoomRead.model_validate(room)

    def get_room_by_identity(self, identity: str) -> RoomORM | None:
        return self._session.scalar(select(RoomORM).where(RoomORM.url == self._normalize_url(identity)))

    def get_active_domains(self) -> list[Room]:
        rooms = self._session.scalars(
            select(RoomORM).where(RoomORM.status.in_([RoomStatus.ACTIVE.value, RoomStatus.RECORDING.value]))
        ).all()
        return [self._to_domain(room) for room in rooms]

    def find_by_identity(self, identity: str) -> Room | None:
        room = self._session.scalar(
            select(RoomORM).where(RoomORM.url == self._normalize_url(identity))
        )
        return self._to_domain(room) if room else None

    # ----------------------------
    # 写操作
    # ----------------------------
    def create_room(self, data: RoomCreate) -> RoomRead:
        now = datetime.now(timezone.utc)
        room = RoomORM(
            url=self._normalize_url(data.url),
            nickname=data.nickname.strip(),
            quality=self._normalize_quality(data.quality),
            status=self._normalize_status(data.status),
            comment=data.comment,
            created_at=now,
            updated_at=now,
        )
        self._session.add(room)
        self._flush_unique("房间已存在或URL重复")
        self._session.refresh(room)
        return RoomRead.model_validate(room)

    def update_room(self, room_id: int, data: RoomUpdate) -> RoomRead:
        room = self._require_room(room_id)
        payload = data.model_dump(exclude_unset=True)
        if "url" in payload:
            room.url = self._normalize_url(payload.pop("url"))
        if "quality" in payload:
            room.quality = self._normalize_quality(payload.pop("quality"))
        if "status" in payload:
            room.status = self._normalize_status(payload.pop("status"))
        for key, value in payload.items():
            setattr(room, key, value)
        room.updated_at = datetime.now(timezone.utc)
        self._flush_unique("房间更新失败，URL 与其他房间冲突")
        self._session.refresh(room)
        return RoomRead.model_validate(room)

    def disable_room(self, room_id: int) -> RoomRead:
        room = self._require_room(room_id)
        room.status = RoomStatus.DISABLED.value
        room.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return RoomRead.model_validate(room)

    def enable_room(self, room_id: int) -> RoomRead:
        room = self._require_room(room_id)
        room.status = RoomStatus.ACTIVE.value
        room.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return RoomRead.model_validate(room)

    def delete_room(self, room_id: int) -> None:
        room = self._require_room(room_id)
        self._session.delete(room)

    # ----------------------------
    # 工具方法
    # ----------------------------
    def _require_room(self, room_id: int) -> RoomORM:
        room = self._session.get(RoomORM, room_id)
        if not room:
            raise ValueError("Room not found")
        return room

    def _flush_unique(self, message: str) -> None:
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError(message) from exc

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            raise ValueError("URL 不能为空")
        url = url.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
            url = "https://" + url
        return url.rstrip("/")

    @staticmethod
    def _normalize_quality(quality: str) -> str:
        return RoomQuality.normalize(quality)

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        if not status:
            return RoomStatus.ACTIVE.value
        return RoomStatus(status).value

    @staticmethod
    def _to_domain(room: RoomORM) -> Room:
        created_at = RoomService._ensure_timezone(room.created_at)
        updated_at = RoomService._ensure_timezone(room.updated_at)
        return Room(
            url=room.url,
            quality=room.quality,
            nickname=room.nickname,
            status=RoomStatus(room.status),
            created_at=created_at,
            updated_at=updated_at,
            comment=room.comment,
        )

    @staticmethod
    def _ensure_timezone(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


__all__ = ["RoomService"]
