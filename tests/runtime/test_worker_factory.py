from __future__ import annotations

import configparser
from pathlib import Path

from app.runtime.worker_factory import (
    build_continuous_config,
    build_cookies_map,
    build_platform_handler,
    build_segment_config,
)
from app.recording.environment import RecordingEnvironment, RecordingOptions, PushConfig
from app.models.room import RoomORM


def _create_environment(tmp_path: Path) -> RecordingEnvironment:
    parser = configparser.RawConfigParser()
    parser.add_section("Cookie")
    parser.set("Cookie", "抖音cookie", "COOKIE_VALUE")
    parser.set("Cookie", "extra_key", "EXTRA")

    options = RecordingOptions(
        folder_by_author=True,
        folder_by_time=False,
        folder_by_title=False,
        filename_by_title=False,
        clean_emoji=True,
        video_save_path=tmp_path / "downloads",
        video_save_type="TS",
        video_record_quality="OD",
        split_video_by_time=False,
        enable_https_recording=True,
        disk_space_limit=1.0,
        split_time=60,
        converts_to_mp4=False,
        converts_to_h264=False,
        delete_origin_file=True,
        create_time_file=False,
        use_proxy=True,
        proxy_addr="http://localhost:8080",
        max_request=3,
        loop_interval=30,
        enable_proxy_platforms=[],
        extra_proxy_platforms=[],
        queue_delay=0,
    )

    push = PushConfig(
        enabled=False,
        channel=None,
        options={},
        title="",
        begin_template="",
        end_template="",
        begin_enable=False,
        end_enable=False,
        disable_record=False,
        frequency_seconds=60,
    )

    return RecordingEnvironment(
        config_path=tmp_path / "config.ini",
        parser=parser,
        options=options,
        push=push,
        cookies={},
    )


def _create_room(enable_segment: bool = True) -> RoomORM:
    return RoomORM(
        url="https://live.example.com/123",
        nickname="主播",
        quality="OD",
        status="active",
        comment=None,
        enable_segment_recording=enable_segment,
        segment_duration=120,
        video_save_type="TS",
        oss_enabled=True,
        run_post_process=not enable_segment,
    )


def test_build_cookies_map(tmp_path) -> None:
    env = _create_environment(tmp_path)
    cookies = build_cookies_map(env)
    assert cookies["dy_cookie"] == "COOKIE_VALUE"
    assert cookies["extra_key"] == "EXTRA"


def test_build_platform_handler_uses_proxy(tmp_path) -> None:
    env = _create_environment(tmp_path)
    handler = build_platform_handler(env)
    assert handler.proxy_addr == "http://localhost:8080"
    assert handler.cookies_map["dy_cookie"] == "COOKIE_VALUE"


def test_segment_config_respects_room_settings(tmp_path) -> None:
    env = _create_environment(tmp_path)
    room = _create_room(enable_segment=True)
    config = build_segment_config(env=env, room=room)

    assert config.segment_duration == 120
    assert config.video_save_type == "TS"
    assert config.folder_by_author is True
    assert config.oss_enabled is True


def test_continuous_config_respects_post_process(tmp_path) -> None:
    env = _create_environment(tmp_path)
    room = _create_room(enable_segment=False)
    config = build_continuous_config(env=env, room=room)

    assert config.video_save_type == "TS"
    assert config.converts_to_mp4 is True
    assert config.delete_origin_file is True
