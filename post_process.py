#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import json
import time
import math
import datetime
from pathlib import Path
from config_reader import ConfigReader
from api_client import APIClient, create_live_record_data, create_mp3_info


def convert_ts_to_m3u8(ts_file_path: str, output_dir: str = None, config: ConfigReader = None) -> str:
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
    
    # FFmpeg命令：将TS文件切片并生成M3U8播放列表
    ffmpeg_command = [
        "ffmpeg",
        "-i", ts_file_path,
        "-c", "copy",
        "-hls_time", str(segment_time),  # 从配置读取切片时间
        "-hls_list_size", str(list_size),  # 从配置读取切片数量限制
        "-hls_segment_filename", segment_pattern,
        "-y",  # 覆盖已存在的文件
    ]
    
    # 添加HLS标志
    if hls_flags:
        ffmpeg_command.extend(["-hls_flags", ",".join(hls_flags)])
    
    ffmpeg_command.append(m3u8_path)
    
    print(f"正在转换TS文件为M3U8格式: {ts_file_path}")
    print(f"M3U8切片时间: {segment_time}秒")
    print(f"M3U8切片数量限制: {list_size}")
    if hls_flags:
        print(f"HLS标志: {', '.join(hls_flags)}")
    
    try:
        subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
        print(f"M3U8转换完成: {m3u8_path}")
        return m3u8_path
    except subprocess.CalledProcessError as e:
        print(f"M3U8转换失败: {e.stderr}")
        raise


def extract_and_split_audio(ts_file_path: str, output_dir: str = None, config: ConfigReader = None) -> list:
    """
    从TS文件提取音频并切割成多个片段
    :param ts_file_path: TS文件路径
    :param output_dir: 输出目录
    :param config: 配置读取器
    :return: 音频文件路径列表
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
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 从配置读取参数
    max_duration = config.get_audio_segment_time()
    audio_codec_params = config.get_audio_codec_params()
    audio_bitrate = config.get_audio_bitrate()
    audio_sample_rate = config.get_audio_sample_rate()
    
    print(f"音频切分时间: {max_duration}秒")
    print(f"音频输出格式: {audio_codec_params['extension']}")
    print(f"音频比特率: {audio_bitrate}")
    print(f"音频采样率: {audio_sample_rate}")
    
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
            # 修改文件命名格式，添加总部分数信息
            output_file = os.path.join(output_dir, f"{file_name}_part{i+1:03d}_of_{segments:03d}.{audio_codec_params['extension']}")
            
            ffmpeg_command = [
                "ffmpeg",
                "-i", ts_file_path,
                "-ss", str(start_time),
                "-t", str(max_duration),
                "-vn",  # 不要视频
                "-acodec", audio_codec_params['codec'],
                "-ab", audio_bitrate,  # 音频比特率
                "-ar", audio_sample_rate,  # 采样率
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
        output_file = os.path.join(output_dir, f"{file_name}.{audio_codec_params['extension']}")
        
        ffmpeg_command = [
            "ffmpeg",
            "-i", ts_file_path,
            "-vn",  # 不要视频
            "-acodec", audio_codec_params['codec'],
            "-ab", audio_bitrate,
            "-ar", audio_sample_rate,
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
    parser.add_argument('--room_id', type=str, default='', help='直播间ID(可选)')
    parser.add_argument('--oss_config_file', type=str, default='oss_config.json', help='OSS配置文件路径')
    parser.add_argument('--record_start_time', type=str, default='', help='录制开始时间(格式: YYYY-MM-DD_HH-MM-SS)')
    
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
    
    # 创建配置读取器
    config = ConfigReader()
    config.print_config_summary()
    
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
    # 记录成功上传的文件信息
    uploaded_files = []
    
    # 1. 转换TS到M3U8
    if config.is_generate_m3u8():
        try:
            m3u8_path = convert_ts_to_m3u8(ts_file_path, output_base_dir, config)
            files_to_upload.append(m3u8_path)
            
            # 添加所有的TS切片文件
            m3u8_dir = os.path.dirname(m3u8_path)
            for file in os.listdir(m3u8_dir):
                if file.endswith('.ts') and file != os.path.basename(ts_file_path):
                    files_to_upload.append(os.path.join(m3u8_dir, file))
        except Exception as e:
            print(f"M3U8转换失败: {e}")
    else:
        print("M3U8生成已禁用")
    
    # 2. 提取并切割音频
    if config.is_extract_audio():
        try:
            audio_files = extract_and_split_audio(ts_file_path, output_base_dir, config)
            files_to_upload.extend(audio_files)
        except Exception as e:
            print(f"音频提取失败: {e}")
    else:
        print("音频提取已禁用")
    
    # 3. 上传到OSS
    if config.is_upload_oss() and oss_config and files_to_upload:
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
                print(f"录制开始时间格式错误: {args.record_start_time}，使用当前时间")
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
        
        for file_path in files_to_upload:
            # 构建OSS路径
            file_name = os.path.basename(file_path)
            file_name_no_ext = os.path.splitext(file_name)[0]
            file_ext = os.path.splitext(file_name)[1][1:]  # 去掉点号
            file_type = 'm3u8' if file_path.endswith('.m3u8') else 'audio' if file_path.endswith('.mp3') else 'video'
            
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
            
            success = upload_to_oss(file_path, oss_config, oss_key)
            if success:
                # 记录成功上传的文件信息
                uploaded_files.append({
                    'local_path': file_path,
                    'oss_key': oss_key,
                    'file_type': file_type,
                    'file_name': file_name
                })

    # 4. 调用API通知后处理结果
    if uploaded_files:
        try:
            notify_api_result(args, uploaded_files, oss_config)
        except Exception as e:
            print(f"API通知失败: {e}")

    print("\n所有处理完成！")


def notify_api_result(args, uploaded_files: list, oss_config: dict):
    """
    通知API后处理结果
    :param args: 命令行参数
    :param uploaded_files: 已上传的文件列表
    :param oss_config: OSS配置信息
    """
    print("\n开始调用API通知后处理结果...")

    # 创建API客户端
    api_client = APIClient()

    # 构建OSS基础URL
    bucket_name = oss_config.get('bucket_name', '')
    endpoint = oss_config.get('endpoint', '')

    # 根据实际OSS配置构建基础URL
    if endpoint.startswith('oss-'):
        base_url = f"https://{bucket_name}.{endpoint}"
    else:
        base_url = f"https://{bucket_name}.{endpoint}"

    # 分类文件
    m3u8_url = None
    ts_url = None
    mp3_infos = []

    for file_info in uploaded_files:
        file_type = file_info['file_type']
        oss_key = file_info['oss_key']

        # 构建完整的OSS URL
        # oss_key格式类似: live-records/20250714/870887192950-央视网/audio/filename.mp3
        full_url = f"{base_url}/{oss_key}"

        if file_type == 'm3u8':
            m3u8_url = full_url
        elif file_type == 'video':
            ts_url = full_url
        elif file_type == 'audio':
            # 从文件名中提取部分编号
            file_name = file_info['file_name']
            if '_part' in file_name and '_of_' in file_name:
                try:
                    # 提取part编号，例如从"test_part001_of_003.mp3"中提取1
                    part_str = file_name.split('_part')[1].split('_of_')[0]
                    section = int(part_str)
                    mp3_infos.append(create_mp3_info(section, full_url))
                except (ValueError, IndexError):
                    print(f"无法解析音频文件部分编号: {file_name}")
                    mp3_infos.append(create_mp3_info(1, full_url))
            else:
                mp3_infos.append(create_mp3_info(1, full_url))

    # 创建直播录制数据
    record_name = args.record_name or "unknown"
    room_id = args.room_id or "unknown"

    # 处理录制开始时间格式
    record_start_time = args.record_start_time or ""
    if record_start_time and record_start_time != "unknown":
        try:
            # 将格式从"2024-01-15_14-30-45"转换为"2024-01-15 14:30:45"
            temp_time = record_start_time.replace('_', ' ')
            parts = temp_time.split(' ')
            if len(parts) == 2:
                date_part = parts[0]  # 2024-01-15
                time_part = parts[1].replace('-', ':')  # 14:30:45
                record_start_time = f"{date_part} {time_part}"
            else:
                record_start_time = temp_time
        except:
            record_start_time = ""

    # 生成录制日期和文件名
    if record_start_time:
        try:
            start_time_obj = datetime.datetime.strptime(record_start_time, '%Y-%m-%d %H:%M:%S')
            record_date = start_time_obj.strftime('%Y-%m-%d')
        except:
            record_date = datetime.datetime.now().strftime('%Y-%m-%d')
    else:
        record_date = datetime.datetime.now().strftime('%Y-%m-%d')

    # 从原始文件路径生成录制文件名
    ts_file_path = args.save_file_path
    record_file_name = os.path.basename(ts_file_path)

    live_record = create_live_record_data(
        record_name=record_name,
        room_id=room_id,
        record_start_time=record_start_time,
        record_date=record_date,
        record_file_name=record_file_name,
        m3u8_url=m3u8_url,
        ts_url=ts_url,
        mp3_urls=mp3_infos if mp3_infos else None
    )

    # 发送通知
    success = api_client.notify_post_process_result([live_record])
    if success:
        print("API通知发送成功")
    else:
        print("API通知发送失败")


if __name__ == "__main__":
    main()