"""录制管理器 - 简化版(无统计字段)"""
import asyncio
import threading
import uuid
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import Session

from app.logger import logger

from app.database import SessionLocal
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.models.video_segment import VideoSegment, SegmentStatus
from app.config import settings



def _make_log_context(platform: str = None, platform_room_id: str = None, 
                      session_id: str = None, segment_id: int = None) -> str:
    """创建统一的日志上下文标识"""
    parts = []
    if platform:
        parts.append(platform)
    if platform_room_id:
        parts.append(platform_room_id)
    if session_id:
        # 只取session_id的前8位
        parts.append(session_id[:8] if len(session_id) > 8 else session_id)
    if segment_id:
        parts.append(f"seg{segment_id}")
    
    return f"[{' | '.join(parts)}]" if parts else ""


class RecordingManager:
    """录制管理器 - 负责持续监听和录制管理"""

    def __init__(self):
        self.monitor_threads: Dict[int, threading.Thread] = {}
        self.recording_threads: Dict[int, threading.Thread] = {}
        self.stop_flags: Dict[int, threading.Event] = {}
        self.lock = threading.Lock()

    def start_monitor(self, room_id: int):
        """启动直播间监听"""
        with self.lock:
            if room_id in self.monitor_threads:
                logger.warning(f"监听线程已存在: room_id={room_id}")
                return

            stop_event = threading.Event()
            self.stop_flags[room_id] = stop_event

            thread = threading.Thread(
                target=self._monitor_worker,
                args=(room_id, stop_event),
                daemon=True,
                name=f"Monitor-Room-{room_id}"
            )
            thread.start()
            self.monitor_threads[room_id] = thread
            logger.info(f"启动监听线程: room_id={room_id}")

    def stop_monitor(self, room_id: int):
        """停止直播间监听"""
        with self.lock:
            if room_id in self.stop_flags:
                logger.info(f"发送停止信号: room_id={room_id}")
                self.stop_flags[room_id].set()

                if room_id in self.monitor_threads:
                    self.monitor_threads[room_id].join(timeout=5)
                    del self.monitor_threads[room_id]

                del self.stop_flags[room_id]

                if room_id in self.recording_threads:
                    del self.recording_threads[room_id]

    def _monitor_worker(self, room_id: int, stop_event: threading.Event):
        """监听工作线程"""
        db = SessionLocal()

        try:
            # 先获取房间信息用于日志
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                logger.warning(f"直播间不存在,退出监听: db_id={room_id}")
                return

            log_ctx = _make_log_context(room.platform, room.platform_room_id)
            logger.info(f"{log_ctx} 监听线程启动")

            while not stop_event.is_set():
                try:
                    room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                    if not room:
                        logger.warning(f"{log_ctx} 直播间不存在,退出监听")
                        break

                    if not room.is_enabled:
                        logger.info(f"{log_ctx} 直播间已禁用,退出监听")
                        break

                    # 检查直播状态
                    is_live = self._check_live_status(room)
                    old_status = room.live_status
                    room.live_status = LiveStatus.LIVE if is_live else LiveStatus.OFFLINE

                    if is_live and old_status != LiveStatus.LIVE:
                        logger.info(f"{log_ctx} 检测到开播, url={room.url}")
                        self._start_recording(db, room)
                    elif not is_live and old_status == LiveStatus.LIVE:
                        logger.info(f"{log_ctx} 检测到下播")
                        self._stop_recording(db, room)

                    db.commit()
                except Exception as e:
                    logger.error(f"{log_ctx} 监听异常: {e}")
                    db.rollback()

                stop_event.wait(settings.check_interval)
        finally:
            db.close()
            if room:
                log_ctx = _make_log_context(room.platform, room.platform_room_id)
                logger.info(f"{log_ctx} 监听线程退出")
            else:
                logger.info(f"监听线程退出: db_id={room_id}")

    def _check_live_status(self, room: LiveRoom) -> bool:
        """检查直播状态"""
        try:
            from app.services.live_recorder import LiveRecorder
            recorder = LiveRecorder(proxy_addr=None, cookies={})
            is_live = asyncio.run(recorder.check_live_status(room.url))
            return is_live
        except Exception as e:
            logger.error(f"检查直播状态失败: room_id={room.id}, error={e}")
            return False

    def _start_recording(self, db: Session, room: LiveRoom):
        """启动录制任务 - 使用已有的 session_id 或生成新的"""
        # 如果当前已经有 session_id(由create接口传入),则使用它
        # 否则生成新的 session_id(自动开播录制场景)
        if room.current_session_id:
            session_id = room.current_session_id
        else:
            session_id = str(uuid.uuid4())

        session_started_at = datetime.now()

        # 更新数据库,设置新的会话信息
        room.current_session_id = session_id
        room.current_session_started_at = session_started_at
        room.record_status = RecordStatus.RECORDING
        db.commit()

        log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)
        logger.info(f"{log_ctx} 创建新录制会话, room_id={room.id}")

        # 启动录制线程
        thread = threading.Thread(
            target=self._recording_worker,
            args=(session_id, room.id),
            daemon=True,
            name=f"Record-Session-{session_id[:8]}"
        )
        thread.start()
        self.recording_threads[room.id] = thread

    def _stop_recording(self, db: Session, room: LiveRoom):
        """停止录制任务 - 清空 session 信息,为下次录制准备"""
        from sqlalchemy import func

        # 记录被终止的 session_id
        stopped_session_id = room.current_session_id

        if stopped_session_id:
            log_ctx = _make_log_context(room.platform, room.platform_room_id, stopped_session_id)
            logger.info(f"{log_ctx} 停止录制,session 结束")

            # 查询该会话的总分片数
            segment_count = db.query(func.count(VideoSegment.id)).filter(
                VideoSegment.session_id == stopped_session_id
            ).scalar() or 0

            # 记录会话结束时间和总分片数
            room.current_session_ended_at = datetime.now()
            room.total_segment = segment_count

            logger.info(f"{log_ctx} 会话统计: 总分片数={segment_count}")

        # 清空当前会话信息,下次激活录制时会生成新的 session_id
        room.current_session_id = None
        room.current_session_started_at = None
        room.record_status = RecordStatus.IDLE
        db.commit()
        
        if stopped_session_id:
            log_ctx = _make_log_context(room.platform, room.platform_room_id, stopped_session_id)
            logger.info(f"{log_ctx} session 已结束,等待新的激活")
        else:
            log_ctx = _make_log_context(room.platform, room.platform_room_id)
            logger.info(f"{log_ctx} 停止录制完成")

    def _recording_worker(self, session_id: str, room_id: int):
        """录制工作线程"""
        db = SessionLocal()
        
        # 获取room信息用于日志上下文
        room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
        if not room:
            logger.error(f"房间不存在: room_id={room_id}")
            return
        
        log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)
        logger.info(f"{log_ctx} 录制线程启动")

        try:
            from app.services.live_recorder import LiveRecorder
            import subprocess
            import os

            # 获取直播流信息
            recorder = LiveRecorder()
            stream_info = asyncio.run(recorder.get_live_stream_info(room.url, room.quality))

            if not stream_info['is_live'] or not stream_info['stream_url']:
                logger.warning(f"{log_ctx} 直播未开播")
                room.record_status = RecordStatus.ERROR
                db.commit()
                return

            # 创建保存目录
            project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            save_dir = os.path.join(
                project_root,
                settings.video_save_path.lstrip('./'),
                room.streamer_name or f"room_{room_id}"
            )
            os.makedirs(save_dir, exist_ok=True)

            # 使用FFmpeg segment muxer进行自动分段
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_pattern = f"{timestamp}_seg%03d.{settings.video_record_format.lower()}"
            file_pattern = os.path.join(save_dir, filename_pattern)

            ffmpeg_cmd = [
                'ffmpeg',
                '-i', stream_info['stream_url'],
                '-c', 'copy',
                '-f', 'segment',
                '-segment_time', str(settings.segment_duration),
                '-segment_format', settings.ffmpeg_format,
                '-reset_timestamps', '1',
                file_pattern
            ]

            logger.info(f"{log_ctx} 启动FFmpeg录制, 分段时长={settings.segment_duration}秒")

            ffmpeg_process = None
            processed_files = set()  # 记录已处理的文件
            video_format = settings.video_record_format.lower()  # 视频格式后缀
            manually_stopped = False  # 标记是否为手动停止

            try:
                ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                # 持续监控:FFmpeg进程 + 文件系统
                while ffmpeg_process.poll() is None:
                    db.refresh(room)

                    # 检查:直播结束 或 用户手动停止
                    if room.live_status != LiveStatus.LIVE or room.record_status == RecordStatus.FINISHED:
                        manually_stopped = True  # 标记为手动停止
                        ffmpeg_process.terminate()
                        break

                    # 实时扫描新生成的分段文件
                    try:
                        # 只扫描视频文件,忽略音频文件
                        all_files = os.listdir(save_dir)
                        video_files = [f for f in all_files
                                      if f.startswith(timestamp) and f.endswith(f'.{video_format}')]
                        current_files = set(video_files)
                        new_files = current_files - processed_files

                        for segment_file in sorted(new_files):
                            file_path = os.path.join(save_dir, segment_file)

                            # 检查文件是否存在且完整(FFmpeg正在写入的文件大小会持续增长)
                            if not os.path.exists(file_path):
                                continue

                            import time
                            time.sleep(1)  # 等待1秒

                            # 二次检查文件是否还存在(可能已被上传线程删除)
                            if not os.path.exists(file_path):
                                processed_files.add(segment_file)
                                continue

                            size1 = os.path.getsize(file_path)
                            time.sleep(1)  # 再等待1秒

                            # 三次检查文件是否还存在
                            if not os.path.exists(file_path):
                                processed_files.add(segment_file)
                                continue

                            size2 = os.path.getsize(file_path)

                            # 如果文件大小不再增长,说明分段已完成
                            if size1 == size2 and size1 > 0:
                                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                                # 提取分段索引
                                import re
                                match = re.search(r'seg(\d+)', segment_file)
                                segment_index = int(match.group(1)) if match else len(processed_files)

                                # 立即处理这个分段
                                self.on_segment_created(
                                    db=db,
                                    session_id=session_id,
                                    room_id=room_id,
                                    file_path=file_path,
                                    segment_index=segment_index,
                                    segment_start_time=file_mtime,
                                    segment_end_time=file_mtime,
                                    duration=settings.segment_duration
                                )

                                processed_files.add(segment_file)
                    except Exception as e:
                        logger.error(f"{log_ctx} 扫描分段文件失败: {e}")

                    import time
                    time.sleep(5)  # 每5秒检查一次

                # FFmpeg进程结束后,处理剩余的文件
                stdout, stderr = ffmpeg_process.communicate(timeout=5)
                return_code = ffmpeg_process.returncode

                # 判断是否为正常终止
                # 0: 正常完成
                # -15: Linux/Mac 上的 SIGTERM
                # 255: Windows 或某些情况下的 SIGTERM
                # 如果是手动停止,255 也视为正常
                is_normal_termination = (
                    return_code == 0 or 
                    return_code == -15 or 
                    (manually_stopped and return_code == 255)
                )
                
                if is_normal_termination:
                    logger.info(f"{log_ctx} FFmpeg录制完成: return_code={return_code}, manually_stopped={manually_stopped}")
                else:
                    logger.error(f"{log_ctx} FFmpeg异常终止: return_code={return_code}")
                    logger.error(f"{log_ctx} FFmpeg stderr: {stderr[-1000:]}")

                # 最后扫描一次,处理所有剩余的视频文件
                all_files = os.listdir(save_dir)
                segment_files = sorted([f for f in all_files
                                       if f.startswith(timestamp) and f.endswith(f'.{video_format}')])
                remaining_files = set(segment_files) - processed_files

                if remaining_files:
                    logger.info(f"{log_ctx} 处理剩余 {len(remaining_files)} 个分段")

                    for segment_file in sorted(remaining_files):
                        file_path = os.path.join(save_dir, segment_file)
                        if os.path.exists(file_path):
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                            # 提取分段索引
                            import re
                            match = re.search(r'seg(\d+)', segment_file)
                            segment_index = int(match.group(1)) if match else 0

                            self.on_segment_created(
                                db=db,
                                session_id=session_id,
                                room_id=room_id,
                                file_path=file_path,
                                segment_index=segment_index,
                                segment_start_time=file_mtime,
                                segment_end_time=file_mtime,
                                duration=settings.segment_duration
                            )

            finally:
                if ffmpeg_process and ffmpeg_process.poll() is None:
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait(timeout=5)

        except Exception as e:
            logger.error(f"{log_ctx} 录制异常: {e}")
            import traceback
            logger.error(f"{log_ctx} 异常堆栈: {traceback.format_exc()}")
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if room:
                room.record_status = RecordStatus.ERROR
                db.commit()
        finally:
            db.close()
            logger.info(f"{log_ctx} 录制线程退出")

    def on_segment_created(self, db: Session, session_id: str, room_id: int,
                          file_path: str, segment_index: int,
                          segment_start_time: datetime, segment_end_time: datetime,
                          duration: int):
        """切片创建回调"""
        import os

        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                return

            log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)

            # 创建切片记录(包含平台冗余字段)
            video_segment = VideoSegment(
                room_id=room_id,
                platform=room.platform,
                platform_room_id=room.platform_room_id,
                session_id=session_id,
                segment_index=segment_index,
                segment_started_at=segment_start_time,
                segment_ended_at=segment_end_time,
                duration=duration,
                status=SegmentStatus.COMPLETED,
                completed_at=datetime.now()
            )
            db.add(video_segment)
            db.commit()
            db.refresh(video_segment)

            seg_ctx = _make_log_context(room.platform, room.platform_room_id, session_id, video_segment.id)

            # 异步上传视频和音频
            threading.Thread(
                target=self._upload_video_and_audio,
                args=(video_segment.id, file_path, room.platform, room.platform_room_id, session_id),
                daemon=True
            ).start()
        except Exception as e:
            logger.error(f"{log_ctx} 切片记录创建失败: {e}")
            import traceback
            logger.error(f"{log_ctx} 异常堆栈: {traceback.format_exc()}")

    def _upload_video_and_audio(self, segment_id: int, video_path: str, 
                                platform: str, platform_room_id: str, session_id: str):
        """录制完成后处理:抽取音频 → 上传 → 回写数据库 → 删除本地文件"""
        from app.services.oss_uploader import oss_uploader
        from app.services.audio_extractor import audio_extractor
        import os
        import concurrent.futures

        db = SessionLocal()
        audio_path = None
        log_ctx = _make_log_context(platform, platform_room_id, session_id, segment_id)

        try:
            video_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not video_segment:
                logger.warning(f"{log_ctx} 视频分片不存在")
                return

            video_segment.status = SegmentStatus.UPLOADING
            db.commit()

            # 1. 抽取音频
            audio_path = audio_extractor.extract_audio(video_path=video_path, delete_source=False)
            if not audio_path:
                raise Exception("音频抽取失败")

            # 2. 并行上传
            video_url = None
            audio_url = None

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 传入日志上下文到OSS上传
                video_future = executor.submit(oss_uploader.upload_file, video_path, None, None, False, log_ctx)
                audio_future = executor.submit(oss_uploader.upload_file, audio_path, None, None, False, log_ctx)

                video_result = video_future.result()
                video_url = video_result.get('url')

                audio_result = audio_future.result()
                audio_url = audio_result.get('url')

            # 3. 回写数据库
            video_segment.oss_video_url = video_url
            video_segment.oss_audio_url = audio_url
            video_segment.status = SegmentStatus.UPLOADED
            db.commit()

            # 4. 发送分片完成通知
            try:
                from app.services.segment_notifier import segment_notifier
                segment_notifier.send_notification_sync(db, segment_id)
            except Exception as notify_error:
                logger.error(f"{log_ctx} 发送分片通知失败: {notify_error}", exc_info=True)
                # 通知失败不影响主流程

            # 5. 删除本地文件
            if os.path.exists(video_path):
                os.remove(video_path)
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

            logger.info(f"{log_ctx} 分片处理完成")
        except Exception as e:
            logger.error(f"{log_ctx} 分片上传处理失败: {e}", exc_info=True)
            video_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if video_segment:
                video_segment.status = SegmentStatus.FAILED
                video_segment.error_message = f"上传处理失败: {str(e)}"
                db.commit()
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass
        finally:
            db.close()

    def activate_recording(self, room_id: int, session_id: str):
        """手动激活录制 - session_id 由外部 API 提供"""
        db = SessionLocal()
        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                logger.error(f"房间不存在: room_id={room_id}")
                return

            # 检查录制状态
            if room.record_status == RecordStatus.RECORDING:
                old_ctx = _make_log_context(room.platform, room.platform_room_id, room.current_session_id)
                logger.warning(f"{old_ctx} 录制已在进行中,room_id={room_id}")
                return

            # 清除旧的 session 信息(如果存在)
            # 这确保了即使上次没有正确清理,本次也会使用新的外部 session
            old_session_id = room.current_session_id
            if old_session_id:
                old_ctx = _make_log_context(room.platform, room.platform_room_id, old_session_id)
                logger.info(f"{old_ctx} 清除旧会话信息")

            # 使用外部提供的 session_id
            session_started_at = datetime.now()

            room.current_session_id = session_id
            room.current_session_started_at = session_started_at
            room.record_status = RecordStatus.RECORDING
            db.commit()

            log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)
            logger.info(f"{log_ctx} 手动激活录制(外部session), room_id={room_id}")

            # 启动录制线程
            thread = threading.Thread(
                target=self._recording_worker,
                args=(session_id, room_id),
                daemon=True,
                name=f"ManualRecord-{session_id[:8]}"
            )
            thread.start()
            self.recording_threads[room_id] = thread
        except Exception as e:
            logger.error(f"激活录制失败: room_id={room_id}, error={e}", exc_info=True)
            if room:
                room.record_status = RecordStatus.ERROR
                db.commit()
        finally:
            db.close()

    def get_monitor_status(self) -> dict:
        """获取监听状态"""
        with self.lock:
            return {
                "total_monitors": len(self.monitor_threads),
                "total_recordings": len(self.recording_threads),
                "monitor_rooms": list(self.monitor_threads.keys()),
                "recording_rooms": list(self.recording_threads.keys())
            }


# 全局单例
recording_manager = RecordingManager()
