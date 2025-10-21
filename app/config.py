"""应用配置"""
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    # Pydantic v2 配置：忽略 .env 中额外的字段
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # 忽略未定义的字段
    )

    # 环境配置
    environment: str = Field("prod", description="运行环境(test/prod/dev)")

    # 数据库配置（分离式）
    db_driver: str = "mysql+pymysql"
    db_username: str = "root"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "douyinlive"

    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"{self.db_driver}://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    
    # 录制配置
    segment_duration: int = 60  # 分段时长（秒）
    video_save_type: str = "mp4"  # 最终保存格式 (上传OSS的格式)
    video_record_format: str = "ts"  # 录制时使用的格式 (ts/flv, ts更稳定)
    video_save_path: str = "./downloads"  # 保存路径

    @property
    def ffmpeg_format(self) -> str:
        """获取FFmpeg录制时的格式参数"""
        format_map = {
            'ts': 'mpegts',  # TS格式的正确FFmpeg参数
            'flv': 'flv',
            'mp4': 'mp4'
        }
        return format_map.get(self.video_record_format.lower(), 'mpegts')

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

    # 分片通知配置
    segment_notification_url: str = Field("", description="分片上传完成后通知的目标URL(留空则不发送通知)")


settings = Settings()
