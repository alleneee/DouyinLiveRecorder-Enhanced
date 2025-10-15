from __future__ import annotations

"""基于 URL_config.ini 的房间仓库实现。"""

from dataclasses import dataclass, field
from pathlib import Path
import re
import threading
from typing import Iterable, List, Sequence

from .models import Room, RoomQuality, RoomStatus


def _ensure_scheme(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        return "https://" + url
    return url


@dataclass(slots=True)
class ParsedLine:
    room: Room | None
    annotation: str | None


@dataclass(slots=True)
class RepositorySnapshot:
    rooms: list[Room] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)

    def active_rooms(self) -> list[Room]:
        return [room for room in self.rooms if room.is_active()]


class RoomRepository:
    """对 URL_config.ini 的线程安全抽象。"""

    def __init__(self, path: Path | str, *, encoding: str = "utf-8-sig"):
        self._path = Path(path)
        self._encoding = encoding
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("", encoding=self._encoding)

    def load(self) -> RepositorySnapshot:
        with self._lock:
            rooms: list[Room] = []
            annotations: list[str] = []
            with self._path.open("r", encoding=self._encoding, errors="ignore") as file:
                for idx, raw in enumerate(file):
                    parsed = self._parse_line(raw.rstrip("\n"), idx)
                    if parsed.room:
                        rooms.append(parsed.room)
                    if parsed.annotation:
                        annotations.append(parsed.annotation)
        return RepositorySnapshot(rooms=rooms, annotations=annotations)

    def save(self, rooms: Sequence[Room], *, annotations: Sequence[str] | None = None) -> None:
        with self._lock:
            lines: List[str] = []
            if annotations:
                lines.extend([f"# {note}" for note in annotations])
            ordered_rooms = sorted(
                rooms,
                key=lambda room: room.line_index if room.line_index is not None else len(rooms),
            )
            for idx, room in enumerate(ordered_rooms):
                if room.line_index != idx:
                    room = room.copy_with(line_index=idx)
                lines.append(room.to_config_line())
            content = "\n".join(lines) + ("\n" if lines else "")
            tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp_path.write_text(content, encoding=self._encoding)
            tmp_path.replace(self._path)

    def add_room(self, room: Room) -> Room:
        with self._lock:
            snapshot = self.load()
            existing = self._find_by_identity(snapshot.rooms, room.identity)
            if existing:
                raise ValueError(f"Room already exists for URL: {room.url}")
            room = room.copy_with(line_index=len(snapshot.rooms))
            snapshot.rooms.append(room)
            self.save(snapshot.rooms, annotations=snapshot.annotations)
            return room

    def update_room(self, identity: str, **changes: object) -> Room:
        with self._lock:
            snapshot = self.load()
            room = self._find_by_identity(snapshot.rooms, identity)
            if not room:
                raise ValueError(f"Room not found: {identity}")
            if "url" in changes and isinstance(changes["url"], str):
                changes["url"] = _ensure_scheme(changes["url"])
                new_identity = changes["url"].rstrip("/")
                existing = self._find_by_identity(snapshot.rooms, new_identity)
                if existing and existing.line_index != room.line_index:
                    raise ValueError(f"Room already exists for URL: {changes['url']}")
            updated = room.copy_with(**changes)
            snapshot.rooms = [updated if r.identity == identity else r for r in snapshot.rooms]
            self.save(snapshot.rooms, annotations=snapshot.annotations)
            return updated

    def remove_room(self, identity: str) -> None:
        with self._lock:
            snapshot = self.load()
            filtered = [room for room in snapshot.rooms if room.identity != identity]
            if len(filtered) == len(snapshot.rooms):
                raise ValueError(f"Room not found: {identity}")
            self.save(filtered, annotations=snapshot.annotations)

    def comment_room(self, identity: str, comment: str) -> Room:
        return self.update_room(identity, comment=comment)

    def disable_room(self, identity: str) -> Room:
        return self.update_room(identity, status=RoomStatus.DISABLED)

    def enable_room(self, identity: str) -> Room:
        return self.update_room(identity, status=RoomStatus.ACTIVE)

    def _parse_line(self, line: str, index: int) -> ParsedLine:
        stripped = line.strip()
        if not stripped:
            return ParsedLine(room=None, annotation=None)

        is_disabled = False
        comment_note: str | None = None

        if stripped.startswith("#"):
            is_disabled = True
            stripped = stripped.lstrip("#").strip()
            if not stripped:
                return ParsedLine(room=None, annotation=None)

        # Split comment at inline '#'
        line_body, inline_comment = self._split_inline_comment(stripped)
        if inline_comment:
            comment_note = inline_comment
        parts = [segment.strip() for segment in re.split(r"[,，]", line_body) if segment.strip()]

        if not parts:
            return ParsedLine(room=None, annotation=None)

        if len(parts) == 1:
            quality = RoomQuality.ORIGINAL.value
            url = parts[0]
            nickname = ""
        elif len(parts) == 2:
            if self._looks_like_url(parts[0]):
                quality = RoomQuality.ORIGINAL.value
                url, nickname = parts
            else:
                quality, url = parts
                nickname = ""
        else:
            quality, url, nickname = parts[0], parts[1], parts[2]

        if not self._looks_like_url(url):
            annotation = f"Invalid URL on line {index + 1}: {line_body}"
            return ParsedLine(room=None, annotation=annotation)

        url = _ensure_scheme(url)
        nickname = self._normalize_nickname(nickname)
        status = RoomStatus.DISABLED if is_disabled else RoomStatus.ACTIVE
        room = Room.from_config(
            quality=quality,
            url=url,
            nickname=nickname,
            status=status,
            line_index=index,
            comment=comment_note,
        )
        return ParsedLine(room=room, annotation=None)

    @staticmethod
    def _split_inline_comment(value: str) -> tuple[str, str | None]:
        if "#" not in value:
            return value, None
        body, _, comment = value.partition("#")
        comment = comment.strip()
        return body.strip(), comment or None

    @staticmethod
    def _normalize_nickname(nickname: str) -> str:
        if not nickname:
            return ""
        if nickname.startswith("主播"):
            _, _, suffix = nickname.partition(":")
            return suffix.strip() or nickname
        return nickname

    @staticmethod
    def _looks_like_url(value: str) -> bool:
        pattern = re.compile(r"(https?://)?[\w.-]+(\.[\w.-]+)+(?:/[^\s]*)?")
        return bool(pattern.match(value.strip()))

    @staticmethod
    def _find_by_identity(rooms: Iterable[Room], identity: str) -> Room | None:
        normalized = identity.rstrip("/")
        for room in rooms:
            if room.identity == normalized:
                return room
        return None
