"""应用配置。"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", case_sensitive=False)

    app_name: str = "Douyin Live Recorder"
    version: str = "0.1.0"
    api_prefix: str = "/api"
    database_url: str = "mysql+pymysql://root:123456@localhost:3306/test"
    sqlalchemy_echo: bool = False
    
    # 录制设置
    video_save_path: str = Field(default="downloads", description="直播保存路径")
    folder_by_author: bool = Field(default=True, description="保存文件夹是否以作者区分")
    folder_by_time: bool = Field(default=False, description="保存文件夹是否以时间区分")
    folder_by_title: bool = Field(default=False, description="保存文件夹是否以标题区分")
    filename_include_title: bool = Field(default=False, description="保存文件名是否包含标题")
    clean_emoji: bool = Field(default=True, description="是否去除名称中的表情符号")
    video_save_type: str = Field(default="MP4", description="视频保存格式: ts/mkv/flv/mp4/mp3/m4a")
    video_quality: str = Field(default="OD", description="视频质量: OD原画/TD超清/HD高清/SD标清/LD流畅")
    use_proxy: bool = Field(default=False, description="是否使用代理")
    proxy_addr: str = Field(default="", description="代理地址")
    max_concurrent_downloads: int = Field(default=3, description="同一时间访问网络的线程数")
    loop_interval: int = Field(default=300, description="循环时间（秒）")
    show_loop_time: bool = Field(default=False, description="是否显示循环秒数")
    show_stream_url: bool = Field(default=False, description="是否显示直播源地址")
    
    # 分段录制配置
    segment_recording_enabled: bool = Field(default=True, description="启用分段录制")
    segment_duration: int = Field(default=60, description="分段时长（秒），默认60秒=1分钟（测试用）")
    force_https: bool = Field(default=False, description="是否强制启用https录制")
    disk_space_threshold: float = Field(default=1.0, description="录制空间剩余阈值(GB)")
    
    # 后处理配置
    converts_to_mp4: bool = Field(default=True, description="录制完成后自动转为mp4格式")
    mp4_reencode_h264: bool = Field(default=False, description="mp4格式重新编码为h264")
    delete_origin_file: bool = Field(default=True, description="追加格式后删除原文件")
    generate_subtitle: bool = Field(default=False, description="生成时间字幕文件")
    run_custom_script: bool = Field(default=False, description="是否录制完成后执行自定义脚本")
    custom_script_command: str = Field(default="", description="自定义脚本执行命令")
    
    # 超时设置
    network_timeout: int = Field(default=30, description="网络请求超时（秒）")
    semaphore_timeout: int = Field(default=10, description="信号量获取超时（秒）")
    post_process_timeout: int = Field(default=3, description="后处理脚本超时（小时）")
    ffmpeg_timeout: int = Field(default=30, description="FFmpeg进程超时（分钟）")
    
    # 日志设置
    log_retention_days: int = Field(default=7, description="日志保留天数")
    log_max_file_size: str = Field(default="10 MB", description="最大文件大小")
    debug_mode: bool = Field(default=False, description="debug模式")
    console_log_enabled: bool = Field(default=False, description="状态信息显示在控制台")
    file_log_enabled: bool = Field(default=True, description="状态信息记录到日志文件")
    
    # OSS 配置
    oss_enabled: bool = Field(default=True, description="启用 OSS 上传")
    oss_access_key_id: str = Field(default="", description="阿里云 AccessKeyId")
    oss_access_key_secret: str = Field(default="", description="阿里云 AccessKeySecret")
    oss_endpoint: str = Field(default="", description="OSS 端点，如 oss-cn-hangzhou.aliyuncs.com")
    oss_bucket_name: str = Field(default="", description="OSS Bucket 名称")
    oss_base_path: str = Field(default="live-recordings", description="OSS 文件基础路径")
    oss_use_internal_endpoint: bool = Field(default=False, description="使用内网端点（阿里云 ECS 内部访问）")
    oss_url_expires: int = Field(default=31536000, description="签名 URL 有效期（秒），默认 1 年")
    oss_upload_immediately: bool = Field(default=False, description="是否立即上传")
    oss_delete_after_upload: bool = Field(default=True, description="上传成功后删除本地文件")
    oss_max_upload_threads: int = Field(default=4, description="最大上传线程数")
    oss_retry_times: int = Field(default=3, description="上传重试次数")
    oss_chunk_size: int = Field(default=8388608, description="分片大小（字节），默认8MB")
    
    # 推送配置
    push_enabled: bool = Field(default=False, description="启用推送通知")
    push_channel: str = Field(default="", description="推送渠道: 钉钉/微信/Telegram等")
    dingtalk_webhook: str = Field(default="", description="钉钉推送接口链接")
    dingtalk_secret: str = Field(default="", description="钉钉签名密钥")
    dingtalk_at_mobiles: str = Field(default="", description="钉钉通知@对象（手机号）")
    dingtalk_at_all: bool = Field(default=False, description="钉钉通知@全体")
    push_on_start: bool = Field(default=True, description="开播推送开启")
    push_on_stop: bool = Field(default=True, description="关播推送开启")
    push_check_interval: int = Field(default=60, description="直播推送检测频率（秒）")


settings = Settings()


__all__ = ["Settings", "settings"]
