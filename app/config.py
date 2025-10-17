"""应用配置"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """应用配置类"""
    
    # 数据库配置
    database_url: str = "sqlite:///./live_recorder.db"
    
    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    
    # 录制配置
    segment_duration: int = 60  # 分段时长（秒）
    video_save_type: str = "mp4"  # 录制格式
    video_save_path: str = "./downloads"  # 保存路径
    video_record_quality: str = "原画"  # 录制质量
    folder_by_author: bool = True  # 按主播分文件夹
    check_interval: int = 30  # 直播状态检查间隔(秒)
    
    # 音频抽取配置
    extract_audio: bool = True  # 是否抽取音频
    audio_format: str = "mp3"  # 音频格式（mp3/aac/m4a）
    audio_bitrate: str = "128k"  # 音频码率
    
    # OSS配置
    oss_enabled: bool = Field(False, description="是否启用OSS上传")
    oss_access_key_id: str = Field("", description="阿里云OSS Access Key ID")
    oss_access_key_secret: str = Field("", description="阿里云OSS Access Key Secret")
    oss_bucket_name: str = Field("", description="OSS Bucket名称")
    oss_endpoint: str = Field("oss-cn-beijing.aliyuncs.com", description="OSS外网Endpoint")
    oss_internal_endpoint: str = Field("", description="OSS内网Endpoint（可选，用于ECS内网访问）")
    oss_auto_delete_local: bool = Field(False, description="上传后是否删除本地文件")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
