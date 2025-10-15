"""录制运行时生命周期管理。"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Awaitable, Callable, Optional

from app.core.logging_config import setup_logging
from app.recording.environment import RecordingEnvironment, load_environment
from app.db.session import get_session
from app.services.recording_service import RecordingService
from app.services.room_service import RoomService
from app.services.repository import DatabaseRoomRepository
from app.core.recording.app import RecordingApplication, build_application
from app.core.recording.context import RecordingContext, get_context
from app.core.recording.models import Room, RoomStatus
from app.core.recording.segment_worker import SegmentRecordingWorker
from app.core.recording.continuous_worker import ContinuousRecordingWorker
from app.core.recording.supervisor import thread_worker_factory
from app.core.platforms.legacy_adapter import LegacyPlatformHandler
from app.models.room import RoomORM
from app.worker_factory import (
    build_continuous_config,
    build_platform_handler,
    build_segment_config,
)

logger = logging.getLogger("app.runtime")

_application: Optional[RecordingApplication] = None
_runtime_env: Optional[RecordingEnvironment] = None


def _ensure_environment() -> RecordingEnvironment:
    """懒加载录制配置环境。"""

    global _runtime_env
    if _runtime_env is None:
        config_dir = Path(__file__).resolve().parents[2] / "config"
        _runtime_env = load_environment(config_dir)
    return _runtime_env


def bootstrap_runtime() -> RecordingContext:
    """确保录制运行时初始化并返回上下文。"""

    global _application

    setup_logging(log_level="INFO", enable_console=True, enable_file=True, debug_mode=False)

    if _application is not None:
        return get_context()

    _ensure_environment()
    repository = DatabaseRoomRepository()
    application = build_application(
        config_file=None,
        worker_factory=thread_worker_factory(_worker_entry),
        repository=repository,
        enable_file_watcher=False,
    )
    application.start()
    _application = application
    logger.info("录制运行时已启动")
    return get_context()


def ensure_runtime() -> RecordingContext:
    try:
        return get_context()
    except RuntimeError:
        return bootstrap_runtime()


def shutdown_runtime() -> None:
    global _application
    global _runtime_env
    if _application is None:
        return
    _application.stop()
    _application = None
    _runtime_env = None
    logger.info("录制运行时已关闭")


def _worker_entry(room: Room, stop_event: threading.Event) -> None:
    """原生录制工作线程入口。"""

    worker_logger = logging.getLogger("app.runtime.worker")
    env = _ensure_environment()
    failure_reason: Optional[str] = None
    latest_file: dict[str, Optional[str]] = {"path": None}
    orm: Optional[RoomORM] = None

    try:
        with get_session() as session:
            data_service = RoomService(session)
            orm = data_service.get_room_by_identity(room.identity)
            if orm is None:
                worker_logger.error("未找到房间 %s，对应录制线程退出", room.identity)
                return

            rec_service = RecordingService(session)
            rec_service.start_recording(orm.id)
            worker_logger.info("录制已启动: room_id=%s", orm.id)

        handler = build_platform_handler(env)
        runner = _create_worker_runner(
            room=room,
            orm=orm,
            env=env,
            handler=handler,
            stop_event=stop_event,
            latest_file=latest_file,
        )

        worker_logger.info("房间 %s 的录制工作线程已启动", room.identity)
        _run_async_worker(runner)
    except Exception as exc:  # noqa: BLE001
        failure_reason = str(exc)
        worker_logger.exception("房间 %s 的录制工作线程失败", room.identity)
    finally:
        if orm is not None:
            with get_session() as session:
                rec_service = RecordingService(session)
                rec_service.stop_recording(orm.id, error_message=failure_reason)
            
            worker_logger.info("房间 %s 的录制工作线程已停止", room.identity)


def _create_worker_runner(
    *,
    room: Room,
    orm: RoomORM,
    env: RecordingEnvironment,
    handler: LegacyPlatformHandler,
    stop_event: threading.Event,
    latest_file: dict[str, Optional[str]],
) -> Callable[[], Awaitable[None]]:

    if orm.enable_segment_recording:
        config = build_segment_config(env=env, room=orm)

        worker = SegmentRecordingWorker(
            room=room,
            handler=handler,
            config=config,
            on_segment_complete=lambda file_path, _data: latest_file.__setitem__("path", file_path),
        )

        async def runner() -> None:
            await worker.start(stop_event)

    else:
        config = build_continuous_config(env=env, room=orm)

        worker = ContinuousRecordingWorker(
            room=room,
            handler=handler,
            config=config,
            on_complete=lambda file_path: latest_file.__setitem__("path", file_path),
        )

        async def runner() -> None:
            await worker.start(stop_event)

    return runner


def _run_async_worker(coro_factory: Callable[[], Awaitable[None]]) -> None:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro_factory())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:  # noqa: BLE001
            pass
        asyncio.set_event_loop(None)
        loop.close()


__all__ = ["bootstrap_runtime", "shutdown_runtime", "ensure_runtime"]
