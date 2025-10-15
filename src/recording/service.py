from __future__ import annotations

"""房间管理的协同服务。"""

import threading
from dataclasses import dataclass
from typing import Iterable, Optional

from .models import Room, RoomStatus
from .registry import RoomRegistry
from .repository import RepositorySnapshot, RoomRepository


@dataclass(slots=True)
class RoomDiff:
    added: list[Room]
    removed: list[Room]
    updated: list[tuple[Room, Room]]


class RoomService:
    """统筹仓库持久化与注册表更新流程。"""

    def __init__(self, repository: RoomRepository, registry: RoomRegistry) -> None:
        self._repository = repository
        self._registry = registry
        self._annotations: list[str] = []
        self._lock = threading.RLock()

    @property
    def annotations(self) -> list[str]:
        return list(self._annotations)

    def rooms(self) -> list[Room]:
        return self._registry.all()

    def remove_duplicates(self) -> list[Room]:
        with self._lock:
            snapshot = self._repository.load()
            seen: dict[str, Room] = {}
            filtered: list[Room] = []
            removed: list[Room] = []
            for room in snapshot.rooms:
                identity = room.identity
                if identity in seen:
                    removed.append(room)
                else:
                    seen[identity] = room
                    filtered.append(room)
            if removed:
                self._repository.save(filtered, annotations=snapshot.annotations)
                self._registry.bootstrap(filtered)
                self._annotations = list(snapshot.annotations)
            return removed

    def bootstrap(self) -> RepositorySnapshot:
        snapshot = self._repository.load()
        with self._lock:
            self._registry.bootstrap(snapshot.rooms)
            self._annotations = list(snapshot.annotations)
        return snapshot

    def sync_from_repository(self) -> RoomDiff:
        snapshot = self._repository.load()
        with self._lock:
            prev_rooms = {room.identity: room for room in self._registry.all()}
            new_rooms = {room.identity: room for room in snapshot.rooms}
            added: list[Room] = []
            removed: list[Room] = []
            updated: list[tuple[Room, Room]] = []

            for identity, room in new_rooms.items():
                existing = prev_rooms.pop(identity, None)
                if existing is None:
                    self._registry.upsert(room)
                    added.append(room)
                elif self._needs_update(existing, room):
                    merged = self._merge_room(existing, room)
                    self._registry.upsert(merged)
                    updated.append((existing, merged))

            for remaining in prev_rooms.values():
                self._registry.remove(remaining.identity)
                removed.append(remaining)

            self._annotations = list(snapshot.annotations)
        return RoomDiff(added=added, removed=removed, updated=updated)

    def add_room(self, room: Room) -> Room:
        with self._lock:
            persisted = self._repository.add_room(room)
            self._registry.upsert(persisted)
            return persisted

    def update_room(self, identity: str, **changes: object) -> Room:
        with self._lock:
            updated = self._repository.update_room(identity, **changes)
            self._registry.upsert(updated)
            return updated

    def remove_room(self, identity: str) -> None:
        with self._lock:
            self._repository.remove_room(identity)
            self._registry.remove(identity)

    def enable_room(self, identity: str) -> Room | None:
        with self._lock:
            try:
                updated = self._repository.enable_room(identity)
            except ValueError:
                return None
            self._registry.upsert(updated)
            return updated

    def disable_room(self, identity: str) -> Room | None:
        with self._lock:
            try:
                updated = self._repository.disable_room(identity)
            except ValueError:
                return None
            self._registry.upsert(updated)
            return updated

    def comment_room(self, identity: str, comment: str) -> Room | None:
        with self._lock:
            try:
                updated = self._repository.comment_room(identity, comment)
            except ValueError:
                return None
            self._registry.upsert(updated)
            return updated

    def _needs_update(self, existing: Room, incoming: Room) -> bool:
        return (
            existing.quality != incoming.quality
            or existing.nickname != incoming.nickname
            or existing.status != incoming.status
        )

    def _merge_room(self, existing: Room, incoming: Room) -> Room:
        status = incoming.status
        if status == RoomStatus.ACTIVE and existing.status == RoomStatus.RECORDING:
            status = RoomStatus.RECORDING
        return existing.copy_with(
            quality=incoming.quality,
            nickname=incoming.nickname,
            status=status,
            comment=incoming.comment,
        )
