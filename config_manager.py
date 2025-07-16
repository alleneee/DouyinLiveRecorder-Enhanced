#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from config_reader import ConfigReader
import configparser


class ConfigManager:
    """
    配置管理器
    用于修改和管理各种切分设置
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        :param config_path: 配置文件路径
        """
        self.config_reader = ConfigReader(config_path)
        self.config_path = config_path or self.config_reader.config_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path, encoding='utf-8')
    
    def update_video_segment_time(self, seconds: int):
        """更新视频分段时间"""
        if not self.config.has_section('录制设置'):
            self.config.add_section('录制设置')
        self.config.set('录制设置', '视频分段时间(秒)', str(seconds))
        print(f"视频分段时间已更新为: {seconds}秒")
    
    def update_m3u8_segment_time(self, seconds: int):
        """更新M3U8切片时间"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')
        self.config.set('后处理设置', 'M3U8切片时间(秒)', str(seconds))
        print(f"M3U8切片时间已更新为: {seconds}秒")
    
    def update_audio_segment_time(self, seconds: int):
        """更新音频切分时间"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')
        self.config.set('后处理设置', '音频切分时间(秒)', str(seconds))
        print(f"音频切分时间已更新为: {seconds}秒")
    
    def update_audio_format(self, format_type: str):
        """更新音频输出格式"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')
        
        supported_formats = ['mp3', 'aac', 'ogg']
        if format_type.lower() not in supported_formats:
            print(f"错误: 不支持的音频格式 '{format_type}'")
            print(f"支持的格式: {', '.join(supported_formats)}")
            return False
        
        self.config.set('后处理设置', '音频输出格式', format_type.lower())
        print(f"音频输出格式已更新为: {format_type.lower()}")
        return True
    
    def update_audio_bitrate(self, bitrate: str):
        """更新音频比特率"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')
        self.config.set('后处理设置', '音频比特率', bitrate)
        print(f"音频比特率已更新为: {bitrate}")
    
    def update_audio_sample_rate(self, sample_rate: str):
        """更新音频采样率"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')
        self.config.set('后处理设置', '音频采样率', sample_rate)
        print(f"音频采样率已更新为: {sample_rate}")
    
    def update_oss_upload_path_template(self, template: str):
        """更新OSS上传路径模板"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')
        self.config.set('后处理设置', 'OSS上传路径模板', template)
        print(f"OSS上传路径模板已更新为: {template}")
        print("可用变量:")
        print("  {record_name} - 录制名称")
        print("  {date_str} - 日期字符串（YYYYMMDD）")
        print("  {time_str} - 时间字符串（HHMMSS）")
        print("  {datetime_str} - 日期时间字符串（YYYYMMDD_HHMMSS）")
        print("  {file_name} - 文件名（包含扩展名）")
        print("  {file_name_no_ext} - 文件名（不包含扩展名）")
        print("  {file_ext} - 文件扩展名")
        print("  {file_type} - 文件类型（video/audio/m3u8）")
        print("  {timestamp} - Unix时间戳")
    
    def update_oss_access_key_id(self, access_key_id: str):
        """更新OSS访问密钥ID"""
        if not self.config.has_section('OSS配置'):
            self.config.add_section('OSS配置')
        self.config.set('OSS配置', 'access_key_id', access_key_id)
        print(f"OSS访问密钥ID已更新")

    def update_oss_access_key_secret(self, access_key_secret: str):
        """更新OSS访问密钥Secret"""
        if not self.config.has_section('OSS配置'):
            self.config.add_section('OSS配置')
        self.config.set('OSS配置', 'access_key_secret', access_key_secret)
        print(f"OSS访问密钥Secret已更新")

    def update_oss_endpoint(self, endpoint: str):
        """更新OSS服务端点"""
        if not self.config.has_section('OSS配置'):
            self.config.add_section('OSS配置')
        self.config.set('OSS配置', 'endpoint', endpoint)
        print(f"OSS服务端点已更新为: {endpoint}")

    def update_oss_bucket_name(self, bucket_name: str):
        """更新OSS存储桶名称"""
        if not self.config.has_section('OSS配置'):
            self.config.add_section('OSS配置')
        self.config.set('OSS配置', 'bucket_name', bucket_name)
        print(f"OSS存储桶名称已更新为: {bucket_name}")

    def update_oss_path_template_new(self, path_template: str):
        """更新OSS路径模板"""
        if not self.config.has_section('OSS配置'):
            self.config.add_section('OSS配置')
        self.config.set('OSS配置', 'path_template', path_template)
        print(f"OSS路径模板已更新为: {path_template}")

    def update_oss_enable_upload(self, enable: bool):
        """更新是否启用OSS上传"""
        if not self.config.has_section('OSS配置'):
            self.config.add_section('OSS配置')
        self.config.set('OSS配置', 'enable_upload', '是' if enable else '否')
        print(f"OSS上传功能已{'启用' if enable else '禁用'}")

    def toggle_feature(self, feature_name: str, enabled: bool):
        """开关功能"""
        if not self.config.has_section('后处理设置'):
            self.config.add_section('后处理设置')

        feature_map = {
            'm3u8': '是否生成M3U8',
            'audio': '是否提取音频',
            'oss': '是否上传OSS',
            'delete_segments': '是否删除旧切片'
        }

        if feature_name not in feature_map:
            print(f"错误: 未知功能 '{feature_name}'")
            print(f"支持的功能: {', '.join(feature_map.keys())}")
            return False

        config_key = feature_map[feature_name]
        value = '是' if enabled else '否'
        self.config.set('后处理设置', config_key, value)
        print(f"{config_key}已设置为: {value}")
        return True
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"配置已保存到: {self.config_path}")
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def show_current_config(self):
        """显示当前配置"""
        self.config_reader.print_config_summary()
    
    def preset_short_video(self):
        """短视频预设 (2-10分钟)"""
        print("应用短视频预设...")
        self.update_video_segment_time(1800)  # 30分钟
        self.update_m3u8_segment_time(10)     # 10秒
        self.update_audio_segment_time(120)   # 2分钟
        self.update_audio_format('mp3')
        self.update_audio_bitrate('128k')
        self.toggle_feature('m3u8', True)
        self.toggle_feature('audio', True)
    
    def preset_long_video(self):
        """长视频预设 (10小时+)"""
        print("应用长视频预设...")
        self.update_video_segment_time(3600)  # 1小时
        self.update_m3u8_segment_time(300)    # 5分钟
        self.update_audio_segment_time(300)   # 5分钟
        self.update_audio_format('mp3')
        self.update_audio_bitrate('192k')
        self.toggle_feature('m3u8', True)
        self.toggle_feature('audio', True)
    
    def preset_live_stream(self):
        """直播流预设"""
        print("应用直播流预设...")
        self.update_video_segment_time(1800)  # 30分钟
        self.update_m3u8_segment_time(6)      # 6秒
        self.update_audio_segment_time(1800)  # 30分钟
        self.update_audio_format('aac')
        self.update_audio_bitrate('128k')
        self.toggle_feature('m3u8', True)
        self.toggle_feature('audio', True)
        self.toggle_feature('delete_segments', True)
    
    def preset_audio_only(self):
        """仅音频预设"""
        print("应用仅音频预设...")
        self.update_video_segment_time(3600)  # 1小时
        self.update_audio_segment_time(300)   # 5分钟
        self.update_audio_format('mp3')
        self.update_audio_bitrate('320k')     # 高质量音频
        self.toggle_feature('m3u8', False)    # 不生成M3U8
        self.toggle_feature('audio', True)


def main():
    parser = argparse.ArgumentParser(description='配置管理工具')
    parser.add_argument('--config', type=str, help='配置文件路径')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 显示配置
    show_parser = subparsers.add_parser('show', help='显示当前配置')
    
    # 设置视频分段时间
    video_parser = subparsers.add_parser('video', help='设置视频分段时间')
    video_parser.add_argument('seconds', type=int, help='分段时间（秒）')
    
    # 设置M3U8切片时间
    m3u8_parser = subparsers.add_parser('m3u8', help='设置M3U8切片时间')
    m3u8_parser.add_argument('seconds', type=int, help='切片时间（秒）')
    
    # 设置音频切分时间
    audio_parser = subparsers.add_parser('audio', help='设置音频切分时间')
    audio_parser.add_argument('seconds', type=int, help='切分时间（秒）')
    
    # 设置音频格式
    format_parser = subparsers.add_parser('format', help='设置音频格式')
    format_parser.add_argument('format', type=str, choices=['mp3', 'aac', 'ogg'], help='音频格式')
    
    # 设置音频比特率
    bitrate_parser = subparsers.add_parser('bitrate', help='设置音频比特率')
    bitrate_parser.add_argument('bitrate', type=str, help='比特率 (如: 192k, 320k)')
    
    # 设置OSS上传路径模板
    oss_path_parser = subparsers.add_parser('oss-path', help='设置OSS上传路径模板')
    oss_path_parser.add_argument('template', type=str, help='路径模板')
    
    # 功能开关
    toggle_parser = subparsers.add_parser('toggle', help='开关功能')
    toggle_parser.add_argument('feature', type=str, choices=['m3u8', 'audio', 'oss', 'delete_segments'], help='功能名称')
    toggle_parser.add_argument('state', type=str, choices=['on', 'off'], help='开关状态')
    
    # 预设配置
    preset_parser = subparsers.add_parser('preset', help='应用预设配置')
    preset_parser.add_argument('preset', type=str, choices=['short', 'long', 'live', 'audio'], help='预设类型')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    config_manager = ConfigManager(args.config)
    
    if args.command == 'show':
        config_manager.show_current_config()
    
    elif args.command == 'video':
        config_manager.update_video_segment_time(args.seconds)
        config_manager.save_config()
    
    elif args.command == 'm3u8':
        config_manager.update_m3u8_segment_time(args.seconds)
        config_manager.save_config()
    
    elif args.command == 'audio':
        config_manager.update_audio_segment_time(args.seconds)
        config_manager.save_config()
    
    elif args.command == 'format':
        if config_manager.update_audio_format(args.format):
            config_manager.save_config()
    
    elif args.command == 'bitrate':
        config_manager.update_audio_bitrate(args.bitrate)
        config_manager.save_config()
    
    elif args.command == 'oss-path':
        config_manager.update_oss_upload_path_template(args.template)
        config_manager.save_config()
    
    elif args.command == 'toggle':
        enabled = args.state == 'on'
        if config_manager.toggle_feature(args.feature, enabled):
            config_manager.save_config()
    
    elif args.command == 'preset':
        if args.preset == 'short':
            config_manager.preset_short_video()
        elif args.preset == 'long':
            config_manager.preset_long_video()
        elif args.preset == 'live':
            config_manager.preset_live_stream()
        elif args.preset == 'audio':
            config_manager.preset_audio_only()
        config_manager.save_config()
    
    print("\n配置更新完成！")


if __name__ == "__main__":
    main()