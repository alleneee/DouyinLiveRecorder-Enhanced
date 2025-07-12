#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import json
import time
import math
from pathlib import Path


def convert_ts_to_m3u8(ts_file_path: str, output_dir: str = None) -> str:
    """
    将TS文件转换为M3U8格式
    :param ts_file_path: TS文件路径
    :param output_dir: 输出目录，如果不指定则使用TS文件所在目录
    :return: M3U8文件路径
    """
    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")
    
    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit('.', 1)[0]
    
    if output_dir is None:
        output_dir = file_dir
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # M3U8输出路径
    m3u8_path = os.path.join(output_dir, f"{file_name}.m3u8")
    segment_pattern = os.path.join(output_dir, f"{file_name}_%03d.ts")
    
    # FFmpeg命令：将TS文件切片并生成M3U8播放列表
    ffmpeg_command = [
        "ffmpeg",
        "-i", ts_file_path,
        "-c", "copy",
        "-hls_time", "10",  # 每个切片10秒
        "-hls_list_size", "0",  # 包含所有切片
        "-hls_segment_filename", segment_pattern,
        "-y",  # 覆盖已存在的文件
        m3u8_path
    ]
    
    print(f"正在转换TS文件为M3U8格式: {ts_file_path}")
    try:
        subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
        print(f"M3U8转换完成: {m3u8_path}")
        return m3u8_path
    except subprocess.CalledProcessError as e:
        print(f"M3U8转换失败: {e.stderr}")
        raise


def extract_and_split_audio(ts_file_path: str, output_dir: str = None, max_duration: int = 18000) -> list:
    """
    从TS文件提取音频并切割成多个片段
    :param ts_file_path: TS文件路径
    :param output_dir: 输出目录
    :param max_duration: 每个音频片段的最大时长（秒），默认18000秒（5小时）
    :return: 音频文件路径列表
    """
    if not os.path.exists(ts_file_path):
        raise FileNotFoundError(f"TS文件不存在: {ts_file_path}")
    
    file_dir = os.path.dirname(ts_file_path)
    file_name = os.path.basename(ts_file_path).rsplit('.', 1)[0]
    
    if output_dir is None:
        output_dir = file_dir
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 首先获取视频总时长
    duration_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        ts_file_path
    ]
    
    try:
        result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        total_duration = float(info['format']['duration'])
        print(f"视频总时长: {total_duration}秒")
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        total_duration = None
    
    audio_files = []
    
    if total_duration and total_duration > max_duration:
        # 需要切割
        segments = math.ceil(total_duration / max_duration)
        print(f"音频将被切割为 {segments} 个片段")
        
        for i in range(segments):
            start_time = i * max_duration
            output_file = os.path.join(output_dir, f"{file_name}_part{i+1:03d}.mp3")
            
            ffmpeg_command = [
                "ffmpeg",
                "-i", ts_file_path,
                "-ss", str(start_time),
                "-t", str(max_duration),
                "-vn",  # 不要视频
                "-acodec", "libmp3lame",
                "-ab", "192k",  # 音频比特率
                "-ar", "44100",  # 采样率
                "-y",
                output_file
            ]
            
            print(f"正在提取音频片段 {i+1}/{segments}: {output_file}")
            try:
                subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
                audio_files.append(output_file)
            except subprocess.CalledProcessError as e:
                print(f"音频片段提取失败: {e.stderr}")
    else:
        # 不需要切割，直接提取整个音频
        output_file = os.path.join(output_dir, f"{file_name}.mp3")
        
        ffmpeg_command = [
            "ffmpeg",
            "-i", ts_file_path,
            "-vn",  # 不要视频
            "-acodec", "libmp3lame",
            "-ab", "192k",
            "-ar", "44100",
            "-y",
            output_file
        ]
        
        print(f"正在提取音频: {output_file}")
        try:
            subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
            audio_files.append(output_file)
        except subprocess.CalledProcessError as e:
            print(f"音频提取失败: {e.stderr}")
            raise
    
    print(f"音频提取完成，共生成 {len(audio_files)} 个文件")
    return audio_files


def upload_to_oss(file_path: str, oss_config: dict, oss_key: str = None):
    """
    上传文件到阿里云OSS
    :param file_path: 要上传的文件路径
    :param oss_config: OSS配置信息
    :param oss_key: OSS中的文件路径，如果不指定则使用文件名
    """
    try:
        import oss2
    except ImportError:
        print("需要安装oss2库: pip install oss2")
        return False
    
    # 从配置中获取OSS参数
    access_key_id = oss_config.get('access_key_id')
    access_key_secret = oss_config.get('access_key_secret')
    endpoint = oss_config.get('endpoint')
    bucket_name = oss_config.get('bucket_name')
    
    if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
        print("OSS配置信息不完整")
        return False
    
    # 创建OSS认证和Bucket对象
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    
    # 如果没有指定OSS key，使用文件名
    if oss_key is None:
        oss_key = os.path.basename(file_path)
    
    print(f"正在上传文件到OSS: {file_path} -> {oss_key}")
    
    try:
        # 使用断点续传上传
        oss2.resumable_upload(bucket, oss_key, file_path)
        print(f"文件上传成功: {oss_key}")
        return True
    except Exception as e:
        print(f"文件上传失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='处理录制完成的视频文件')
    parser.add_argument('--record_name', type=str, help='录制名称')
    parser.add_argument('--save_file_path', type=str, required=True, help='保存的文件路径')
    parser.add_argument('--save_type', type=str, help='保存类型')
    parser.add_argument('--split_video_by_time', type=str, help='是否按时间分割视频')
    parser.add_argument('--converts_to_mp4', type=str, help='是否转换为MP4')
    parser.add_argument('--oss_config_file', type=str, default='oss_config.json', help='OSS配置文件路径')
    
    args = parser.parse_args()
    
    ts_file_path = args.save_file_path
    
    # 检查文件是否存在
    if not os.path.exists(ts_file_path):
        print(f"文件不存在: {ts_file_path}")
        return
    
    # 检查文件是否为TS格式
    if not ts_file_path.lower().endswith('.ts'):
        print(f"不是TS文件，跳过处理: {ts_file_path}")
        return
    
    # 创建输出目录
    output_base_dir = os.path.join(os.path.dirname(ts_file_path), 'processed')
    os.makedirs(output_base_dir, exist_ok=True)
    
    # 读取OSS配置
    oss_config = {}
    if os.path.exists(args.oss_config_file):
        try:
            with open(args.oss_config_file, 'r', encoding='utf-8') as f:
                oss_config = json.load(f)
        except Exception as e:
            print(f"读取OSS配置文件失败: {e}")
    
    # 记录所有需要上传的文件
    files_to_upload = []
    
    # 1. 转换TS到M3U8
    try:
        m3u8_path = convert_ts_to_m3u8(ts_file_path, output_base_dir)
        files_to_upload.append(m3u8_path)
        
        # 添加所有的TS切片文件
        m3u8_dir = os.path.dirname(m3u8_path)
        for file in os.listdir(m3u8_dir):
            if file.endswith('.ts') and file != os.path.basename(ts_file_path):
                files_to_upload.append(os.path.join(m3u8_dir, file))
    except Exception as e:
        print(f"M3U8转换失败: {e}")
    
    # 2. 提取并切割音频
    try:
        audio_files = extract_and_split_audio(ts_file_path, output_base_dir)
        files_to_upload.extend(audio_files)
    except Exception as e:
        print(f"音频提取失败: {e}")
    
    # 3. 上传到OSS
    if oss_config and files_to_upload:
        # 获取直播间名称作为OSS目录
        record_name = args.record_name or "unknown"
        date_str = time.strftime('%Y%m%d')
        
        for file_path in files_to_upload:
            # 构建OSS路径
            file_name = os.path.basename(file_path)
            file_type = 'm3u8' if file_path.endswith('.m3u8') else 'audio' if file_path.endswith('.mp3') else 'video'
            oss_key = f"live-records/{record_name}/{date_str}/{file_type}/{file_name}"
            
            upload_to_oss(file_path, oss_config, oss_key)
    
    print("\n所有处理完成！")


if __name__ == "__main__":
    main()