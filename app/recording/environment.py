"""录制环境配置加载模块。"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.legacy import utils


@dataclass(slots=True)
class PushConfig:
    enabled: bool
    channel: str | None
    options: dict[str, Any]
    title: str
    begin_template: str
    end_template: str
    begin_enable: bool
    end_enable: bool
    disable_record: bool
    frequency_seconds: int


@dataclass(slots=True)
class RecordingOptions:
    folder_by_author: bool
    folder_by_time: bool
    folder_by_title: bool
    filename_by_title: bool
    clean_emoji: bool
    video_save_path: Path
    video_save_type: str
    video_record_quality: str
    split_video_by_time: bool
    enable_https_recording: bool
    disk_space_limit: float
    split_time: int
    converts_to_mp4: bool
    converts_to_h264: bool
    delete_origin_file: bool
    create_time_file: bool
    use_proxy: bool
    proxy_addr: str | None
    max_request: int
    loop_interval: int
    enable_proxy_platforms: list[str]
    extra_proxy_platforms: list[str]
    queue_delay: int


@dataclass(slots=True)
class RecordingEnvironment:
    config_path: Path
    parser: configparser.RawConfigParser
    options: RecordingOptions
    push: PushConfig
    cookies: dict[str, str]


def load_environment(config_dir: Path) -> RecordingEnvironment:
    """从旧版 ini 配置加载录制环境。"""

    config_file = config_dir / "config.ini"
    parser = configparser.RawConfigParser()
    parser.read(config_file, encoding="utf-8")

    options = {
        "是": True,
        "否": False,
    }

    def read(section: str, key: str, default: str) -> str:
        return parser.get(section, key, fallback=default)

    def read_bool(section: str, key: str, default: str) -> bool:
        return options.get(read(section, key, default), False)

    record_path = Path(read("录制设置", "直播保存路径(不填则默认)", ""))
    if not record_path:
        record_path = Path(config_dir.parent / "downloads")

    recording_options = RecordingOptions(
        folder_by_author=read_bool("录制设置", "保存文件夹是否以作者区分", "是"),
        folder_by_time=read_bool("录制设置", "保存文件夹是否以时间区分", "否"),
        folder_by_title=read_bool("录制设置", "保存文件夹是否以标题区分", "否"),
        filename_by_title=read_bool("录制设置", "保存文件名是否包含标题", "否"),
        clean_emoji=read_bool("录制设置", "是否去除名称中的表情符号", "是"),
        video_save_path=record_path,
        video_save_type=read("录制设置", "视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频", "ts").upper(),
        video_record_quality=read("录制设置", "原画|超清|高清|标清|流畅", "原画"),
        split_video_by_time=read_bool("录制设置", "分段录制是否开启", "否"),
        enable_https_recording=read_bool("录制设置", "是否强制启用https录制", "否"),
        disk_space_limit=float(read("录制设置", "录制空间剩余阈值(gb)", "1")),
        split_time=int(read("录制设置", "视频分段时间(秒)", "1800")),
        converts_to_mp4=read_bool("录制设置", "录制完成后自动转为mp4格式", "否"),
        converts_to_h264=read_bool("录制设置", "mp4格式重新编码为h264", "否"),
        delete_origin_file=read_bool("录制设置", "追加格式后删除原文件", "否"),
        create_time_file=read_bool("录制设置", "生成时间字幕文件", "否"),
        use_proxy=read_bool("录制设置", "是否使用代理ip(是/否)", "是"),
        proxy_addr=read("录制设置", "代理地址", "") or None,
        max_request=int(read("录制设置", "同一时间访问网络的线程数", "3")),
        loop_interval=int(read("录制设置", "循环时间(秒)", "120")),
        enable_proxy_platforms=_split_list(read("录制设置", "使用代理录制的平台(逗号分隔)", "")),
        extra_proxy_platforms=_split_list(read("录制设置", "额外使用代理录制的平台(逗号分隔)", "")),
        queue_delay=int(read("录制设置", "排队读取网址时间(秒)", "0")),
    )

    push_channel = read("推送配置", "直播状态推送渠道", "") or None
    push_title = read("推送配置", "自定义推送标题", "直播间状态更新通知")
    push_begin_template = read("推送配置", "自定义开播推送内容", "")
    push_end_template = read("推送配置", "自定义关播推送内容", "")
    push_begin_enable = read_bool("推送配置", "开播推送开启(是/否)", "是")
    push_end_enable = read_bool("推送配置", "关播推送开启(是/否)", "否")
    push_disable_record = read_bool("推送配置", "只推送通知不录制(是/否)", "否")
    push_frequency = int(read("推送配置", "直播推送检测频率(秒)", "1800"))

    push_config = PushConfig(
        enabled=bool(push_channel),
        channel=push_channel,
        options={
            "dingtalk": {
                "url": read("推送配置", "钉钉推送接口链接", ""),
                "secret": read("推送配置", "钉钉签名密钥", ""),
            },
            "tg": {
                "token": read("推送配置", "tgapi令牌", ""),
                "chat_id": read("推送配置", "tg聊天id(个人或者群组id)", ""),
            },
            "channels_raw": push_channel or "",
        },
        title=push_title,
        begin_template=push_begin_template,
        end_template=push_end_template,
        begin_enable=push_begin_enable,
        end_enable=push_end_enable,
        disable_record=push_disable_record,
        frequency_seconds=push_frequency,
    )

    cookie_sections = "Cookie", "Authorization"
    cookies: dict[str, str] = {}
    for section in cookie_sections:
        if parser.has_section(section):
            for key, value in parser.items(section):
                cookies[key] = value

    return RecordingEnvironment(
        config_path=config_file,
        parser=parser,
        options=recording_options,
        push=push_config,
        cookies=cookies,
    )


__all__ = [
    "RecordingEnvironment",
    "RecordingOptions",
    "PushConfig",
    "load_environment",
]
def _split_list(value: str) -> list[str]:
    if not value:
        return []
    items = [item.strip() for item in value.replace('，', ',').split(',')]
    return [item for item in items if item]
