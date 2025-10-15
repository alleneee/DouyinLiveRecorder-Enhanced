"""配置文件加载器 - 从 config.ini 加载配置到 Settings。"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any

from .config import settings


def str_to_bool(value: str) -> bool:
    """将中文是/否或英文yes/no转换为布尔值。"""
    value = value.strip().lower()
    return value in ("是", "yes", "true", "1", "on")


def load_config_from_ini(ini_path: str | Path = "config/config.ini") -> dict[str, Any]:
    """从 config.ini 文件加载配置。
    
    Args:
        ini_path: config.ini 文件路径
    
    Returns:
        配置字典
    """
    ini_path = Path(ini_path)
    if not ini_path.exists():
        return {}
    
    config = configparser.ConfigParser()
    config.read(ini_path, encoding="utf-8")
    
    settings_dict = {}
    
    # 录制设置
    if config.has_section("录制设置"):
        section = config["录制设置"]
        settings_dict.update({
            "video_save_path": section.get("直播保存路径(不填则默认)", "downloads").strip() or "downloads",
            "folder_by_author": str_to_bool(section.get("保存文件夹是否以作者区分", "是")),
            "folder_by_time": str_to_bool(section.get("保存文件夹是否以时间区分", "否")),
            "folder_by_title": str_to_bool(section.get("保存文件夹是否以标题区分", "否")),
            "filename_include_title": str_to_bool(section.get("保存文件名是否包含标题", "否")),
            "clean_emoji": str_to_bool(section.get("是否去除名称中的表情符号", "是")),
            "video_save_type": section.get("视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频", "ts"),
            "video_quality": section.get("原画|超清|高清|标清|流畅", "流畅"),
            "use_proxy": str_to_bool(section.get("是否使用代理ip(是/否)", "否")),
            "proxy_addr": section.get("代理地址", "").strip(),
            "max_concurrent_downloads": int(section.get("同一时间访问网络的线程数", "3")),
            "loop_interval": int(section.get("循环时间(秒)", "300")),
            "show_loop_time": str_to_bool(section.get("是否显示循环秒数", "否")),
            "show_stream_url": str_to_bool(section.get("是否显示直播源地址", "否")),
            "segment_recording_enabled": str_to_bool(section.get("分段录制是否开启", "是")),
            "segment_duration": int(section.get("视频分段时间(秒)", "1800")),
            "force_https": str_to_bool(section.get("是否强制启用https录制", "否")),
            "disk_space_threshold": float(section.get("录制空间剩余阈值(gb)", "1.0")),
            "converts_to_mp4": str_to_bool(section.get("录制完成后自动转为mp4格式", "是")),
            "mp4_reencode_h264": str_to_bool(section.get("mp4格式重新编码为h264", "否")),
            "delete_origin_file": str_to_bool(section.get("追加格式后删除原文件", "是")),
            "generate_subtitle": str_to_bool(section.get("生成时间字幕文件", "否")),
            "run_custom_script": str_to_bool(section.get("是否录制完成后执行自定义脚本", "否")),
            "custom_script_command": section.get("自定义脚本执行命令", "").strip(),
            "console_log_enabled": str_to_bool(section.get("状态信息显示在控制台(是/否)", "否")),
            "file_log_enabled": str_to_bool(section.get("状态信息记录到日志文件(是/否)", "是")),
        })
    
    # 超时设置
    if config.has_section("超时设置"):
        section = config["超时设置"]
        settings_dict.update({
            "network_timeout": int(section.get("网络请求超时(秒)", "30")),
            "semaphore_timeout": int(section.get("信号量获取超时(秒)", "10")),
            "post_process_timeout": int(section.get("后处理脚本超时(小时)", "3")),
            "ffmpeg_timeout": int(section.get("FFmpeg进程超时(分钟)", "30")),
        })
    
    # 日志设置
    if config.has_section("日志设置"):
        section = config["日志设置"]
        settings_dict.update({
            "log_retention_days": int(section.get("日志保留天数", "7")),
            "log_max_file_size": section.get("最大文件大小", "10 MB"),
            "debug_mode": str_to_bool(section.get("debug模式", "否")),
        })
    
    # OSS配置
    if config.has_section("OSS配置"):
        section = config["OSS配置"]
        settings_dict.update({
            "oss_enabled": str_to_bool(section.get("enable_upload", "否")),
            "oss_access_key_id": section.get("access_key_id", "").strip(),
            "oss_access_key_secret": section.get("access_key_secret", "").strip(),
            "oss_endpoint": section.get("endpoint", "").strip(),
            "oss_bucket_name": section.get("bucket_name", "").strip(),
            "oss_base_path": section.get("base_path", "live-recordings").strip(),
            "oss_upload_immediately": str_to_bool(section.get("upload_immediately", "否")),
            "oss_delete_after_upload": str_to_bool(section.get("delete_after_upload", "否")),
            "oss_max_upload_threads": int(section.get("max_upload_threads", "4")),
            "oss_retry_times": int(section.get("retry_times", "3")),
            "oss_chunk_size": int(section.get("chunk_size", "8388608")),
            "oss_use_internal_endpoint": str_to_bool(section.get("use_internal_endpoint", "否")),
            "oss_url_expires": int(section.get("url_expires", "31536000")),
        })
    
    # 推送配置
    if config.has_section("推送配置"):
        section = config["推送配置"]
        settings_dict.update({
            "push_enabled": str_to_bool(section.get("开播推送开启(是/否)", "是")) or str_to_bool(section.get("关播推送开启(是/否)", "是")),
            "push_channel": section.get("直播状态推送渠道", "").strip(),
            "dingtalk_webhook": section.get("钉钉推送接口链接", "").strip(),
            "dingtalk_secret": section.get("钉钉签名密钥", "").strip(),
            "dingtalk_at_mobiles": section.get("钉钉通知@对象(填手机号)", "").strip(),
            "dingtalk_at_all": str_to_bool(section.get("钉钉通知@全体(是/否)", "否")),
            "push_on_start": str_to_bool(section.get("开播推送开启(是/否)", "是")),
            "push_on_stop": str_to_bool(section.get("关播推送开启(是/否)", "是")),
            "push_check_interval": int(section.get("直播推送检测频率(秒)", "60")),
        })
    
    return settings_dict


def apply_ini_config():
    """应用 config.ini 配置到全局 settings。"""
    config_dict = load_config_from_ini()
    
    # 更新 settings 对象
    for key, value in config_dict.items():
        if hasattr(settings, key):
            setattr(settings, key, value)


__all__ = ["load_config_from_ini", "apply_ini_config", "str_to_bool"]
