"""
视频格式转换服务
将录制的TS格式转换为配置的最终格式(如MP4)
"""
import logging
import subprocess
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class VideoConverter:
    """视频格式转换器"""

    def convert_to_target_format(
        self,
        input_path: str,
        delete_source: bool = True,
        log_context: str = ""
    ) -> Optional[str]:
        """
        将视频转换为目标格式

        Args:
            input_path: 输入视频路径 (例如 .ts 文件)
            delete_source: 转换成功后是否删除源文件
            log_context: 日志上下文前缀

        Returns:
            转换后的文件路径,失败返回 None
        """
        # 如果录制格式和保存格式相同,无需转换
        if settings.video_record_format == settings.video_save_type:
            logger.debug(f"{log_context} 录制格式与保存格式相同({settings.video_save_type}),跳过转换")
            return input_path

        input_file = Path(input_path)
        if not input_file.exists():
            logger.error(f"{log_context} 输入文件不存在: {input_path}")
            return None

        # 生成输出路径 (同目录,不同扩展名)
        output_file = input_file.with_suffix(f".{settings.video_save_type}")

        try:
            logger.info(f"{log_context} 开始格式转换: {input_file.suffix} → .{settings.video_save_type}")

            # FFmpeg 转换命令 (复制流,不重新编码,速度快)
            cmd = [
                "ffmpeg",
                "-i", str(input_file),
                "-c", "copy",  # 复制音视频流,不重新编码
                "-y",  # 覆盖已存在的文件
                str(output_file)
            ]

            # 执行转换
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode != 0:
                logger.error(
                    f"{log_context} FFmpeg格式转换失败: "
                    f"return_code={result.returncode}, "
                    f"stderr={result.stderr[:500]}"
                )
                return None

            # 检查输出文件
            if not output_file.exists() or output_file.stat().st_size == 0:
                logger.error(f"{log_context} 转换后的文件不存在或为空")
                return None

            logger.info(
                f"{log_context} 格式转换成功: "
                f"size={output_file.stat().st_size // 1024 // 1024}MB, "
                f"path={output_file.name}"
            )

            # 删除源文件
            if delete_source:
                try:
                    input_file.unlink()
                    logger.debug(f"{log_context} 已删除源文件: {input_file.name}")
                except Exception as e:
                    logger.warning(f"{log_context} 删除源文件失败: {e}")

            return str(output_file)

        except subprocess.TimeoutExpired:
            logger.error(f"{log_context} 格式转换超时(5分钟)")
            return None
        except Exception as e:
            logger.error(f"{log_context} 格式转换异常: {e}", exc_info=True)
            return None


# 全局单例
video_converter = VideoConverter()
