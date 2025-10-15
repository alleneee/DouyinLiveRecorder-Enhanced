from __future__ import annotations

"""具备事件广播能力的内存房间注册表。"""

from dataclasses import dataclass
from enum import Enum
from queue import Queue
import threading
from typing import Dict, Iterable, List, Optional

from .models import Room, RoomStatus


class RoomEventType(str, Enum):
    ADDED = "added"
    UPDATED = "updated"
    REMOVED = "removed"
    DISABLED = "disabled"
    ENABLED = "enabled"


@dataclass(slots=True)
class RoomEvent:
    event_type: RoomEventType
    room: Room
    previous: Room | None = None


class RoomRegistry:
    """线程安全的房间注册表，会发布生命周期事件。"""

    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}
        self._lock = threading.RLock()
        self._listeners: List[Queue[RoomEvent]] = []

    def bootstrap(self, rooms: Iterable[Room]) -> None:
        with self._lock:
            self._rooms = {room.identity: room for room in rooms}

    def subscribe(self) -> Queue[RoomEvent]:
        listener: Queue[RoomEvent] = Queue()
        with self._lock:
            self._listeners.append(listener)
        return listener

    def unsubscribe(self, listener: Queue[RoomEvent]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def get(self, identity: str) -> Optional[Room]:
        with self._lock:
            return self._rooms.get(identity.rstrip("/"))

    def all(self) -> List[Room]:
        with self._lock:
            return list(self._rooms.values())

    def upsert(self, room: Room) -> Room:
        with self._lock:
            identity = room.identity
            previous = self._rooms.get(identity)
            self._rooms[identity] = room
            if previous is None:
                self._publish(RoomEvent(RoomEventType.ADDED, room, previous=None))
            else:
                if previous.status != room.status:
                    if room.status == RoomStatus.DISABLED:
                        self._publish(RoomEvent(RoomEventType.DISABLED, room, previous=previous))
                    elif previous.status == RoomStatus.DISABLED and room.status != RoomStatus.DISABLED:
                        self._publish(RoomEvent(RoomEventType.ENABLED, room, previous=previous))
                    else:
                        self._publish(RoomEvent(RoomEventType.UPDATED, room, previous=previous))
                else:
                    self._publish(RoomEvent(RoomEventType.UPDATED, room, previous=previous))
        return room

    def remove(self, identity: str) -> None:
        normalized = identity.rstrip("/")
        with self._lock:
            previous = self._rooms.pop(normalized, None)
            if previous:
                self._publish(RoomEvent(RoomEventType.REMOVED, previous, previous=None))

    def mark_disabled(self, identity: str) -> Room | None:
        with self._lock:
            room = self._rooms.get(identity.rstrip("/"))
            if not room:
                return None
            updated = room.copy_with(status=RoomStatus.DISABLED)
            self._rooms[updated.identity] = updated
            self._publish(RoomEvent(RoomEventType.DISABLED, updated, previous=room))
            return updated

    def mark_enabled(self, identity: str) -> Room | None:
        with self._lock:
            room = self._rooms.get(identity.rstrip("/"))
            if not room:
                return None
            updated = room.copy_with(status=RoomStatus.ACTIVE)
            self._rooms[updated.identity] = updated
            self._publish(RoomEvent(RoomEventType.ENABLED, updated, previous=room))
            return updated

    def _publish(self, event: RoomEvent) -> None:
        listeners_snapshot: List[Queue[RoomEvent]]
        with self._lock:
            listeners_snapshot = list(self._listeners)
        for listener in listeners_snapshot:
            listener.put(event)
