"""录制工作器：封装单个直播间的录制逻辑。"""

from __future__ import annotations

import asyncio
import datetime
import os
import random
import re
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.platforms import PlatformHandler, StreamInfo
from app.legacy.utils import logger
from app.legacy.logger import log_key_info, log_error

from .models import Room


class RecordingConfig:
    """录制配置。"""
    
    def __init__(self, **kwargs):
        self.video_save_path = kwargs.get("video_save_path", "downloads")
        self.video_save_type = kwargs.get("video_save_type", "TS")
        self.loop_interval = kwargs.get("loop_interval", 60)
        self.split_time = kwargs.get("split_time", 3600)
        self.split_video_by_time = kwargs.get("split_video_by_time", False)
        self.enable_https = kwargs.get("enable_https", True)
        self.converts_to_mp4 = kwargs.get("converts_to_mp4", False)
        self.delete_origin_file = kwargs.get("delete_origin_file", True)
        self.folder_by_author = kwargs.get("folder_by_author", True)
        self.folder_by_time = kwargs.get("folder_by_time", False)
        self.clean_emoji = kwargs.get("clean_emoji", True)


class RecordingWorker:
    """单个直播间的录制工作器。
    
    负责：
    1. 监控直播状态
    2. 启动 FFmpeg 录制进程
    3. 管理录制生命周期
    4. 处理录制完成后的任务
    """
    
    def __init__(
        self,
        room: Room,
        platform_handler: PlatformHandler,
        *,
        config: RecordingConfig,
        stop_event: Optional[threading.Event] = None,
        on_complete: Optional[Callable[[str], None]] = None,
    ):
        self.room = room
        self.handler = platform_handler
        self.config = config
        self.stop_event = stop_event or threading.Event()
        self.on_complete = on_complete
        
        self._error_count = 0
        self._recording_start_time: Optional[datetime.datetime] = None
        self._process: Optional[subprocess.Popen] = None
    
    def should_stop(self) -> bool:
        """检查是否应该停止录制。"""
        return self.stop_event.is_set()
    
    async def run(self) -> None:
        """主循环：监控直播并录制。"""
        retry_delay = self.config.loop_interval
        
        while not self.should_stop():
            try:
                stream_info = await self.handler.get_stream_info(
                    self.room.url,
                    self.room.quality,
                )
                
                if not stream_info or not stream_info.is_live:
                    # 未开播，等待后重试
                    await self._wait_with_check(retry_delay)
                    continue
                
                # 开始录制
                success = await self._record_stream(stream_info)
                
                if success:
                    # 录制正常结束，短暂等待后重新检测
                    await self._wait_with_check(30)
                else:
                    # 录制失败，增加等待时间
                    self._error_count += 1
                    await self._wait_with_check(retry_delay + 60)
                    
            except Exception as e:
                logger.error(f"录制循环出错: {e}")
                self._error_count += 1
                await self._wait_with_check(retry_delay)
    
    async def _record_stream(self, stream_info: StreamInfo) -> bool:
        """执行录制。"""
        try:
            # 生成文件路径
            save_path = self._generate_save_path(stream_info)
            
            # 构建 FFmpeg 命令
            ffmpeg_cmd = self._build_ffmpeg_command(
                stream_info.real_url,
                save_path,
            )
            
            # 启动录制进程
            self._recording_start_time = datetime.datetime.now()
            success = await self._run_ffmpeg(ffmpeg_cmd, save_path)
            
            if success:
                log_key_info(f"录制完成: {self.room.nickname} - {save_path}")
                # 执行后处理
                await self._post_process(save_path)
                
                # 调用完成回调
                if self.on_complete:
                    self.on_complete(save_path)
            
            return success
            
        except Exception as e:
            logger.error(f"录制流失败: {e}")
            return False
        finally:
            self._recording_start_time = None
    
    async def _run_ffmpeg(self, command: list[str], save_path: str) -> bool:
        """运行 FFmpeg 进程并监控。"""
        try:
            # 启动进程
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            
            # 监控进程
            while self._process.poll() is None:
                if self.should_stop():
                    # 收到停止信号
                    self._terminate_ffmpeg()
                    break
                await asyncio.sleep(1)
            
            return_code = self._process.returncode
            return return_code == 0 or self.should_stop()
            
        except Exception as e:
            logger.error(f"FFmpeg 进程错误: {e}")
            return False
        finally:
            self._process = None
    
    def _terminate_ffmpeg(self) -> None:
        """终止 FFmpeg 进程。"""
        if not self._process:
            return
        
        try:
            if os.name == "nt":
                # Windows: 发送 'q' 命令
                if self._process.stdin:
                    self._process.stdin.write(b"q")
                    self._process.stdin.close()
            else:
                # Unix: 发送 SIGINT 信号
                import signal
                self._process.send_signal(signal.SIGINT)
            
            # 等待进程退出
            self._process.wait(timeout=10)
        except Exception as e:
            logger.error(f"终止 FFmpeg 失败: {e}")
            self._process.kill()
    
    def _build_ffmpeg_command(self, stream_url: str, save_path: str) -> list[str]:
        """构建 FFmpeg 命令。"""
        command = ["ffmpeg", "-i", stream_url]
        
        # 基本参数
        if self.config.enable_https and stream_url.startswith("https"):
            command.extend(["-reconnect", "1", "-reconnect_streamed", "1"])
        
        # 视频音频编码
        if self.config.video_save_type == "TS":
            command.extend([
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0",
                "-f", "mpegts",
                save_path,
            ])
        elif "音频" in self.config.video_save_type:
            if "MP3" in self.config.video_save_type:
                command.extend([
                    "-map", "0:a",
                    "-c:a", "libmp3lame",
                    "-ab", "320k",
                    save_path,
                ])
            else:  # M4A
                command.extend([
                    "-map", "0:a",
                    "-c:a", "aac",
                    "-ab", "320k",
                    save_path,
                ])
        
        return command
    
    def _generate_save_path(self, stream_info: StreamInfo) -> str:
        """生成保存路径。"""
        # 清理文件名
        anchor_name = self._clean_name(stream_info.anchor_name or self.room.nickname)
        title = self._clean_name(stream_info.title)
        
        # 生成时间戳
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # 确定基础目录
        base_dir = Path(self.config.video_save_path)
        
        # 按作者分文件夹
        if self.config.folder_by_author:
            base_dir = base_dir / anchor_name
        
        # 按时间分文件夹
        if self.config.folder_by_time:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            base_dir = base_dir / date_str
        
        # 创建目录
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 提取房间 ID
        room_id = self._extract_room_id(self.room.url)
        
        # 文件名
        extension = "ts" if self.config.video_save_type == "TS" else "mp3"
        if "M4A" in self.config.video_save_type:
            extension = "m4a"
        
        filename = f"{room_id}_{anchor_name}_{title}_{now}.{extension}"
        
        return str(base_dir / filename)
    
    def _clean_name(self, name: str) -> str:
        """清理文件名中的非法字符。"""
        if not name:
            return "unknown"
        
        # 替换非法字符
        rstr = r"[\/\\\:\*\？?\"\<\>\|&#.。,， ~！· ]"
        cleaned = re.sub(rstr, "_", name.strip()).strip("_")
        cleaned = cleaned.replace("（", "(").replace("）", ")")
        
        # 清理 emoji
        if self.config.clean_emoji:
            from app.legacy import utils
            cleaned = utils.remove_emojis(cleaned, "_").strip("_")
        
        return cleaned or "unknown"
    
    def _extract_room_id(self, url: str) -> str:
        """从 URL 提取房间 ID。"""
        # 优先匹配数字串
        match = re.search(r"(\d{5,})", url)
        if match:
            return match.group(1)
        
        # 否则使用 URL 最后一段
        parsed = urllib.parse.urlparse(url)
        segments = parsed.path.rsplit("/", maxsplit=1)
        return segments[-1] if segments else "unknown"
    
    async def _wait_with_check(self, seconds: int) -> None:
        """带停止检查的等待。"""
        for _ in range(seconds):
            if self.should_stop():
                break
            await asyncio.sleep(1)
    
    async def _post_process(self, save_path: str) -> None:
        """后处理：转码、通知等。"""
        # 转码为 MP4
        if self.config.converts_to_mp4 and self.config.video_save_type == "TS":
            threading.Thread(
                target=self._convert_to_mp4,
                args=(save_path, self.config.delete_origin_file),
                daemon=True,
            ).start()
    
    def _convert_to_mp4(self, ts_path: str, delete_origin: bool = True) -> None:
        """转码为 MP4（在后台线程执行）。"""
        try:
            if not os.path.exists(ts_path) or os.path.getsize(ts_path) == 0:
                return
            
            mp4_path = ts_path.rsplit(".", maxsplit=1)[0] + ".mp4"
            
            command = [
                "ffmpeg",
                "-i", ts_path,
                "-c:v", "copy",
                "-c:a", "copy",
                "-f", "mp4",
                mp4_path,
            ]
            
            subprocess.check_output(command, stderr=subprocess.STDOUT)
            
            if delete_origin:
                time.sleep(1)
                if os.path.exists(ts_path):
                    os.remove(ts_path)
                    logger.info(f"已删除原始文件: {ts_path}")
            
            logger.info(f"转码完成: {mp4_path}")
            
        except Exception as e:
            logger.error(f"转码失败: {e}")


__all__ = ["RecordingWorker", "RecordingConfig"]
