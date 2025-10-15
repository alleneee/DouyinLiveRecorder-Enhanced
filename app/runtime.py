"""录制运行时生命周期管理。"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from app.core.logging_config import setup_logging
from app.recording.environment import RecordingEnvironment, load_environment
from app.recording.legacy_adapter import LegacyRecorder
from app.db.session import get_session
from app.services.recording_service import RecordingService
from app.services.room_service import RoomService
from app.services.repository import DatabaseRoomRepository
from app.core.recording.app import RecordingApplication, build_application
from app.core.recording.context import RecordingContext, get_context
from app.core.recording.models import Room, RoomStatus
from app.core.recording.supervisor import legacy_worker_factory

logger = logging.getLogger("app.runtime")

_application: Optional[RecordingApplication] = None
_legacy_recorder: Optional[LegacyRecorder] = None
_legacy_env: Optional[RecordingEnvironment] = None


def bootstrap_runtime() -> RecordingContext:
    """确保录制运行时初始化并返回上下文。"""

    global _application
    global _legacy_recorder
    global _legacy_env
    
    # 初始化日志系统（首次调用）
    setup_logging(
        log_level="INFO",
        enable_console=True,
        enable_file=True,
        debug_mode=False,  # 可从配置文件读取
    )
    
    if _application is not None:
        return get_context()

    repository = DatabaseRoomRepository()
    application = build_application(
        config_file=None,
        worker_factory=legacy_worker_factory(_worker_entry),
        repository=repository,
        enable_file_watcher=False,
    )
    application.start()
    _application = application
    context = get_context()

    config_dir = Path(__file__).resolve().parents[2] / "config"
    _legacy_env = load_environment(config_dir)
    _legacy_recorder = LegacyRecorder(_legacy_env, context)
    logger.info("录制运行时已启动")
    return get_context()


def ensure_runtime() -> RecordingContext:
    try:
        return get_context()
    except RuntimeError:
        return bootstrap_runtime()


def shutdown_runtime() -> None:
    global _application
    global _legacy_recorder
    global _legacy_env
    if _application is None:
        return
    _application.stop()
    _application = None
    _legacy_recorder = None
    _legacy_env = None
    logger.info("录制运行时已关闭")


def _worker_entry(room: Room, stop_event: threading.Event) -> None:
    """占位录制线程：目前仅做记录并保持线程存活。"""

    worker_logger = logging.getLogger("app.runtime.worker")
    recorder = _legacy_recorder
    if recorder is None:
        worker_logger.error("旧版录制器未初始化，跳过录制")
        return
    recording_id: int | None = None
    failure_reason: str | None = None
    try:
        with get_session() as session:
            data_service = RoomService(session)
            orm = data_service.get_room_by_identity(room.identity)
            if orm:
                rec_service = RecordingService(session)
                active = rec_service.get_active_entry(orm.id)
                if active:
                    recording_id = active.id
                else:
                    entry = rec_service.mark_started(orm.id)
                    recording_id = entry.id
                context = ensure_runtime()
                context.service.update_room(orm.url, status=RoomStatus.RECORDING.value)

        worker_logger.info("房间 %s 的录制工作线程已启动", room.identity)
        recorder.record(room, stop_event=stop_event)
    except Exception as exc:  # noqa: BLE001
        worker_logger.exception("房间 %s 的录制工作线程失败", room.identity)
        failure_reason = str(exc)
    finally:
        if recording_id is not None:
            with get_session() as session:
                rec_service = RecordingService(session)
                rec_service.mark_stopped(recording_id, error_message=failure_reason)
        worker_logger.info("房间 %s 的录制工作线程已停止", room.identity)


__all__ = ["bootstrap_runtime", "shutdown_runtime", "ensure_runtime"]
