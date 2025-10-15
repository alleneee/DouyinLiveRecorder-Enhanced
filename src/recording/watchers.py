from __future__ import annotations

"""兼容旧版逻辑的文件与命令监控组件。"""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .service import RoomDiff, RoomService


class FilePollingWatcher:
    def __init__(
        self,
        path: Path | str,
        service: RoomService,
        *,
        interval: float = 2.0,
        on_change: Optional[Callable[[RoomDiff], None]] = None,
    ) -> None:
        self._path = Path(path)
        self._service = service
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_mtime: float | None = None
        self._on_change = on_change

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._last_mtime = self._get_mtime()
        self._thread = threading.Thread(target=self._run, name="RoomFileWatcher", daemon=True)
        self._thread.start()

    def stop(self, *, wait: bool = True) -> None:
        self._stop_event.set()
        if self._thread and wait:
            self._thread.join()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(self._interval)
            current_mtime = self._get_mtime()
            if current_mtime is None:
                continue
            if self._last_mtime is None or current_mtime > self._last_mtime:
                diff = self._service.sync_from_repository()
                if self._on_change:
                    self._on_change(diff)
                self._last_mtime = current_mtime

    def _get_mtime(self) -> Optional[float]:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            return None


class RoomCommandInterface:
    """提供运行期房间管理的简易命令行通道。"""

    def __init__(self, service: RoomService, *, prompt: str = "room> ") -> None:
        self._service = service
        self._prompt = prompt
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="RoomCLI", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                command_line = input(self._prompt)
            except EOFError:
                break
            if not command_line:
                continue
            command, *args = command_line.strip().split()
            command = command.lower()
            if command in {"exit", "quit"}:
                self._stop_event.set()
                break
            if command == "list":
                self._handle_list()
            elif command == "add":
                self._handle_add(args)
            elif command == "remove":
                self._handle_remove(args)
            elif command == "disable":
                self._handle_disable(args)
            elif command == "enable":
                self._handle_enable(args)
            else:
                print("未知命令，可用命令: list/add/remove/disable/enable/quit")

    def _handle_list(self) -> None:
        rooms = self._service.rooms()
        if not rooms:
            print("当前无房间")
            return
        for room in rooms:
            print(f"- {room.quality} | {room.url} | {room.nickname or '-'} | {room.status.value}")

    def _handle_add(self, args: list[str]) -> None:
        if len(args) < 2:
            print("用法: add <清晰度> <URL> [主播昵称]")
            return
        quality, url, *nickname = args
        nickname_value = " ".join(nickname)
        try:
            from .models import Room

            room = Room.from_config(quality=quality, url=url, nickname=nickname_value)
            persisted = self._service.add_room(room)
            print(f"已添加: {persisted.url}")
        except ValueError as exc:
            print(f"添加失败: {exc}")

    def _handle_remove(self, args: list[str]) -> None:
        if not args:
            print("用法: remove <URL>")
            return
        identity = args[0]
        try:
            self._service.remove_room(identity)
            print(f"已移除: {identity}")
        except ValueError as exc:
            print(f"移除失败: {exc}")

    def _handle_disable(self, args: list[str]) -> None:
        if not args:
            print("用法: disable <URL>")
            return
        result = self._service.disable_room(args[0])
        if result:
            print(f"已禁用: {result.url}")
        else:
            print("禁用失败: 未找到房间")

    def _handle_enable(self, args: list[str]) -> None:
        if not args:
            print("用法: enable <URL>")
            return
        result = self._service.enable_room(args[0])
        if result:
            print(f"已启用: {result.url}")
        else:
            print("启用失败: 未找到房间")
