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
from app.models.live_room import LiveRoom, RecordStatus
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
            notification_url: 通知目标URL,默认从环境变量动态拼接
            timeout: HTTP请求超时时间(秒)
        """
        # 优先使用传入的URL,否则使用配置的动态拼接URL
        self.notification_url = notification_url or settings.segment_notification_url
        self.timeout = timeout
        self.enabled = bool(self.notification_url)

        if not self.enabled:
            logger.warning("⚠️ 分片通知服务未启用(segment_notification_base_url未配置)")
        else:
            logger.info(f"✅ 分片通知服务已启用: {self.notification_url}")

    def _get_http_error_message(self, status_code: int, response_text: str) -> str:
        """
        根据HTTP状态码返回详细的错误说明

        Args:
            status_code: HTTP状态码
            response_text: 响应内容

        Returns:
            详细的错误说明和排查建议
        """
        error_messages = {
            400: "❌ 400 Bad Request - 请求数据格式错误\n  排查: 检查接收端数据验证逻辑",
            401: "❌ 401 Unauthorized - 未授权\n  排查: 检查是否需要认证token",
            403: "❌ 403 Forbidden - 禁止访问\n  排查: 检查接收端访问权限配置",
            404: "❌ 404 Not Found - 接口不存在\n  排查: 检查URL路径是否正确: /shard/plan",
            405: "❌ 405 Method Not Allowed - 请求方法不允许\n  排查: 确认接口支持POST方法",
            429: "❌ 429 Too Many Requests - 请求过于频繁\n  排查: 接收端可能有限流,稍后重试",
            500: "❌ 500 Internal Server Error - 接收端服务器内部错误\n  排查: 查看接收端错误日志,检查业务逻辑bug",
            502: "❌ 502 Bad Gateway - 网关错误\n  排查建议:\n"
                 "    1. 检查接收端服务是否正常运行: systemctl status your-service\n"
                 "    2. 检查反向代理(Nginx/Apache)配置和日志\n"
                 "    3. 检查接收端服务端口是否正确监听\n"
                 "    4. 测试接收端可用性: curl -X POST http://your-api/shard/plan",
            503: "❌ 503 Service Unavailable - 服务不可用\n  排查: 接收端服务可能在维护或重启中",
            504: "❌ 504 Gateway Timeout - 网关超时\n  排查: 接收端处理时间过长(>30秒),优化处理逻辑或增加超时配置"
        }

        return error_messages.get(
            status_code,
            f"❌ HTTP {status_code} - 未知错误\n  排查: 查看接收端日志了解详情"
        )

    def format_datetime_to_iso(self, dt: datetime) -> str:
        """
        将datetime对象格式化为ISO格式字符串

        Args:
            dt: datetime对象

        Returns:
            ISO格式的时间字符串 (YYYY-MM-DDTHH:MM:SS)
        """
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    def build_full_url(self, oss_key: Optional[str]) -> str:
        """
        将OSS相对路径key拼接为完整URL

        Args:
            oss_key: OSS对象键(相对路径)
                    例如: live-recorder/prod/抖音/296728101980/20251021/48/video.ts

        Returns:
            完整的访问URL
            例如: https://ts-bigdata-chart-prd.oss-cn-beijing.aliyuncs.com/live-recorder/prod/抖音/296728101980/20251021/48/video.ts
            如果oss_key为空,返回空字符串
        """
        if not oss_key:
            return ""
        
        # 拼接完整URL: https://{bucket}.{endpoint}/{key}
        return f"https://{settings.oss_bucket_name}.{settings.oss_endpoint}/{oss_key}"

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

            # 检查录制开始时间
            if not room.current_session_started_at:
                logger.error(f"录制开始时间不存在: room_id={segment.room_id}")
                return None

            # 将HH:MM:SS格式的相对时间转换为绝对时间
            def parse_time_str(time_str: str) -> int:
                """解析HH:MM:SS格式，返回总秒数"""
                try:
                    if not time_str or not isinstance(time_str, str):
                        logger.warning(f"时间格式无效: {time_str}")
                        return 0
                    parts = time_str.split(':')
                    if len(parts) != 3:
                        logger.warning(f"时间格式错误，应为HH:MM:SS: {time_str}")
                        return 0
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                except Exception as e:
                    logger.error(f"解析时间字符串失败: {time_str}, error={e}")
                    return 0
            
            try:
                start_seconds = parse_time_str(segment.segment_started_at)
                absolute_start_time = room.current_session_started_at + timedelta(seconds=start_seconds)

                if segment.segment_ended_at:
                    end_seconds = parse_time_str(segment.segment_ended_at)
                    absolute_end_time = room.current_session_started_at + timedelta(seconds=end_seconds)
                else:
                    logger.error(
                        f"分片结束时间不存在: segment_id={segment.id}, "
                        f"started_at={segment.segment_started_at}, "
                        f"ended_at={segment.segment_ended_at}, "
                        f"duration={segment.duration}"
                    )
                    return None
            except Exception as e:
                logger.error(
                    f"时间转换失败: segment_id={segment.id}, "
                    f"started_at={segment.segment_started_at}, "
                    f"ended_at={segment.segment_ended_at}, "
                    f"error={e}",
                    exc_info=True
                )
                return None

            # 判断是否为最后一个片段
            # 查询该session的最大segment_index
            from sqlalchemy import func
            max_segment_index = db.query(func.max(VideoSegment.segment_index)).filter(
                VideoSegment.session_id == segment.session_id
            ).scalar()

            # 判断当前片段是否为最大索引 且 该session的录制已停止
            is_last_segment = (
                max_segment_index is not None and
                segment.segment_index == max_segment_index and
                room.record_status != RecordStatus.RECORDING
            )

            # 构建请求数据，直接使用OSS相对路径key（不拼接完整URL）
            # 注意: 发送给第三方的是OSS key，例如 live-recorder/test/抖音/296728101980/20251022/0/xxx.mp3
            notification = SegmentNotificationRequest(
                live_info=LiveInfo(
                    live_id=segment.session_id,  
                    live_url=room.url,
                    live_name=room.streamer_name
                ),
                sub_video_info=SubVideoInfo(
                    video_url=segment.oss_video_url,  
                    audio_url=segment.oss_audio_url,  
                    duration=segment.duration or 0,
                    absolute_start_time=self.format_datetime_to_iso(absolute_start_time),
                    absolute_end_time=self.format_datetime_to_iso(absolute_end_time),
                    serial_num=segment.segment_index or 0,
                    last_segment_flag=is_last_segment
                )
            )

            return notification

        except Exception as e:
            logger.error(f"构建通知数据失败: segment_id={segment.id}, error={str(e)}", exc_info=True)
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

            # 构建业务日志上下文
            log_ctx = f"[{segment.platform} | {segment.platform_room_id} | {segment.session_id[:8]} | seg{segment.segment_index}]"

            # 检查是否已上传完成
            if not segment.oss_video_url or not segment.oss_audio_url:
                logger.warning(
                    f"{log_ctx} 分片尚未上传完成,跳过通知: "
                    f"video={bool(segment.oss_video_url)}, audio={bool(segment.oss_audio_url)}"
                )
                return False

            # 构建通知数据
            notification_data = self.build_notification_data(db, segment)
            if not notification_data:
                return False

            import json
            request_data = notification_data.model_dump()
            logger.info(f"通知处理分片: {request_data}")

            import aiohttp
            
            try:
                # 创建 ClientSession 时禁用代理环境变量读取
                connector = aiohttp.TCPConnector()
                async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
                    async with session.post(
                        self.notification_url,
                        json=request_data,
                        headers={'User-Agent': 'DouyinLiveRecorder/1.0'},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        status = response.status
                        response_text = await response.text()
                        
                        if 200 <= status < 300:
                            logger.info(
                                f"{log_ctx} ✅ 分片通知发送成功: "
                                f"status={status}, response={response_text[:200]}"
                            )
                            return True
                        else:
                            logger.error(
                                f"{log_ctx} ❌ 分片通知发送失败: "
                                f"status={status}, response={response_text[:200]}"
                            )
                            return False
                            
            except Exception as e:
                logger.error(f"{log_ctx} 通知发送异常: {e}", exc_info=True)
                return False

        except Exception as e:
            logger.error(
                f"{log_ctx if 'log_ctx' in locals() else ''} ❌ 分片通知发送失败: "
                f"segment_id={segment_id}, error={e}",
                exc_info=True
            )
            return False

    def send_notification_sync(
        self,
        db: Session,
        segment_id: int
    ) -> bool:
        """
        同步发送通知并验证响应(用于线程中调用)

        改进点:
        1. 检查HTTP状态码(200-299为成功)
        2. 验证响应body格式
        3. 记录详细的成功/失败日志
        4. 返回实际发送结果

        Args:
            db: 数据库会话
            segment_id: 视频分片ID

        Returns:
            True: 通知发送成功且对方确认接收
            False: 发送失败或对方拒绝
        """
        if not self.enabled:
            return False

        try:
            # 获取分片信息
            segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not segment:
                logger.error(f"视频分片不存在: segment_id={segment_id}")
                return False

            # 构建业务日志上下文
            log_ctx = f"[{segment.platform} | {segment.platform_room_id} | {segment.session_id[:8]} | seg{segment.segment_index}]"

            # 检查是否已上传完成
            if not segment.oss_video_url or not segment.oss_audio_url:
                logger.warning(
                    f"{log_ctx} 分片尚未上传完成,跳过通知: "
                    f"video={bool(segment.oss_video_url)}, audio={bool(segment.oss_audio_url)}"
                )
                return False

            # 构建通知数据
            notification_data = self.build_notification_data(db, segment)
            if not notification_data:
                logger.error(f"{log_ctx} 构建通知数据失败")
                return False

            import json
            import requests
            request_data = notification_data.model_dump()

            # 🔍 始终打印请求入参(使用print确保输出)
            print(f"\n{'='*80}")
            print(f"{log_ctx} 📤 准备发送分片通知")
            print(f"{'='*80}")
            print(f"URL: {self.notification_url}")
            print(f"请求入参:")
            print(json.dumps(request_data, ensure_ascii=False, indent=2))
            print(f"{'='*80}\n")

            # 同时记录到日志
            logger.info(
                f"{log_ctx} 📤 准备发送分片通知:\n"
                f"  URL: {self.notification_url}\n"
                f"  入参: {json.dumps(request_data, ensure_ascii=False, indent=2)}"
            )

            # ✅ 使用 requests 同步发送并验证响应
            # 禁用代理,避免本地代理导致的 502 错误
            try:
                # 临时保存环境变量中的代理设置
                import os
                old_http_proxy = os.environ.get('HTTP_PROXY')
                old_https_proxy = os.environ.get('HTTPS_PROXY')
                old_http_proxy_lower = os.environ.get('http_proxy')
                old_https_proxy_lower = os.environ.get('https_proxy')
                
                # 临时清除环境变量中的代理设置
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)
                os.environ.pop('http_proxy', None)
                os.environ.pop('https_proxy', None)
                
                try:
                    response = requests.post(
                        self.notification_url,
                        json=request_data,
                        headers={'User-Agent': 'DouyinLiveRecorder/1.0'},
                        timeout=self.timeout,
                        proxies={'http': None, 'https': None}  # 禁用代理
                    )
                finally:
                    # 恢复原始的代理环境变量
                    if old_http_proxy is not None:
                        os.environ['HTTP_PROXY'] = old_http_proxy
                    if old_https_proxy is not None:
                        os.environ['HTTPS_PROXY'] = old_https_proxy
                    if old_http_proxy_lower is not None:
                        os.environ['http_proxy'] = old_http_proxy_lower
                    if old_https_proxy_lower is not None:
                        os.environ['https_proxy'] = old_https_proxy_lower

                status_code = response.status_code
                response_text = response.text[:1000]  # 增加到1000字符

                # ✅ 检查HTTP状态码
                if 200 <= status_code < 300:
                    # 尝试解析响应body
                    try:
                        response_body = response.json()
                        logger.info(
                            f"{log_ctx} ✅ 分片通知发送成功:\n"
                            f"  HTTP状态: {status_code}\n"
                            f"  响应内容: {json.dumps(response_body, ensure_ascii=False, indent=2)}"
                        )
                    except Exception:
                        # 无法解析JSON,使用原始文本
                        logger.info(
                            f"{log_ctx} ✅ 分片通知发送成功:\n"
                            f"  HTTP状态: {status_code}\n"
                            f"  响应内容: {response_text}"
                        )
                    return True

                else:
                    # ❌ HTTP状态码异常
                    error_msg = self._get_http_error_message(status_code, response_text)

                    logger.error(
                        f"{log_ctx} ❌ 分片通知发送失败:\n"
                        f"  HTTP状态: {status_code}\n"
                        f"  响应内容: {response_text}\n"
                        f"  {error_msg}"
                    )

                    # 同时打印到控制台
                    print(f"\n{'='*80}")
                    print(f"{log_ctx} ❌ 分片通知发送失败")
                    print(f"{'='*80}")
                    print(f"HTTP状态: {status_code}")
                    print(f"响应内容: {response_text}")
                    print(f"{error_msg}")
                    print(f"{'='*80}\n")

                    return False

            except requests.exceptions.Timeout:
                logger.error(
                    f"{log_ctx} ❌ 分片通知超时:\n"
                    f"  超时时间: {self.timeout}秒\n"
                    f"  请检查网络连接或增加timeout配置"
                )
                return False

            except requests.exceptions.ConnectionError as conn_err:
                logger.error(
                    f"{log_ctx} ❌ 分片通知连接失败:\n"
                    f"  错误信息: {str(conn_err)}\n"
                    f"  请检查URL是否正确: {self.notification_url}"
                )
                return False

            except Exception as req_err:
                logger.error(
                    f"{log_ctx} ❌ 分片通知请求异常:\n"
                    f"  错误类型: {type(req_err).__name__}\n"
                    f"  错误信息: {str(req_err)}",
                    exc_info=True
                )
                return False

        except Exception as e:
            logger.error(
                f"{log_ctx if 'log_ctx' in locals() else ''} ❌ 分片通知处理失败: "
                f"segment_id={segment_id}, error={e}",
                exc_info=True
            )
            return False


# 全局单例
segment_notifier = SegmentNotifier()
