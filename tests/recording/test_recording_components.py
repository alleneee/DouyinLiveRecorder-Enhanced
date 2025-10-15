from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
import threading

from src.recording.legacy_adapter import LegacyRoomAdapter
from src.recording.repository import RoomRepository
from src.recording.registry import RoomRegistry
from src.recording.service import RoomService
from src.recording.supervisor import RecordingSupervisor, legacy_worker_factory


def write_config(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


class RecordingComponentsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "URL_config.ini"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repository_parses_rooms(self) -> None:
        write_config(
            self.config_path,
            """
            原画,https://live.douyin.com/12345,主播: 主播A
            蓝光,live.kuaishou.com/67890,主播: 主播B
            # https://live.douyin.com/24680,主播: 主播C
            """,
        )

        repo = RoomRepository(self.config_path)
        snapshot = repo.load()

        self.assertEqual(len(snapshot.rooms), 3)
        active = [room for room in snapshot.rooms if room.is_active()]
        disabled = [room for room in snapshot.rooms if room.status.value == "disabled"]

        self.assertEqual(len(active), 2)
        self.assertEqual(len(disabled), 1)
        self.assertTrue(active[1].url.startswith("https://"))
        self.assertEqual(active[1].quality, "蓝光")
        self.assertEqual(disabled[0].nickname, "主播C")

    def test_repository_add_update_disable_remove(self) -> None:
        write_config(
            self.config_path,
            """
            原画,https://live.douyin.com/12345,主播: 主播A
            """,
        )

        repo = RoomRepository(self.config_path)
        snapshot = repo.load()
        room = snapshot.rooms[0]

        repo.add_room(room.copy_with(url="https://live.douyin.com/67890", nickname="主播B"))
        updated = repo.update_room(room.identity, nickname="主播A-修改")
        self.assertEqual(updated.nickname, "主播A-修改")

        repo.disable_room(updated.identity)
        disabled = repo.load().rooms[0]
        self.assertEqual(disabled.status.value, "disabled")

        repo.remove_room("https://live.douyin.com/67890")
        remaining = repo.load().rooms
        self.assertEqual(len(remaining), 1)

    def test_service_remove_duplicates(self) -> None:
        write_config(
            self.config_path,
            """
            原画,https://live.douyin.com/12345,主播: 主播A
            原画,https://live.douyin.com/12345,主播: 主播A-重复
            蓝光,https://live.douyin.com/67890,主播: 主播B
            """,
        )

        repo = RoomRepository(self.config_path)
        registry = RoomRegistry()
        service = RoomService(repo, registry)
        service.bootstrap()

        removed = service.remove_duplicates()
        self.assertTrue(removed)
        rooms = service.rooms()
        self.assertEqual(len(rooms), 2)
        identities = {room.identity for room in rooms}
        self.assertEqual(identities, {"https://live.douyin.com/12345", "https://live.douyin.com/67890"})

    def test_legacy_adapter_snapshot(self) -> None:
        write_config(
            self.config_path,
            """
            原画,https://live.douyin.com/12345,主播: 主播A
            # https://live.douyin.com/67890,主播: 主播B
            """,
        )

        repo = RoomRepository(self.config_path)
        registry = RoomRegistry()
        service = RoomService(repo, registry)
        service.bootstrap()

        adapter = LegacyRoomAdapter(service)
        snapshot = adapter.load_snapshot()

        self.assertEqual(snapshot.disabled_urls, ["https://live.douyin.com/67890"])
        self.assertEqual(snapshot.active_entries, [("原画", "https://live.douyin.com/12345", "主播A")])

    def test_supervisor_start_and_stop_workers(self) -> None:
        write_config(
            self.config_path,
            """
            原画,https://live.douyin.com/12345,主播: 主播A
            """,
        )

        repo = RoomRepository(self.config_path)
        registry = RoomRegistry()
        service = RoomService(repo, registry)
        service.bootstrap()

        started_event = threading.Event()
        stopped_event = threading.Event()

        def worker(room, stop_event):
            started_event.set()
            stop_event.wait(0.1)
            stopped_event.set()

        supervisor = RecordingSupervisor(registry, legacy_worker_factory(worker))
        supervisor.start()

        self.assertTrue(started_event.wait(1.0), "worker should start after supervisor begins")

        service.disable_room("https://live.douyin.com/12345")
        self.assertTrue(stopped_event.wait(1.0), "worker should stop after room disabled")

        supervisor.stop()


if __name__ == "__main__":
    unittest.main()
