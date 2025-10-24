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
    segment_duration: int = 300  # 分段时长（秒）- 默认5分钟（测试用）
    segment_method: str = Field("hls", description="录制分片方式: hls(推荐稳定) / segment(传统模式)")
    audio_codec_mode: str = Field("copy", description="音频编码模式: copy(直接复制,性能高) / aac(重编码,兼容性好)")
    video_save_type: str = "mp4"  # 最终保存格式 (上传OSS的格式)
    video_record_format: str = "ts"  # 录制时使用的格式 (ts/flv, ts更稳定)
    video_save_path: str = "./downloads"  # 保存路径
    max_concurrent_recordings: int = Field(50, description="最大并发录制数量（防止资源耗尽，推荐30-50）")
    
    # FFmpeg编码配置
    force_keyframe_mode: bool = Field(True, description="强制关键帧模式：确保精确分段但需重新编码视频")
    ffmpeg_preset: str = Field("ultrafast", description="FFmpeg编码预设（ultrafast/superfast/veryfast/faster/fast/medium）")
    ffmpeg_crf: int = Field(23, description="FFmpeg质量控制（18-28，越小质量越高但文件越大）")
    ffmpeg_gop_seconds: int = Field(2, description="GOP间隔（秒），建议2-4秒，越小切片越精确但编码负载越高")
    ffmpeg_assumed_fps: int = Field(30, description="假设的视频帧率，用于计算GOP大小")

    # 重试机制配置
    max_retry_attempts: int = Field(3, description="录制失败最大重试次数")
    retry_delay_seconds: int = Field(10, description="重试间隔（秒）")
    retry_backoff_multiplier: float = Field(2.0, description="重试延迟倍增因子（指数退避）")

    # 监控配置
    ffmpeg_progress_ratio: float = Field(0.2, description="FFmpeg录制进度日志输出频率（占segment_duration的比率），0表示禁用进度日志。例如0.2表示每20%分段时长输出一次")

    # 线程池配置
    monitor_thread_pool_size: int = Field(50, description="监控线程池大小（建议>=max_concurrent_recordings）")
    recording_thread_pool_size: int = Field(50, description="录制线程池大小（建议>=max_concurrent_recordings）")
    
    # OSS上传队列配置
    oss_upload_workers: int = Field(15, description="OSS上传工作线程数（建议10-20）")
    oss_upload_queue_size: int = Field(500, description="OSS上传队列最大长度")

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
    segment_notification_base_url: str = Field("", description="分片通知服务的基础URL(如: http://api.example.com)")
    
    @property
    def segment_notification_url(self) -> str:
        """构建完整的分片通知URL
        
        Returns:
            完整URL: {base_url}/shard/plan
            如果base_url为空,返回空字符串
        """
        if not self.segment_notification_base_url:
            return ""
        
        # 去除base_url末尾的斜杠,统一拼接格式
        base = self.segment_notification_base_url.rstrip('/')
        return f"{base}/shard/plan"


settings = Settings()
