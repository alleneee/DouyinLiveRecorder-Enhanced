"""
视频分片通知服务
在分片上传完成后,构建并发送通知到外部API
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
import httpx
from sqlalchemy.orm import Session

from app.models.video_segment import VideoSegment
from app.models.live_room import LiveRoom
from app.schemas.segment_notification import (
    SegmentNotificationRequest,
    LiveInfo,
    SubVideoInfo,
    VideoShardInfo
)
from app.config import settings

logger = logging.getLogger(__name__)


class SegmentNotifier:
    """视频分片通知服务"""

    def __init__(self, notification_url: Optional[str] = None, timeout: int = 30):
        """
        初始化通知服务

        Args:
            notification_url: 通知目标URL,默认从环境变量读取
            timeout: HTTP请求超时时间(秒)
        """
        self.notification_url = notification_url or getattr(settings, 'SEGMENT_NOTIFICATION_URL', '')
        self.timeout = timeout
        self.enabled = bool(self.notification_url)

        if not self.enabled:
            logger.info("分片通知服务未启用(SEGMENT_NOTIFICATION_URL未配置)")

    def format_datetime_to_iso(self, dt: datetime) -> str:
        """
        将datetime对象格式化为ISO格式字符串

        Args:
            dt: datetime对象

        Returns:
            ISO格式的时间字符串 (YYYY-MM-DDTHH:MM:SS)
        """
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    def build_notification_data(
        self,
        db: Session,
        segment: VideoSegment
    ) -> Optional[SegmentNotificationRequest]:
        """
        构建通知数据

        Args:
            db: 数据库会话
            segment: 视频分片对象

        Returns:
            通知请求对象,如果构建失败返回None
        """
        try:
            # 获取直播间信息
            room = db.query(LiveRoom).filter(LiveRoom.id == segment.room_id).first()
            if not room:
                logger.error(f"直播间不存在: room_id={segment.room_id}")
                return None

            # 检查时间信息完整性
            if not segment.segment_started_at:
                logger.error(f"分片开始时间不存在: segment_id={segment.id}")
                return None

            # 使用segment_ended_at,如果不存在则使用started_at + duration
            if segment.segment_ended_at:
                end_time = segment.segment_ended_at
            elif segment.duration:
                end_time = segment.segment_started_at + timedelta(seconds=segment.duration)
            else:
                logger.error(f"分片结束时间无法确定: segment_id={segment.id}")
                return None

            # 构建请求数据,直接使用数据库中的绝对时间
            notification = SegmentNotificationRequest(
                live_info=LiveInfo(
                    live_id=room.current_session_id,
                    live_url=room.url,
                    live_name=room.streamer_name
                ),
                sub_video_info=SubVideoInfo(
                    video_url=segment.oss_video_url or "",
                    audio_url=segment.oss_audio_url or "",
                    duration=segment.duration or 0,
                    absolute_start_time=self.format_datetime_to_iso(segment.segment_started_at),
                    absolute_end_time=self.format_datetime_to_iso(end_time),
                    serial_num=segment.segment_index or 0
                ),
                video_shard_info=[]  # 当前版本为空,预留扩展
            )

            return notification

        except Exception as e:
            logger.error(f"构建通知数据失败: segment_id={segment.id}, error={e}", exc_info=True)
            return None

    async def send_notification_async(
        self,
        db: Session,
        segment_id: int
    ) -> bool:
        """
        异步发送通知

        Args:
            db: 数据库会话
            segment_id: 视频分片ID

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug(f"通知服务未启用,跳过发送: segment_id={segment_id}")
            return False

        try:
            # 获取分片信息
            segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not segment:
                logger.error(f"视频分片不存在: segment_id={segment_id}")
                return False

            # 检查是否已上传完成
            if not segment.oss_video_url or not segment.oss_audio_url:
                logger.warning(
                    f"分片尚未上传完成,跳过通知: segment_id={segment_id}, "
                    f"video={bool(segment.oss_video_url)}, audio={bool(segment.oss_audio_url)}"
                )
                return False

            # 构建通知数据
            notification_data = self.build_notification_data(db, segment)
            if not notification_data:
                return False

            # 发送HTTP请求
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.notification_url,
                    json=notification_data.model_dump(),
                    headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                logger.info(
                    f"分片通知发送成功: segment_id={segment_id}, "
                    f"status={response.status_code}, url={self.notification_url}"
                )
                return True

        except httpx.HTTPError as e:
            logger.error(
                f"分片通知发送失败(HTTP错误): segment_id={segment_id}, "
                f"error={e}, url={self.notification_url}",
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                f"分片通知发送失败: segment_id={segment_id}, error={e}",
                exc_info=True
            )
            return False

    def send_notification_sync(
        self,
        db: Session,
        segment_id: int
    ) -> bool:
        """
        同步发送通知(用于线程中调用)

        Args:
            db: 数据库会话
            segment_id: 视频分片ID

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug(f"通知服务未启用,跳过发送: segment_id={segment_id}")
            return False

        try:
            # 获取分片信息
            segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not segment:
                logger.error(f"视频分片不存在: segment_id={segment_id}")
                return False

            # 检查是否已上传完成
            if not segment.oss_video_url or not segment.oss_audio_url:
                logger.warning(
                    f"分片尚未上传完成,跳过通知: segment_id={segment_id}, "
                    f"video={bool(segment.oss_video_url)}, audio={bool(segment.oss_audio_url)}"
                )
                return False

            # 构建通知数据
            notification_data = self.build_notification_data(db, segment)
            if not notification_data:
                return False

            # 发送HTTP请求(同步)
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.notification_url,
                    json=notification_data.model_dump(),
                    headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                logger.info(
                    f"分片通知发送成功: segment_id={segment_id}, "
                    f"status={response.status_code}, url={self.notification_url}"
                )
                return True

        except httpx.HTTPError as e:
            logger.error(
                f"分片通知发送失败(HTTP错误): segment_id={segment_id}, "
                f"error={e}, url={self.notification_url}",
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                f"分片通知发送失败: segment_id={segment_id}, error={e}",
                exc_info=True
            )
            return False


# 全局单例
segment_notifier = SegmentNotifier()
