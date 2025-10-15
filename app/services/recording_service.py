"""录制服务层实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
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
        logger.info("标记房间 {} 开始录制", room_id)
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
        logger.debug("添加录制记录到数据库: ID={}", record.id)
        self._session.flush()
        self._session.refresh(record)
        logger.debug("刷新录制记录: ID={}", record.id)
        logger.debug("录制记录已创建: ID={}", record.id)
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
            logger.error("录制记录不存在: ID={}", recording_id)
            raise ValueError("Recording entry not found")
        
        status = "completed" if error_message is None else "failed"
        logger.info("标记录制 {} 状态: {}", recording_id, status)
        if error_message:
            logger.error("录制失败: {}", error_message)
        
        record.status = status
        record.file_path = file_path or record.file_path
        record.error_message = error_message
        record.stopped_at = datetime.now(timezone.utc)
        record.updated_at = record.stopped_at
        logger.debug("更新录制记录: ID={}", record.id)
        self._session.flush()
        self._session.refresh(record)
        logger.debug("刷新录制记录: ID={}", record.id)
        return RecordingRead.model_validate(record)

    def mark_failed(self, room_id: int, *, error_message: str) -> RecordingRead:
        logger.error("房间 {} 录制失败: {}", room_id, error_message)
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
        logger.debug("添加失败记录到数据库: ID={}", record.id)
        self._session.flush()
        self._session.refresh(record)
        logger.debug("刷新失败记录: ID={}", record.id)
        logger.debug("失败记录已创建: ID={}", record.id)
        return RecordingRead.model_validate(record)


__all__ = ["RecordingService"]
