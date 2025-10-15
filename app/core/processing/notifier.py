"""推送通知服务。"""

from __future__ import annotations

from typing import Optional

from msg_push import dingtalk, xizhi, tg_bot, send_email, bark, ntfy
from app.legacy.utils import logger


class PushNotifier:
    """推送通知服务。
    
    负责向各种渠道发送直播状态通知。
    """
    
    def __init__(
        self,
        *,
        enabled_channels: list[str] | None = None,
        title: str = "直播间状态更新通知",
        begin_template: str = "{anchor_name} 开始直播了",
        end_template: str = "{anchor_name} 直播结束",
        **channel_configs,
    ):
        self.enabled_channels = enabled_channels or []
        self.title = title
        self.begin_template = begin_template
        self.end_template = end_template
        self.channel_configs = channel_configs
    
    def notify_live_start(
        self,
        anchor_name: str,
        live_url: str,
        *,
        extra_info: Optional[dict] = None,
    ) -> None:
        """通知直播开始。"""
        content = self.begin_template.format(
            anchor_name=anchor_name,
            live_url=live_url,
            **(extra_info or {}),
        )
        self._send_notification(content, live_url)
    
    def notify_live_end(
        self,
        anchor_name: str,
        live_url: str,
        *,
        duration: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """通知直播结束。"""
        content = self.end_template.format(
            anchor_name=anchor_name,
            live_url=live_url,
            duration=duration or "未知",
            file_path=file_path or "未保存",
        )
        self._send_notification(content, live_url)
    
    def _send_notification(self, content: str, live_url: str) -> None:
        """发送通知到各个渠道。"""
        push_functions = {
            "微信": lambda: xizhi(
                self.channel_configs.get("xizhi_api_url", ""),
                self.title,
                content,
            ),
            "钉钉": lambda: dingtalk(
                self.channel_configs.get("dingtalk_api_url", ""),
                self.channel_configs.get("dingtalk_secret", ""),
                self.title,
                content,
                self.channel_configs.get("dingtalk_phone_num", ""),
                self.channel_configs.get("dingtalk_is_atall", False),
            ),
            "TG": lambda: tg_bot(
                self.channel_configs.get("tg_token", ""),
                self.channel_configs.get("tg_chat_id", ""),
                self.title,
                content,
            ),
            "bark": lambda: bark(
                self.channel_configs.get("bark_msg_api", ""),
                self.title,
                content,
                self.channel_configs.get("bark_msg_level", "active"),
                self.channel_configs.get("bark_msg_ring", "bell"),
            ),
            "ntfy": lambda: ntfy(
                self.channel_configs.get("ntfy_api", ""),
                self.title,
                content,
                self.channel_configs.get("ntfy_tags", "tada"),
                self.channel_configs.get("ntfy_email", ""),
            ),
            "邮箱": lambda: send_email(
                self.channel_configs.get("email_host", ""),
                self.channel_configs.get("smtp_port", 587),
                self.channel_configs.get("login_email", ""),
                self.channel_configs.get("email_password", ""),
                self.channel_configs.get("sender_email", ""),
                self.channel_configs.get("to_email", ""),
                self.title,
                content,
                self.channel_configs.get("sender_name", ""),
                self.channel_configs.get("open_smtp_ssl", True),
            ),
        }
        
        for channel in self.enabled_channels:
            if channel in push_functions:
                try:
                    push_functions[channel]()
                    logger.info(f"通知已发送到 {channel}")
                except Exception as e:
                    logger.error(f"发送通知到 {channel} 失败: {e}")


__all__ = ["PushNotifier"]
