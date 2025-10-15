from __future__ import annotations

"""在旧逻辑与新服务之间搭建桥梁的兼容适配工具。"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .models import Room, RoomStatus
from .service import RoomService


@dataclass(slots=True)
class LegacyRoomSnapshot:
    active_entries: List[Tuple[str, str, str]]
    disabled_urls: List[str]


class LegacyRoomAdapter:
    def __init__(self, service: RoomService) -> None:
        self._service = service

    def load_snapshot(self) -> LegacyRoomSnapshot:
        rooms = self._service.rooms()
        duplicates = self._service.remove_duplicates()
        if duplicates:
            rooms = self._service.rooms()
        active: List[Tuple[str, str, str]] = []
        disabled: List[str] = []
        for room in rooms:
            entry = (room.quality, room.url, room.nickname)
            if room.status == RoomStatus.DISABLED:
                disabled.append(room.url)
            else:
                active.append(entry)
        return LegacyRoomSnapshot(active_entries=active, disabled_urls=disabled)

    def ensure_room(self, quality: str, url: str, nickname: str) -> Room:
        room = Room.from_config(quality=quality, url=url, nickname=nickname)
        try:
            return self._service.add_room(room)
        except ValueError:
            return self._service.update_room(room.identity, quality=quality, nickname=nickname)

    def disable_room(self, url: str) -> None:
        self._service.disable_room(url)

    def enable_room(self, url: str) -> None:
        self._service.enable_room(url)

    def update_room_url(self, old_url: str, new_url: str) -> Room:
        return self._service.update_room(old_url, url=new_url)
