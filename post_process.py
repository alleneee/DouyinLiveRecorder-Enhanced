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
from pathlib import Path
from typing import Optional
from config_reader import ConfigReader
from api_client import APIClient, create_live_record_data, create_mp3_info

# 添加日志导入
from src.logger import logger


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


def upload_to_oss(file_path: str, oss_config: dict, oss_key: Optional[str] = None):
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
    
    # 从config.ini读取OSS配置
    oss_config = config.get_oss_config_dict()

    # 兼容性处理：如果config.ini中没有配置，尝试从JSON文件读取
    if not oss_config.get('access_key_id') and os.path.exists(args.oss_config_file):
        try:
            with open(args.oss_config_file, 'r', encoding='utf-8') as f:
                json_config = json.load(f)
                if 'oss_config' in json_config:
                    oss_config.update(json_config['oss_config'])
                    print("从JSON文件读取OSS配置（建议迁移到config.ini）")
        except Exception as e:
            print(f"读取OSS配置文件失败: {e}")
    
    # 记录所有需要上传的文件
    files_to_upload = []
    # 记录成功上传的文件信息
    uploaded_files = []

    # 1. 添加原始TS文件到上传列表（上传到video目录）
    if os.path.exists(ts_file_path):
        files_to_upload.append(ts_file_path)
        print(f"添加原始视频文件到上传列表: {ts_file_path}")
    
    # 2. 转换TS到M3U8（上传到m3u8目录）
    if config.is_generate_m3u8():
        try:
            m3u8_path = convert_ts_to_m3u8(ts_file_path, output_base_dir, config)
            files_to_upload.append(m3u8_path)
            print(f"添加M3U8播放列表到上传列表: {m3u8_path}")
            
            # 添加所有的TS切片文件（排除原始文件）
            m3u8_dir = os.path.dirname(m3u8_path)
            original_filename_base = os.path.splitext(os.path.basename(ts_file_path))[0]
            
            print(f"在目录中查找TS切片文件: {m3u8_dir}")
            print(f"原始文件基础名: {original_filename_base}")
            
            for file in os.listdir(m3u8_dir):
                if file.endswith('.ts'):
                    # 检查是否为切片文件（包含_数字模式）
                    if '_' in file and file != os.path.basename(ts_file_path):
                        # 进一步验证是否为我们生成的切片文件
                        file_base = file.rsplit('_', 1)[0]  # 移除最后的_xxx.ts部分
                        if file_base == original_filename_base:
                            ts_segment_path = os.path.join(m3u8_dir, file)
                            files_to_upload.append(ts_segment_path)
                            print(f"添加TS切片到上传列表: {ts_segment_path}")
                        else:
                            print(f"跳过非匹配文件: {file}")
                    else:
                        print(f"跳过原始文件或无下划线文件: {file}")
                        
            # 验证是否找到了切片文件
            segment_count = sum(1 for f in files_to_upload if f.endswith('.ts') and f != ts_file_path and f != m3u8_path)
            print(f"找到 {segment_count} 个TS切片文件")
            
        except Exception as e:
            print(f"M3U8转换失败: {e}")
    else:
        print("M3U8生成已禁用")
    
    # 3. 提取并切割音频（上传到audio目录）
    if config.is_extract_audio():
        try:
            audio_files = extract_and_split_audio(ts_file_path, output_base_dir, config)
            files_to_upload.extend(audio_files)
            print(f"添加音频文件到上传列表: {len(audio_files)} 个文件")
        except Exception as e:
            print(f"音频提取失败: {e}")
    else:
        print("音频提取已禁用")
    
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
            
            # 改进文件类型分类逻辑
            if file_path.endswith('.m3u8'):
                file_type = 'm3u8'
            elif file_path.endswith('.mp3') or file_path.endswith('.m4a'):
                file_type = 'audio'
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
            
            success = upload_to_oss(file_path, oss_config, oss_key)
            if success:
                # 记录成功上传的文件信息
                uploaded_files.append({
                    'local_path': file_path,
                    'oss_key': oss_key,
                    'file_type': file_type,
                    'file_name': file_name
                })

    # 5. 调用API通知后处理结果
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
    print("\n" + "="*60)
    print("开始调用API通知后处理结果...")
    print("="*60)

    # 关键日志：开始API通知流程
    logger.info("开始调用API通知后处理结果")

    # 创建API客户端
    try:
        api_client = APIClient()
        print("✓ API客户端创建成功")
    except Exception as e:
        # 关键日志：API客户端创建失败
        logger.info(f"API客户端创建失败: {e}")
        print(f"✗ API客户端创建失败: {e}")
        return

    # 构建OSS基础URL
    bucket_name = oss_config.get('bucket_name', '')
    endpoint = oss_config.get('endpoint', '')

    print(f"OSS配置:")
    print(f"  Bucket: {bucket_name}")
    print(f"  Endpoint: {endpoint}")

    if not bucket_name or not endpoint:
        print("✗ OSS配置信息不完整，无法构建URL")
        return

    # 根据实际OSS配置构建基础URL
    if endpoint.startswith('oss-'):
        base_url = f"https://{bucket_name}.{endpoint}"
    else:
        base_url = f"https://{bucket_name}.{endpoint}"

    print(f"  Base URL: {base_url}")

    # 分类文件
    m3u8_url = None
    ts_url = None
    mp3_infos = []

    print(f"\n文件分类处理:")
    print(f"  共需要处理 {len(uploaded_files)} 个文件")

    for i, file_info in enumerate(uploaded_files, 1):
        file_name = file_info['file_name']
        oss_path = file_info['oss_key']
        full_url = f"{base_url}/{oss_path}"
        
        print(f"  [{i}] 文件: {file_name}")

        # 识别文件类型
        if file_name.endswith('.ts') and '_' not in file_name.split('.')[0].split('_')[-1:]:
            # 原始TS文件（不包含分段标识）
            print(f"      识别为原始视频文件: {file_name}")
            print(f"      文件分类: {file_name} -> video 目录")
            print(f"      OSS路径: {oss_path}")
            print(f"      完整URL: {full_url}")
            print(f"      → 设置为视频文件URL")
            ts_url = full_url
        elif file_name.endswith('.m3u8'):
            print(f"      类型: m3u8")
            print(f"      文件分类: {file_name} -> m3u8 目录")
            print(f"      OSS路径: {oss_path}")
            print(f"      完整URL: {full_url}")
            print(f"      → 设置为M3U8播放列表URL")
            m3u8_url = full_url
        elif file_name.endswith('.ts') and ('_' in file_name and file_name.split('_')[-1].split('.')[0].isdigit()):
            # TS切片文件
            print(f"      识别为TS切片文件: {file_name}")
            print(f"      文件分类: {file_name} -> m3u8 目录")
            print(f"      OSS路径: {oss_path}")
            print(f"      完整URL: {full_url}")
            print(f"      → 跳过（TS切片文件，不是播放列表）")
        elif file_name.endswith('.mp3') and 'part' in file_name:
            print(f"      类型: audio")
            print(f"      文件分类: {file_name} -> audio 目录")
            print(f"      OSS路径: {oss_path}")
            print(f"      完整URL: {full_url}")
            
            # 解析音频片段编号
            try:
                import re
                match = re.search(r'_part(\d+)_of_(\d+)', file_name)
                if match:
                    section = int(match.group(1))
                    mp3_info = create_mp3_info(section, full_url)
                    mp3_infos.append(mp3_info)
                    print(f"      → 添加为音频片段 {section}")
                else:
                    print(f"      → 跳过（无法解析音频片段编号）")
            except Exception as e:
                print(f"      → 跳过（解析音频片段编号失败: {e}）")
        else:
            print(f"      → 跳过（未知文件类型）")

    # 创建直播录制数据
    print(f"\n创建直播录制数据:")
    record_name = args.record_name or "unknown"
    room_id = args.room_id or "unknown"
    
    print(f"  录制名称: {record_name}")
    print(f"  房间ID: {room_id}")

    # 处理录制开始时间格式
    record_start_time = args.record_start_time or ""
    print(f"  原始录制开始时间: {record_start_time}")
    
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
            print(f"  格式化后录制开始时间: {record_start_time}")
        except Exception as e:
            print(f"  ⚠ 录制开始时间格式化失败: {e}")
            record_start_time = ""

    # 生成录制日期和文件名
    if record_start_time:
        try:
            start_time_obj = datetime.datetime.strptime(record_start_time, '%Y-%m-%d %H:%M:%S')
            record_date = start_time_obj.strftime('%Y-%m-%d')
            print(f"  根据录制时间生成录制日期: {record_date}")
        except Exception as e:
            print(f"  ⚠ 解析录制时间失败: {e}")
            record_date = datetime.datetime.now().strftime('%Y-%m-%d')
            print(f"  使用当前日期: {record_date}")
    else:
        record_date = datetime.datetime.now().strftime('%Y-%m-%d')
        print(f"  使用当前日期: {record_date}")

    # 从原始文件路径生成录制文件名
    ts_file_path = args.save_file_path
    record_file_name = os.path.basename(ts_file_path)
    print(f"  录制文件名: {record_file_name}")

    # 汇总URL信息
    print(f"\n汇总URL信息:")
    print(f"  M3U8 URL: {m3u8_url or '无'}")
    print(f"  TS URL: {ts_url or '无'}")
    print(f"  音频文件数量: {len(mp3_infos)}")
    if mp3_infos:
        for i, mp3_info in enumerate(mp3_infos, 1):
            print(f"    [{i}] 片段{mp3_info['section']}: {mp3_info['mp3Url']}")

    try:
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
        print(f"✓ 直播录制数据创建成功")
        print(f"数据结构预览:")
        print(json.dumps(live_record, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"✗ 直播录制数据创建失败: {e}")
        return

    # 发送通知
    print(f"\n发送API通知:")
    try:
        success = api_client.notify_post_process_result([live_record])
        if success:
            # 关键日志：API通知发送成功
            logger.info("API通知发送成功")
            print("✓ API通知发送成功")
        else:
            # 关键日志：API通知发送失败
            logger.info("API通知发送失败")
            print("✗ API通知发送失败")
    except Exception as e:
        # 关键日志：API通知过程异常
        logger.info(f"API通知过程中发生异常: {e}")
        print(f"✗ API通知过程中发生异常: {e}")
        import traceback
        print(f"详细错误信息:")
        traceback.print_exc()

    print("="*60)


if __name__ == "__main__":
    main()