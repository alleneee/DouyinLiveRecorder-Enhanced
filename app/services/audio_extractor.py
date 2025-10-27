"""音频抽取服务 - 从视频中提取音频"""
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from app.logger import logger
from app.config import settings


class AudioExtractor:
    """音频抽取器
    
    使用FFmpeg从视频文件中提取音频。
    
    Features:
    - 支持多种音频格式（mp3/aac/m4a）
    - 可配置音频码率
    - 自动清理临时文件
    
    Examples:
        >>> extractor = AudioExtractor()
        >>> audio_path = extractor.extract_audio("/path/to/video.ts")
        >>> print(audio_path)  # /path/to/video.mp3
    """
    
    def __init__(self):
        """初始化音频抽取器"""
        self.audio_format = settings.audio_format
        self.audio_bitrate = settings.audio_bitrate
    
    def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        delete_source: bool = False
    ) -> Optional[str]:
        """从视频文件中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径（可选，默认与视频同目录同名）
            delete_source: 是否删除源视频文件
            
        Returns:
            音频文件路径，失败返回None
            
        Examples:
            >>> # 基本用法
            >>> audio_path = extractor.extract_audio("/path/to/video.ts")
            
            >>> # 指定输出路径
            >>> audio_path = extractor.extract_audio(
            ...     "/path/to/video.ts",
            ...     output_path="/path/to/audio.mp3"
            ... )
            
            >>> # 抽取后删除源文件
            >>> audio_path = extractor.extract_audio(
            ...     "/path/to/video.ts",
            ...     delete_source=True
            ... )
        """
        if not settings.extract_audio:
            logger.debug("音频抽取未启用")
            return None
        
        # 验证视频文件存在
        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"视频文件不存在: {video_path}")
            return None
        
        # 生成输出路径
        if not output_path:
            output_path = video_path.with_suffix(f".{self.audio_format}")
        else:
            output_path = Path(output_path)
        
        logger.info(
            f"开始提取音频: video={video_path.name}, "
            f"format={self.audio_format}, bitrate={self.audio_bitrate}"
        )
        
        try:
            # 构建FFmpeg命令
            cmd = self._build_ffmpeg_command(str(video_path), str(output_path))
            
            # 打印完整FFmpeg命令（用于调试）
            cmd_str = ' '.join(
                f'"{arg}"' if ' ' in str(arg) else str(arg)
                for arg in cmd
            )
            logger.debug(f"FFmpeg音频提取命令:\n{cmd_str}")
            
            # 执行FFmpeg
            logger.debug("正在执行FFmpeg音频提取...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                # 打印更详细的错误信息
                stderr_lines = result.stderr.split('\n') if result.stderr else []
                # 提取最后50行错误信息（更有价值）
                stderr_preview = '\n'.join(stderr_lines[-50:]) if len(stderr_lines) > 50 else result.stderr
                
                logger.error(
                    f"FFmpeg音频提取失败: "
                    f"returncode={result.returncode}, "
                    f"video={video_path.name}\n"
                    f"stderr输出:\n{stderr_preview}"
                )
                return None
            
            # 验证输出文件
            if not output_path.exists():
                logger.error(f"音频文件未生成: {output_path}")
                return None
            
            audio_size = output_path.stat().st_size
            logger.info(
                f"音频提取成功: "
                f"audio={output_path.name}, "
                f"size={audio_size // 1024 // 1024}MB ({audio_size} bytes)"
            )
            
            # 删除源文件（如果需要）
            if delete_source:
                try:
                    video_path.unlink()
                    logger.info(f"源视频已删除: {video_path}")
                except Exception as e:
                    logger.warning(f"删除源视频失败: {e}")
            
            return str(output_path)
            
        except subprocess.TimeoutExpired:
            logger.error(
                f"FFmpeg音频提取超时(5分钟): video={video_path.name}"
            )
            return None
        except Exception as e:
            logger.error(
                f"音频提取异常: video={video_path.name}, error={e}",
                exc_info=True
            )
            return None
    
    def _build_ffmpeg_command(self, input_path: str, output_path: str) -> list:
        """构建FFmpeg命令
        
        Args:
            input_path: 输入视频路径
            output_path: 输出音频路径
            
        Returns:
            FFmpeg命令列表
        """
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vn',  # 不处理视频
            '-acodec', self._get_audio_codec(),
            '-ab', self.audio_bitrate,
            '-ar', '44100',  # 采样率
            '-ac', '2',  # 双声道
            '-y',  # 覆盖输出文件
            output_path
        ]
        
        return cmd
    
    def _get_audio_codec(self) -> str:
        """获取音频编码器
        
        Returns:
            FFmpeg音频编码器名称
        """
        codec_map = {
            'mp3': 'libmp3lame',
            'aac': 'aac',
            'm4a': 'aac',
            'opus': 'libopus',
            'flac': 'flac'
        }
        
        return codec_map.get(self.audio_format, 'libmp3lame')
    
    def extract_audio_batch(
        self,
        video_paths: list[str],
        delete_source: bool = False
    ) -> list[Tuple[str, Optional[str]]]:
        """批量提取音频
        
        Args:
            video_paths: 视频文件路径列表
            delete_source: 是否删除源视频文件
            
        Returns:
            (视频路径, 音频路径)元组列表
            
        Examples:
            >>> results = extractor.extract_audio_batch([
            ...     "/path/to/video1.ts",
            ...     "/path/to/video2.ts"
            ... ])
            >>> for video, audio in results:
            ...     print(f"{video} -> {audio}")
        """
        results = []
        
        for video_path in video_paths:
            audio_path = self.extract_audio(video_path, delete_source=delete_source)
            results.append((video_path, audio_path))
        
        return results
    
    def get_audio_info(self, audio_path: str) -> Optional[dict]:
        """获取音频文件信息
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            音频信息字典，包含duration、bitrate、codec等
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                audio_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                format_info = data.get('format', {})
                stream_info = data.get('streams', [{}])[0]
                
                return {
                    'duration': float(format_info.get('duration', 0)),
                    'size': int(format_info.get('size', 0)),
                    'bitrate': int(format_info.get('bit_rate', 0)),
                    'codec': stream_info.get('codec_name', ''),
                    'sample_rate': int(stream_info.get('sample_rate', 0)),
                    'channels': int(stream_info.get('channels', 0))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"获取音频信息失败: {e}")
            return None


# 全局单例
audio_extractor = AudioExtractor()
