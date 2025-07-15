#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import os
from pathlib import Path
from typing import Union


class ConfigReader:
    """
    配置文件读取器
    用于读取和管理各种切分设置
    """
    
    def __init__(self, config_path: str = None):
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
            self.config.read(self.config_path, encoding='utf-8')
            print(f"成功加载配置文件: {self.config_path}")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            # 使用默认配置
            self._load_default_config()
    
    def _load_default_config(self):
        """加载默认配置"""
        print("使用默认配置")
        self.config.read_dict({
            '后处理设置': {
                'M3U8切片时间(秒)': '300',
                'M3U8切片数量限制': '0',
                '是否删除旧切片': '否',
                '音频切分时间(秒)': '300',
                '音频输出格式': 'mp3',
                '音频比特率': '192k',
                '音频采样率': '44100',
                '是否生成M3U8': '是',
                '是否提取音频': '是',
                '是否上传OSS': '是'
            },
            '录制设置': {
                '视频分段时间(秒)': '3600'
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
        print("=" * 60)


# 测试代码
if __name__ == "__main__":
    config = ConfigReader()
    config.print_config_summary()