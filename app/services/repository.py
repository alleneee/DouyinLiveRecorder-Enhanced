"""基于数据库的房间仓库适配。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import RoomORM
from app.core.recording.models import Room, RoomQuality, RoomStatus
from app.core.recording.repository import RepositorySnapshot


class DatabaseRoomRepository:
    """提供与文件仓库等价的数据库持久化实现。"""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or SessionLocal

    def load(self) -> RepositorySnapshot:
        with self._session_scope() as session:
            rows = session.execute(select(RoomORM).order_by(RoomORM.created_at)).scalars().all()
            rooms = [self._to_domain(row) for row in rows]
        return RepositorySnapshot(rooms=rooms, annotations=[])

    def add_room(self, room: Room) -> Room:
        with self._session_scope() as session:
            record = RoomORM(
                url=self._normalize_url(room.url),
                nickname=room.nickname,
                quality=RoomQuality.normalize(room.quality),
                status=room.status.value,
                comment=room.comment,
                created_at=self._ensure_aware(room.created_at),
                updated_at=self._ensure_aware(room.updated_at),
            )
            session.add(record)
            self._flush_unique(session, "房间已存在或URL重复")
            session.refresh(record)
            return self._to_domain(record)

    def update_room(self, identity: str, **changes: object) -> Room:
        with self._session_scope() as session:
            record = self._require_by_identity(session, identity)
            self._apply_changes(record, changes)
            record.updated_at = datetime.now(timezone.utc)
            self._flush_unique(session, "房间更新失败，URL 与其他房间冲突")
            session.refresh(record)
            return self._to_domain(record)

    def remove_room(self, identity: str) -> None:
        with self._session_scope() as session:
            record = self._require_by_identity(session, identity)
            session.delete(record)

    def disable_room(self, identity: str) -> Room:
        with self._session_scope() as session:
            record = self._require_by_identity(session, identity)
            record.status = RoomStatus.DISABLED.value
            record.updated_at = datetime.now(timezone.utc)
            session.flush()
            session.refresh(record)
            return self._to_domain(record)

    def enable_room(self, identity: str) -> Room:
        with self._session_scope() as session:
            record = self._require_by_identity(session, identity)
            record.status = RoomStatus.ACTIVE.value
            record.updated_at = datetime.now(timezone.utc)
            session.flush()
            session.refresh(record)
            return self._to_domain(record)

    def comment_room(self, identity: str, comment: str) -> Room:
        return self.update_room(identity, comment=comment)

    # ----------------------------
    # 内部工具
    # ----------------------------
    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _require_by_identity(self, session: Session, identity: str) -> RoomORM:
        normalized = self._normalize_url(identity)
        record = session.scalar(select(RoomORM).where(RoomORM.url == normalized))
        if not record:
            raise ValueError(f"Room not found: {identity}")
        return record

    def _apply_changes(self, record: RoomORM, changes: dict[str, object]) -> None:
        payload = dict(changes)
        if "url" in payload and isinstance(payload["url"], str):
            record.url = self._normalize_url(payload.pop("url"))
        if "quality" in payload and isinstance(payload["quality"], str):
            record.quality = RoomQuality.normalize(payload.pop("quality"))
        if "status" in payload and isinstance(payload["status"], str):
            record.status = RoomStatus(payload.pop("status")).value
        for key, value in payload.items():
            setattr(record, key, value)

    def _flush_unique(self, session: Session, message: str) -> None:
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError(message) from exc

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if not url:
            raise ValueError("URL 不能为空")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        return url.rstrip("/")

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _to_domain(record: RoomORM) -> Room:
        return Room(
            url=record.url,
            quality=record.quality,
            nickname=record.nickname,
            status=RoomStatus(record.status),
            created_at=DatabaseRoomRepository._ensure_aware(record.created_at),
            updated_at=DatabaseRoomRepository._ensure_aware(record.updated_at),
            comment=record.comment,
        )


__all__ = ["DatabaseRoomRepository"]
