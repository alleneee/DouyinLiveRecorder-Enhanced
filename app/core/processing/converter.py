"""视频转码服务。"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from app.legacy.utils import logger


class VideoConverter:
    """视频转码服务。
    
    负责将录制完成的视频转换为不同格式。
    """
    
    def __init__(
        self,
        *,
        convert_to_h264: bool = False,
        delete_origin: bool = True,
    ):
        self.convert_to_h264 = convert_to_h264
        self.delete_origin = delete_origin
    
    def convert_to_mp4(
        self,
        source_path: str,
        *,
        output_path: Optional[str] = None,
    ) -> str | None:
        """将视频转换为 MP4 格式。
        
        Args:
            source_path: 源文件路径
            output_path: 输出路径（可选，默认与源文件同目录）
        
        Returns:
            转换后的文件路径，失败返回 None
        """
        try:
            if not os.path.exists(source_path) or os.path.getsize(source_path) == 0:
                logger.warning(f"源文件不存在或为空: {source_path}")
                return None
            
            # 确定输出路径
            if output_path is None:
                output_path = str(Path(source_path).with_suffix(".mp4"))
            
            # 构建 FFmpeg 命令
            if self.convert_to_h264:
                logger.info("转码为 MP4 并重新编码为 H264")
                command = [
                    "ffmpeg",
                    "-i", source_path,
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-vf", "format=yuv420p",
                    "-c:a", "copy",
                    "-f", "mp4",
                    output_path,
                ]
            else:
                # 仅容器转换，不重新编码
                command = [
                    "ffmpeg",
                    "-i", source_path,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-f", "mp4",
                    output_path,
                ]
            
            # 执行转换
            subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
            )
            
            logger.info(f"转码完成: {output_path}")
            
            # 删除原始文件
            if self.delete_origin:
                time.sleep(1)
                if os.path.exists(source_path):
                    os.remove(source_path)
                    logger.info(f"已删除原始文件: {source_path}")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"转码失败: {e}")
            return None
        except Exception as e:
            logger.error(f"转码过程出错: {e}")
            return None
    
    def segment_video(
        self,
        source_path: str,
        segment_time: int = 3600,
        *,
        output_format: str = "mp4",
    ) -> list[str]:
        """将视频分段。
        
        Args:
            source_path: 源文件路径
            segment_time: 分段时长（秒）
            output_format: 输出格式
        
        Returns:
            生成的分段文件列表
        """
        try:
            if not os.path.exists(source_path) or os.path.getsize(source_path) == 0:
                return []
            
            # 生成输出路径模式
            source = Path(source_path)
            output_pattern = str(source.parent / f"{source.stem}_%03d.{output_format}")
            
            # 构建命令
            command = [
                "ffmpeg",
                "-i", source_path,
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0",
                "-f", "segment",
                "-segment_time", str(segment_time),
                "-segment_format", output_format,
                "-reset_timestamps", "1",
                output_pattern,
            ]
            
            # 执行分段
            subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
            )
            
            # 查找生成的文件
            segments = list(source.parent.glob(f"{source.stem}_*.{output_format}"))
            logger.info(f"分段完成，生成 {len(segments)} 个文件")
            
            # 删除原始文件
            if self.delete_origin and segments:
                time.sleep(1)
                if os.path.exists(source_path):
                    os.remove(source_path)
            
            return [str(s) for s in segments]
            
        except Exception as e:
            logger.error(f"分段失败: {e}")
            return []


__all__ = ["VideoConverter"]
