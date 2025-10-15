"""录制服务层实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import RecordingORM
from app.schemas.recordings import RecordingRead


class RecordingService:
    def __init__(self, session: Session):
        self._session = session

    def list_by_room(self, room_id: int, *, limit: int | None = None) -> list[RecordingRead]:
        stmt = (
            select(RecordingORM)
            .where(RecordingORM.room_id == room_id)
            .order_by(RecordingORM.started_at.desc().nullslast())
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [RecordingRead.model_validate(row) for row in rows]

    def get_active_entry(self, room_id: int) -> RecordingRead | None:
        stmt = select(RecordingORM).where(
            and_(RecordingORM.room_id == room_id, RecordingORM.status == "recording")
        )
        row = self._session.execute(stmt).scalars().first()
        return RecordingRead.model_validate(row) if row else None

    def mark_started(self, room_id: int, *, file_path: str | None = None) -> RecordingRead:
        now = datetime.now(timezone.utc)
        record = RecordingORM(
            room_id=room_id,
            status="recording",
            file_path=file_path,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return RecordingRead.model_validate(record)

    def mark_stopped(
        self,
        recording_id: int,
        *,
        file_path: str | None = None,
        error_message: str | None = None,
    ) -> RecordingRead:
        record = self._session.get(RecordingORM, recording_id)
        if not record:
            raise ValueError("Recording entry not found")
        record.status = "completed" if error_message is None else "failed"
        record.file_path = file_path or record.file_path
        record.error_message = error_message
        record.stopped_at = datetime.now(timezone.utc)
        record.updated_at = record.stopped_at
        self._session.flush()
        self._session.refresh(record)
        return RecordingRead.model_validate(record)

    def mark_failed(self, room_id: int, *, error_message: str) -> RecordingRead:
        now = datetime.now(timezone.utc)
        record = RecordingORM(
            room_id=room_id,
            status="failed",
            error_message=error_message,
            started_at=now,
            stopped_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.flush()
        self._session.refresh(record)
        return RecordingRead.model_validate(record)


__all__ = ["RecordingService"]
