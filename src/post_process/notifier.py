"""后处理阶段的 API 通知辅助工具。"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass
from typing import Iterable

from api_client import APIClient, create_live_record_data, create_mp3_info

from .logging import logger


@dataclass(slots=True)
class NotificationContext:
    record_name: str
    room_id: str
    record_start_time: str
    record_date: str
    record_file_name: str
    m3u8_url: str | None
    video_url: str | None
    mp3_infos: list[dict]
    cover_image_url: str | None


def _extract_url_classification(
    uploaded_files: Iterable[dict], oss_config: dict
) -> tuple[str | None, str | None, list[dict], str | None]:
    m3u8_url = None
    video_url = None
    cover_image_url = None
    mp3_infos: list[dict] = []

    bucket_name = oss_config.get("bucket_name", "")
    endpoint = oss_config.get("endpoint", "")
    if not bucket_name or not endpoint:
        return m3u8_url, video_url, mp3_infos, cover_image_url

    if endpoint.startswith("oss-"):
        base_url = f"https://{bucket_name}.{endpoint}"
    else:
        base_url = f"https://{bucket_name}.{endpoint}"

    for file_info in uploaded_files:
        file_name = file_info["file_name"]
        oss_path = file_info["oss_key"]
        full_url = f"{base_url}/{oss_path}"

        if file_name.endswith(".ts"):
            if "/video/" in oss_path:
                video_url = full_url
            elif "/m3u8/" in oss_path:
                continue
            else:
                name_without_ext = file_name.split(".")[0]
                import re

                is_m3u8_segment = bool(re.search(r"_\d{3}$", name_without_ext))
                is_part_file = "part" in name_without_ext.lower()
                if not is_m3u8_segment and not is_part_file:
                    video_url = full_url
        elif file_name.endswith(".m3u8"):
            m3u8_url = full_url
        elif file_name.endswith((".jpg", ".jpeg", ".png")) and "_cover." in file_name:
            cover_image_url = full_url
        elif file_name.endswith(".mp3"):
            if "part" in file_name:
                import re

                match = re.search(r"_part(\d+)_of_(\d+)", file_name)
                if match:
                    section = int(match.group(1))
                    mp3_infos.append(create_mp3_info(section, full_url))
            else:
                mp3_infos.append(create_mp3_info(1, full_url))

    return m3u8_url, video_url, mp3_infos, cover_image_url


def _build_notification_context(args, uploaded_files: list[dict], oss_config: dict) -> NotificationContext:
    m3u8_url, video_url, mp3_infos, cover_image_url = _extract_url_classification(uploaded_files, oss_config)

    record_name = args.record_name or "unknown"
    room_id = args.room_id or "unknown"
    record_start_time = args.record_start_time or ""

    if record_start_time and record_start_time != "unknown":
        try:
            temp_time = record_start_time.replace("_", " ")
            parts = temp_time.split(" ")
            if len(parts) == 2:
                date_part = parts[0]
                time_part = parts[1].replace("-", ":")
                record_start_time = f"{date_part} {time_part}"
            else:
                record_start_time = temp_time
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("录制开始时间格式化失败: %s", exc)
            record_start_time = ""

    if record_start_time:
        try:
            start_time_obj = datetime.datetime.strptime(record_start_time, "%Y-%m-%d %H:%M:%S")
            record_date = start_time_obj.strftime("%Y-%m-%d")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("解析录制时间失败: %s", exc)
            record_date = datetime.datetime.now().strftime("%Y-%m-%d")
    else:
        record_date = datetime.datetime.now().strftime("%Y-%m-%d")

    record_file_name = args.save_file_path and args.save_file_path.rsplit(os.sep, 1)[-1]
    if not record_file_name:
        record_file_name = ""

    return NotificationContext(
        record_name=record_name,
        room_id=room_id,
        record_start_time=record_start_time,
        record_date=record_date,
        record_file_name=record_file_name,
        m3u8_url=m3u8_url,
        video_url=video_url,
        mp3_infos=mp3_infos,
        cover_image_url=cover_image_url,
    )


class PostProcessNotifier:
    """封装后处理完成后的 API 通知流程。"""

    def notify(self, args, uploaded_files: list[dict], oss_config: dict) -> bool:
        if not uploaded_files:
            return False

        try:
            api_client = APIClient()
        except Exception as exc:
            logger.error("API客户端创建失败: %s", exc)
            print(f"[失败] API客户端创建失败: {exc}")
            return False

        bucket_name = oss_config.get("bucket_name", "")
        endpoint = oss_config.get("endpoint", "")
        if not bucket_name or not endpoint:
            print("[失败] OSS配置信息不完整，无法构建URL")
            return False

        context = _build_notification_context(args, uploaded_files, oss_config)

        validation_errors = []
        if not context.record_name or context.record_name == "unknown":
            validation_errors.append("录制名称不能为空或unknown")
        if not context.room_id or context.room_id == "unknown":
            validation_errors.append("房间ID不能为空或unknown")
        if not context.record_start_time:
            validation_errors.append("录制开始时间不能为空")
        if not context.record_date:
            validation_errors.append("录制日期不能为空")
        if not context.record_file_name:
            validation_errors.append("录制文件名不能为空")
        if not context.m3u8_url and not context.video_url:
            validation_errors.append("至少需要提供 m3u8_url 或 video_url 其中一个")

        if validation_errors:
            logger.error("数据验证失败: %s", "; ".join(validation_errors))
            print("[失败] 数据验证失败，跳过API通知")
            return False

        try:
            live_record = create_live_record_data(
                record_name=context.record_name,
                room_id=context.room_id,
                record_start_time=context.record_start_time,
                record_date=context.record_date,
                record_file_name=context.record_file_name,
                m3u8_url=context.m3u8_url,
                video_url=context.video_url,
                mp3_urls=context.mp3_infos if context.mp3_infos else None,
                cover_image_url=context.cover_image_url,
                biz_type="live",
            )
        except Exception as exc:
            logger.error("直播录制数据创建失败: %s", exc)
            print(f"[失败] 直播录制数据创建失败: {exc}")
            return False

        logger.info(
            "开始发送API通知,API请求参数: %s",
            json.dumps([live_record], ensure_ascii=False, indent=2),
        )

        try:
            success = api_client.notify_post_process_result([live_record])
            if success:
                logger.info("API通知发送成功")
                print("[成功] API通知发送成功")
                return True
            logger.info("API通知发送失败")
            print("[失败] API通知发送失败")
            return False
        except Exception as exc:
            logger.info("API通知过程中发生异常: %s", exc)
            print(f"[异常] API通知过程中发生异常: {exc}")
            return False
