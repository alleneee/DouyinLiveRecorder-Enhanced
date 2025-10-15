"""后处理流程的端到端编排。"""

from __future__ import annotations

import datetime
import json
import os
import time
from typing import Any

from config_reader import ConfigReader

from .cleanup import PostProcessCleaner
from .logging import log_post_process, logger
from .media import MediaProcessor
from .notifier import PostProcessNotifier
from .upload import OSSUploader


class PostProcessPipeline:
    """统筹媒体生成、上传、通知及清理环节。"""

    def __init__(self, config: ConfigReader) -> None:
        self._config = config
        self._media = MediaProcessor(config)
        self._uploader: OSSUploader | None = None
        self._notifier = PostProcessNotifier()
        self._cleaner = PostProcessCleaner()

    @property
    def config(self) -> ConfigReader:
        return self._config

    def run(self, args) -> None:
        ts_file_path = args.save_file_path

        if not os.path.exists(ts_file_path):
            logger.error("文件不存在: %s", ts_file_path)
            return

        if not ts_file_path.lower().endswith(".ts"):
            logger.warning("不是TS文件，跳过处理: %s", ts_file_path)
            return

        self._config.print_config_summary()

        output_base_dir = os.path.join(os.path.dirname(ts_file_path), "processed")
        os.makedirs(output_base_dir, exist_ok=True)

        oss_config = self._load_oss_config(args)
        self._uploader = OSSUploader(oss_config)

        files_to_upload: list[str] = []
        uploaded_files: list[dict[str, Any]] = []

        if os.path.exists(ts_file_path):
            files_to_upload.append(ts_file_path)

        try:
            cover_image_path = self._media.extract_first_frame_cover(ts_file_path, output_base_dir)
            if cover_image_path:
                files_to_upload.append(cover_image_path)
        except Exception as exc:  # pragma: no cover - defensive logging
            log_post_process(f"封面图片提取失败: {exc}", "error")

        m3u8_path: str | None = None
        if self._config.is_generate_m3u8():
            try:
                m3u8_path = self._media.convert_ts_to_m3u8(ts_file_path, output_base_dir)
                files_to_upload.append(m3u8_path)

                m3u8_dir = os.path.dirname(m3u8_path)
                original_filename_base = os.path.splitext(os.path.basename(ts_file_path))[0]

                for file_name in os.listdir(m3u8_dir):
                    if file_name.endswith(".ts"):
                        if "_" in file_name and file_name != os.path.basename(ts_file_path):
                            file_base = file_name.rsplit("_", 1)[0]
                            if file_base == original_filename_base:
                                ts_segment_path = os.path.join(m3u8_dir, file_name)
                                files_to_upload.append(ts_segment_path)

                segment_count = sum(
                    1
                    for path in files_to_upload
                    if path.endswith(".ts") and path not in {ts_file_path, m3u8_path}
                )
                log_post_process(f"找到 {segment_count} 个TS切片文件", "debug")
            except Exception as exc:  # pragma: no cover - defensive logging
                log_post_process(f"M3U8转换失败: {exc}", "error")

        if self._config.is_extract_audio():
            try:
                actual_duration = None
                if m3u8_path and os.path.exists(m3u8_path):
                    actual_duration = self._media.get_m3u8_total_duration(m3u8_path)
                    log_post_process(
                        f"使用M3U8实际时长进行音频提取: {actual_duration}秒",
                        "debug",
                    )

                audio_files = self._media.extract_and_split_audio(ts_file_path, output_base_dir)

                if actual_duration and audio_files:
                    log_post_process(f"M3U8时长: {actual_duration:.3f}秒", "debug")
                    log_post_process(
                        "注意：如果音频时长与M3U8时长不一致，可能是原始TS文件的音频流不完整",
                        "debug",
                    )
                files_to_upload.extend(audio_files)
            except Exception as exc:  # pragma: no cover - defensive logging
                log_post_process(f"音频提取失败: {exc}", "error")

        if self._should_upload(oss_config, files_to_upload):
            files_info = self._build_files_info(
                files_to_upload,
                ts_file_path,
                args.record_name or "unknown",
                args.room_id or "unknown",
                args.record_start_time,
            )
            log_post_process(f"开始OSS上传: {len(files_info)} 个文件")
            uploaded_files = self._uploader.upload_many(files_info)

        api_success = False
        if uploaded_files:
            try:
                api_success = self._notifier.notify(args, uploaded_files, oss_config)
            except Exception as exc:  # pragma: no cover - defensive logging
                log_post_process(f"API通知失败: {exc}", "error")

        if self._config.is_delete_local_files_after_upload():
            if uploaded_files and api_success:
                try:
                    self._cleaner.cleanup(uploaded_files, ts_file_path)
                except Exception as exc:  # pragma: no cover - defensive logging
                    log_post_process(f"文件清理失败: {exc}", "error")
            elif uploaded_files and not api_success:
                log_post_process("API通知失败，保留本地文件", "info")
            elif not uploaded_files:
                log_post_process("OSS上传失败，保留本地文件", "info")
        else:
            log_post_process("配置为不删除本地文件，保留所有文件", "info")

        log_post_process("后处理完成")

    def _load_oss_config(self, args) -> dict[str, Any]:
        oss_config = self._config.get_oss_config_dict()
        if not oss_config.get("access_key_id") and os.path.exists(args.oss_config_file):
            try:
                with open(args.oss_config_file, "r", encoding="utf-8") as handle:
                    json_config = json.load(handle)
                    if "oss_config" in json_config:
                        oss_config.update(json_config["oss_config"])
                        logger.warning("从JSON文件读取OSS配置（建议迁移到config.ini）")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("读取OSS配置文件失败: %s", exc)
        return oss_config

    def _should_upload(self, oss_config: dict[str, Any], files_to_upload: list[str]) -> bool:
        return (
            self._config.is_upload_oss()
            and oss_config.get("enable_upload")
            and oss_config.get("access_key_id")
            and bool(files_to_upload)
        )

    def _build_files_info(
        self,
        files_to_upload: list[str],
        ts_file_path: str,
        record_name: str,
        room_id: str,
        record_start_time: str | None,
    ) -> list[dict[str, Any]]:
        if record_start_time and record_start_time != "unknown":
            try:
                start_time = datetime.datetime.strptime(record_start_time, "%Y-%m-%d_%H-%M-%S")
                date_str = start_time.strftime("%Y%m%d")
                time_str = start_time.strftime("%H%M%S")
                datetime_str = start_time.strftime("%Y%m%d_%H%M%S")
                timestamp = str(int(start_time.timestamp()))
            except ValueError:
                logger.warning("录制开始时间格式错误: %s，使用当前时间", record_start_time)
                date_str, time_str, datetime_str, timestamp = self._current_time_tokens()
        else:
            date_str, time_str, datetime_str, timestamp = self._current_time_tokens()

        path_template = self._config.get_oss_upload_path_template()
        files_info: list[dict[str, Any]] = []

        for file_path in files_to_upload:
            file_name = os.path.basename(file_path)
            file_name_no_ext, file_ext_with_dot = os.path.splitext(file_name)
            file_ext = file_ext_with_dot[1:] if file_ext_with_dot else ""

            if file_path.endswith(".m3u8"):
                file_type = "m3u8"
            elif file_path.endswith(".mp3"):
                file_type = "audio"
            elif file_path.endswith((".jpg", ".jpeg", ".png")) and "_cover." in file_name:
                file_type = ""
                print(f"识别为封面图片文件: {file_name} (将放在根目录)")
            elif os.path.abspath(file_path) == os.path.abspath(ts_file_path):
                file_type = "video"
                print(f"识别为原始视频文件: {file_name}")
            elif file_path.endswith(".ts"):
                file_type = "m3u8"
                print(f"识别为TS切片文件: {file_name}")
            else:
                file_type = "video"

            print(f"文件分类: {file_name} -> {file_type} 目录")

            oss_key = path_template.format(
                record_name=record_name,
                room_id=room_id,
                date_str=date_str,
                time_str=time_str,
                datetime_str=datetime_str,
                file_name=file_name,
                file_name_no_ext=file_name_no_ext,
                file_ext=file_ext,
                file_type=file_type,
                timestamp=timestamp,
            )

            oss_key = oss_key.replace("//", "/").strip("/")

            files_info.append(
                {
                    "file_path": file_path,
                    "oss_key": oss_key,
                    "file_type": file_type,
                    "file_name": file_name,
                }
            )

        return files_info

    @staticmethod
    def _current_time_tokens() -> tuple[str, str, str, str]:
        date_str = time.strftime("%Y%m%d")
        time_str = time.strftime("%H%M%S")
        datetime_str = time.strftime("%Y%m%d_%H%M%S")
        timestamp = str(int(time.time()))
        return date_str, time_str, datetime_str, timestamp
