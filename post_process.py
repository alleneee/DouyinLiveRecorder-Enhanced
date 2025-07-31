#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
直播录制后处理脚本
功能：
1. 将TS文件转换为M3U8格式
2. 提取音频并切分
3. 上传到OSS
4. 调用API通知结果
"""

import argparse
import os
import subprocess
import datetime
import json
import time
import math
import threading
import shutil
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from config_reader import ConfigReader
from api_client import APIClient, create_live_record_data, create_mp3_info

# 添加日志导入
from src.logger import log_post_process_key, log_post_process_error, log_post_process_debug, _logger_manager, logger


def log_post_process(message: str, level: str = "info"):
    """
    后处理专用日志记录函数 - 整合到app.log
    :param message: 要记录的消息
    :param level: 日志级别 (info, error, debug)
    """
    if level.lower() == "error":
        log_post_process_error(message)
    elif level.lower() == "debug":
        log_post_process_debug(message)
    else:
        log_post_process_key(message)


def get_ffmpeg_path(tool_name: str = "ffmpeg") -> str:
    """
    跨平台获取FFmpeg工具路径，智能检测项目安装的FFmpeg
    :param tool_name: 工具名称 (ffmpeg, ffprobe)
    :return: 工具的完整路径
    """
    import sys
    import platform

    # 首先尝试从PATH中查找
    tool_path = shutil.which(tool_name)
    if tool_path:
        log_post_process(f"在PATH中找到{tool_name}: {tool_path}", "debug")
        return tool_path

    # 获取项目根目录（与ffmpeg_install.py中的逻辑一致）
    execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]
    project_ffmpeg_dir = os.path.join(execute_dir, 'ffmpeg')

    # 检测项目安装的FFmpeg（优先级最高）
    if platform.system() == "Windows":
        tool_exe = f"{tool_name}.exe"
        project_paths = [
            os.path.join(project_ffmpeg_dir, tool_exe),  # 项目根目录/ffmpeg/
            os.path.join(project_ffmpeg_dir, "bin", tool_exe),  # 项目根目录/ffmpeg/bin/
        ]
    else:
        project_paths = [
            os.path.join(project_ffmpeg_dir, tool_name),
            os.path.join(project_ffmpeg_dir, "bin", tool_name),
        ]

    for path in project_paths:
        if os.path.exists(path):
            return path

    # Mac环境下的系统路径
    if platform.system() == "Darwin":
        mac_paths = [
            f"/opt/homebrew/bin/{tool_name}",
            f"/usr/local/bin/{tool_name}",
        ]
        for path in mac_paths:
            if os.path.exists(path):
                return path

    # Windows环境下的常见安装路径（动态搜索）
    if platform.system() == "Windows":
        win_exe = f"{tool_name}.exe"
        # 搜索常见的FFmpeg安装目录
        search_paths = [
            "C:\\ffmpeg",
            "C:\\Program Files\\ffmpeg",
            "C:\\Program Files (x86)\\ffmpeg",
        ]

        # 搜索以ffmpeg开头的目录
        for drive in ["C:\\"]:
            try:
                for item in os.listdir(drive):
                    if item.lower().startswith("ffmpeg") and os.path.isdir(os.path.join(drive, item)):
                        search_paths.append(os.path.join(drive, item))
            except (PermissionError, FileNotFoundError):
                pass

        # 在搜索路径中查找工具
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

    # 本地目录查找
    local_paths = []
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

    # 最后尝试默认命令
    log_post_process(f"未找到{tool_name}，使用默认命令", "debug")
    return tool_name


def run_subprocess_safe(cmd, **kwargs):
    """
    安全的subprocess调用，处理Windows编码问题
    """
    import platform
    if platform.system() == "Windows":
        # Windows下设置编码参数
        kwargs.setdefault('encoding', 'utf-8')
        kwargs.setdefault('errors', 'ignore')
    return subprocess.run(cmd, **kwargs)


def ensure_ffmpeg_available() -> bool:
    """
    确保FFmpeg可用，如果不可用则尝试安装
    :return: FFmpeg是否可用
    """
    try:
        # 尝试检测ffmpeg
        ffmpeg_path = get_ffmpeg_path("ffmpeg")
        ffprobe_path = get_ffmpeg_path("ffprobe")

        # 测试是否可执行
        result = run_subprocess_safe([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            log_post_process(f"FFmpeg可用: {ffmpeg_path}", "debug")
            return True
        else:
            log_post_process(f"FFmpeg不可执行: {ffmpeg_path}", "error")
    except Exception as e:
        log_post_process(f"FFmpeg检测失败: {e}", "error")

    # 如果检测失败，尝试使用项目的安装脚本
    try:
        log_post_process("尝试自动安装FFmpeg...", "info")
        from ffmpeg_install import check_ffmpeg
        if check_ffmpeg():
            log_post_process("FFmpeg安装成功", "info")
            return True
        else:
            log_post_process("FFmpeg自动安装失败", "error")
    except ImportError:
        log_post_process("无法导入FFmpeg安装模块", "error")
    except Exception as e:
        log_post_process(f"FFmpeg自动安装异常: {e}", "error")

    return False


def convert_ts_to_m3u8(ts_file_path: str, output_dir: Optional[str] = None, config: Optional[ConfigReader] = None) -> str:
    """
    将TS文件转换为M3U8格式
    :param ts_file_path: TS文件路径
    :param output_dir: 输出目录，如果不指定则使用TS文件所在目录
    :param config: 配置读取器
    :return: M3U8文件路径
    """
    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")
    
    # 如果没有提供配置，使用默认配置
    if config is None:
        config = ConfigReader()
    
    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit('.', 1)[0]
    
    if output_dir is None:
        output_dir = file_dir
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # M3U8输出路径
    m3u8_path = os.path.join(output_dir, f"{file_name}.m3u8")
    segment_pattern = os.path.join(output_dir, f"{file_name}_%03d.ts")
    
    # 从配置读取参数
    segment_time = config.get_m3u8_segment_time()
    list_size = config.get_m3u8_list_size()
    hls_flags = config.get_hls_flags()
    
    # 构建HLS标志列表 - 使用更精确的切分策略
    all_hls_flags = [
        "split_by_time",      # 按时间切分
        "independent_segments"  # 确保每个切片都是独立的
    ]
    if hls_flags:
        all_hls_flags.extend(hls_flags)

    # 将标志列表转换为字符串
    hls_flags_str = "+".join(all_hls_flags)  # 使用+连接而不是逗号

    # FFmpeg命令：使用精确切分模式（重新编码以确保严格按时间切分）
    ffmpeg_path = get_ffmpeg_path("ffmpeg")

    ffmpeg_command = [
        ffmpeg_path,
        "-i", ts_file_path,
        # 视频编码设置
        "-c:v", "libx264",  # 重新编码视频以确保精确切分
        "-preset", "fast",  # 快速编码预设
        "-crf", "23",       # 保持较好的质量
        # 音频编码设置
        "-c:a", "aac",      # 重新编码音频
        "-b:a", "128k",     # 音频比特率
        # 关键帧控制 - 确保精确按时间切分
        "-g", str(int(segment_time * 25)),  # GOP大小=切片时间*帧率（假设25fps）
        "-keyint_min", str(int(segment_time * 25)),  # 最小关键帧间隔
        "-sc_threshold", "0",  # 禁用场景切换检测，避免额外关键帧
        "-force_key_frames", f"expr:gte(t,n_forced*{segment_time})",  # 强制在精确时间点生成关键帧
        # HLS设置
        "-hls_time", str(segment_time),  # 精确切片时间
        "-hls_list_size", str(list_size),  # 切片数量限制
        "-hls_segment_filename", segment_pattern,
        "-hls_flags", hls_flags_str,
        "-y",  # 覆盖已存在的文件
    ]
    
    ffmpeg_command.append(m3u8_path)

    log_post_process(f"开始M3U8转换: {os.path.basename(ts_file_path)}")
    log_post_process(f"转换参数: 切片时间={segment_time}秒", "debug")

    try:
        run_subprocess_safe(ffmpeg_command, check=True, capture_output=True, text=True)
        log_post_process(f"M3U8转换完成: {os.path.basename(m3u8_path)}")
        return m3u8_path
    except subprocess.CalledProcessError as e:
        log_post_process(f"M3U8转换失败: {e.stderr}", "error")
        raise


def get_video_duration(video_file_path: str) -> Optional[float]:
    """
    获取视频文件的时长（秒）
    :param video_file_path: 视频文件路径
    :return: 视频时长（秒），失败返回None
    """
    if not os.path.exists(video_file_path):
        log_post_process(f"视频文件不存在: {video_file_path}", "error")
        return None

    # FFprobe命令：获取视频时长
    ffprobe_path = get_ffmpeg_path("ffprobe")
    ffprobe_command = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_file_path
    ]

    try:
        result = run_subprocess_safe(ffprobe_command, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        log_post_process(f"获取视频时长: {duration:.2f}秒", "debug")
        return duration
    except subprocess.CalledProcessError as e:
        log_post_process(f"获取视频时长失败: {e.stderr}", "error")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        log_post_process(f"解析视频时长信息失败: {e}", "error")
        return None


def extract_first_frame_cover(ts_file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    从TS文件提取第一帧作为封面图片
    :param ts_file_path: TS文件路径
    :param output_dir: 输出目录
    :return: 封面图片文件路径，失败返回None
    """
    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")

    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit('.', 1)[0]

    if output_dir is None:
        output_dir = file_dir

    os.makedirs(output_dir, exist_ok=True)

    # 生成封面图片文件名
    cover_file = os.path.join(output_dir, f"{file_name}_cover.jpg")

    log_post_process(f"开始提取封面图片: {os.path.basename(ts_file_path)}")

    # FFmpeg命令：提取第一帧
    ffmpeg_path = get_ffmpeg_path("ffmpeg")
    ffmpeg_command = [
        ffmpeg_path,
        "-i", ts_file_path,
        "-vframes", "1",  # 只提取1帧
        "-q:v", "2",      # 高质量
        "-y",             # 覆盖已存在的文件
        cover_file
    ]

    try:
        run_subprocess_safe(ffmpeg_command, check=True, capture_output=True, text=True)
        log_post_process(f"封面图片提取完成: {os.path.basename(cover_file)}")
        return cover_file
    except subprocess.CalledProcessError as e:
        log_post_process(f"封面图片提取失败: {e.stderr}", "error")
        return None


def extract_and_split_audio(ts_file_path: str, output_dir: Optional[str] = None, config: Optional[ConfigReader] = None) -> list:
    """
    从TS文件提取音频并切割成多个片段
    :param ts_file_path: TS文件路径
    :param output_dir: 输出目录
    :param config: 配置读取器
    :return: 音频文件路径列表
    """
    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")

    # 确保FFmpeg可用
    if not ensure_ffmpeg_available():
        log_post_process("FFmpeg不可用，无法进行音频处理", "error")
        return []
    
    # 如果没有提供配置，使用默认配置
    if config is None:
        config = ConfigReader()
    
    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit('.', 1)[0]
    
    if output_dir is None:
        output_dir = file_dir
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 从配置读取参数
    max_duration = config.get_audio_segment_time()
    audio_codec_params = config.get_audio_codec_params()
    audio_bitrate = config.get_audio_bitrate()
    audio_sample_rate = config.get_audio_sample_rate()
    
    log_post_process(f"开始音频提取: {os.path.basename(ts_file_path)}")
    log_post_process(f"音频参数: 切分时间={max_duration}秒, 格式={audio_codec_params['extension']}, 比特率={audio_bitrate}", "debug")

    # 首先获取视频总时长
    ffprobe_path = get_ffmpeg_path("ffprobe")
    duration_cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        ts_file_path
    ]

    try:
        log_post_process(f"执行ffprobe命令: {' '.join(duration_cmd)}", "debug")

        # 使用安全的subprocess调用
        result = run_subprocess_safe(duration_cmd, capture_output=True, text=True, check=True)

        log_post_process(f"ffprobe返回码: {result.returncode}", "debug")
        log_post_process(f"ffprobe输出长度: {len(result.stdout) if result.stdout else 0}", "debug")

        if result.stdout:
            log_post_process(f"ffprobe输出前200字符: {result.stdout[:200]}...", "debug")
        else:
            log_post_process("ffprobe输出为空", "debug")

        if not result.stdout or result.stdout.strip() == "":
            raise ValueError("ffprobe返回空输出")

        # 检查是否为空JSON（只包含空白的JSON对象）
        if result.stdout.strip() in ['{}', '{\n}', '{\n\n}']:
            raise ValueError("ffprobe返回空JSON对象，可能文件不存在或无法读取")

        info = json.loads(result.stdout)
        if 'format' not in info:
            raise ValueError("ffprobe输出中缺少format信息")
        if 'duration' not in info['format']:
            raise ValueError("ffprobe输出中缺少duration信息")
        if info['format']['duration'] is None:
            raise ValueError("duration值为null")

        total_duration = float(info['format']['duration'])
        log_post_process(f"获取到视频时长: {total_duration}秒", "debug")
    except subprocess.CalledProcessError as e:
        log_post_process(f"ffprobe命令执行失败: 返回码={e.returncode}", "error")
        log_post_process(f"ffprobe stderr: {e.stderr}", "error")
        log_post_process(f"ffprobe stdout: {e.stdout}", "error")
        total_duration = None
    except json.JSONDecodeError as e:
        log_post_process(f"解析ffprobe JSON输出失败: {e}", "error")
        if 'result' in locals() and result.stdout:
            log_post_process(f"原始输出: {repr(result.stdout)}", "error")
        total_duration = None
    except Exception as e:
        log_post_process(f"获取视频时长失败: {e}", "error")
        total_duration = None
    
    audio_files = []

    # 判断是否需要切分
    should_split = False
    segments = 1

    if total_duration is not None:
        log_post_process(f"视频时长: {total_duration}秒, 切分阈值: {max_duration}秒", "debug")
        if total_duration > max_duration:
            should_split = True
            segments = math.ceil(total_duration / max_duration)
            log_post_process(f"需要切割，将分为 {segments} 个片段", "debug")
        else:
            log_post_process(f"视频时长未超过阈值，不需要切割", "debug")
    else:
        log_post_process(f"无法获取视频时长，将尝试按时间切分（每{max_duration}秒一段）", "debug")
        # 即使无法获取时长，也尝试切分（设置一个合理的默认分段数）
        should_split = True
        segments = 3  # 默认切分为3段，可以根据需要调整

    if should_split:
        log_post_process(f"开始音频切割，使用Java分片方法确保完整性", "debug")

        # 优先使用FFmpeg segment模式（Java分片方法）
        ffmpeg_path = get_ffmpeg_path("ffmpeg")
        segment_pattern = os.path.join(output_dir, f"{file_name}_part%03d.{audio_codec_params['extension']}")

        segment_command = [
            ffmpeg_path,
            # 时间戳和错误处理优化
            "-fflags", "+genpts+igndts",      # 修复时间戳连续性
            "-err_detect", "explode",         # 严格错误检测
            "-i", ts_file_path,
            "-vn",  # 不要视频
            # 音频编码优化
            "-c:a", "libmp3lame",             # 使用libmp3lame编码器
            "-q:a", "2",                      # VBR模式，中等音质
            "-ar", "48000",                   # 统一使用48kHz采样率
            "-copytb", "1",                   # 继承输入流时间基
            "-af", "aresample=async=1:min_comp=0.01",  # 动态填充样本防截断
            "-max_muxing_queue_size", "1024", # 扩大缓冲区防阻塞
            "-write_xing", "0",               # 禁用MP3头信息干扰
            # 分片核心参数（Java方法）
            "-f", "segment",                  # 启用分片模式
            "-segment_time", str(max_duration),  # 每个分片时间长度
            "-reset_timestamps", "1",         # 重置分片时间戳（从0开始）
            "-segment_start_number", "1",     # 让编号从1开始
            "-segment_format", audio_codec_params['extension'],  # 指定分片格式
            "-y",
            segment_pattern
        ]

        try:
            log_post_process("使用Java分片方法提取音频", "debug")
            run_subprocess_safe(segment_command, check=True, capture_output=True, text=True)

            # 收集生成的分片文件
            i = 1
            while True:
                segment_file = os.path.join(output_dir, f"{file_name}_part{i:03d}.{audio_codec_params['extension']}")
                if os.path.exists(segment_file):
                    audio_files.append(segment_file)
                    i += 1
                else:
                    break

            log_post_process(f"Java分片方法完成，生成 {len(audio_files)} 个音频文件", "debug")

        except subprocess.CalledProcessError as e:
            log_post_process(f"Java分片方法失败: {e.stderr}", "error")
            log_post_process("回退到传统切分方法", "debug")

            # 回退到传统方法
            for i in range(segments):
                start_time = i * max_duration
                output_file = os.path.join(output_dir, f"{file_name}_part{i+1:03d}_of_{segments:03d}.{audio_codec_params['extension']}")

                fallback_command = [
                    ffmpeg_path,
                    "-fflags", "+genpts+igndts",
                    "-err_detect", "explode",
                    "-i", ts_file_path,
                    "-ss", str(start_time),
                    "-t", str(max_duration),
                    "-vn",
                    "-c:a", "libmp3lame",
                    "-q:a", "2",
                    "-ar", "48000",
                    "-copytb", "1",
                    "-af", "aresample=async=1:min_comp=0.01",
                    "-max_muxing_queue_size", "1024",
                    "-write_xing", "0",
                    "-y",
                    output_file
                ]

                try:
                    run_subprocess_safe(fallback_command, check=True, capture_output=True, text=True)
                    audio_files.append(output_file)
                except subprocess.CalledProcessError as e:
                    log_post_process(f"音频片段提取失败: {e.stderr}", "error")
    else:
        # 不需要切割，但使用分片模式确保音频完整性
        log_post_process("使用Java分片模式提取完整音频（单个大分片）", "debug")

        # 使用一个大的分片时间（比视频时长更长）来提取完整音频
        large_segment_time = max_duration * 2  # 使用2倍的切分时间作为单个分片
        segment_pattern = os.path.join(output_dir, f"{file_name}_%03d.{audio_codec_params['extension']}")

        ffmpeg_path = get_ffmpeg_path("ffmpeg")
        segment_command = [
            ffmpeg_path,
            # 时间戳和错误处理优化
            "-fflags", "+genpts+igndts",      # 修复时间戳连续性
            "-err_detect", "explode",         # 严格错误检测
            "-i", ts_file_path,
            "-vn",  # 不要视频
            # 音频编码优化
            "-c:a", "libmp3lame",             # 使用libmp3lame编码器
            "-q:a", "2",                      # VBR模式，中等音质
            "-ar", "48000",                   # 统一使用48kHz采样率
            "-copytb", "1",                   # 继承输入流时间基
            "-af", "aresample=async=1:min_comp=0.01",  # 动态填充样本防截断
            "-max_muxing_queue_size", "1024", # 扩大缓冲区防阻塞
            "-write_xing", "0",               # 禁用MP3头信息干扰
            # Java分片模式参数（确保音频完整性）
            "-f", "segment",                  # 启用分片模式
            "-segment_time", str(large_segment_time),  # 大分片时间
            "-reset_timestamps", "1",         # 重置分片时间戳
            "-segment_start_number", "1",     # 编号从1开始
            "-segment_format", audio_codec_params['extension'],  # 分片格式
            "-y",
            segment_pattern
        ]

        try:
            log_post_process("使用Java分片模式确保音频完整性", "debug")
            run_subprocess_safe(segment_command, check=True, capture_output=True, text=True)

            # 收集生成的分片文件（通常只有一个）
            i = 1
            while True:
                segment_file = os.path.join(output_dir, f"{file_name}_{i:03d}.{audio_codec_params['extension']}")
                if os.path.exists(segment_file):
                    audio_files.append(segment_file)
                    i += 1
                else:
                    break

            if audio_files:
                log_post_process(f"Java分片模式提取完成，生成 {len(audio_files)} 个音频文件", "debug")
            else:
                log_post_process("Java分片模式未生成文件，回退到传统方法", "debug")
                raise Exception("分片模式未生成文件")

        except Exception as e:
            log_post_process(f"Java分片模式失败: {e}，回退到传统方法", "debug")

            # 回退到传统单文件方法
            output_file = os.path.join(output_dir, f"{file_name}.{audio_codec_params['extension']}")
            fallback_command = [
                ffmpeg_path,
                "-fflags", "+genpts+igndts",
                "-err_detect", "explode",
                "-i", ts_file_path,
                "-vn",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                "-ar", "48000",
                "-copytb", "1",
                "-af", "aresample=async=1:min_comp=0.01",
                "-max_muxing_queue_size", "1024",
                "-write_xing", "0",
                "-y",
                output_file
            ]

            try:
                run_subprocess_safe(fallback_command, check=True, capture_output=True, text=True)
                audio_files.append(output_file)
            except subprocess.CalledProcessError as e:
                logger.error(f"音频提取失败: {e.stderr}")
                raise

    log_post_process(f"音频提取完成: 共 {len(audio_files)} 个文件")
    return audio_files


def get_m3u8_total_duration(m3u8_file: str) -> float:
    """
    计算M3U8文件的总时长
    :param m3u8_file: M3U8文件路径
    :return: 总时长（秒）
    """
    try:
        with open(m3u8_file, 'r', encoding='utf-8') as f:
            content = f.read()

        total_duration = 0.0
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#EXTINF:'):
                duration_str = line.split(':')[1].split(',')[0]
                duration = float(duration_str)
                total_duration += duration

        return total_duration
    except Exception as e:
        log_post_process(f"计算M3U8总时长失败: {e}", "error")
        return 0.0


def extract_audio_from_m3u8_segments(m3u8_path: str, output_dir: str, config: ConfigReader) -> list:
    """
    从M3U8切片中提取音频，确保与M3U8时长一致
    :param m3u8_path: M3U8文件路径
    :param output_dir: 输出目录
    :param config: 配置读取器
    :return: 生成的音频文件列表
    """
    log_post_process(f"从M3U8切片提取音频: {os.path.basename(m3u8_path)}")

    # 获取M3U8的实际总时长
    total_duration = get_m3u8_total_duration(m3u8_path)
    log_post_process(f"M3U8总时长: {total_duration}秒", "debug")

    # 读取M3U8文件，获取所有TS切片文件
    m3u8_dir = os.path.dirname(m3u8_path)
    ts_segments = []

    try:
        with open(m3u8_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if line.endswith('.ts'):
                ts_file = os.path.join(m3u8_dir, line)
                if os.path.exists(ts_file):
                    ts_segments.append(ts_file)

        log_post_process(f"找到 {len(ts_segments)} 个TS切片文件", "debug")

    except Exception as e:
        log_post_process(f"读取M3U8文件失败: {e}", "error")
        return []

    if not ts_segments:
        log_post_process("未找到TS切片文件", "error")
        return []

    # 音频参数
    max_duration = config.get_audio_segment_time()
    audio_codec_params = config.get_audio_codec_params()
    audio_bitrate = config.get_audio_bitrate()
    audio_sample_rate = config.get_audio_sample_rate()

    file_name = os.path.basename(m3u8_path).rsplit('.', 1)[0]
    audio_files = []

    # 判断是否需要切分
    if total_duration <= max_duration:
        # 不需要切分，合并所有切片为一个音频文件
        log_post_process(f"音频时长({total_duration}s)未超过阈值({max_duration}s)，合并为单个文件", "debug")

        output_file = os.path.join(output_dir, f"{file_name}.{audio_codec_params['extension']}")

        # 创建文件列表用于concat
        concat_file = os.path.join(output_dir, f"{file_name}_concat.txt")
        try:
            with open(concat_file, 'w', encoding='utf-8') as f:
                for ts_file in ts_segments:
                    f.write(f"file '{ts_file}'\n")

            ffmpeg_path = get_ffmpeg_path("ffmpeg")
            ffmpeg_command = [
                ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-vn",  # 不要视频
                "-acodec", audio_codec_params['codec'],
                "-ab", audio_bitrate,
                "-ar", audio_sample_rate,
                "-y",
                output_file
            ]

            run_subprocess_safe(ffmpeg_command, check=True, capture_output=True, text=True)
            audio_files.append(output_file)

            # 清理临时文件
            os.remove(concat_file)

        except Exception as e:
            log_post_process(f"合并音频失败: {e}", "error")
            if os.path.exists(concat_file):
                os.remove(concat_file)

    else:
        # 需要切分，按时间段合并切片
        log_post_process(f"音频时长({total_duration}s)超过阈值({max_duration}s)，需要切分", "debug")

        segments = math.ceil(total_duration / max_duration)
        log_post_process(f"将分为 {segments} 个音频片段", "debug")

        # 这里可以实现更复杂的切分逻辑
        # 暂时使用简化方案：提取完整音频然后切分
        temp_audio = os.path.join(output_dir, f"{file_name}_temp.{audio_codec_params['extension']}")

        try:
            # 先合并所有切片
            concat_file = os.path.join(output_dir, f"{file_name}_concat.txt")
            with open(concat_file, 'w', encoding='utf-8') as f:
                for ts_file in ts_segments:
                    f.write(f"file '{ts_file}'\n")

            ffmpeg_path = get_ffmpeg_path("ffmpeg")

            # 合并音频
            merge_command = [
                ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-vn",
                "-acodec", audio_codec_params['codec'],
                "-ab", audio_bitrate,
                "-ar", audio_sample_rate,
                "-y",
                temp_audio
            ]

            run_subprocess_safe(merge_command, check=True, capture_output=True, text=True)

            # 然后按时间切分
            for i in range(segments):
                start_time = i * max_duration
                output_file = os.path.join(output_dir, f"{file_name}_part{i+1:03d}_of_{segments:03d}.{audio_codec_params['extension']}")

                split_command = [
                    ffmpeg_path,
                    "-i", temp_audio,
                    "-ss", str(start_time),
                    "-t", str(max_duration),
                    "-acodec", "copy",  # 直接复制，不重新编码
                    "-y",
                    output_file
                ]

                run_subprocess_safe(split_command, check=True, capture_output=True, text=True)
                audio_files.append(output_file)

            # 清理临时文件
            os.remove(concat_file)
            os.remove(temp_audio)

        except Exception as e:
            log_post_process(f"切分音频失败: {e}", "error")
            # 清理临时文件
            for temp_file in [concat_file, temp_audio]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

    log_post_process(f"从M3U8提取音频完成: 共 {len(audio_files)} 个文件")
    return audio_files


def upload_to_oss(file_path: str, oss_config: dict, oss_key: Optional[str] = None):
    """
    上传文件到阿里云OSS（优化版本）
    :param file_path: 要上传的文件路径
    :param oss_config: OSS配置信息
    :param oss_key: OSS中的文件路径，如果不指定则使用文件名
    """
    try:
        import oss2
        from oss2.models import PartInfo
    except ImportError:
        logger.error("需要安装oss2库: pip install oss2")
        return False

    # 从配置中获取OSS参数
    access_key_id = oss_config.get('access_key_id')
    access_key_secret = oss_config.get('access_key_secret')
    endpoint = oss_config.get('endpoint')
    bucket_name = oss_config.get('bucket_name')
    chunk_size = oss_config.get('chunk_size', 8388608)  # 默认8MB
    retry_times = oss_config.get('retry_times', 3)

    if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
        logger.error("OSS配置信息不完整")
        return False

    # 创建OSS认证和Bucket对象
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # 如果没有指定OSS key，使用文件名
    if oss_key is None:
        oss_key = os.path.basename(file_path)

    # 获取文件大小
    file_size = os.path.getsize(file_path)
    logger.info(f"正在上传文件到OSS: {file_path} -> {oss_key} (大小: {file_size / 1024 / 1024:.2f}MB)")

    try:
        # 强制使用并发分片上传方式（不使用简单上传）
        logger.info(f"使用并发分片上传方式，分片大小: {chunk_size / 1024 / 1024:.2f}MB")
        logger.info(f"文件大小: {file_size / 1024 / 1024:.2f}MB，并发线程数: {oss_config.get('max_upload_threads', 4)}")

        # 使用优化的断点续传参数
        oss2.resumable_upload(
            bucket,
            oss_key,
            file_path,
            part_size=chunk_size,  # 分片大小
            num_threads=oss_config.get('max_upload_threads', 4),  # 并发线程数
            store=oss2.ResumableStore(root='/tmp'),  # 断点续传存储目录
            progress_callback=lambda consumed_bytes, total_bytes:
                logger.info(f"上传进度: {consumed_bytes / total_bytes * 100:.1f}% ({consumed_bytes / 1024 / 1024:.2f}MB / {total_bytes / 1024 / 1024:.2f}MB)")
                if consumed_bytes % (chunk_size * 5) == 0 or consumed_bytes == total_bytes  # 每5个分片或完成时打印
                else None
        )

        logger.info(f"文件上传成功: {oss_key}")
        return True

    except Exception as e:
        logger.error(f"文件上传失败: {e}")

        # 重试机制 - 使用并发上传
        for retry in range(retry_times):
            logger.info(f"正在重试上传 ({retry + 1}/{retry_times})")
            try:
                # 重试时也使用并发分片上传
                oss2.resumable_upload(
                    bucket,
                    oss_key,
                    file_path,
                    part_size=chunk_size,
                    num_threads=oss_config.get('max_upload_threads', 4),
                    store=oss2.ResumableStore(root='/tmp')
                )
                logger.info(f"重试上传成功: {oss_key}")
                return True
            except Exception as retry_e:
                logger.error(f"重试 {retry + 1} 失败: {retry_e}")
                if retry == retry_times - 1:
                    logger.error(f"所有重试均失败，上传终止: {oss_key}")

        return False


def upload_files_to_oss_concurrent(files_info: list, oss_config: dict) -> list:
    """
    并发上传多个文件到OSS
    :param files_info: 文件信息列表，每个元素包含 {'file_path': str, 'oss_key': str, 'file_type': str, 'file_name': str}
    :param oss_config: OSS配置信息
    :return: 成功上传的文件信息列表
    """
    max_workers = min(oss_config.get('max_upload_threads', 4), len(files_info))
    uploaded_files = []
    upload_lock = threading.Lock()

    def upload_single_file(file_info):
        """上传单个文件的任务函数"""
        try:
            success = upload_to_oss(file_info['file_path'], oss_config, file_info['oss_key'])
            if success:
                with upload_lock:
                    uploaded_files.append(file_info)
                    logger.info(f"文件上传成功: {file_info['file_name']} ({len(uploaded_files)}/{len(files_info)})")
            return success
        except Exception as e:
            logger.error(f"上传文件时发生异常: {file_info['file_name']} - {e}")
            return False

    logger.info(f"开始并发上传 {len(files_info)} 个文件，使用 {max_workers} 个线程")
    start_time = time.time()

    # 使用线程池并发上传
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有上传任务
        future_to_file = {executor.submit(upload_single_file, file_info): file_info for file_info in files_info}

        # 等待所有任务完成
        for future in as_completed(future_to_file):
            file_info = future_to_file[future]
            try:
                success = future.result()
                if not success:
                    logger.error(f"文件上传失败: {file_info['file_name']}")
            except Exception as e:
                logger.error(f"上传任务异常: {file_info['file_name']} - {e}")

    end_time = time.time()
    upload_duration = end_time - start_time

    logger.info(f"并发上传完成: 成功 {len(uploaded_files)}/{len(files_info)} 个文件，耗时 {upload_duration:.2f} 秒")

    return uploaded_files


def main():
    parser = argparse.ArgumentParser(description='处理录制完成的视频文件')
    parser.add_argument('--record_name', type=str, help='录制名称')
    parser.add_argument('--save_file_path', type=str, required=True, help='保存的文件路径')
    parser.add_argument('--save_type', type=str, help='保存类型')
    parser.add_argument('--split_video_by_time', type=str, help='是否按时间分割视频')
    parser.add_argument('--converts_to_mp4', type=str, help='是否转换为MP4')
    parser.add_argument('--room_id', type=str, default='', help='直播间ID(可选)')
    parser.add_argument('--oss_config_file', type=str, default='oss_config.json', help='OSS配置文件路径')
    parser.add_argument('--record_start_time', type=str, default='', help='录制开始时间(格式: YYYY-MM-DD_HH-MM-SS)')
    
    args = parser.parse_args()
    
    ts_file_path = args.save_file_path
    
    # 检查文件是否存在
    if not os.path.exists(ts_file_path):
        logger.error(f"文件不存在: {ts_file_path}")
        return

    # 检查文件是否为TS格式
    if not ts_file_path.lower().endswith('.ts'):
        logger.warning(f"不是TS文件，跳过处理: {ts_file_path}")
        return
    
    # 创建配置读取器
    config = ConfigReader()
    config.print_config_summary()
    
    # 创建输出目录
    output_base_dir = os.path.join(os.path.dirname(ts_file_path), 'processed')
    os.makedirs(output_base_dir, exist_ok=True)
    
    # 从config.ini读取OSS配置
    oss_config = config.get_oss_config_dict()

    # 兼容性处理：如果config.ini中没有配置，尝试从JSON文件读取
    if not oss_config.get('access_key_id') and os.path.exists(args.oss_config_file):
        try:
            with open(args.oss_config_file, 'r', encoding='utf-8') as f:
                json_config = json.load(f)
                if 'oss_config' in json_config:
                    oss_config.update(json_config['oss_config'])
                    logger.warning("从JSON文件读取OSS配置（建议迁移到config.ini）")
        except Exception as e:
            logger.error(f"读取OSS配置文件失败: {e}")
    
    # 记录所有需要上传的文件
    files_to_upload = []
    # 记录成功上传的文件信息
    uploaded_files = []

    # 1. 添加原始TS文件到上传列表（上传到video目录）
    if os.path.exists(ts_file_path):
        files_to_upload.append(ts_file_path)

    # 2. 提取视频第一帧作为封面图片（上传到video目录）
    cover_image_path = None
    try:
        cover_image_path = extract_first_frame_cover(ts_file_path, output_base_dir)
        if cover_image_path:
            files_to_upload.append(cover_image_path)
    except Exception as e:
        log_post_process(f"封面图片提取失败: {e}", "error")

    # 3. 转换TS到M3U8（上传到m3u8目录）
    if config.is_generate_m3u8():
        try:
            m3u8_path = convert_ts_to_m3u8(ts_file_path, output_base_dir, config)
            files_to_upload.append(m3u8_path)

            # 添加所有的TS切片文件（排除原始文件）
            m3u8_dir = os.path.dirname(m3u8_path)
            original_filename_base = os.path.splitext(os.path.basename(ts_file_path))[0]
            
            for file in os.listdir(m3u8_dir):
                if file.endswith('.ts'):
                    # 检查是否为切片文件（包含_数字模式）
                    if '_' in file and file != os.path.basename(ts_file_path):
                        # 进一步验证是否为我们生成的切片文件
                        file_base = file.rsplit('_', 1)[0]  # 移除最后的_xxx.ts部分
                        if file_base == original_filename_base:
                            ts_segment_path = os.path.join(m3u8_dir, file)
                            files_to_upload.append(ts_segment_path)
                        
            # 验证是否找到了切片文件
            segment_count = sum(1 for f in files_to_upload if f.endswith('.ts') and f != ts_file_path and f != m3u8_path)
            log_post_process(f"找到 {segment_count} 个TS切片文件", "debug")

        except Exception as e:
            log_post_process(f"M3U8转换失败: {e}", "error")
    
    # 3. 提取并切割音频（上传到audio目录）
    if config.is_extract_audio():
        try:
            # 获取M3U8的实际时长用于音频提取
            actual_duration = None
            if config.is_generate_m3u8() and 'm3u8_path' in locals() and m3u8_path and os.path.exists(m3u8_path):
                actual_duration = get_m3u8_total_duration(m3u8_path)
                log_post_process(f"使用M3U8实际时长进行音频提取: {actual_duration}秒", "debug")

            # 从原始TS文件提取音频
            # 注意：某些TS文件可能存在音频流不完整的问题，这是原始录制文件的问题
            audio_files = extract_and_split_audio(ts_file_path, output_base_dir, config)

            # 记录时长差异用于调试
            if actual_duration and audio_files:
                log_post_process(f"M3U8时长: {actual_duration:.3f}秒", "debug")
                log_post_process("注意：如果音频时长与M3U8时长不一致，可能是原始TS文件的音频流不完整", "debug")
            files_to_upload.extend(audio_files)
        except Exception as e:
            log_post_process(f"音频提取失败: {e}", "error")
    
    # 4. 上传到OSS
    if config.is_upload_oss() and oss_config.get('enable_upload') and oss_config.get('access_key_id') and files_to_upload:
        # 获取直播间名称作为OSS目录
        record_name = args.record_name or "unknown"
        room_id = args.room_id or "unknown"

        # 使用录制开始时间或当前时间
        if args.record_start_time and args.record_start_time != "unknown":
            try:
                # 解析录制开始时间
                start_time = datetime.datetime.strptime(args.record_start_time, '%Y-%m-%d_%H-%M-%S')
                date_str = start_time.strftime('%Y%m%d')
                time_str = start_time.strftime('%H%M%S')
                datetime_str = start_time.strftime('%Y%m%d_%H%M%S')
                timestamp = str(int(start_time.timestamp()))
            except ValueError:
                logger.warning(f"录制开始时间格式错误: {args.record_start_time}，使用当前时间")
                date_str = time.strftime('%Y%m%d')
                time_str = time.strftime('%H%M%S')
                datetime_str = time.strftime('%Y%m%d_%H%M%S')
                timestamp = str(int(time.time()))
        else:
            # 使用当前时间作为fallback
            date_str = time.strftime('%Y%m%d')
            time_str = time.strftime('%H%M%S')
            datetime_str = time.strftime('%Y%m%d_%H%M%S')
            timestamp = str(int(time.time()))
        
        # 获取OSS上传路径模板
        path_template = config.get_oss_upload_path_template()

        # 准备文件信息列表用于并发上传
        files_info = []
        for file_path in files_to_upload:
            # 构建OSS路径
            file_name = os.path.basename(file_path)
            file_name_no_ext = os.path.splitext(file_name)[0]
            file_ext = os.path.splitext(file_name)[1][1:]  # 去掉点号

            # 改进文件类型分类逻辑
            if file_path.endswith('.m3u8'):
                file_type = 'm3u8'
            elif file_path.endswith('.mp3'):
                file_type = 'audio'
            elif file_path.endswith(('.jpg', '.jpeg', '.png')) and '_cover.' in file_name:
                # 封面图片放在根目录下，使用空字符串作为file_type
                file_type = ''
                print(f"识别为封面图片文件: {file_name} (将放在根目录)")
            elif os.path.abspath(file_path) == os.path.abspath(ts_file_path):
                # 原始TS文件归类为video（使用绝对路径比较）
                file_type = 'video'
                print(f"识别为原始视频文件: {file_name}")
            elif file_path.endswith('.ts'):
                # 切分后的TS文件归类为m3u8
                file_type = 'm3u8'
                print(f"识别为TS切片文件: {file_name}")
            else:
                # 其他文件类型
                file_type = 'video'

            print(f"文件分类: {file_name} -> {file_type} 目录")

            # 使用模板生成OSS路径
            oss_key = path_template.format(
                record_name=record_name,
                room_id=room_id,
                date_str=date_str,
                time_str=time_str,
                datetime_str=datetime_str,
                file_name=file_name,
                file_name_no_ext=file_name_no_ext,
                file_ext=file_ext,
                file_type=file_type,
                timestamp=timestamp
            )

            # 清理路径中的多余斜杠（当file_type为空时可能产生）
            oss_key = oss_key.replace('//', '/').strip('/')

            files_info.append({
                'file_path': file_path,
                'oss_key': oss_key,
                'file_type': file_type,
                'file_name': file_name
            })

        # 根据配置选择上传方式
        log_post_process(f"开始OSS上传: {len(files_info)} 个文件")

        if oss_config.get('enable_concurrent_upload', True) and len(files_info) > 1:
            uploaded_files = upload_files_to_oss_concurrent(files_info, oss_config)
        else:
            uploaded_files = []
            for file_info in files_info:
                success = upload_to_oss(file_info['file_path'], oss_config, file_info['oss_key'])
                if success:
                    uploaded_files.append(file_info)

    # 5. 调用API通知后处理结果
    api_success = False
    if uploaded_files:
        try:
            api_success = notify_api_result(args, uploaded_files, oss_config)
        except Exception as e:
            log_post_process(f"API通知失败: {e}", "error")

    # 6. 后置操作：根据配置决定是否删除本地文件
    if config and config.is_delete_local_files_after_upload():
        if uploaded_files and api_success:
            try:
                cleanup_local_files(uploaded_files, ts_file_path)
            except Exception as e:
                log_post_process(f"文件清理失败: {e}", "error")
        elif uploaded_files and not api_success:
            log_post_process("API通知失败，保留本地文件", "info")
        elif not uploaded_files:
            log_post_process("OSS上传失败，保留本地文件", "info")
    else:
        log_post_process("配置为不删除本地文件，保留所有文件", "info")

    log_post_process("后处理完成")


def notify_api_result(args, uploaded_files: list, oss_config: dict) -> bool:
    """
    通知API后处理结果
    :param args: 命令行参数
    :param uploaded_files: 已上传的文件列表
    :param oss_config: OSS配置信息
    :return: API通知是否成功
    """
    # 创建API客户端
    try:
        api_client = APIClient()
    except Exception as e:
        logger.error(f"API客户端创建失败: {e}")
        print(f"[失败] API客户端创建失败: {e}")
        return False

    # 构建OSS基础URL
    bucket_name = oss_config.get('bucket_name', '')
    endpoint = oss_config.get('endpoint', '')

    if not bucket_name or not endpoint:
        print("[失败] OSS配置信息不完整，无法构建URL")
        return False

    # 根据实际OSS配置构建基础URL
    if endpoint.startswith('oss-'):
        base_url = f"https://{bucket_name}.{endpoint}"
    else:
        base_url = f"https://{bucket_name}.{endpoint}"

    # 分类文件
    m3u8_url = None
    video_url = None
    cover_image_url = None
    mp3_infos = []

    for file_info in uploaded_files:
        file_name = file_info['file_name']
        oss_path = file_info['oss_key']
        full_url = f"{base_url}/{oss_path}"

        # 识别文件类型
        if file_name.endswith('.ts'):
            # 基于OSS路径判断是否为原始TS文件
            # 原始文件通常在video目录下，M3U8切片在m3u8目录下

            if '/video/' in oss_path:
                # 在video目录下的TS文件是原始录制文件
                video_url = full_url
            elif '/m3u8/' in oss_path:
                # 在m3u8目录下的TS文件是M3U8切片，不设置为video_url
                pass
            else:
                # 兼容旧逻辑：如果路径中没有明确的目录标识，使用文件名判断
                name_without_ext = file_name.split('.')[0]
                import re
                is_m3u8_segment = bool(re.search(r'_\d{3}$', name_without_ext))
                is_part_file = 'part' in name_without_ext.lower()

                if not is_m3u8_segment and not is_part_file:
                    # 原始TS录制文件
                    video_url = full_url
        elif file_name.endswith('.m3u8'):
            m3u8_url = full_url
        elif file_name.endswith(('.jpg', '.jpeg', '.png')) and '_cover.' in file_name:
            # 封面图片文件
            cover_image_url = full_url
        elif file_name.endswith('.mp3'):
            # 检查是否为分段音频文件
            if 'part' in file_name:
                # 解析音频片段编号
                try:
                    import re
                    match = re.search(r'_part(\d+)_of_(\d+)', file_name)
                    if match:
                        section = int(match.group(1))
                        mp3_info = create_mp3_info(section, full_url)
                        mp3_infos.append(mp3_info)
                except Exception as e:
                    pass  # 忽略解析失败的音频文件
            else:
                # 完整音频文件，作为第1个片段
                mp3_info = create_mp3_info(1, full_url)
                mp3_infos.append(mp3_info)

    # 创建直播录制数据
    record_name = args.record_name or "unknown"
    room_id = args.room_id or "unknown"

    # 处理录制开始时间格式
    record_start_time = args.record_start_time or ""

    if record_start_time and record_start_time != "unknown":
        try:
            temp_time = record_start_time.replace('_', ' ')
            parts = temp_time.split(' ')
            if len(parts) == 2:
                date_part = parts[0]  # 2024-01-15
                time_part = parts[1].replace('-', ':')  # 14:30:45
                record_start_time = f"{date_part} {time_part}"
            else:
                record_start_time = temp_time
        except Exception as e:
            logger.error(f"录制开始时间格式化失败: {e}")
            record_start_time = ""

    # 生成录制日期和文件名
    if record_start_time:
        try:
            start_time_obj = datetime.datetime.strptime(record_start_time, '%Y-%m-%d %H:%M:%S')
            record_date = start_time_obj.strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"解析录制时间失败: {e}")
            record_date = datetime.datetime.now().strftime('%Y-%m-%d')
    else:
        record_date = datetime.datetime.now().strftime('%Y-%m-%d')

    # 从原始文件路径生成录制文件名
    ts_file_path = args.save_file_path
    record_file_name = os.path.basename(ts_file_path)

    # 数据验证
    validation_errors = []

    if not record_name or record_name == "unknown":
        validation_errors.append("录制名称不能为空或unknown")

    if not room_id or room_id == "unknown":
        validation_errors.append("房间ID不能为空或unknown")

    if not record_start_time:
        validation_errors.append("录制开始时间不能为空")

    if not record_date:
        validation_errors.append("录制日期不能为空")

    if not record_file_name:
        validation_errors.append("录制文件名不能为空")

    # 重要：API需要至少一个URL字段
    if not m3u8_url and not video_url:
        validation_errors.append("至少需要提供 m3u8_url 或 video_url 其中一个")

    if validation_errors:
        logger.error(f"数据验证失败: {'; '.join(validation_errors)}")
        print(f"[失败] 数据验证失败，跳过API通知")
        return False

    try:
        live_record = create_live_record_data(
            record_name=record_name,
            room_id=room_id,
            record_start_time=record_start_time,
            record_date=record_date,
            record_file_name=record_file_name,
            m3u8_url=m3u8_url,
            video_url=video_url,
            mp3_urls=mp3_infos if mp3_infos else None,
            cover_image_url=cover_image_url,
            biz_type="live" 
        )
    except Exception as e:
        logger.error(f"直播录制数据创建失败: {e}")
        print(f"[失败] 直播录制数据创建失败: {e}")
        return False

    # 发送通知
    logger.info(f"开始发送API通知,API请求参数: {json.dumps([live_record], ensure_ascii=False, indent=2)}")
    
    try:
        success = api_client.notify_post_process_result([live_record])
        if success:
            logger.info("API通知发送成功")
            print("[成功] API通知发送成功")
            return True
        else:
            logger.info("API通知发送失败")
            print("[失败] API通知发送失败")
            return False
    except Exception as e:
        logger.info(f"API通知过程中发生异常: {e}")
        print(f"[异常] API通知过程中发生异常: {e}")
        return False


def cleanup_local_files(uploaded_files: list, original_ts_file: str):
    """
    清理本地文件：删除已上传的文件、原始录制文件和整个直播间目录
    :param uploaded_files: 已上传的文件列表
    :param original_ts_file: 原始TS录制文件路径
    """
    log_post_process("开始清理本地文件")

    deleted_count = 0
    failed_count = 0

    # 删除已上传的处理文件
    for file_info in uploaded_files:
        file_path = file_info['file_path']
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                log_post_process(f"已删除: {os.path.basename(file_path)}", "debug")
                deleted_count += 1
            else:
                log_post_process(f"文件不存在，跳过: {os.path.basename(file_path)}", "debug")
        except Exception as e:
            log_post_process(f"删除文件失败: {os.path.basename(file_path)} - {e}", "error")
            failed_count += 1

    # 删除原始录制文件
    try:
        if os.path.exists(original_ts_file):
            os.remove(original_ts_file)
            log_post_process(f"已删除原始录制文件: {os.path.basename(original_ts_file)}", "debug")
            deleted_count += 1
        else:
            log_post_process(f"原始录制文件不存在，跳过: {os.path.basename(original_ts_file)}", "debug")
    except Exception as e:
        log_post_process(f"删除原始录制文件失败: {os.path.basename(original_ts_file)} - {e}", "error")
        failed_count += 1

    # 删除整个直播间目录
    try:
        # 获取直播间目录路径（原始文件的父目录）
        live_room_dir = os.path.dirname(original_ts_file)

        if os.path.exists(live_room_dir) and os.path.isdir(live_room_dir):
            # 使用shutil.rmtree删除整个目录树
            shutil.rmtree(live_room_dir)
            log_post_process(f"已删除整个直播间目录: {live_room_dir}", "info")

            # 检查是否还有其他直播间目录，如果平台目录为空也删除
            platform_dir = os.path.dirname(live_room_dir)
            if os.path.exists(platform_dir) and os.path.isdir(platform_dir):
                try:
                    # 检查平台目录是否为空
                    if not os.listdir(platform_dir):
                        os.rmdir(platform_dir)
                        log_post_process(f"已删除空的平台目录: {platform_dir}", "debug")
                    else:
                        log_post_process(f"平台目录不为空，保留: {platform_dir}", "debug")
                except Exception as e:
                    log_post_process(f"删除平台目录失败: {e}", "debug")
        else:
            log_post_process(f"直播间目录不存在，跳过: {live_room_dir}", "debug")

    except Exception as e:
        log_post_process(f"删除直播间目录失败: {e}", "error")
        failed_count += 1

    log_post_process(f"文件清理完成: 成功删除 {deleted_count} 个文件, 失败 {failed_count} 个文件")


if __name__ == "__main__":
    main()