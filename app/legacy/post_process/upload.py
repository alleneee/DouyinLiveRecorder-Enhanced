"""后处理输出的 OSS 上传工具。"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .logging import logger


def upload_to_oss(file_path: str, oss_config: dict[str, Any], oss_key: str | None = None) -> bool:
    """使用断点续传配置将单个文件上传至 OSS。"""

    try:
        import oss2
        from oss2.models import PartInfo  # noqa: F401  # kept for compatibility hints
    except ImportError:  # pragma: no cover - runtime dependency guard
        logger.error("需要安装oss2库: pip install oss2")
        return False

    access_key_id = oss_config.get("access_key_id")
    access_key_secret = oss_config.get("access_key_secret")
    endpoint = oss_config.get("endpoint")
    bucket_name = oss_config.get("bucket_name")
    chunk_size = oss_config.get("chunk_size", 8_388_608)
    retry_times = oss_config.get("retry_times", 3)

    if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
        logger.error("OSS配置信息不完整")
        return False

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    oss_key = oss_key or os.path.basename(file_path)

    file_size = os.path.getsize(file_path)
    logger.info(
        "正在上传文件到OSS: %s -> %s (大小: %.2fMB)",
        file_path,
        oss_key,
        file_size / 1024 / 1024,
    )

    try:
        logger.info(
            "使用并发分片上传方式，分片大小: %.2fMB",
            chunk_size / 1024 / 1024,
        )
        logger.info(
            "文件大小: %.2fMB，并发线程数: %s",
            file_size / 1024 / 1024,
            oss_config.get("max_upload_threads", 4),
        )

        oss2.resumable_upload(
            bucket,
            oss_key,
            file_path,
            part_size=chunk_size,
            num_threads=oss_config.get("max_upload_threads", 4),
            store=oss2.ResumableStore(root="/tmp"),
            progress_callback=lambda consumed, total: logger.info(
                "上传进度: %.1f%% (%.2fMB / %.2fMB)",
                consumed / total * 100,
                consumed / 1024 / 1024,
                total / 1024 / 1024,
            ),
        )

        logger.info("文件上传成功: %s", oss_key)
        return True
    except Exception as exc:
        logger.error("文件上传失败: %s", exc)

        for retry in range(retry_times):
            logger.info("正在重试上传 (%s/%s)", retry + 1, retry_times)
            try:
                oss2.resumable_upload(
                    bucket,
                    oss_key,
                    file_path,
                    part_size=chunk_size,
                    num_threads=oss_config.get("max_upload_threads", 4),
                    store=oss2.ResumableStore(root="/tmp"),
                )
                logger.info("重试上传成功: %s", oss_key)
                return True
            except Exception as retry_exc:
                logger.error("重试 %s 失败: %s", retry + 1, retry_exc)
                if retry == retry_times - 1:
                    logger.error("所有重试均失败，上传终止: %s", oss_key)

        return False


def upload_files_to_oss_concurrent(
    files_info: list[dict[str, Any]], oss_config: dict[str, Any]
) -> list[dict[str, Any]]:
    """并发上传多个文件到 OSS。"""

    max_workers = min(oss_config.get("max_upload_threads", 4), len(files_info)) or 1
    uploaded_files: list[dict[str, Any]] = []
    upload_lock = threading.Lock()

    def upload_single_file(file_info: dict[str, Any]) -> bool:
        try:
            success = upload_to_oss(file_info["file_path"], oss_config, file_info.get("oss_key"))
            if success:
                with upload_lock:
                    uploaded_files.append(file_info)
                    logger.info(
                        "文件上传成功: %s (%s/%s)",
                        file_info["file_name"],
                        len(uploaded_files),
                        len(files_info),
                    )
            return success
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("上传文件时发生异常: %s - %s", file_info.get("file_name"), exc)
            return False

    logger.info("开始并发上传 %s 个文件，使用 %s 个线程", len(files_info), max_workers)
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(upload_single_file, file_info): file_info for file_info in files_info
        }
        for future in as_completed(future_to_file):
            file_info = future_to_file[future]
            try:
                success = future.result()
                if not success:
                    logger.error("文件上传失败: %s", file_info["file_name"])
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("上传任务异常: %s - %s", file_info["file_name"], exc)

    upload_duration = time.time() - start_time
    logger.info(
        "并发上传完成: 成功 %s/%s 个文件，耗时 %.2f 秒",
        len(uploaded_files),
        len(files_info),
        upload_duration,
    )

    return uploaded_files


class OSSUploader:
    """封装 OSS 上传辅助函数的包装器。"""

    def __init__(self, oss_config: dict[str, Any]):
        self._oss_config = oss_config

    @property
    def config(self) -> dict[str, Any]:
        return self._oss_config

    def upload(self, file_path: str, oss_key: str | None = None) -> bool:
        return upload_to_oss(file_path, self._oss_config, oss_key)

    def upload_many(self, files_info: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not files_info:
            return []
        if self._oss_config.get("enable_concurrent_upload", True) and len(files_info) > 1:
            return upload_files_to_oss_concurrent(files_info, self._oss_config)

        uploaded: list[dict[str, Any]] = []
        for file_info in files_info:
            if upload_to_oss(file_info["file_path"], self._oss_config, file_info.get("oss_key")):
                uploaded.append(file_info)
        return uploaded
