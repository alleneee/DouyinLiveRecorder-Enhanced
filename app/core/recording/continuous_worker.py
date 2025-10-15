"""连续录制工作器 - 录制到直播结束，然后触发后处理。"""

from __future__ import annotations

import asyncio
import datetime
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from app.core.platforms import PlatformHandler, StreamInfo
from app.core.recording.models import Room
from app.legacy.utils import logger


@dataclass
class ContinuousConfig:
    """连续录制配置。"""
    video_save_path: str = "downloads"
    video_save_type: str = "TS"
    folder_by_author: bool = True
    converts_to_mp4: bool = False
    delete_origin_file: bool = True


class ContinuousRecordingWorker:
    """连续录制工作器 - 录制到直播结束。"""
    
    def __init__(
        self,
        room: Room,
        handler: PlatformHandler,
        config: ContinuousConfig,
        *,
        on_complete: Optional[Callable[[str], None]] = None,
    ):
        self.room = room
        self.handler = handler
        self.config = config
        self.on_complete = on_complete
        
        self.recording_start_time: Optional[datetime.datetime] = None
        self.current_file_path: Optional[str] = None
    
    async def start(self, stop_event: threading.Event):
        """启动连续录制。"""
        logger.info(f"开始监控直播间（连续录制模式）: {self.room.url}")
        
        while not stop_event.is_set():
            try:
                # 获取流信息
                stream_info = await self.handler.get_stream_info(
                    self.room.url,
                    self.room.quality
                )
                
                if not stream_info or not stream_info.is_live:
                    logger.info(f"直播间未开播，等待60秒后重试...")
                    await asyncio.sleep(60)
                    continue
                
                # 开始录制
                logger.info(f"检测到直播开始: {stream_info.anchor_name}")
                self.recording_start_time = datetime.datetime.now()
                
                # 生成保存路径
                save_path = self._generate_file_path(stream_info)
                self.current_file_path = save_path
                
                # 录制到直播结束
                await self._record_until_end(stream_info, save_path, stop_event)
                
                # 录制完成，触发后处理
                if self.current_file_path and Path(self.current_file_path).exists():
                    logger.info(f"直播结束，开始后处理: {self.current_file_path}")
                    await self._trigger_post_process(self.current_file_path)
                    
                    # 触发完成回调
                    if self.on_complete:
                        self.on_complete(self.current_file_path)
                
                # 等待一段时间后继续监控
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"录制出错: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _record_until_end(
        self,
        stream_info: StreamInfo,
        save_path: str,
        stop_event: threading.Event
    ):
        """录制到直播结束。"""
        try:
            # 构建 FFmpeg 命令
            command = self._build_ffmpeg_command(stream_info.real_url, save_path)
            
            # 启动 FFmpeg 进程
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info(f"开始录制: {save_path}")
            
            # 持续监控直播状态
            while not stop_event.is_set():
                # 检查进程是否结束
                if process.poll() is not None:
                    logger.info("FFmpeg 进程已结束")
                    break
                
                # 检查直播是否还在继续（每60秒检查一次）
                await asyncio.sleep(60)
                
                stream_info = await self.handler.get_stream_info(
                    self.room.url,
                    self.room.quality
                )
                
                if not stream_info or not stream_info.is_live:
                    logger.info("直播已结束，停止录制")
                    process.terminate()
                    process.wait(timeout=5)
                    break
            
            # 如果是手动停止，终止进程
            if stop_event.is_set() and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            
            logger.info(f"录制完成: {save_path}")
            
        except Exception as e:
            logger.error(f"录制失败: {e}", exc_info=True)
    
    def _build_ffmpeg_command(self, stream_url: str, save_path: str) -> list[str]:
        """构建 FFmpeg 命令。"""
        command = [
            "ffmpeg",
            "-i", stream_url,
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "mpegts",
            save_path,
        ]
        return command
    
    def _generate_file_path(self, stream_info: StreamInfo) -> str:
        """生成文件路径。"""
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
        
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        room_id = self.room.url.split("/")[-1]
        filename = f"{room_id}_{anchor_name}_{title}_{now}.ts"
        
        return str(base_dir / filename)
    
    def _clean_name(self, name: str) -> str:
        """清理文件名中的非法字符。"""
        import re
        name = re.sub(r'[\\/:*?"<>|]', '_', name)
        return name[:50] if len(name) > 50 else name
    
    async def _trigger_post_process(self, file_path: str):
        """触发后处理流程。"""
        try:
            from app.legacy.post_process.pipeline import PostProcessPipeline
            from config_reader import ConfigReader
            
            # 创建配置
            config = ConfigReader()
            
            # 创建后处理管道
            pipeline = PostProcessPipeline(config)
            
            # 创建参数对象
            class Args:
                def __init__(self, file_path: str):
                    self.save_file_path = file_path
            
            args = Args(file_path)
            
            # 执行后处理
            logger.info(f"开始执行后处理: {file_path}")
            pipeline.run(args)
            logger.info(f"后处理完成: {file_path}")
            
        except Exception as e:
            logger.error(f"后处理失败: {e}", exc_info=True)


__all__ = ["ContinuousRecordingWorker", "ContinuousConfig"]
