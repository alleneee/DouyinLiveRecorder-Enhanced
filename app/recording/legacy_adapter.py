"""适配旧版 `main.start_record` 的包装器。"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.recording.environment import RecordingEnvironment
from src.recording.context import RecordingContext
from src.recording.models import Room


@dataclass(slots=True)
class LegacyRecorder:
    env: RecordingEnvironment
    context: RecordingContext

    def __post_init__(self) -> None:
        import main as legacy_main  # 延迟导入，确保原模块可用

        self._legacy = legacy_main
        self._configure_globals()

    def _configure_globals(self) -> None:
        env = self.env
        opts = env.options
        push = env.push
        parser = env.parser
        legacy = self._legacy

        def read(section: str, key: str, default: str = "") -> str:
            return parser.get(section, key, fallback=default)

        def read_bool(section: str, key: str, default: str = "否") -> bool:
            return read(section, key, default) in {"是", "True", "true", "1"}

        def set_attr(name: str, value) -> None:
            setattr(legacy, name, value)

        # 录制输出相关
        set_attr("folder_by_author", opts.folder_by_author)
        set_attr("folder_by_time", opts.folder_by_time)
        set_attr("folder_by_title", opts.folder_by_title)
        set_attr("filename_by_title", opts.filename_by_title)
        set_attr("clean_emoji", opts.clean_emoji)
        set_attr("video_save_path", str(opts.video_save_path))
        set_attr("video_save_type", opts.video_save_type)
        set_attr("video_record_quality", opts.video_record_quality)
        set_attr("split_video_by_time", opts.split_video_by_time)
        set_attr("enable_https_recording", opts.enable_https_recording)
        set_attr("disk_space_limit", opts.disk_space_limit)
        set_attr("split_time", opts.split_time)
        set_attr("converts_to_mp4", opts.converts_to_mp4)
        set_attr("converts_to_h264", opts.converts_to_h264)
        set_attr("delete_origin_file", opts.delete_origin_file)
        set_attr("create_time_file", opts.create_time_file)
        if opts.video_save_path:
            set_attr("default_path", str(opts.video_save_path))

        # 代理、线程并发控制
        set_attr("use_proxy", opts.use_proxy)
        set_attr("proxy_addr", opts.proxy_addr)
        set_attr("proxy_addr_bak", opts.proxy_addr)
        set_attr("enable_proxy_platform_list", opts.enable_proxy_platforms)
        set_attr("extra_enable_proxy_platform_list", opts.extra_proxy_platforms)
        set_attr("max_request", opts.max_request)
        set_attr("semaphore", threading.Semaphore(opts.max_request))
        set_attr("delay_default", opts.loop_interval)
        set_attr("global_proxy", bool(opts.proxy_addr))
        set_attr("local_delay_default", opts.queue_delay)

        # 推送配置
        set_attr("live_status_push", push.options.get("channels_raw", ""))
        set_attr("push_message_title", push.title)
        set_attr("begin_push_message_text", push.begin_template)
        set_attr("over_push_message_text", push.end_template)
        set_attr("begin_show_push", push.begin_enable)
        set_attr("over_show_push", push.end_enable)
        set_attr("disable_record", push.disable_record)
        set_attr("push_check_seconds", push.frequency_seconds)

        # 推送渠道详细配置
        set_attr("xizhi_api_url", read("推送配置", "微信推送接口链接"))
        set_attr("dingtalk_api_url", read("推送配置", "钉钉推送接口链接"))
        set_attr("dingtalk_secret", read("推送配置", "钉钉签名密钥"))
        set_attr("dingtalk_phone_num", read("推送配置", "钉钉通知@对象(填手机号)"))
        set_attr("dingtalk_is_atall", read_bool("推送配置", "钉钉通知@全体(是/否)", "否"))
        set_attr("tg_token", read("推送配置", "tgapi令牌"))
        set_attr("tg_chat_id", read("推送配置", "tg聊天id(个人或者群组id)"))
        set_attr("bark_msg_api", read("推送配置", "bark推送接口链接"))
        set_attr("bark_msg_level", read("推送配置", "bark推送中断级别", "active"))
        set_attr("bark_msg_ring", read("推送配置", "bark推送铃声", "bell"))
        set_attr("ntfy_api", read("推送配置", "ntfy推送地址"))
        set_attr("ntfy_tags", read("推送配置", "ntfy推送标签", "tada"))
        set_attr("ntfy_email", read("推送配置", "ntfy推送邮箱"))
        set_attr("begin_push_message_text", push.begin_template)
        set_attr("over_push_message_text", push.end_template)

        set_attr("email_host", read("推送配置", "SMTP邮件服务器"))
        set_attr("smtp_port", read("推送配置", "SMTP邮件服务器端口"))
        set_attr("open_smtp_ssl", read_bool("推送配置", "是否使用SMTP服务SSL加密(是/否)", "是"))
        set_attr("login_email", read("推送配置", "邮箱登录账号"))
        set_attr("email_password", read("推送配置", "发件人密码(授权码)"))
        set_attr("sender_email", read("推送配置", "发件人邮箱"))
        set_attr("sender_name", read("推送配置", "发件人显示昵称"))
        set_attr("to_email", read("推送配置", "收件人邮箱"))

        # 账号信息
        set_attr("sooplive_username", read("账号密码", "sooplive账号"))
        set_attr("sooplive_password", read("账号密码", "sooplive密码"))
        set_attr("flextv_username", read("账号密码", "flextv账号"))
        set_attr("flextv_password", read("账号密码", "flextv密码"))
        set_attr("popkontv_username", read("账号密码", "popkontv账号"))
        set_attr("popkontv_partner_code", read("账号密码", "partner_code", "P-00001"))
        set_attr("popkontv_password", read("账号密码", "popkontv密码"))
        set_attr("twitcasting_account_type", read("账号密码", "twitcasting账号类型", "normal"))
        set_attr("twitcasting_username", read("账号密码", "twitcasting账号"))
        set_attr("twitcasting_password", read("账号密码", "twitcasting密码"))
        set_attr("popkontv_access_token", read("Authorization", "popkontv_token"))

        # Cookie 映射
        cookie_map = {
            "抖音cookie": "dy_cookie",
            "快手cookie": "ks_cookie",
            "tiktok_cookie": "tiktok_cookie",
            "虎牙cookie": "hy_cookie",
            "斗鱼cookie": "douyu_cookie",
            "yy_cookie": "yy_cookie",
            "B站cookie": "bili_cookie",
            "小红书cookie": "xhs_cookie",
            "bigo_cookie": "bigo_cookie",
            "blued_cookie": "blued_cookie",
            "sooplive_cookie": "sooplive_cookie",
            "netease_cookie": "netease_cookie",
            "千度热播_cookie": "qiandurebo_cookie",
            "pandatv_cookie": "pandatv_cookie",
            "猫耳fm_cookie": "maoerfm_cookie",
            "winktv_cookie": "winktv_cookie",
            "flextv_cookie": "flextv_cookie",
            "look_cookie": "look_cookie",
            "twitcasting_cookie": "twitcasting_cookie",
            "baidu_cookie": "baidu_cookie",
            "weibo_cookie": "weibo_cookie",
            "kugou_cookie": "kugou_cookie",
            "twitch_cookie": "twitch_cookie",
            "liveme_cookie": "liveme_cookie",
            "huajiao_cookie": "huajiao_cookie",
            "liuxing_cookie": "liuxing_cookie",
            "showroom_cookie": "showroom_cookie",
            "acfun_cookie": "acfun_cookie",
            "changliao_cookie": "changliao_cookie",
            "yinbo_cookie": "yinbo_cookie",
            "yingke_cookie": "yingke_cookie",
            "zhihu_cookie": "zhihu_cookie",
            "chzzk_cookie": "chzzk_cookie",
            "haixiu_cookie": "haixiu_cookie",
            "vvxqiu_cookie": "vvxqiu_cookie",
            "17live_cookie": "yiqilive_cookie",
            "langlive_cookie": "langlive_cookie",
            "pplive_cookie": "pplive_cookie",
            "6room_cookie": "six_room_cookie",
            "lehaitv_cookie": "lehaitv_cookie",
            "huamao_cookie": "huamao_cookie",
            "shopee_cookie": "shopee_cookie",
            "youtube_cookie": "youtube_cookie",
            "taobao_cookie": "taobao_cookie",
            "jd_cookie": "jd_cookie",
            "faceit_cookie": "faceit_cookie",
            "migu_cookie": "migu_cookie",
        }
        if parser.has_section("Cookie"):
            for key, attr in cookie_map.items():
                set_attr(attr, read("Cookie", key))

    def record(self, room: Room, *, stop_event: threading.Event | None = None) -> None:
        self._legacy.start_record((room.quality, room.url, room.nickname), stop_event=stop_event, room=room)

    def record(self, room: Room, *, stop_event: threading.Event | None = None) -> None:
        self._legacy.start_record((room.quality, room.url, room.nickname), stop_event=stop_event, room=room)


__all__ = ["LegacyRecorder"]
