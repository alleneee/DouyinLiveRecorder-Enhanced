#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import os
from pathlib import Path
from typing import Union, Optional


class ConfigReader:
    """
    配置文件读取器
    用于读取和管理各种切分设置
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置读取器
        :param config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.ini')
        
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read(self.config_path, encoding='utf-8-sig')
            print(f"成功加载配置文件: {self.config_path}")
        except Exception as e:
            try:
                # 如果失败，尝试普通utf-8编码
                self.config.read(self.config_path, encoding='utf-8')
                print(f"成功加载配置文件: {self.config_path}")
            except Exception as e2:
                print(f"加载配置文件失败: {e2}")
                # 使用默认配置
                self._load_default_config()
    
    def _load_default_config(self):
        """加载默认配置"""
        print("使用默认配置")
        self.config.read_dict({
            '后处理设置': {
                'M3U8切片时间(秒)': '6',
                'M3U8切片数量限制': '0',
                '是否删除旧切片': '否',
                '音频切分时间(秒)': '18000',
                '音频输出格式': 'mp3',
                '音频比特率': '192k',
                '音频采样率': '44100',
                '是否生成M3U8': '是',
                '是否提取音频': '是',
                '是否上传OSS': '是'
            },
            '录制设置': {
                '视频分段时间(秒)': '3600'
            },

            'OSS配置': {
                'access_key_id': '',
                'access_key_secret': '',
                'endpoint': 'oss-cn-hangzhou.aliyuncs.com',
                'bucket_name': '',
                'path_template': 'live-records/{date}/{room_id}-{streamer_name}/',
                'enable_upload': '否',
                'upload_immediately': '否',
                'delete_after_upload': '否',
                'max_upload_threads': '4',
                'retry_times': '3',
                'chunk_size': '8388608',
                'enable_concurrent_upload': '是',
                'connection_timeout': '60',
                'read_timeout': '300'
            }
        })
    
    def get_video_segment_time(self) -> int:
        """获取视频分段时间（秒）"""
        try:
            return int(self.config.get('录制设置', '视频分段时间(秒)', fallback='3600'))
        except:
            return 3600
    

    
    def get_m3u8_segment_time(self) -> int:
        """获取M3U8切片时间（秒）"""
        try:
            return int(self.config.get('后处理设置', 'M3U8切片时间(秒)', fallback='300'))
        except:
            return 300
    
    def get_m3u8_list_size(self) -> int:
        """获取M3U8切片数量限制"""
        try:
            return int(self.config.get('后处理设置', 'M3U8切片数量限制', fallback='0'))
        except:
            return 0
    
    def get_audio_segment_time(self) -> int:
        """获取音频切分时间（秒）"""
        try:
            return int(self.config.get('后处理设置', '音频切分时间(秒)', fallback='300'))
        except:
            return 300
    
    def get_audio_format(self) -> str:
        """获取音频输出格式"""
        return self.config.get('后处理设置', '音频输出格式', fallback='mp3')
    
    def get_audio_bitrate(self) -> str:
        """获取音频比特率"""
        return self.config.get('后处理设置', '音频比特率', fallback='192k')
    
    def get_audio_sample_rate(self) -> str:
        """获取音频采样率"""
        return self.config.get('后处理设置', '音频采样率', fallback='44100')
    
    def is_generate_m3u8(self) -> bool:
        """是否生成M3U8"""
        return self.config.get('后处理设置', '是否生成M3U8', fallback='是') == '是'
    
    def is_extract_audio(self) -> bool:
        """是否提取音频"""
        return self.config.get('后处理设置', '是否提取音频', fallback='是') == '是'
    
    def is_upload_oss(self) -> bool:
        """是否上传OSS"""
        return self.config.get('后处理设置', '是否上传OSS', fallback='是') == '是'
    
    def get_oss_upload_path_template(self) -> str:
        """获取OSS上传路径模板"""
        return self.config.get('后处理设置', 'OSS上传路径模板', 
                              fallback='live-records/{date_str}/{room_id}-{record_name}/{file_type}/{file_name}')
    
    def is_delete_old_segments(self) -> bool:
        """是否删除旧切片"""
        return self.config.get('后处理设置', '是否删除旧切片', fallback='否') == '是'
    
    def get_hls_flags(self) -> list:
        """获取HLS标志"""
        flags = []
        if self.is_delete_old_segments():
            flags.append('delete_segments')
        return flags

    # OSS配置相关方法
    def get_oss_access_key_id(self) -> str:
        """获取OSS访问密钥ID"""
        return self.config.get('OSS配置', 'access_key_id', fallback='')

    def get_oss_access_key_secret(self) -> str:
        """获取OSS访问密钥Secret"""
        return self.config.get('OSS配置', 'access_key_secret', fallback='')

    def get_oss_endpoint(self) -> str:
        """获取OSS服务端点"""
        return self.config.get('OSS配置', 'endpoint', fallback='oss-cn-hangzhou.aliyuncs.com')

    def get_oss_bucket_name(self) -> str:
        """获取OSS存储桶名称"""
        return self.config.get('OSS配置', 'bucket_name', fallback='')

    def get_oss_path_template(self) -> str:
        """获取OSS路径模板"""
        return self.config.get('OSS配置', 'path_template',
                              fallback='live-records/{date}/{room_id}-{streamer_name}/')

    def is_oss_upload_enabled(self) -> bool:
        """是否启用OSS上传"""
        return self.config.get('OSS配置', 'enable_upload', fallback='否') == '是'

    def is_oss_upload_immediately(self) -> bool:
        """是否立即上传"""
        return self.config.get('OSS配置', 'upload_immediately', fallback='否') == '是'

    def is_oss_delete_after_upload(self) -> bool:
        """上传后是否删除本地文件"""
        return self.config.get('OSS配置', 'delete_after_upload', fallback='否') == '是'

    def is_delete_local_files_after_upload(self) -> bool:
        """上传成功后是否删除本地文件"""
        return self.config.get('后处理设置', '上传成功后删除本地文件', fallback='否') == '是'

    def get_oss_max_upload_threads(self) -> int:
        """获取最大上传线程数"""
        try:
            return int(self.config.get('OSS配置', 'max_upload_threads', fallback='4'))
        except:
            return 4

    def get_oss_retry_times(self) -> int:
        """获取上传重试次数"""
        try:
            return int(self.config.get('OSS配置', 'retry_times', fallback='3'))
        except:
            return 3

    def get_oss_chunk_size(self) -> int:
        """获取分片上传大小"""
        try:
            return int(self.config.get('OSS配置', 'chunk_size', fallback='8388608'))
        except:
            return 8388608

    def is_oss_concurrent_upload_enabled(self) -> bool:
        """是否启用并发上传"""
        return self.config.get('OSS配置', 'enable_concurrent_upload', fallback='是') == '是'

    def get_oss_connection_timeout(self) -> int:
        """获取连接超时时间"""
        try:
            return int(self.config.get('OSS配置', 'connection_timeout', fallback='60'))
        except:
            return 60

    def get_oss_read_timeout(self) -> int:
        """获取读取超时时间"""
        try:
            return int(self.config.get('OSS配置', 'read_timeout', fallback='300'))
        except:
            return 300

    def get_oss_config_dict(self) -> dict:
        """获取完整的OSS配置字典"""
        return {
            'access_key_id': self.get_oss_access_key_id(),
            'access_key_secret': self.get_oss_access_key_secret(),
            'endpoint': self.get_oss_endpoint(),
            'bucket_name': self.get_oss_bucket_name(),
            'path_template': self.get_oss_path_template(),
            'enable_upload': self.is_oss_upload_enabled(),
            'upload_immediately': self.is_oss_upload_immediately(),
            'delete_after_upload': self.is_oss_delete_after_upload(),
            'max_upload_threads': self.get_oss_max_upload_threads(),
            'retry_times': self.get_oss_retry_times(),
            'chunk_size': self.get_oss_chunk_size(),
            'enable_concurrent_upload': self.is_oss_concurrent_upload_enabled(),
            'connection_timeout': self.get_oss_connection_timeout(),
            'read_timeout': self.get_oss_read_timeout()
        }
    
    def get_audio_codec_params(self) -> dict:
        """获取音频编码参数"""
        audio_format = self.get_audio_format()
        
        if audio_format.lower() == 'mp3':
            return {
                'codec': 'libmp3lame',
                'extension': 'mp3'
            }
        elif audio_format.lower() == 'aac':
            return {
                'codec': 'aac',
                'extension': 'm4a'
            }
        elif audio_format.lower() == 'ogg':
            return {
                'codec': 'libvorbis',
                'extension': 'ogg'
            }
        else:
            # 默认MP3
            return {
                'codec': 'libmp3lame',
                'extension': 'mp3'
            }
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("=" * 60)
        print("当前配置摘要:")
        print("=" * 60)
        print(f"视频分段时间: {self.get_video_segment_time()}秒")

        print(f"M3U8切片时间: {self.get_m3u8_segment_time()}秒")
        print(f"M3U8切片数量限制: {self.get_m3u8_list_size()}")
        print(f"音频切分时间: {self.get_audio_segment_time()}秒")
        print(f"音频输出格式: {self.get_audio_format()}")
        print(f"音频比特率: {self.get_audio_bitrate()}")
        print(f"音频采样率: {self.get_audio_sample_rate()}")
        print(f"是否生成M3U8: {self.is_generate_m3u8()}")
        print(f"是否提取音频: {self.is_extract_audio()}")
        print(f"是否上传OSS: {self.is_upload_oss()}")
        print(f"OSS上传路径模板: {self.get_oss_upload_path_template()}")
        print(f"是否删除旧切片: {self.is_delete_old_segments()}")
        print("-" * 60)
        print("OSS配置:")
        print(f"  启用OSS上传: {self.is_oss_upload_enabled()}")
        print(f"  OSS端点: {self.get_oss_endpoint()}")
        print(f"  存储桶: {self.get_oss_bucket_name()}")
        print(f"  路径模板: {self.get_oss_path_template()}")
        print(f"  立即上传: {self.is_oss_upload_immediately()}")
        print(f"  上传后删除: {self.is_oss_delete_after_upload()}")
        print(f"  最大线程数: {self.get_oss_max_upload_threads()}")
        print(f"  重试次数: {self.get_oss_retry_times()}")
        print("=" * 60)


# 测试代码
if __name__ == "__main__":
    config = ConfigReader()
    config.print_config_summary()