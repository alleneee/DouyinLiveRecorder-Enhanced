"""FastAPI 依赖注入定义。"""

from collections.abc import Generator

from fastapi import Depends

from app.runtime import ensure_runtime
from app.services.unit_of_work import UnitOfWork
from src.recording.context import RecordingContext


def get_uow() -> Generator[UnitOfWork, None, None]:
    with UnitOfWork() as uow:
        yield uow


def get_recording_context() -> RecordingContext:
    return ensure_runtime()


__all__ = ["get_uow", "get_recording_context"]
