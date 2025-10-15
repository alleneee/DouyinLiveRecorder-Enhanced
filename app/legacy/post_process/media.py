"""基于 FFmpeg 的媒体处理辅助工具。"""

from __future__ import annotations

import json
import math
import os
import platform
import shutil
import subprocess
from typing import Optional

from config_reader import ConfigReader

from .logging import log_post_process, logger


def run_subprocess_safe(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """以平台友好的默认参数运行子进程。"""

    if platform.system() == "Windows":
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "ignore")
    return subprocess.run(cmd, **kwargs)


def get_ffmpeg_path(tool_name: str = "ffmpeg") -> str:
    """在常见安装路径中解析 FFmpeg 可执行文件。"""

    tool_path = shutil.which(tool_name)
    if tool_path:
        log_post_process(f"在PATH中找到{tool_name}: {tool_path}", "debug")
        return tool_path

    import sys

    execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]
    project_ffmpeg_dir = os.path.join(execute_dir, "ffmpeg")

    if platform.system() == "Windows":
        tool_exe = f"{tool_name}.exe"
        project_paths = [
            os.path.join(project_ffmpeg_dir, tool_exe),
            os.path.join(project_ffmpeg_dir, "bin", tool_exe),
        ]
    else:
        project_paths = [
            os.path.join(project_ffmpeg_dir, tool_name),
            os.path.join(project_ffmpeg_dir, "bin", tool_name),
        ]

    for path in project_paths:
        if os.path.exists(path):
            return path

    if platform.system() == "Darwin":
        for path in (f"/opt/homebrew/bin/{tool_name}", f"/usr/local/bin/{tool_name}"):
            if os.path.exists(path):
                return path

    if platform.system() == "Windows":
        win_exe = f"{tool_name}.exe"
        search_paths = [
            "C:\\ffmpeg",
            "C:\\Program Files\\ffmpeg",
            "C:\\Program Files (x86)\\ffmpeg",
        ]
        for drive in ["C:\\"]:
            try:
                for item in os.listdir(drive):
                    candidate = os.path.join(drive, item)
                    if item.lower().startswith("ffmpeg") and os.path.isdir(candidate):
                        search_paths.append(candidate)
            except (PermissionError, FileNotFoundError):
                pass

        for base_path in search_paths:
            possible_paths = [
                os.path.join(base_path, win_exe),
                os.path.join(base_path, "bin", win_exe),
                os.path.join(base_path, "ffmpeg", win_exe),
                os.path.join(base_path, "ffmpeg", "bin", win_exe),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return path

    local_paths: list[str]
    if platform.system() == "Windows":
        tool_exe = f"{tool_name}.exe"
        local_paths = [
            f"./ffmpeg/bin/{tool_exe}",
            f"./ffmpeg/{tool_exe}",
            f"./{tool_exe}",
        ]
    else:
        local_paths = [
            f"./ffmpeg/bin/{tool_name}",
            f"./ffmpeg/{tool_name}",
            f"./{tool_name}",
        ]

    for path in local_paths:
        if os.path.exists(path):
            return path

    log_post_process(f"未找到{tool_name}，使用默认命令", "debug")
    return tool_name


def ensure_ffmpeg_available() -> bool:
    """检查 FFmpeg 是否可用，并在缺失时尝试安装。"""

    try:
        ffmpeg_path = get_ffmpeg_path("ffmpeg")
        ffprobe_path = get_ffmpeg_path("ffprobe")
        result = run_subprocess_safe(
            [ffmpeg_path, "-version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            log_post_process(f"FFmpeg可用: {ffmpeg_path}", "debug")
            return True
        log_post_process(f"FFmpeg不可执行: {ffmpeg_path}", "error")
    except Exception as exc:  # pragma: no cover - defensive logging
        log_post_process(f"FFmpeg检测失败: {exc}", "error")

    try:
        log_post_process("尝试自动安装FFmpeg...", "info")
        from ffmpeg_install import check_ffmpeg

        if check_ffmpeg():
            log_post_process("FFmpeg安装成功", "info")
            return True
        log_post_process("FFmpeg自动安装失败", "error")
    except ImportError:
        log_post_process("无法导入FFmpeg安装模块", "error")
    except Exception as exc:  # pragma: no cover - defensive logging
        log_post_process(f"FFmpeg自动安装异常: {exc}", "error")

    return False


def convert_ts_to_m3u8(
    ts_file_path: str,
    output_dir: Optional[str] = None,
    config: Optional[ConfigReader] = None,
) -> str:
    """依据配置化的 HLS 参数将 TS 转换为 M3U8。"""

    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")

    config = config or ConfigReader()
    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit(".", 1)[0]
    output_dir = output_dir or file_dir
    os.makedirs(output_dir, exist_ok=True)

    m3u8_path = os.path.join(output_dir, f"{file_name}.m3u8")
    segment_pattern = os.path.join(output_dir, f"{file_name}_%03d.ts")

    segment_time = config.get_m3u8_segment_time()
    list_size = config.get_m3u8_list_size()
    hls_flags = config.get_hls_flags()

    all_hls_flags = ["split_by_time", "independent_segments"]
    if hls_flags:
        all_hls_flags.extend(hls_flags)

    ffmpeg_path = get_ffmpeg_path("ffmpeg")
    ffmpeg_command = [
        ffmpeg_path,
        "-i",
        ts_file_path,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-g",
        str(int(segment_time * 25)),
        "-keyint_min",
        str(int(segment_time * 25)),
        "-sc_threshold",
        "0",
        "-force_key_frames",
        f"expr:gte(t,n_forced*{segment_time})",
        "-hls_time",
        str(segment_time),
        "-hls_list_size",
        str(list_size),
        "-hls_segment_filename",
        segment_pattern,
        "-hls_flags",
        "+".join(all_hls_flags),
        "-y",
        m3u8_path,
    ]

    log_post_process(f"开始M3U8转换: {os.path.basename(ts_file_path)}")
    log_post_process(f"转换参数: 切片时间={segment_time}秒", "debug")

    try:
        run_subprocess_safe(ffmpeg_command, check=True, capture_output=True, text=True)
        log_post_process(f"M3U8转换完成: {os.path.basename(m3u8_path)}")
        return m3u8_path
    except subprocess.CalledProcessError as exc:  # pragma: no cover - passthrough
        log_post_process(f"M3U8转换失败: {exc.stderr}", "error")
        raise


def get_video_duration(video_file_path: str) -> Optional[float]:
    """通过 ffprobe 获取媒体文件的时长。"""

    if not os.path.exists(video_file_path):
        log_post_process(f"视频文件不存在: {video_file_path}", "error")
        return None

    ffprobe_path = get_ffmpeg_path("ffprobe")
    ffprobe_command = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        video_file_path,
    ]

    try:
        result = run_subprocess_safe(ffprobe_command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        log_post_process(f"获取视频时长: {duration:.2f}秒", "debug")
        return duration
    except subprocess.CalledProcessError as exc:
        log_post_process(f"获取视频时长失败: {exc.stderr}", "error")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        log_post_process(f"解析视频时长信息失败: {exc}", "error")
        return None


def extract_first_frame_cover(ts_file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """从 TS 文件提取首帧作为封面图片。"""

    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")

    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit(".", 1)[0]
    output_dir = output_dir or file_dir
    os.makedirs(output_dir, exist_ok=True)
    cover_file = os.path.join(output_dir, f"{file_name}_cover.jpg")

    log_post_process(f"开始提取封面图片: {os.path.basename(ts_file_path)}")

    ffmpeg_path = get_ffmpeg_path("ffmpeg")
    ffmpeg_command = [
        ffmpeg_path,
        "-i",
        ts_file_path,
        "-vframes",
        "1",
        "-q:v",
        "2",
        "-y",
        cover_file,
    ]

    try:
        run_subprocess_safe(ffmpeg_command, check=True, capture_output=True, text=True)
        log_post_process(f"封面图片提取完成: {os.path.basename(cover_file)}")
        return cover_file
    except subprocess.CalledProcessError as exc:
        log_post_process(f"封面图片提取失败: {exc.stderr}", "error")
        return None


def extract_and_split_audio(
    ts_file_path: str,
    output_dir: Optional[str] = None,
    config: Optional[ConfigReader] = None,
) -> list[str]:
    """提取音频并按需拆分为多个片段。"""

    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")

    if not ensure_ffmpeg_available():
        log_post_process("FFmpeg不可用，无法进行音频处理", "error")
        return []

    config = config or ConfigReader()
    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit(".", 1)[0]
    output_dir = output_dir or file_dir
    os.makedirs(output_dir, exist_ok=True)

    max_duration = config.get_audio_segment_time()
    audio_codec_params = config.get_audio_codec_params()
    audio_bitrate = config.get_audio_bitrate()
    audio_sample_rate = config.get_audio_sample_rate()

    log_post_process(f"开始音频提取: {os.path.basename(ts_file_path)}")
    log_post_process(
        f"音频参数: 切分时间={max_duration}秒, 格式={audio_codec_params['extension']}, 比特率={audio_bitrate}",
        "debug",
    )

    ffprobe_path = get_ffmpeg_path("ffprobe")
    duration_cmd = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        ts_file_path,
    ]

    total_duration: Optional[float]
    try:
        log_post_process(f"执行ffprobe命令: {' '.join(duration_cmd)}", "debug")
        result = run_subprocess_safe(duration_cmd, capture_output=True, text=True, check=True)
        if not result.stdout or result.stdout.strip() == "":
            raise ValueError("ffprobe返回空输出")
        if result.stdout.strip() in ["{}", "{\n}", "{\n\n}"]:
            raise ValueError("ffprobe返回空JSON对象，可能文件不存在或无法读取")

        info = json.loads(result.stdout)
        if "format" not in info or "duration" not in info["format"] or info["format"]["duration"] is None:
            raise ValueError("ffprobe输出缺少duration信息")

        total_duration = float(info["format"]["duration"])
        log_post_process(f"获取到视频时长: {total_duration}秒", "debug")
    except subprocess.CalledProcessError as exc:
        log_post_process(f"ffprobe命令执行失败: 返回码={exc.returncode}", "error")
        log_post_process(f"ffprobe stderr: {exc.stderr}", "error")
        log_post_process(f"ffprobe stdout: {exc.stdout}", "error")
        total_duration = None
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        log_post_process(f"解析ffprobe JSON输出失败: {exc}", "error")
        total_duration = None
    except Exception as exc:  # pragma: no cover - defensive logging
        log_post_process(f"获取视频时长失败: {exc}", "error")
        total_duration = None

    audio_files: list[str] = []
    should_split = False
    segments = 1

    if total_duration is not None:
        log_post_process(f"视频时长: {total_duration}秒, 切分阈值: {max_duration}秒", "debug")
        if total_duration > max_duration:
            should_split = True
            segments = math.ceil(total_duration / max_duration)
            log_post_process(f"需要切割，将分为 {segments} 个片段", "debug")
        else:
            log_post_process("视频时长未超过阈值，不需要切割", "debug")
    else:
        log_post_process(
            f"无法获取视频时长，将尝试按时间切分（每{max_duration}秒一段）",
            "debug",
        )
        should_split = True
        segments = 3

    ffmpeg_path = get_ffmpeg_path("ffmpeg")

    if should_split:
        log_post_process("开始音频切割，使用Java分片方法确保完整性", "debug")
        segment_pattern = os.path.join(
            output_dir, f"{file_name}_part%03d.{audio_codec_params['extension']}"
        )
        segment_command = [
            ffmpeg_path,
            "-fflags",
            "+genpts+igndts",
            "-err_detect",
            "explode",
            "-i",
            ts_file_path,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-ar",
            "48000",
            "-copytb",
            "1",
            "-af",
            "aresample=async=1:min_comp=0.01",
            "-max_muxing_queue_size",
            "1024",
            "-write_xing",
            "0",
            "-f",
            "segment",
            "-segment_time",
            str(max_duration),
            "-reset_timestamps",
            "1",
            "-segment_start_number",
            "1",
            "-segment_format",
            audio_codec_params["extension"],
            "-y",
            segment_pattern,
        ]

        try:
            log_post_process("使用Java分片方法提取音频", "debug")
            run_subprocess_safe(segment_command, check=True, capture_output=True, text=True)

            index = 1
            while True:
                segment_file = os.path.join(
                    output_dir, f"{file_name}_part{index:03d}.{audio_codec_params['extension']}"
                )
                if os.path.exists(segment_file):
                    audio_files.append(segment_file)
                    index += 1
                else:
                    break

            if audio_files:
                log_post_process(
                    f"Java分片模式提取完成，生成 {len(audio_files)} 个音频文件",
                    "debug",
                )
            else:
                log_post_process("Java分片模式未生成文件，回退到传统方法", "debug")
                raise RuntimeError("分片模式未生成文件")
        except Exception as exc:
            log_post_process(f"Java分片模式失败: {exc}，回退到传统方法", "debug")
            output_file = os.path.join(
                output_dir, f"{file_name}.{audio_codec_params['extension']}"
            )
            fallback_command = [
                ffmpeg_path,
                "-fflags",
                "+genpts+igndts",
                "-err_detect",
                "explode",
                "-i",
                ts_file_path,
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                "-ar",
                "48000",
                "-copytb",
                "1",
                "-af",
                "aresample=async=1:min_comp=0.01",
                "-max_muxing_queue_size",
                "1024",
                "-write_xing",
                "0",
                "-y",
                output_file,
            ]

            try:
                run_subprocess_safe(fallback_command, check=True, capture_output=True, text=True)
                audio_files.append(output_file)
            except subprocess.CalledProcessError as exc2:
                logger.error(f"音频提取失败: {exc2.stderr}")
                raise
    else:
        output_file = os.path.join(output_dir, f"{file_name}.{audio_codec_params['extension']}")
        fallback_command = [
            ffmpeg_path,
            "-fflags",
            "+genpts+igndts",
            "-err_detect",
            "explode",
            "-i",
            ts_file_path,
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-ar",
            "48000",
            "-copytb",
            "1",
            "-af",
            "aresample=async=1:min_comp=0.01",
            "-max_muxing_queue_size",
            "1024",
            "-write_xing",
            "0",
            "-y",
            output_file,
        ]
        run_subprocess_safe(fallback_command, check=True, capture_output=True, text=True)
        audio_files.append(output_file)

    log_post_process(f"音频提取完成: 共 {len(audio_files)} 个文件")
    return audio_files


def get_m3u8_total_duration(m3u8_file: str) -> float:
    """计算 M3U8 播放列表声明的总时长。"""

    try:
        with open(m3u8_file, "r", encoding="utf-8") as handle:
            content = handle.read()

        total_duration = 0.0
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#EXTINF:"):
                duration_str = line.split(":")[1].split(",")[0]
                total_duration += float(duration_str)
        return total_duration
    except Exception as exc:  # pragma: no cover - defensive logging
        log_post_process(f"计算M3U8总时长失败: {exc}", "error")
        return 0.0


def extract_audio_from_m3u8_segments(
    m3u8_path: str, output_dir: str, config: ConfigReader
) -> list[str]:
    """基于 HLS 切片提取音频并保持时长信息。"""

    log_post_process(f"从M3U8切片提取音频: {os.path.basename(m3u8_path)}")

    total_duration = get_m3u8_total_duration(m3u8_path)
    log_post_process(f"M3U8总时长: {total_duration}秒", "debug")

    m3u8_dir = os.path.dirname(m3u8_path)
    ts_segments: list[str] = []

    try:
        with open(m3u8_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in lines:
            line = line.strip()
            if line.endswith(".ts"):
                ts_file = os.path.join(m3u8_dir, line)
                if os.path.exists(ts_file):
                    ts_segments.append(ts_file)
        log_post_process(f"找到 {len(ts_segments)} 个TS切片文件", "debug")
    except Exception as exc:
        log_post_process(f"读取M3U8文件失败: {exc}", "error")
        return []

    if not ts_segments:
        log_post_process("未找到TS切片文件", "error")
        return []

    max_duration = config.get_audio_segment_time()
    audio_codec_params = config.get_audio_codec_params()
    audio_bitrate = config.get_audio_bitrate()
    audio_sample_rate = config.get_audio_sample_rate()

    file_name = os.path.basename(m3u8_path).rsplit(".", 1)[0]
    audio_files: list[str] = []

    if total_duration <= max_duration:
        log_post_process(
            f"音频时长({total_duration}s)未超过阈值({max_duration}s)，合并为单个文件",
            "debug",
        )
        output_file = os.path.join(output_dir, f"{file_name}.{audio_codec_params['extension']}")
        concat_file = os.path.join(output_dir, f"{file_name}_concat.txt")
        try:
            with open(concat_file, "w", encoding="utf-8") as handle:
                for ts_file in ts_segments:
                    handle.write(f"file '{ts_file}'\n")

            ffmpeg_path = get_ffmpeg_path("ffmpeg")
            ffmpeg_command = [
                ffmpeg_path,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file,
                "-vn",
                "-acodec",
                audio_codec_params["codec"],
                "-ab",
                audio_bitrate,
                "-ar",
                audio_sample_rate,
                "-y",
                output_file,
            ]

            run_subprocess_safe(ffmpeg_command, check=True, capture_output=True, text=True)
            audio_files.append(output_file)
            os.remove(concat_file)
        except Exception as exc:
            log_post_process(f"合并音频失败: {exc}", "error")
            if os.path.exists(concat_file):
                os.remove(concat_file)
    else:
        log_post_process(
            f"音频时长({total_duration}s)超过阈值({max_duration}s)，需要切分",
            "debug",
        )
        segments = math.ceil(total_duration / max_duration)
        log_post_process(f"将分为 {segments} 个音频片段", "debug")
        temp_audio = os.path.join(output_dir, f"{file_name}_temp.{audio_codec_params['extension']}")
        try:
            concat_file = os.path.join(output_dir, f"{file_name}_concat.txt")
            with open(concat_file, "w", encoding="utf-8") as handle:
                for ts_file in ts_segments:
                    handle.write(f"file '{ts_file}'\n")

            ffmpeg_path = get_ffmpeg_path("ffmpeg")
            merge_command = [
                ffmpeg_path,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file,
                "-vn",
                "-acodec",
                audio_codec_params["codec"],
                "-ab",
                audio_bitrate,
                "-ar",
                audio_sample_rate,
                "-y",
                temp_audio,
            ]

            run_subprocess_safe(merge_command, check=True, capture_output=True, text=True)

            for index in range(segments):
                start_time = index * max_duration
                output_file = os.path.join(
                    output_dir,
                    f"{file_name}_part{index + 1:03d}_of_{segments:03d}.{audio_codec_params['extension']}",
                )
                split_command = [
                    ffmpeg_path,
                    "-i",
                    temp_audio,
                    "-ss",
                    str(start_time),
                    "-t",
                    str(max_duration),
                    "-acodec",
                    "copy",
                    "-y",
                    output_file,
                ]
                run_subprocess_safe(split_command, check=True, capture_output=True, text=True)
                audio_files.append(output_file)

            os.remove(concat_file)
            os.remove(temp_audio)
        except Exception as exc:
            log_post_process(f"切分音频失败: {exc}", "error")
            for temp_file in [concat_file, temp_audio]:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)

    log_post_process(f"从M3U8提取音频完成: 共 {len(audio_files)} 个文件")
    return audio_files


class MediaProcessor:
    """媒体相关后处理任务的门面类。"""

    def __init__(self, config: Optional[ConfigReader] = None) -> None:
        self._config = config or ConfigReader()

    @property
    def config(self) -> ConfigReader:
        return self._config

    def ensure_ffmpeg_available(self) -> bool:
        return ensure_ffmpeg_available()

    def get_ffmpeg_path(self, tool_name: str = "ffmpeg") -> str:
        return get_ffmpeg_path(tool_name)

    def convert_ts_to_m3u8(self, ts_file_path: str, output_dir: Optional[str] = None) -> str:
        return convert_ts_to_m3u8(ts_file_path, output_dir, self._config)

    def get_video_duration(self, video_file_path: str) -> Optional[float]:
        return get_video_duration(video_file_path)

    def extract_first_frame_cover(self, ts_file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        return extract_first_frame_cover(ts_file_path, output_dir)

    def extract_and_split_audio(
        self, ts_file_path: str, output_dir: Optional[str] = None
    ) -> list[str]:
        return extract_and_split_audio(ts_file_path, output_dir, self._config)

    def extract_audio_from_m3u8_segments(
        self, m3u8_path: str, output_dir: str
    ) -> list[str]:
        return extract_audio_from_m3u8_segments(m3u8_path, output_dir, self._config)

    def get_m3u8_total_duration(self, m3u8_file: str) -> float:
        return get_m3u8_total_duration(m3u8_file)
