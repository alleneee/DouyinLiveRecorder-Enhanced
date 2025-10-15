from __future__ import annotations

"""录制系统的高层应用装配逻辑。"""

from pathlib import Path
from typing import Callable, Optional

from .context import RecordingContext, set_context
from .models import Room
from .registry import RoomRegistry
from .repository import RoomRepository
from .service import RoomService
from .supervisor import RecordingSupervisor, WorkerFactory
from .watchers import FilePollingWatcher, RoomCommandInterface


class RecordingApplication:
    def __init__(
        self,
        config_path: Path | None,
        worker_factory: WorkerFactory,
        *,
        repository: RoomRepository | None = None,
        enable_cli: bool = False,
        enable_file_watcher: bool = True,
        file_watch_interval: float = 3.0,
    ) -> None:
        self._repository = repository or RoomRepository(config_path or Path("config/URL_config.ini"))
        self._registry = RoomRegistry()
        self._service = RoomService(self._repository, self._registry)
        self._service.bootstrap()
        self._supervisor = RecordingSupervisor(self._registry, worker_factory)
        self._watcher = (
            FilePollingWatcher(config_path, self._service, interval=file_watch_interval)
            if enable_file_watcher and config_path is not None
            else None
        )
        self._cli = RoomCommandInterface(self._service) if enable_cli else None
        set_context(
            RecordingContext(
                repository=self._repository,
                registry=self._registry,
                service=self._service,
                supervisor=self._supervisor,
            )
        )

    @property
    def service(self) -> RoomService:
        return self._service

    @property
    def supervisor(self) -> RecordingSupervisor:
        return self._supervisor

    def start(self) -> None:
        self._supervisor.start()
        if self._watcher:
            self._watcher.start()
        if self._cli:
            self._cli.start()

    def stop(self) -> None:
        if self._watcher:
            self._watcher.stop()
        if self._cli:
            self._cli.stop()
        self._supervisor.stop()


def build_application(
    config_file: Path | str | None,
    *,
    worker_factory: Optional[WorkerFactory] = None,
    repository: RoomRepository | None = None,
    enable_cli: bool = False,
    enable_file_watcher: bool = True,
    file_watch_interval: float = 3.0,
) -> RecordingApplication:
    path = Path(config_file) if config_file is not None else None
    if worker_factory is None:
        def worker(room: Room, stop_event):
            raise RuntimeError("Worker factory is not provided")

        worker_factory = lambda room, stop_event: worker(room, stop_event)  # type: ignore[return-value]
    app = RecordingApplication(
        path,
        worker_factory,
        repository=repository,
        enable_cli=enable_cli,
        enable_file_watcher=enable_file_watcher,
        file_watch_interval=file_watch_interval,
    )
    return app
