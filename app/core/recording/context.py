from __future__ import annotations

"""录制组件共享的运行时上下文。"""

from dataclasses import dataclass
from typing import Optional

from .repository import RoomRepository
from .registry import RoomRegistry
from .service import RoomService
from .supervisor import RecordingSupervisor


@dataclass(slots=True)
class RecordingContext:
    repository: RoomRepository
    registry: RoomRegistry
    service: RoomService
    supervisor: RecordingSupervisor


_context: Optional[RecordingContext] = None


def set_context(context: RecordingContext) -> None:
    global _context
    _context = context


def get_context() -> RecordingContext:
    if _context is None:
        raise RuntimeError("Recording context has not been initialized")
    return _context
