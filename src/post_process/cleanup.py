"""后处理输出的清理辅助工具。"""

from __future__ import annotations

import os
import shutil

from .logging import log_post_process


class PostProcessCleaner:
    """负责在上传完成后移除本地遗留文件。"""

    def cleanup(self, uploaded_files: list[dict], original_ts_file: str) -> None:
        log_post_process("开始清理本地文件")

        deleted_count = 0
        failed_count = 0

        for file_info in uploaded_files:
            file_path = file_info["file_path"]
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    log_post_process(f"已删除: {os.path.basename(file_path)}", "debug")
                    deleted_count += 1
                else:
                    log_post_process(f"文件不存在，跳过: {os.path.basename(file_path)}", "debug")
            except Exception as exc:  # pragma: no cover - defensive logging
                log_post_process(
                    f"删除文件失败: {os.path.basename(file_path)} - {exc}", "error"
                )
                failed_count += 1

        try:
            if os.path.exists(original_ts_file):
                os.remove(original_ts_file)
                log_post_process(f"已删除原始录制文件: {os.path.basename(original_ts_file)}", "debug")
                deleted_count += 1
            else:
                log_post_process(
                    f"原始录制文件不存在，跳过: {os.path.basename(original_ts_file)}",
                    "debug",
                )
        except Exception as exc:  # pragma: no cover - defensive logging
            log_post_process(
                f"删除原始录制文件失败: {os.path.basename(original_ts_file)} - {exc}",
                "error",
            )
            failed_count += 1

        try:
            live_room_dir = os.path.dirname(original_ts_file)
            if os.path.exists(live_room_dir) and os.path.isdir(live_room_dir):
                shutil.rmtree(live_room_dir)
                log_post_process(f"已删除整个直播间目录: {live_room_dir}", "info")

                platform_dir = os.path.dirname(live_room_dir)
                if os.path.exists(platform_dir) and os.path.isdir(platform_dir):
                    if not os.listdir(platform_dir):
                        os.rmdir(platform_dir)
                        log_post_process(f"已删除空的平台目录: {platform_dir}", "debug")
                    else:
                        log_post_process(f"平台目录不为空，保留: {platform_dir}", "debug")
            else:
                log_post_process(f"直播间目录不存在，跳过: {live_room_dir}", "debug")
        except Exception as exc:  # pragma: no cover - defensive logging
            log_post_process(f"删除直播间目录失败: {exc}", "error")
            failed_count += 1

        log_post_process(f"文件清理完成: 成功删除 {deleted_count} 个文件, 失败 {failed_count} 个文件")
