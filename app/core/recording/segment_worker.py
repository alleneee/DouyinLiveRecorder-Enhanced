"""分段录制工作器 - 按配置的时长保存分段文件并上传到OSS。"""

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
from app.core.storage import OSSUploader
from app.legacy.utils import logger


@dataclass
class SegmentConfig:
    """分段录制配置。"""
    segment_duration: int = 1200  # 20分钟 = 1200秒
    video_save_path: str = "downloads"
    video_save_type: str = "TS"
    folder_by_author: bool = True
    
    # OSS 配置
    oss_enabled: bool = False
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = ""
    oss_bucket_name: str = ""


class SegmentRecordingWorker:
    """分段录制工作器 - 按配置的时长保存分段文件。"""
    
    def __init__(
        self,
        room: Room,
        handler: PlatformHandler,
        config: SegmentConfig,
        *,
        on_segment_complete: Optional[Callable[[str, dict], None]] = None,
    ):
        self.room = room
        self.handler = handler
        self.config = config
        self.on_segment_complete = on_segment_complete
        
        self.segment_index = 0
        self.recording_start_time: Optional[datetime.datetime] = None
        
        # 初始化 OSS 上传器
        self.oss_uploader: Optional[OSSUploader] = None
        if config.oss_enabled:
            try:
                self.oss_uploader = OSSUploader(
                    access_key_id=config.oss_access_key_id,
                    access_key_secret=config.oss_access_key_secret,
                    endpoint=config.oss_endpoint,
                    bucket_name=config.oss_bucket_name,
                )
                logger.info("OSS 上传器初始化成功")
            except Exception as e:
                logger.error(f"OSS 上传器初始化失败: {e}")
    
    async def start(self, stop_event: threading.Event):
        """启动分段录制。"""
        logger.info(f"开始监控直播间: {self.room.url}")
        
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
                await self._record_with_segments(stream_info, stop_event)
                
            except Exception as e:
                logger.error(f"录制出错: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _record_with_segments(
        self,
        stream_info: StreamInfo,
        stop_event: threading.Event
    ):
        """分段录制主循环。"""
        while not stop_event.is_set():
            self.segment_index += 1
            segment_start = datetime.datetime.now()
            
            # 生成当前分段的保存路径
            save_path = self._generate_segment_path(stream_info, self.segment_index)
            
            logger.info(f"开始录制第 {self.segment_index} 段: {save_path} (时长: {self.config.segment_duration}秒)")
            
            # 录制一个分段
            success = await self._record_segment(
                stream_info,
                save_path,
                stop_event
            )
            
            segment_end = datetime.datetime.now()
            
            if success and Path(save_path).exists():
                # 处理录制完成的分段
                await self._handle_segment_complete(
                    save_path,
                    segment_start,
                    segment_end,
                    stream_info
                )
            
            # 检查直播是否还在继续
            stream_info = await self.handler.get_stream_info(
                self.room.url,
                self.room.quality
            )
            
            if not stream_info or not stream_info.is_live:
                logger.info("直播已结束")
                break
    
    async def _record_segment(
        self,
        stream_info: StreamInfo,
        save_path: str,
        stop_event: threading.Event
    ) -> bool:
        """录制单个分段（时长由config.segment_duration配置）。"""
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
            
            # 等待录制完成或达到时长限制
            start_time = datetime.datetime.now()
            while not stop_event.is_set():
                # 检查进程是否结束
                if process.poll() is not None:
                    break
                
                # 检查是否达到分段时长
                elapsed = (datetime.datetime.now() - start_time).total_seconds()
                if elapsed >= self.config.segment_duration:
                    logger.info(f"达到分段时长 {self.config.segment_duration}秒，停止当前分段")
                    process.terminate()
                    process.wait(timeout=5)
                    break
                
                await asyncio.sleep(1)
            
            # 如果是手动停止，终止进程
            if stop_event.is_set() and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            
            return True
            
        except Exception as e:
            logger.error(f"录制分段失败: {e}", exc_info=True)
            return False
    
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
    
    def _generate_segment_path(self, stream_info: StreamInfo, segment_index: int) -> str:
        """生成分段文件路径。"""
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
        
        # 生成文件名（包含分段序号）
        room_id = self.room.url.split("/")[-1]
        filename = f"{room_id}_{anchor_name}_{title}_seg{segment_index:03d}_{now}.ts"
        
        return str(base_dir / filename)
    
    def _clean_name(self, name: str) -> str:
        """清理文件名中的非法字符。"""
        import re
        # 移除或替换非法字符
        name = re.sub(r'[\\/:*?"<>|]', '_', name)
        # 限制长度
        return name[:50] if len(name) > 50 else name
    
    async def _handle_segment_complete(
        self,
        file_path: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        stream_info: StreamInfo
    ):
        """处理录制完成的分段。"""
        upload_success = False
        final_file_path = file_path  # 最终文件路径（可能转换后）
        
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"❌ 分段文件不存在: {file_path}")
                return
            
            file_size = file_path_obj.stat().st_size
            duration = int((end_time - start_time).total_seconds())
            
            logger.info(f"✅ 分段录制完成: {file_path} ({file_size / 1024 / 1024:.2f} MB, {duration} 秒)")
            
            # 格式转换（如果需要）
            if self.config.video_save_type.upper() != "TS":
                final_file_path = await self._convert_format(file_path)
                if final_file_path and final_file_path != file_path:
                    # 更新文件大小
                    file_size = Path(final_file_path).stat().st_size
                    logger.info(f"🔄 格式转换完成: {final_file_path} ({file_size / 1024 / 1024:.2f} MB)")
                else:
                    logger.warning(f"⚠️ 格式转换失败，使用原始TS文件")
                    final_file_path = file_path
            
            # 准备数据库记录
            segment_data = {
                "room_url": self.room.url,
                "anchor_name": stream_info.anchor_name or self.room.nickname,
                "segment_index": self.segment_index,
                "local_path": final_file_path,
                "file_size": file_size,
                "duration_seconds": duration,
                "start_time": start_time,
                "end_time": end_time,
                "upload_status": "pending",
            }
            
            # 上传到 OSS
            if self.oss_uploader:
                try:
                    logger.info(f"开始上传分段到 OSS: {final_file_path}")
                    segment_data["upload_status"] = "uploading"
                    
                    oss_result = self.oss_uploader.upload_file(final_file_path)
                    
                    segment_data.update({
                        "oss_key": oss_result["oss_key"],
                        "oss_url": oss_result["oss_url"],
                        "upload_status": "success",
                        "upload_time": datetime.datetime.now(),
                    })
                    
                    upload_success = True
                    logger.info(f"✅ OSS 上传成功: {oss_result['oss_url']}")
                    
                except Exception as e:
                    logger.error(f"❌ OSS 上传失败: {e}")
                    segment_data["upload_status"] = "failed"
            
            # 保存到数据库
            try:
                await self._save_to_database(segment_data)
                # 更新room统计信息
                await self._update_room_stats(segment_data)
            except Exception as e:
                logger.error(f"❌ 数据库保存失败，但继续执行: {e}")
            
            # 回调通知
            if self.on_segment_complete:
                try:
                    self.on_segment_complete(final_file_path, segment_data)
                except Exception as e:
                    logger.error(f"❌ 回调执行失败: {e}")
                
        except Exception as e:
            logger.error(f"处理分段完成失败: {e}", exc_info=True)
        
        finally:
            # 上传成功后删除本地文件
            if upload_success and self.config.oss_enabled:
                try:
                    final_path_obj = Path(final_file_path)
                    if final_path_obj.exists():
                        final_path_obj.unlink()
                        logger.info(f"🗑️ 本地文件已删除: {final_file_path}")
                except Exception as del_err:
                    logger.warning(f"⚠️ 删除本地文件失败: {del_err}")
    
    async def _save_to_database(self, segment_data: dict):
        """保存分段信息到数据库。"""
        try:
            from app.db.session import get_session
            from app.models.video_segment import VideoSegmentORM
            
            with get_session() as db:
                segment = VideoSegmentORM(**segment_data)
                db.add(segment)
                db.commit()
                db.refresh(segment)
                logger.info(f"✅ 分段信息已保存到数据库: ID={segment.id}, segment_index={segment_data['segment_index']}, file={segment_data['local_path']}")
        except Exception as e:
            logger.error(f"❌ 保存到数据库失败: {e}", exc_info=True)
            raise
    
    async def _update_room_stats(self, segment_data: dict):
        """更新room表的统计信息。"""
        try:
            from app.db.session import get_session
            from app.models.room import RoomORM
            
            with get_session() as db:
                room = db.query(RoomORM).filter(RoomORM.url == segment_data['room_url']).first()
                if room:
                    room.total_segments += 1
                    room.total_size_bytes += segment_data['file_size']
                    db.commit()
                    logger.debug(f"📊 更新room统计: url={segment_data['room_url']}, segments={room.total_segments}")
        except Exception as e:
            logger.error(f"❌ 更新room统计失败: {e}", exc_info=True)
    
    async def _convert_format(self, ts_file_path: str) -> str:
        """
        将TS文件转换为配置的目标格式。
        
        Args:
            ts_file_path: TS文件路径
        
        Returns:
            转换后的文件路径，失败则返回原路径
        """
        try:
            target_format = self.config.video_save_type.upper()
            ts_path = Path(ts_file_path)
            
            # 确定目标文件扩展名
            format_map = {
                "MP4": ".mp4",
                "FLV": ".flv",
                "MKV": ".mkv",
                "TS": ".ts",
            }
            
            if target_format not in format_map:
                logger.warning(f"不支持的格式: {target_format}，保持TS格式")
                return ts_file_path
            
            target_ext = format_map[target_format]
            output_path = ts_path.with_suffix(target_ext)
            
            logger.info(f"🔄 开始格式转换: {target_format}")
            
            # 构建FFmpeg命令（快速转封装，不重新编码）
            command = [
                "ffmpeg",
                "-i", str(ts_path),
                "-c:v", "copy",  # 视频流复制，不重新编码
                "-c:a", "copy",  # 音频流复制，不重新编码
                "-f", target_format.lower(),
                str(output_path),
                "-y",  # 覆盖已存在的文件
            ]
            
            # 执行转换
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0 and output_path.exists():
                # 转换成功，删除原始TS文件
                ts_path.unlink()
                logger.info(f"✅ 格式转换成功: {output_path}")
                return str(output_path)
            else:
                logger.error(f"❌ 格式转换失败: {result.stderr}")
                return ts_file_path
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ 格式转换超时")
            return ts_file_path
        except Exception as e:
            logger.error(f"❌ 格式转换异常: {e}", exc_info=True)
            return ts_file_path


__all__ = ["SegmentRecordingWorker", "SegmentConfig"]
