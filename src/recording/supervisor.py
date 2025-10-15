from __future__ import annotations

"""事件驱动的录制调度器。"""

import threading
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Callable, Dict, Optional

from .models import Room
from .registry import RoomEvent, RoomEventType, RoomRegistry


WorkerFactory = Callable[[Room, threading.Event], threading.Thread]


@dataclass(slots=True)
class _WorkerHandle:
    room: Room
    thread: threading.Thread
    stop_event: threading.Event


class RecordingSupervisor:
    """根据注册表事件派发录制工作线程。"""

    def __init__(
        self,
        registry: RoomRegistry,
        worker_factory: WorkerFactory,
        *,
        poll_interval: float = 0.5,
    ) -> None:
        self._registry = registry
        self._worker_factory = worker_factory
        self._poll_interval = poll_interval
        self._listener: Queue[RoomEvent] | None = None
        self._dispatcher_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._workers: Dict[str, _WorkerHandle] = {}
        self._lock = threading.RLock()

    def start(self) -> None:
        if self._dispatcher_thread and self._dispatcher_thread.is_alive():
            return
        self._listener = self._registry.subscribe()
        self._dispatcher_thread = threading.Thread(target=self._run_loop, name="RecordingSupervisor")
        self._dispatcher_thread.daemon = True
        self._dispatcher_thread.start()
        for room in list(self._registry.all()):
            if room.is_active():
                self._ensure_worker(room)

    def stop(self, *, wait: bool = True) -> None:
        self._stop_event.set()
        if self._dispatcher_thread and wait:
            self._dispatcher_thread.join()
        with self._lock:
            for handle in list(self._workers.values()):
                handle.stop_event.set()
            if wait:
                for handle in list(self._workers.values()):
                    handle.thread.join()
            self._workers.clear()
        if self._listener:
            self._registry.unsubscribe(self._listener)
            self._listener = None

    def _run_loop(self) -> None:
        assert self._listener is not None
        listener = self._listener
        while not self._stop_event.is_set():
            try:
                event = listener.get(timeout=self._poll_interval)
            except Empty:
                continue
            self._handle_event(event)

    def _handle_event(self, event: RoomEvent) -> None:
        if event.event_type in (RoomEventType.ADDED, RoomEventType.ENABLED):
            if event.room.is_active():
                self._ensure_worker(event.room)
        elif event.event_type == RoomEventType.UPDATED:
            if self._should_refresh(event):
                self._refresh_worker(event.room)
        elif event.event_type in (RoomEventType.DISABLED, RoomEventType.REMOVED):
            self._stop_worker(event.room.identity)

    def _ensure_worker(self, room: Room) -> None:
        with self._lock:
            if room.identity in self._workers:
                return
            stop_event = threading.Event()
            thread = self._worker_factory(room, stop_event)
            handle = _WorkerHandle(room=room, thread=thread, stop_event=stop_event)
            self._workers[room.identity] = handle
            thread.daemon = True
            thread.start()

    def _refresh_worker(self, room: Room) -> None:
        self._stop_worker(room.identity)
        if room.is_active():
            self._ensure_worker(room)

    def _stop_worker(self, identity: str) -> None:
        with self._lock:
            handle = self._workers.pop(identity.rstrip("/"), None)
        if not handle:
            return
        handle.stop_event.set()
        handle.thread.join()

    @staticmethod
    def _should_refresh(event: RoomEvent) -> bool:
        previous = event.previous
        if not previous:
            return True
        if previous.url != event.room.url:
            return True
        if previous.quality != event.room.quality:
            return True
        return False

    def worker_count(self) -> int:
        with self._lock:
            return len(self._workers)

    def running_rooms(self) -> list[Room]:
        with self._lock:
            return [handle.room for handle in self._workers.values()]


def legacy_worker_factory(task: Callable[[Room, threading.Event], None]) -> WorkerFactory:
    """用于将旧版逻辑适配成工作线程工厂的辅助方法。"""

    def factory(room: Room, stop_event: threading.Event) -> threading.Thread:
        thread = threading.Thread(target=task, args=(room, stop_event), name=f"Recorder-{room.identity}")
        return thread

    return factory
