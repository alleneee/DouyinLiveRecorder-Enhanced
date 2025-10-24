"""录制管理器 - 简化版(无统计字段)"""
import asyncio
import threading
import uuid
import os
import time
import re
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import Session
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.logger import logger

from app.database import SessionLocal
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.models.video_segment import VideoSegment, SegmentStatus
from app.config import settings


class SegmentFileHandler(FileSystemEventHandler):
    """分片文件监控处理器 - 使用 watchdog 实时监控文件创建"""

    def __init__(self, recording_manager, session_id: str, room_id: int,
                 platform: str, platform_room_id: str, video_format: str):
        """
        Args:
            recording_manager: RecordingManager 实例
            session_id: 录制会话ID
            room_id: 直播间ID
            platform: 平台名称
            platform_room_id: 平台房间ID
            video_format: 视频格式 (如 'ts')
        """
        super().__init__()
        self.recording_manager = recording_manager
        self.session_id = session_id
        self.room_id = room_id
        self.platform = platform
        self.platform_room_id = platform_room_id
        self.video_format = video_format
        self.processing = set()  # 正在处理的文件路径
        self.processed = set()   # 已处理的文件路径
        self.pending_segment = None  # 待处理的上一个分片（等下一个分片创建时才处理）
        self.lock = threading.Lock()

    def on_created(self, event):
        """文件创建事件回调 - 实时触发"""
        if event.is_directory:
            return

        file_path = event.src_path

        # 跳过.m3u8索引文件（HLS模式会生成）
        if file_path.endswith('.m3u8'):
            return

        # 只处理视频分片文件
        if not file_path.endswith(f'.{self.video_format}'):
            return

        # 检查是否已处理或正在处理
        with self.lock:
            if file_path in self.processed or file_path in self.processing:
                return
            self.processing.add(file_path)

        try:
            log_ctx = f"[{self.platform} | {self.platform_room_id} | {self.session_id[:8]}]"
            logger.info(f"{log_ctx} watchdog检测到新分片: {os.path.basename(file_path)}")

            # 等待文件写入完成
            if self._wait_for_stable(file_path):
                # 提取分片索引
                segment_index = self._extract_index(file_path)

                # 获取文件时间
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                # HLS模式 vs Segment模式处理逻辑
                if settings.segment_method == "hls":
                    # ===== HLS模式：立即处理当前分片 =====
                    # HLS每个分片创建即完整，无需等待下一个分片
                    db = SessionLocal()
                    try:
                        self.recording_manager.on_segment_created(
                            db=db,
                            session_id=self.session_id,
                            room_id=self.room_id,
                            file_path=file_path,
                            segment_index=segment_index,
                            segment_start_time=file_mtime,
                            segment_end_time=file_mtime,
                            duration=settings.segment_duration
                        )

                        # 标记为已处理
                        with self.lock:
                            self.processed.add(file_path)

                        logger.info(f"{log_ctx} HLS分片处理完成: seg{segment_index}")
                    except Exception as e:
                        logger.error(f"{log_ctx} HLS分片处理失败: {e}")
                    finally:
                        db.close()
                else:
                    # ===== Segment模式：延迟处理（等待下一个分片确认上一个完整）=====
                    previous_segment = None
                    with self.lock:
                        previous_segment = self.pending_segment
                        # 将当前分片设为待处理
                        self.pending_segment = {
                            'file_path': file_path,
                            'segment_index': segment_index,
                            'file_mtime': file_mtime
                        }

                    # 如果存在上一个分片，则处理它
                    if previous_segment:
                        db = SessionLocal()
                        try:
                            prev_file_path = previous_segment['file_path']
                            prev_index = previous_segment['segment_index']
                            prev_mtime = previous_segment['file_mtime']

                            self.recording_manager.on_segment_created(
                                db=db,
                                session_id=self.session_id,
                                room_id=self.room_id,
                                file_path=prev_file_path,
                                segment_index=prev_index,
                                segment_start_time=prev_mtime,
                                segment_end_time=prev_mtime,
                                duration=settings.segment_duration
                            )

                            # 标记为已处理
                            with self.lock:
                                self.processed.add(prev_file_path)

                            logger.info(f"{log_ctx} Segment分片处理完成: seg{prev_index}")
                        except Exception as e:
                            logger.error(f"{log_ctx} Segment分片处理失败: {e}")
                        finally:
                            db.close()
                    else:
                        logger.info(f"{log_ctx} 第一个分片seg{segment_index}已创建，等待下一个分片创建后再处理")
            else:
                logger.warning(f"{log_ctx} 文件未稳定,跳过: {os.path.basename(file_path)}")
        finally:
            # 从处理中移除
            with self.lock:
                self.processing.discard(file_path)

    def _wait_for_stable(self, file_path: str, timeout: int = 5) -> bool:
        """等待文件大小稳定

        Args:
            file_path: 文件路径
            timeout: 超时时间(秒)

        Returns:
            bool: 文件是否稳定
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not os.path.exists(file_path):
                return False

            try:
                size1 = os.path.getsize(file_path)
                time.sleep(0.5)  # 500ms 检查间隔

                if not os.path.exists(file_path):
                    return False

                size2 = os.path.getsize(file_path)

                # 文件大小不再变化且非空
                if size1 == size2 and size1 > 0:
                    return True
            except OSError:
                return False

        return False

    def _extract_index(self, file_path: str) -> int:
        """从文件名提取分片索引

        Args:
            file_path: 文件路径

        Returns:
            int: 分片索引
        """
        match = re.search(r'seg(\d+)', os.path.basename(file_path))
        return int(match.group(1)) if match else 0

    def process_final_segment(self):
        """处理最后一个待处理的分片（录制结束时调用）"""
        log_ctx = f"[{self.platform} | {self.platform_room_id} | {self.session_id[:8]}]"
        
        with self.lock:
            final_segment = self.pending_segment
            self.pending_segment = None  # 清空待处理分片
        
        if final_segment:
            logger.info(f"{log_ctx} 录制结束，处理最后一个分片seg{final_segment['segment_index']}")
            db = SessionLocal()
            try:
                self.recording_manager.on_segment_created(
                    db=db,
                    session_id=self.session_id,
                    room_id=self.room_id,
                    file_path=final_segment['file_path'],
                    segment_index=final_segment['segment_index'],
                    segment_start_time=final_segment['file_mtime'],
                    segment_end_time=final_segment['file_mtime'],
                    duration=settings.segment_duration
                )
                
                with self.lock:
                    self.processed.add(final_segment['file_path'])
                
                logger.info(f"{log_ctx} 最后分片处理完成: seg{final_segment['segment_index']}")
            except Exception as e:
                logger.error(f"{log_ctx} 最后分片处理失败: {e}", exc_info=True)
            finally:
                db.close()
        else:
            logger.info(f"{log_ctx} 无待处理的最后分片")



def retry_on_failure(max_attempts: int = None, delay: int = None, backoff: float = None):
    """重试装饰器 - 用于网络异常自动恢复
    
    Args:
        max_attempts: 最大重试次数（默认使用配置）
        delay: 初始重试延迟秒数（默认使用配置）
        backoff: 延迟倍增因子（默认使用配置）
    
    Returns:
        装饰后的函数，失败时会自动重试
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = max_attempts or settings.max_retry_attempts
            current_delay = delay or settings.retry_delay_seconds
            multiplier = backoff or settings.retry_backoff_multiplier
            
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == attempts:
                        logger.error(f"重试失败 {func.__name__} - 已达最大尝试次数 {attempts}: {e}")
                        raise
                    
                    logger.warning(f"重试 {func.__name__} - 第 {attempt}/{attempts} 次失败: {e}")
                    logger.info(f"等待 {current_delay} 秒后重试...")
                    time.sleep(current_delay)
                    current_delay *= multiplier  # 指数退避
            
        return wrapper
    return decorator

def _make_log_context(platform: str = None, platform_room_id: str = None,
                      session_id: str = None, segment_index: int = None) -> str:
    """创建统一的日志上下文标识

    Args:
        platform: 平台名称 (如 "抖音")
        platform_room_id: 平台直播间ID
        session_id: 录制会话ID (只取前8位)
        segment_index: 分片序号 (注意是segment_index,不是segment_id)

    Returns:
        格式化的日志上下文,如 "[抖音 | 296728101980 | c840ef38 | seg48]"
    """
    parts = []
    if platform:
        parts.append(platform)
    if platform_room_id:
        parts.append(platform_room_id)
    if session_id:
        # 只取session_id的前8位
        parts.append(session_id[:8] if len(session_id) > 8 else session_id)
    if segment_index is not None:  # 使用 is not None 以支持 segment_index=0
        parts.append(f"seg{segment_index}")

    return f"[{' | '.join(parts)}]" if parts else ""


class RecordingManager:
    """录制管理器 - 负责持续监听和录制管理"""

    def __init__(self):
        # 线程和事件字典（保留用于兼容性和追踪）
        self.monitor_threads: Dict[int, threading.Thread] = {}
        self.recording_threads: Dict[int, threading.Thread] = {}
        self.stop_flags: Dict[int, threading.Event] = {}  # 监听线程停止标志
        self.recording_stop_flags: Dict[int, threading.Event] = {}  # 录制线程停止标志
        
        # ✅ 线程池化: 使用 ThreadPoolExecutor 替代独立线程
        self.monitor_pool = ThreadPoolExecutor(
            max_workers=settings.monitor_thread_pool_size,
            thread_name_prefix="Monitor-Pool"
        )
        self.recording_pool = ThreadPoolExecutor(
            max_workers=settings.recording_thread_pool_size,
            thread_name_prefix="Recording-Pool"
        )
        
        # Future 追踪 (用于管理线程池任务)
        self.monitor_futures: Dict[int, Future] = {}
        self.recording_futures: Dict[int, Future] = {}
        
        self.lock = threading.Lock()
        
        # ✅ 并发控制: 限制同时录制的数量,防止资源耗尽
        self.recording_semaphore = threading.Semaphore(settings.max_concurrent_recordings)

        # ✅ Watchdog Observer 字典: 跟踪每个目录的监控器,避免重复监控
        self.directory_observers: Dict[str, Observer] = {}  # key=save_dir, value=Observer
        self.segment_handlers: Dict[str, 'SegmentFileHandler'] = {}  # key=session_id, value=Handler
        self.observer_lock = threading.Lock()
        
        # ✅ 启动全局OSS上传队列
        if settings.oss_enabled:
            from app.services.upload_queue_manager import upload_queue_manager
            upload_queue_manager.start()
            logger.info(f"✅ OSS上传队列已启动: workers={settings.oss_upload_workers}, queue_size={settings.oss_upload_queue_size}")

        logger.info(f"RecordingManager initialized:")
        logger.info(f"  - max_concurrent_recordings={settings.max_concurrent_recordings}")
        logger.info(f"  - monitor_thread_pool_size={settings.monitor_thread_pool_size}")
        logger.info(f"  - recording_thread_pool_size={settings.recording_thread_pool_size}")
        logger.info(f"  - max_retry_attempts={settings.max_retry_attempts}")

    def recover_interrupted_recordings(self):
        """
        应用重启后,恢复中断的录制任务

        检查数据库中所有 record_status=RECORDING 的房间,
        保留原有的 session_id 并重新启动录制任务
        """
        from app.database import SessionLocal
        from app.models.live_room import LiveRoom, RecordStatus

        db = SessionLocal()
        try:
            # 查询所有正在录制的房间
            recording_rooms = db.query(LiveRoom).filter(
                LiveRoom.record_status == RecordStatus.RECORDING
            ).all()

            if not recording_rooms:
                logger.info("📋 没有需要恢复的录制任务")
                return

            logger.info(f"📋 发现 {len(recording_rooms)} 个中断的录制任务,开始恢复...")

            for room in recording_rooms:
                try:
                    log_ctx = _make_log_context(
                        room.platform,
                        room.platform_room_id,
                        room.current_session_id
                    )

                    # 验证 session 信息完整性
                    if not room.current_session_id:
                        logger.warning(f"{log_ctx} session_id 缺失,跳过恢复")
                        room.record_status = RecordStatus.IDLE
                        db.commit()
                        continue

                    if not room.current_session_started_at:
                        logger.warning(f"{log_ctx} session_started_at 缺失,跳过恢复")
                        room.record_status = RecordStatus.IDLE
                        db.commit()
                        continue

                    # 检查直播状态
                    logger.info(f"{log_ctx} 检查直播状态...")
                    is_live = self._check_live_status(room)

                    if not is_live:
                        # 直播已结束,清理 session
                        logger.info(f"{log_ctx} 直播已结束,清理会话")
                        self._stop_recording(db, room)
                        continue

                    # 直播仍在进行,恢复录制 (保留原有 session_id)
                    logger.info(f"{log_ctx} 🔄 恢复录制任务...")
                    logger.info(f"{log_ctx}   Session ID: {room.current_session_id}")
                    logger.info(f"{log_ctx}   开始时间: {room.current_session_started_at}")

                    # 重新启动录制任务 (会使用现有的 session_id)
                    self._start_recording(db, room)

                    logger.info(f"{log_ctx} ✅ 录制任务恢复成功")

                except Exception as e:
                    logger.error(
                        f"恢复录制任务失败 room_id={room.id}: {e}",
                        exc_info=True
                    )
                    # 发生错误时重置状态
                    try:
                        room.record_status = RecordStatus.IDLE
                        db.commit()
                    except:
                        db.rollback()

            logger.info("✅ 录制任务恢复完成")

        except Exception as e:
            logger.error(f"恢复录制任务异常: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    def cleanup_unused_observers(self):
        """清理未使用的 watchdog observers - 在录制结束后调用"""
        with self.observer_lock:
            unused_dirs = []
            for save_dir, observer in list(self.directory_observers.items()):
                # 检查 observer 是否还在运行
                try:
                    if not observer.is_alive():
                        unused_dirs.append(save_dir)
                except:
                    unused_dirs.append(save_dir)

            # 清理未使用的 observers
            for save_dir in unused_dirs:
                try:
                    observer = self.directory_observers[save_dir]
                    if observer.is_alive():
                        observer.stop()
                        observer.join(timeout=3)
                    del self.directory_observers[save_dir]
                    logger.info(f"已停止并清理 watchdog observer: {save_dir}")
                except Exception as e:
                    logger.error(f"清理 observer 失败 {save_dir}: {e}")

    def cleanup_session(self, room_id: int, session_id: str = None):
        """清理会话资源 - 完善会话生命周期管理

        Args:
            room_id: 直播间ID
            session_id: 会话ID（可选，用于日志）
        """
        db = SessionLocal()
        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                logger.warning(f"清理会话失败: room_id={room_id} 不存在")
                return
            
            log_ctx = _make_log_context(
                room.platform, 
                room.platform_room_id, 
                session_id or room.current_session_id or "unknown"
            )
            
            logger.info(f"{log_ctx} 开始清理会话资源")
            
            # 0. 处理最后一个待处理的分片
            active_session_id = session_id or room.current_session_id
            if active_session_id and active_session_id in self.segment_handlers:
                try:
                    handler = self.segment_handlers[active_session_id]
                    handler.process_final_segment()
                except Exception as e:
                    logger.error(f"{log_ctx} 处理最后分片失败: {e}")
                finally:
                    # 清理handler引用
                    del self.segment_handlers[active_session_id]
            
            # 1. 清理线程引用
            with self.lock:
                if room_id in self.recording_threads:
                    thread = self.recording_threads[room_id]
                    if thread.is_alive():
                        logger.warning(f"{log_ctx} 录制线程仍在运行，等待其自然结束")
                        thread.join(timeout=5)
                    del self.recording_threads[room_id]
                    logger.debug(f"{log_ctx} 已清理录制线程引用")
                
                if room_id in self.recording_stop_flags:
                    del self.recording_stop_flags[room_id]
                    logger.debug(f"{log_ctx} 已清理停止标志")
            
            # 2. 更新数据库状态
            if room.current_session_id:
                # 标记会话结束
                session_ended_at = datetime.now()
                logger.info(f"{log_ctx} 会话结束时间: {session_ended_at}")
                
                # 更新 room 状态
                room.current_session_id = None
                room.current_session_started_at = None
                room.record_status = RecordStatus.IDLE
                
                db.commit()
                logger.info(f"{log_ctx} 会话清理完成")
            else:
                logger.debug(f"{log_ctx} 无活跃会话，跳过清理")

            # 3. 清理未使用的 watchdog observers
            self.cleanup_unused_observers()

        except Exception as e:
            logger.error(f"清理会话异常 room_id={room_id}: {e}")
            db.rollback()
        finally:
            db.close()

    def shutdown(self):
        """应用程序关闭时的优雅关闭 - 停止所有任务并关闭线程池"""
        logger.info("🛑 开始关闭 RecordingManager...")

        # 1. 停止所有监听任务
        with self.lock:
            room_ids = list(self.stop_flags.keys())

        for room_id in room_ids:
            try:
                logger.info(f"停止监听: room_id={room_id}")
                self.stop_monitor(room_id)
            except Exception as e:
                logger.error(f"停止监听失败 room_id={room_id}: {e}")

        # 2. 停止所有录制任务
        with self.lock:
            room_ids = list(self.recording_stop_flags.keys())

        for room_id in room_ids:
            try:
                logger.info(f"停止录制: room_id={room_id}")
                if room_id in self.recording_stop_flags:
                    self.recording_stop_flags[room_id].set()
            except Exception as e:
                logger.error(f"停止录制失败 room_id={room_id}: {e}")

        # 3. 关闭线程池（等待所有任务完成）
        logger.info("关闭线程池: monitor_pool")
        self.monitor_pool.shutdown(wait=True, cancel_futures=False)

        logger.info("关闭线程池: recording_pool")
        self.recording_pool.shutdown(wait=True, cancel_futures=False)

        # 4. 停止所有 watchdog observers
        logger.info("停止所有 watchdog observers...")
        with self.observer_lock:
            for save_dir, observer in list(self.directory_observers.items()):
                try:
                    if observer.is_alive():
                        observer.stop()
                        observer.join(timeout=3)
                    logger.info(f"已停止 watchdog observer: {save_dir}")
                except Exception as e:
                    logger.error(f"停止 observer 失败 {save_dir}: {e}")
            self.directory_observers.clear()
        
        # 5. 停止OSS上传队列（等待队列清空）
        if settings.oss_enabled:
            logger.info("停止OSS上传队列...")
            try:
                from app.services.upload_queue_manager import upload_queue_manager
                upload_queue_manager.stop(timeout=60)
                logger.info("✅ OSS上传队列已停止")
            except Exception as e:
                logger.error(f"停止OSS上传队列失败: {e}")

        logger.info("✅ RecordingManager 已安全关闭")

    def start_monitor(self, room_id: int, url: str = None, platform: str = None,
                      platform_room_id: str = None, quality: str = None):
        """启动直播间监听（使用线程池）

        Args:
            room_id: 直播间ID
            url: 直播间URL(可选,如果不传则从数据库查询)
            platform: 平台名称(可选)
            platform_room_id: 平台房间ID(可选)
            quality: 视频质量(可选)
        """
        with self.lock:
            if room_id in self.monitor_futures:
                logger.warning(f"监听任务已存在: room_id={room_id}")
                return

            stop_event = threading.Event()
            self.stop_flags[room_id] = stop_event

            # ✅ 使用线程池提交监控任务
            future = self.monitor_pool.submit(
                self._monitor_worker,
                room_id, stop_event, url, platform, platform_room_id, quality
            )
            self.monitor_futures[room_id] = future
            logger.info(f"✅ 提交监听任务到线程池: room_id={room_id}")

    def stop_monitor(self, room_id: int):
        """停止直播间监听（线程池任务）"""
        with self.lock:
            if room_id in self.stop_flags:
                logger.info(f"发送停止信号: room_id={room_id}")
                self.stop_flags[room_id].set()

                # ✅ 等待线程池任务完成
                if room_id in self.monitor_futures:
                    future = self.monitor_futures[room_id]
                    try:
                        future.result(timeout=5)  # 等待任务完成
                    except Exception as e:
                        logger.warning(f"监听任务异常结束: room_id={room_id}, error={e}")
                    del self.monitor_futures[room_id]

                del self.stop_flags[room_id]

                # 清理录制任务引用
                if room_id in self.recording_futures:
                    del self.recording_futures[room_id]

    def stop_recording_manually(self, room_id: int):
        """手动停止录制并停止监听
        
        适用场景:
        1. 用户手动停止 - 暂时不需要监控了
        2. 直播关播 - 继续监听也没意义
        
        下次需要录制时,会手动触发开播检测再决定是否开始
        """
        with self.lock:
            stopped_recording = False
            stopped_monitor = False
            
            # 1. 停止录制线程
            if room_id in self.recording_stop_flags:
                logger.info(f"发送录制停止信号: room_id={room_id}")
                self.recording_stop_flags[room_id].set()
                stopped_recording = True
            
            # 2. 停止监听线程
            if room_id in self.stop_flags:
                logger.info(f"发送监听停止信号: room_id={room_id}")
                self.stop_flags[room_id].set()
                
                # 等待监听线程结束
                if room_id in self.monitor_threads:
                    self.monitor_threads[room_id].join(timeout=5)
                    del self.monitor_threads[room_id]
                
                del self.stop_flags[room_id]
                stopped_monitor = True
            
            # 3. 清理录制线程引用
            if room_id in self.recording_threads:
                del self.recording_threads[room_id]
            
            if stopped_recording or stopped_monitor:
                logger.info(
                    f"停止完成: room_id={room_id}, "
                    f"录制={'已停止' if stopped_recording else '未运行'}, "
                    f"监听={'已停止' if stopped_monitor else '未运行'}"
                )
                return True
            else:
                logger.warning(f"录制和监听线程均不存在: room_id={room_id}")
                return False

    def _monitor_worker(self, room_id: int, stop_event: threading.Event,
                       url: str = None, platform: str = None,
                       platform_room_id: str = None, quality: str = None):
        """监听工作线程

        Args:
            room_id: 直播间ID
            stop_event: 停止事件
            url: 直播间URL
            platform: 平台名称
            platform_room_id: 平台房间ID
            quality: 视频质量
        """
        db = SessionLocal()

        try:
            # 如果没有传入参数,从数据库加载一次
            if not url or not platform or not platform_room_id:
                room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                if not room:
                    logger.warning(f"直播间不存在,退出监听: db_id={room_id}")
                    return

                url = url or room.url
                platform = platform or room.platform
                platform_room_id = platform_room_id or room.platform_room_id
                quality = quality or room.quality
                is_enabled = room.is_enabled
            else:
                # 使用传入的参数,只查询 is_enabled 状态
                room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                is_enabled = room.is_enabled if room else True

            log_ctx = _make_log_context(platform, platform_room_id)
            logger.info(f"{log_ctx} 监听线程启动,使用缓存配置")

            # 使用缓存的参数,减少数据库查询
            old_live_status = LiveStatus.OFFLINE

            while not stop_event.is_set():
                try:
                    # 定期从数据库刷新 is_enabled 状态(轻量级查询)
                    try:
                        room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                        if room:
                            is_enabled = room.is_enabled
                            # 如果用户修改了配置,更新缓存
                            if room.url != url:
                                url = room.url
                                logger.info(f"{log_ctx} 检测到URL变更,已更新")
                            if room.quality != quality:
                                quality = room.quality
                                logger.info(f"{log_ctx} 检测到质量设置变更,已更新")
                        else:
                            logger.warning(f"{log_ctx} 数据库查询失败,使用缓存配置")
                    except Exception as db_error:
                        logger.debug(f"{log_ctx} 数据库查询异常: {db_error},使用缓存配置")

                    if not is_enabled:
                        logger.info(f"{log_ctx} 直播间已禁用,退出监听")
                        break

                    # 使用缓存的 url 和 quality 检查直播平台状态
                    from app.services.live_recorder import LiveRecorder
                    recorder = LiveRecorder(proxy_addr=None, cookies={})
                    is_live = asyncio.run(recorder.check_live_status(url))
                    current_live_status = LiveStatus.LIVE if is_live else LiveStatus.OFFLINE

                    if is_live and old_live_status != LiveStatus.LIVE:
                        logger.info(f"{log_ctx} 检测到开播, url={url}")

                        # 优先使用外部传入的 session_id, 如无则生成新的
                        session_id = room.current_session_id or str(uuid.uuid4())
                        session_started_at = room.current_session_started_at or datetime.now()

                        # 如果数据库中缺少这些字段,补充写入
                        if not room.current_session_id:
                            room.current_session_id = session_id
                        if not room.current_session_started_at:
                            room.current_session_started_at = session_started_at

                        db.commit()
                        logger.info(f"{log_ctx} 激活session: {session_id[:8]}")

                        self._start_recording(db, room)
                    elif not is_live and old_live_status == LiveStatus.LIVE:
                        logger.info(f"{log_ctx} 检测到下播")
                        self._stop_recording(db, room)

                    # 更新直播状态到数据库
                    if room and room.live_status != current_live_status:
                        room.live_status = current_live_status
                        db.commit()

                    # 更新本地状态变量
                    old_live_status = current_live_status
                except Exception as e:
                    logger.error(f"{log_ctx} 监听异常: {e}")
                    db.rollback()

                stop_event.wait(settings.check_interval)
        finally:
            db.close()
            if platform and platform_room_id:
                log_ctx = _make_log_context(platform, platform_room_id)
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
        """启动录制任务（使用线程池） - 使用已有的 session_id"""
        # session_id 应该已经在调用此方法前设置好
        if not room.current_session_id:
            session_id = str(uuid.uuid4())
            session_started_at = datetime.now()
            room.current_session_id = session_id
            room.current_session_started_at = session_started_at
            logger.warning(f"session_id 未提前设置,补充生成: {session_id[:8]}")
        else:
            session_id = room.current_session_id

        # 更新录制状态
        room.record_status = RecordStatus.RECORDING
        db.commit()

        log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)
        logger.info(f"{log_ctx} 启动录制任务, room_id={room.id}")

        # 创建录制停止事件
        with self.lock:
            recording_stop_event = threading.Event()
            self.recording_stop_flags[room.id] = recording_stop_event

        # ✅ 使用线程池提交录制任务
        future = self.recording_pool.submit(
            self._recording_worker,
            session_id, room.id, recording_stop_event
        )
        self.recording_futures[room.id] = future
        logger.info(f"✅ 提交录制任务到线程池: session={session_id[:8]}")

    def _stop_recording(self, db: Session, room: LiveRoom):
        """停止录制任务 - 清空 session 信息并清理资源"""
        from sqlalchemy import func

        # 记录被终止的 session_id
        stopped_session_id = room.current_session_id

        if stopped_session_id:
            log_ctx = _make_log_context(room.platform, room.platform_room_id, stopped_session_id)
            logger.info(f"{log_ctx} 停止录制,开始会话清理")

            # 查询该会话的总分片数
            segment_count = db.query(func.count(VideoSegment.id)).filter(
                VideoSegment.session_id == stopped_session_id
            ).scalar() or 0

            logger.info(f"{log_ctx} 会话统计: 总分片数={segment_count}")

        # ✅ 调用会话清理逻辑
        self.cleanup_session(room.id, stopped_session_id)
        
        # 最后更新录制状态为 PENDING
        room.record_status = RecordStatus.PENDING
        db.commit()

        if stopped_session_id:
            log_ctx = _make_log_context(room.platform, room.platform_room_id, stopped_session_id)
            logger.info(f"{log_ctx} 录制停止完成，会话已清理")
        else:
            logger.info(f"[room_id={room.id}] 停止录制完成")


    def _execute_recording_with_retry(self, session_id: str, room_id: int, stop_event: threading.Event):
        """执行录制核心逻辑 - 带自动重试
        
        Args:
            session_id: 录制会话ID
            room_id: 直播间ID
            stop_event: 停止事件
            
        Raises:
            Exception: 录制失败或超过最大重试次数
        """
        attempt = 0
        max_attempts = settings.max_retry_attempts
        current_delay = settings.retry_delay_seconds
        
        while attempt < max_attempts:
            attempt += 1
            
            try:
                logger.info(f"[Session {session_id[:8]}] 录制尝试 {attempt}/{max_attempts}")
                
                # 执行实际的录制逻辑
                self._do_recording(session_id, room_id, stop_event)
                
                # 成功完成，退出重试循环
                logger.info(f"[Session {session_id[:8]}] 录制成功完成")
                return
                
            except Exception as e:
                # 检查是否是手动停止（不应重试）
                if stop_event.is_set():
                    logger.info(f"[Session {session_id[:8]}] 手动停止，不进行重试")
                    raise
                
                # 最后一次尝试失败
                if attempt >= max_attempts:
                    logger.error(f"[Session {session_id[:8]}] 录制失败，已达最大重试次数 {max_attempts}: {e}")
                    raise
                
                # 记录失败并准备重试
                logger.warning(f"[Session {session_id[:8]}] 录制第 {attempt}/{max_attempts} 次失败: {e}")
                logger.info(f"[Session {session_id[:8]}] 等待 {current_delay} 秒后重试...")
                
                # 指数退避等待
                time.sleep(current_delay)
                current_delay *= settings.retry_backoff_multiplier

    def _do_recording(self, session_id: str, room_id: int, stop_event: threading.Event):
        """执行录制的核心逻辑（单次尝试）
        
        Args:
            session_id: 录制会话ID
            room_id: 直播间ID
            stop_event: 停止事件
        """
        db = SessionLocal()
        
        try:
            # 获取room信息用于日志上下文
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                raise ValueError(f"房间不存在: room_id={room_id}")
            
            log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)

            observer = None  # 初始化为 None，用于 finally 块清理
            
            try:
                from app.services.live_recorder import LiveRecorder
                import subprocess
                import os

                # 获取直播流信息
                recorder = LiveRecorder()
                stream_info = asyncio.run(recorder.get_live_stream_info(room.url, room.quality))

                if not stream_info['is_live'] or not stream_info['stream_url']:
                    raise ValueError(f"{log_ctx} 直播未开播或无法获取流地址")

                # 创建保存目录
                project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                save_dir = os.path.join(
                    project_root,
                    settings.video_save_path.lstrip('./'),
                    room.streamer_name or f"room_{room_id}"
                )
                os.makedirs(save_dir, exist_ok=True)

                # 使用FFmpeg HLS/Segment muxer进行自动分段
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                segment_interval = settings.segment_duration

                # GOP配置（Group of Pictures）
                # GOP应该设置为2-10秒的帧数，太大会影响切片精度
                # 从配置读取GOP间隔和帧率
                gop_size = settings.ffmpeg_gop_seconds * settings.ffmpeg_assumed_fps  # GOP大小（帧数）

                # 根据配置选择录制模式
                if settings.segment_method == "hls":
                    # ===== HLS模式 (推荐) =====
                    # 优势：业界标准、自动关键帧处理、音视频同步、稳定性高
                    # 适用：长时间录制、稳定分片、生产环境

                    # HLS分片文件名模式 (使用strftime支持时间戳)
                    hls_segment_filename = os.path.join(save_dir, f"{timestamp}_seg%03d.ts")
                    playlist_path = os.path.join(save_dir, f"{timestamp}_playlist.m3u8")

                    # 音频编码配置（根据配置选择）
                    if settings.audio_codec_mode == "copy":
                        audio_codec_params = ['-c:a', 'copy']
                    else:
                        audio_codec_params = ['-c:a', 'aac', '-b:a', settings.audio_bitrate]

                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-i', stream_info['stream_url'],
                        # 视频编码
                        '-c:v', 'libx264',
                        '-preset', settings.ffmpeg_preset,
                        '-crf', str(settings.ffmpeg_crf),
                        '-g', str(gop_size),  # GOP大小
                        '-sc_threshold', '0',  # 禁用场景切换检测
                        # 音频编码 (根据配置)
                        *audio_codec_params,
                        # HLS配置
                        '-f', 'hls',
                        '-hls_time', str(segment_interval),  # 分片时长
                        '-hls_list_size', '0',  # 保留所有分片到m3u8
                        '-hls_segment_type', 'mpegts',  # TS格式
                        '-hls_segment_filename', hls_segment_filename,
                        '-hls_flags', 'independent_segments',  # 独立分片
                        playlist_path
                    ]

                    logger.info(
                        f"{log_ctx} 启动FFmpeg录制 (HLS模式), "
                        f"分段时长={segment_interval}秒, "
                        f"preset={settings.ffmpeg_preset}, crf={settings.ffmpeg_crf}, "
                        f"GOP={gop_size}帧, 音频={settings.audio_codec_mode}"
                    )
                else:
                    # ===== Segment模式 (传统) =====
                    # 适用：需要特定格式、兼容性需求
                    filename_pattern = f"{timestamp}_seg%03d.{settings.video_record_format.lower()}"
                    file_pattern = os.path.join(save_dir, filename_pattern)

                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-i', stream_info['stream_url'],
                        # 视频：重新编码 + 强制关键帧
                        '-c:v', 'libx264',
                        '-preset', settings.ffmpeg_preset,
                        '-crf', str(settings.ffmpeg_crf),
                        '-force_key_frames', f'expr:gte(t,n_forced*{segment_interval})',
                        '-g', str(gop_size),
                        '-keyint_min', str(gop_size),
                        '-sc_threshold', '0',
                        # 音频：重编码 (修复音频同步问题)
                        '-c:a', 'aac',
                        '-b:a', settings.audio_bitrate,
                        # Segment配置
                        '-f', 'segment',
                        '-segment_time', str(segment_interval),
                        '-segment_time_delta', '5',
                        '-segment_format', settings.ffmpeg_format,
                        '-reset_timestamps', '1',
                        file_pattern
                    ]

                    logger.info(
                        f"{log_ctx} 启动FFmpeg录制 (Segment模式), "
                        f"分段时长={segment_interval}秒, "
                        f"preset={settings.ffmpeg_preset}, crf={settings.ffmpeg_crf}, "
                        f"GOP={gop_size}帧"
                    )

                ffmpeg_process = None
                video_format = settings.video_record_format.lower()
                manually_stopped = False

                handler = SegmentFileHandler(
                    recording_manager=self,
                    session_id=session_id,
                    room_id=room_id,
                    platform=room.platform,
                    platform_room_id=room.platform_room_id,
                    video_format=video_format
                )
                
                # 存储handler引用，用于录制结束时处理最后一个分片
                with self.observer_lock:
                    self.segment_handlers[session_id] = handler
                    
                    if save_dir not in self.directory_observers:
                        observer = Observer()
                        observer.schedule(handler, path=save_dir, recursive=False)
                        observer.start()
                        self.directory_observers[save_dir] = observer
                        logger.info(f"{log_ctx} watchdog文件监控已启动 (新建): {save_dir}")
                    else:
                        # 复用已有observer，但为新session添加handler
                        observer = self.directory_observers[save_dir]
                        observer.schedule(handler, path=save_dir, recursive=False)
                        logger.info(f"{log_ctx} watchdog文件监控已存在 (复用+添加handler): {save_dir}")

                try:
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1  # 行缓冲，实时输出
                    )

                    # 启动线程实时读取FFmpeg的stderr输出
                    def read_ffmpeg_stderr():
                        """实时读取并打印FFmpeg的stderr输出（用于调试）"""
                        try:
                            for line in iter(ffmpeg_process.stderr.readline, ''):
                                if line:
                                    # 只输出关键信息，避免刷屏
                                    line = line.strip()
                                    # 关键事件：分片创建、错误、警告
                                    if any(keyword in line.lower() for keyword in ['error', 'warning', 'opening', 'segment', 'failed', 'could not']):
                                        logger.info(f"{log_ctx} [FFmpeg] {line}")
                                    # 每60秒输出一次进度信息（包含time=）
                                    elif 'time=' in line and 'bitrate=' in line:
                                        # 提取时间信息（例如：time=00:05:23.45）
                                        import re
                                        time_match = re.search(r'time=(\S+)', line)
                                        if time_match:
                                            # 每60秒输出一次
                                            time_str = time_match.group(1)
                                            if time_str.count(':') >= 2:  # 确保格式正确
                                                parts = time_str.split(':')
                                                try:
                                                    total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
                                                    if total_seconds > 0 and total_seconds % 60 < 2:  # 每分钟输出一次
                                                        logger.info(f"{log_ctx} [FFmpeg] 录制进度: {time_str}")
                                                except:
                                                    pass
                        except Exception as e:
                            logger.warning(f"{log_ctx} FFmpeg stderr读取异常: {e}")

                    import threading
                    stderr_thread = threading.Thread(target=read_ffmpeg_stderr, daemon=True)
                    stderr_thread.start()

                    while ffmpeg_process.poll() is None:
                        if stop_event.is_set():
                            manually_stopped = True
                            logger.info(f"{log_ctx} 收到停止信号,终止录制")
                            ffmpeg_process.terminate()
                            break

                        # 强制从数据库重新加载最新状态,避免缓存问题
                        db.expire(room)
                        db.refresh(room)

                        # 检查:直播结束
                        if room.live_status != LiveStatus.LIVE:
                            manually_stopped = True
                            logger.info(f"{log_ctx} 直播已结束,停止录制")
                            ffmpeg_process.terminate()
                            break

                        time.sleep(1)

                    # FFmpeg进程结束后,处理剩余的文件
                    _, stderr = ffmpeg_process.communicate(timeout=5)
                    return_code = ffmpeg_process.returncode

                    # ✅ 检查 stderr 判断是否为手动停止（received signal）
                    is_signal_stop = "received signal" in stderr if stderr else False

                    # 判断是否为正常终止
                    is_normal_termination = (
                        return_code == 0 or
                        return_code == -15 or
                        (manually_stopped and return_code == 255) or
                        is_signal_stop  # ✅ SIGINT/SIGTERM 也视为正常
                    )

                    if is_normal_termination:
                        logger.info(f"{log_ctx} FFmpeg录制完成: return_code={return_code}, manually_stopped={manually_stopped}, signal_stop={is_signal_stop}")
                    else:
                        error_msg = f"FFmpeg异常终止: return_code={return_code}, stderr={stderr[-1000:]}"
                        logger.error(f"{log_ctx} {error_msg}")
                        raise RuntimeError(error_msg)

                    # ✅ 最后扫描一次,处理 watchdog 可能错过的文件
                    all_files = os.listdir(save_dir)
                    segment_files = sorted([f for f in all_files
                                           if f.startswith(timestamp) and f.endswith(f'.{video_format}')])
                    processed_paths = {os.path.basename(p) for p in handler.processed}
                    remaining_files = set(segment_files) - processed_paths

                    if remaining_files:
                        logger.info(f"{log_ctx} 处理watchdog错过的 {len(remaining_files)} 个分段")

                        for segment_file in sorted(remaining_files):
                            file_path = os.path.join(save_dir, segment_file)
                            if os.path.exists(file_path):
                                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
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
                    # ✅ 清理 watchdog 监控器 (只在没有其他任务使用时停止)
                    # 注意: 由于可能有多个 session 共享同一目录,这里不立即停止 observer
                    # 而是在 cleanup_session 中检查并清理无用的 observer
                    logger.info(f"{log_ctx} watchdog监控继续运行 (可能被其他session共享)")

                    # 清理 FFmpeg 进程
                    if ffmpeg_process and ffmpeg_process.poll() is None:
                        ffmpeg_process.terminate()
                        ffmpeg_process.wait(timeout=5)

            except Exception as e:
                logger.error(f"{log_ctx} 录制异常: {e}")
                room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                if room:
                    room.record_status = RecordStatus.ERROR
                    db.commit()
                raise
                
        finally:
            db.close()

    def _recording_worker(self, session_id: str, room_id: int, stop_event: threading.Event):
        """录制工作线程 - 负责并发控制和重试协调"""
        # ✅ 并发控制: 获取录制许可,超出限制时会阻塞等待
        logger.info(f"[Session {session_id[:8]}] 等待录制许可 (当前限制: {settings.max_concurrent_recordings})")
        
        with self.recording_semaphore:
            logger.info(f"[Session {session_id[:8]}] 获得录制许可,开始录制")
            
            try:
                # 执行带重试机制的录制
                self._execute_recording_with_retry(session_id, room_id, stop_event)
            except Exception as e:
                logger.error(f"[Session {session_id[:8]}] 录制最终失败: {e}")
                # 更新数据库状态
                db = SessionLocal()
                try:
                    room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                    if room:
                        room.record_status = RecordStatus.ERROR
                        room.current_session_id = None
                        room.current_session_started_at = None
                        db.commit()
                finally:
                    db.close()
            finally:
                logger.info(f"[Session {session_id[:8]}] 释放录制许可")

    def on_segment_created(self, db: Session, session_id: str, room_id: int,
                          file_path: str, segment_index: int,
                          segment_start_time: datetime, segment_end_time: datetime,
                          duration: int):
        """切片创建回调"""
        import os
        from datetime import timedelta

        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                return

            # 计算相对时间（HH:MM:SS格式）
            # 例如：seg0: "00:00:00" -> "00:20:00", seg1: "00:20:00" -> "00:40:00"
            start_seconds = segment_index * settings.segment_duration
            end_seconds = start_seconds + duration
            
            # 转换为HH:MM:SS格式
            def seconds_to_time_str(seconds: int) -> str:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            
            relative_start = seconds_to_time_str(start_seconds)
            relative_end = seconds_to_time_str(end_seconds)

            # 创建切片记录(包含平台冗余字段)
            video_segment = VideoSegment(
                room_id=room_id,
                platform=room.platform,
                platform_room_id=room.platform_room_id,
                session_id=session_id,
                segment_index=segment_index,
                segment_started_at=relative_start,  # 存储相对时间（HH:MM:SS）
                segment_ended_at=relative_end,      # 存储相对时间（HH:MM:SS）
                duration=duration,
                status=SegmentStatus.COMPLETED,
                completed_at=datetime.now()
            )
            db.add(video_segment)
            db.commit()
            db.refresh(video_segment)

            # 使用包含 segment_index 的日志上下文
            seg_ctx = _make_log_context(room.platform, room.platform_room_id, session_id, segment_index)
            logger.info(f"{seg_ctx} 分片创建成功, 时长={duration}秒, 文件={os.path.basename(file_path)}")

            # 异步上传视频和音频（使用线程池）
            if settings.oss_enabled:
                self.recording_pool.submit(
                    self._upload_video_and_audio_with_queue,
                    video_segment.id, file_path, room.platform, room.platform_room_id, session_id, segment_index
                )
            else:
                # 未启用OSS，直接处理（转换格式）
                self.recording_pool.submit(
                    self._upload_video_and_audio,
                    video_segment.id, file_path, room.platform, room.platform_room_id, session_id
                )
        except Exception as e:
            # 在异常时也使用带 segment_index 的上下文(如果可用)
            error_ctx = _make_log_context(
                room.platform if room else None,
                room.platform_room_id if room else None,
                session_id,
                segment_index
            )
            logger.error(f"{error_ctx} 切片记录创建失败: {e}")
            import traceback
            logger.error(f"{error_ctx} 异常堆栈: {traceback.format_exc()}")

    def _upload_video_and_audio_with_queue(self, segment_id: int, video_path: str,
                                            platform: str, platform_room_id: str, session_id: str, segment_index: int):
        """使用上传队列处理视频和音频上传
        
        Args:
            segment_id: 分片ID
            video_path: 视频文件路径
            platform: 平台名称
            platform_room_id: 平台房间ID
            session_id: 会话ID
            segment_index: 分片索引
        """
        from app.services.upload_queue_manager import upload_queue_manager, UploadTask
        from app.services.audio_extractor import audio_extractor
        from app.services.video_converter import video_converter
        import os
        
        db = SessionLocal()
        audio_path = None
        original_ts_path = None
        converted_video_path = None
        log_ctx = _make_log_context(platform, platform_room_id, session_id, segment_index)
        
        try:
            video_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not video_segment:
                logger.warning(f"{log_ctx} 视频分片不存在")
                return
            
            video_segment.status = SegmentStatus.UPLOADING
            db.commit()
            
            # 1. 格式转换 (TS → MP4)
            logger.debug(f"{log_ctx} 开始格式转换")
            original_ts_path = video_path
            converted_video_path = video_converter.convert_to_target_format(
                input_path=video_path,
                delete_source=False,
                log_context=log_ctx
            )
            
            if not converted_video_path:
                raise Exception("视频格式转换失败")
            
            video_path = converted_video_path
            
            # 2. 抽取音频
            logger.debug(f"{log_ctx} 开始抽取音频")
            audio_path = audio_extractor.extract_audio(video_path=video_path, delete_source=False)
            if not audio_path:
                raise Exception("音频抽取失败")
            
            # 3. 创建上传任务并提交到队列（FIFO，先进先出）
            # 视频上传任务
            video_task = UploadTask(
                task_id=f"video_{segment_id}",
                file_path=video_path,
                object_key=None,
                log_context=log_ctx,
                priority=5,  # 固定优先级，按提交顺序FIFO处理
                callback=lambda success, result, error: self._on_video_upload_complete(
                    segment_id, video_path, audio_path, original_ts_path,
                    success, result, error, log_ctx
                )
            )
            
            # 音频上传任务
            audio_task = UploadTask(
                task_id=f"audio_{segment_id}",
                file_path=audio_path,
                object_key=None,
                log_context=log_ctx,
                priority=5,  # 固定优先级，按提交顺序FIFO处理
                callback=lambda success, result, error: self._on_audio_upload_complete(
                    segment_id, video_path, audio_path, original_ts_path,
                    success, result, error, log_ctx
                )
            )
            
            # 提交任务到队列
            video_submitted = upload_queue_manager.submit(video_task)
            audio_submitted = upload_queue_manager.submit(audio_task)
            
            if not (video_submitted and audio_submitted):
                raise Exception(f"任务提交失败: video={video_submitted}, audio={audio_submitted}")
            
            logger.info(f"{log_ctx} 上传任务已提交到队列, queue_size={upload_queue_manager.get_queue_size()}")
            
        except Exception as e:
            logger.error(f"{log_ctx} 准备上传任务失败: {e}", exc_info=True)
            
            # 更新失败状态
            try:
                failed_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
                if failed_segment:
                    failed_segment.status = SegmentStatus.FAILED.value
                    failed_segment.error_message = f"准备上传失败: {str(e)}"
                    db.commit()
            except Exception as update_error:
                logger.error(f"{log_ctx} 更新失败状态出错: {update_error}")
            
            # 清理临时文件
            self._cleanup_temp_files(video_path, audio_path, original_ts_path, log_ctx)
        finally:
            db.close()
    
    def _on_video_upload_complete(self, segment_id: int, video_path: str,
                                   audio_path: str, original_ts_path: str,
                                   success: bool, result: dict, error: str, log_ctx: str):
        """视频上传完成回调
        
        ⚠️ 注意：此回调在上传队列的工作线程中执行，创建独立的数据库会话
        """
        db_callback = SessionLocal()
        try:
            if success:
                try:
                    video_segment = db_callback.query(VideoSegment).filter(
                        VideoSegment.id == segment_id
                    ).first()
                    
                    if video_segment:
                        video_segment.oss_video_url = result['key']
                        db_callback.commit()
                        logger.debug(f"{log_ctx} 视频URL已保存: {result['key']}")
                        
                        # ✅ 检查是否视频和音频都已上传完成，如果是则发送通知
                        self._check_and_finalize_upload(
                            db_callback, segment_id, video_path, audio_path, 
                            original_ts_path, log_ctx
                        )
                except Exception as e:
                    logger.error(f"{log_ctx} 保存视频URL失败: {e}", exc_info=True)
                    db_callback.rollback()
            else:
                logger.error(f"{log_ctx} 视频上传失败: {error}")
                self._mark_segment_failed(db_callback, segment_id, f"视频上传失败: {error}")
        finally:
            db_callback.close()
    
    def _on_audio_upload_complete(self, segment_id: int, video_path: str,
                                   audio_path: str, original_ts_path: str,
                                   success: bool, result: dict, error: str, log_ctx: str):
        """音频上传完成回调
        
        ⚠️ 注意：此回调在上传队列的工作线程中执行，创建独立的数据库会话
        """
        db_callback = SessionLocal()
        try:
            if success:
                try:
                    video_segment = db_callback.query(VideoSegment).filter(
                        VideoSegment.id == segment_id
                    ).first()
                    
                    if video_segment:
                        video_segment.oss_audio_url = result['key']
                        db_callback.commit()
                        logger.debug(f"{log_ctx} 音频URL已保存: {result['key']}")
                        
                        # ✅ 检查是否视频和音频都已上传完成，如果是则发送通知
                        self._check_and_finalize_upload(
                            db_callback, segment_id, video_path, audio_path, 
                            original_ts_path, log_ctx
                        )
                except Exception as e:
                    logger.error(f"{log_ctx} 保存音频URL失败: {e}", exc_info=True)
                    db_callback.rollback()
            else:
                logger.error(f"{log_ctx} 音频上传失败: {error}")
                self._mark_segment_failed(db_callback, segment_id, f"音频上传失败: {error}")
        finally:
            db_callback.close()
    
    def _check_and_finalize_upload(self, db: Session, segment_id: int,
                                    video_path: str, audio_path: str, original_ts_path: str, log_ctx: str):
        """检查并完成上传流程（线程安全，只通知一次）
        
        ⚠️ 重要：视频和音频上传是并行的，两个回调都会调用此方法
        需要确保：
        1. 只有当视频和音频都上传完成时才执行后续逻辑
        2. 通知只发送一次（幂等性）
        3. 线程安全（数据库行锁）
        """
        try:
            # ✅ 使用 with_for_update() 添加行锁，避免并发更新冲突
            video_segment = db.query(VideoSegment).filter(
                VideoSegment.id == segment_id
            ).with_for_update().first()
            
            if not video_segment:
                logger.warning(f"{log_ctx} 分片不存在，可能已被删除")
                return
            
            # ✅ 幂等性检查：如果已经是UPLOADED状态，说明已经处理过了，直接返回
            if video_segment.status == SegmentStatus.UPLOADED:
                logger.debug(f"{log_ctx} 分片已处理完成，跳过重复处理")
                return
            
            # ✅ 检查视频和音频是否都已上传完成
            has_video = bool(video_segment.oss_video_url)
            has_audio = bool(video_segment.oss_audio_url)
            
            if not (has_video and has_audio):
                # 还有文件未上传完成，等待另一个回调
                logger.debug(
                    f"{log_ctx} 等待其他文件上传完成 "
                    f"(video={has_video}, audio={has_audio})"
                )
                db.commit()  # 释放行锁
                return
            
            video_segment.status = SegmentStatus.UPLOADED
            db.commit()
            
            logger.info(f"{log_ctx} 🎉 分片上传完成，准备发送通知")
            
            try:
                db_new = SessionLocal()
                try:
                    seg_for_stats = db_new.query(VideoSegment).filter(
                        VideoSegment.id == segment_id
                    ).first()
                    if seg_for_stats:
                        self._update_session_completion_if_needed(db_new, seg_for_stats)
                finally:
                    db_new.close()
            except Exception as stats_error:
                logger.error(f"{log_ctx} 更新session统计失败: {stats_error}")
            
            # ✅ 异步发送通知（fire-and-forget，不阻塞主流程）
            try:
                from app.services.segment_notifier import segment_notifier
                # 提交到线程池异步执行，不等待结果
                self.recording_pool.submit(
                    self._send_notification_async,
                    segment_id,
                    log_ctx
                )
                logger.info(f"{log_ctx} 📤 分片通知已提交到后台线程")
            except Exception as notify_error:
                logger.error(f"{log_ctx} ❌ 提交分片通知任务失败: {notify_error}", exc_info=True)
            
            # ✅ 清理本地文件
            self._cleanup_temp_files(video_path, audio_path, original_ts_path, log_ctx, include_m3u8=True)
            
        except Exception as e:
            logger.error(f"{log_ctx} 完成上传流程失败: {e}", exc_info=True)
            db.rollback()
    
    def _mark_segment_failed(self, db: Session, segment_id: int, error_msg: str):
        """标记分片上传失败"""
        try:
            segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if segment:
                segment.status = SegmentStatus.FAILED.value
                segment.error_message = error_msg
                db.commit()
        except Exception as e:
            logger.error(f"标记分片失败状态出错: {e}")
    
    def _cleanup_temp_files(self, video_path: str, audio_path: str, original_ts_path: str,
                            log_ctx: str, include_m3u8: bool = False):
        """清理临时文件"""
        import os
        
        try:
            files_cleaned = []
            
            # 删除原始TS文件
            if original_ts_path and os.path.exists(original_ts_path) and original_ts_path != video_path:
                os.remove(original_ts_path)
                files_cleaned.append(f"TS: {os.path.basename(original_ts_path)}")
            
            # 删除MP4文件
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
                files_cleaned.append(f"MP4: {os.path.basename(video_path)}")
            
            # 删除音频文件
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                files_cleaned.append(f"MP3: {os.path.basename(audio_path)}")
            
            # 删除m3u8文件
            if include_m3u8 and settings.segment_method == "hls" and original_ts_path:
                ts_basename = os.path.basename(original_ts_path)
                timestamp_part = ts_basename.split('_seg')[0] if '_seg' in ts_basename else ts_basename.rsplit('.', 1)[0]
                m3u8_filename = f"{timestamp_part}_playlist.m3u8"
                m3u8_path = os.path.join(os.path.dirname(original_ts_path), m3u8_filename)
                
                if os.path.exists(m3u8_path):
                    os.remove(m3u8_path)
                    files_cleaned.append(f"M3U8: {os.path.basename(m3u8_path)}")
            
            if files_cleaned:
                logger.info(f"{log_ctx} ✅ 本地文件已清理: {', '.join(files_cleaned)}")
        except Exception as e:
            logger.error(f"{log_ctx} 清理临时文件失败: {e}")

    def _send_notification_async(self, segment_id: int, log_ctx: str):
        """
        在后台线程中发送分片通知
        
        Args:
            segment_id: 分片ID
            log_ctx: 日志上下文
        
        说明:
            - 此方法在线程池中异步执行
            - 不阻塞主流程
            - 使用独立的数据库会话
            - 即使失败也不影响主流程
        """
        db_new = None
        try:
            from app.database import SessionLocal
            from app.services.segment_notifier import segment_notifier
            
            db_new = SessionLocal()
            
            # 调用同步发送方法（在后台线程中执行）
            success = segment_notifier.send_notification_sync(db_new, segment_id)
            
            if success:
                logger.info(f"{log_ctx} ✅ 分片通知发送成功")
            else:
                logger.warning(f"{log_ctx} ⚠️ 分片通知发送失败(详见上方错误日志)")
                
        except Exception as e:
            logger.error(f"{log_ctx} ❌ 后台发送分片通知异常: {e}", exc_info=True)
        finally:
            if db_new:
                db_new.close()

    def _update_session_completion_if_needed(self, db: Session, video_segment: VideoSegment):
        """检查并更新 session 完成信息
        
        当满足以下条件时更新 room 表:
        1. 该 session 对应的录制已停止(room.record_status != RECORDING 或 room.current_session_id != segment.session_id)
        2. 该 session 的所有分片都已上传完成
        
        Args:
            db: 数据库会话
            video_segment: 刚上传完成的分片
        """
        from sqlalchemy import func
        
        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == video_segment.room_id).first()
            if not room:
                return
            
            session_id = video_segment.session_id
            log_ctx = _make_log_context(room.platform, room.platform_room_id, session_id)
            
            # 检查该 session 是否已经不是当前活跃的 session
            is_session_ended = (
                room.current_session_id != session_id or 
                room.record_status != RecordStatus.RECORDING
            )
            
            if not is_session_ended:
                # session 还在录制中,不更新
                return
            
            # 查询该 session 的所有分片
            total_segments = db.query(func.count(VideoSegment.id)).filter(
                VideoSegment.session_id == session_id
            ).scalar() or 0
            
            uploaded_segments = db.query(func.count(VideoSegment.id)).filter(
                VideoSegment.session_id == session_id,
                VideoSegment.status == SegmentStatus.UPLOADED
            ).scalar() or 0
            
            # 如果所有分片都已上传完成
            if total_segments > 0 and uploaded_segments == total_segments:
                # 获取最后一个分片的结束时间作为 session 结束时间
                last_segment = db.query(VideoSegment).filter(
                    VideoSegment.session_id == session_id
                ).order_by(VideoSegment.segment_index.desc()).first()
                
                if last_segment and last_segment.segment_ended_at:
                    # 更新 room 表的 session 结束时间和总分片数
                    room.current_session_ended_at = last_segment.segment_ended_at
                    room.total_segment = total_segments
                    db.commit()
                    
                    logger.info(
                        f"{log_ctx} Session 所有分片上传完成,更新统计: "
                        f"total_segment={total_segments}, "
                        f"ended_at={last_segment.segment_ended_at}"
                    )
        except Exception as e:
            logger.error(f"更新 session 完成信息失败: {e}", exc_info=True)
            db.rollback()

    def _upload_video_and_audio(self, segment_id: int, video_path: str,
                                platform: str, platform_room_id: str, session_id: str):
        """
        录制完成后处理流程:
        1. 格式转换 (TS → MP4)
        2. 抽取音频 (MP4 → MP3)
        3. 并行上传 (视频 + 音频)
        4. 回写数据库
        5. 更新session统计
        6. 发送通知
        7. 删除本地文件
        """
        from app.services.oss_uploader import oss_uploader
        from app.services.audio_extractor import audio_extractor
        import os
        import concurrent.futures

        db = SessionLocal()
        audio_path = None
        original_ts_path = None  # 原始TS文件路径
        converted_video_path = None  # 转换后的MP4文件路径
        log_ctx = None  # ✅ 初始化 log_ctx,避免在异常处理中未定义

        try:
            video_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not video_segment:
                logger.warning(f"视频分片不存在: segment_id={segment_id}")
                return

            # 使用 segment_index 而不是 segment_id 构建日志上下文
            log_ctx = _make_log_context(platform, platform_room_id, session_id, video_segment.segment_index)

            # ✅ 添加调试日志:检查 video_segment 的字段
            logger.debug(f"{log_ctx} 分片上传开始, segment.status={video_segment.status}, segment.id={video_segment.id}")

            video_segment.status = SegmentStatus.UPLOADING
            db.commit()
            logger.debug(f"{log_ctx} 状态已更新为 UPLOADING")

            # 1. 格式转换 (TS → MP4)
            logger.debug(f"{log_ctx} 步骤1: 开始格式转换, input={video_path}")
            from app.services.video_converter import video_converter
            original_ts_path = video_path  # 保存原始TS路径，用于最后清理
            converted_video_path = video_converter.convert_to_target_format(
                input_path=video_path,
                delete_source=False,  # 不删除原始TS文件，等上传成功后再统一清理
                log_context=log_ctx
            )

            if not converted_video_path:
                raise Exception("视频格式转换失败")

            # 更新video_path为转换后的路径
            video_path = converted_video_path
            logger.debug(f"{log_ctx} 步骤1完成: 格式转换成功, output={video_path}")

            # 2. 抽取音频
            logger.debug(f"{log_ctx} 步骤2: 开始抽取音频")
            audio_path = audio_extractor.extract_audio(video_path=video_path, delete_source=False)
            if not audio_path:
                raise Exception("音频抽取失败")
            logger.debug(f"{log_ctx} 步骤2完成: 音频抽取成功, audio={audio_path}")

            # 3. 并行上传
            logger.debug(f"{log_ctx} 步骤3: 开始并行上传")
            video_key = None
            audio_key = None

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 传入日志上下文到OSS上传
                video_future = executor.submit(oss_uploader.upload_file, video_path, None, None, False, log_ctx)
                audio_future = executor.submit(oss_uploader.upload_file, audio_path, None, None, False, log_ctx)

                video_result = video_future.result()
                logger.debug(f"{log_ctx} 视频上传完成: {type(video_result)}, keys={video_result.keys() if isinstance(video_result, dict) else 'NOT_DICT'}")
                video_key = video_result.get('key')  # 获取相对路径key而非完整URL

                audio_result = audio_future.result()
                logger.debug(f"{log_ctx} 音频上传完成: {type(audio_result)}, keys={audio_result.keys() if isinstance(audio_result, dict) else 'NOT_DICT'}")
                audio_key = audio_result.get('key')  # 获取相对路径key而非完整URL

            logger.debug(f"{log_ctx} 步骤3完成: 并行上传成功, video_key={video_key}, audio_key={audio_key}")

            # 4. 回写数据库 (存储相对路径key,不包含域名前缀)
            logger.debug(f"{log_ctx} 步骤4: 开始回写数据库")
            video_segment.oss_video_url = video_key
            video_segment.oss_audio_url = audio_key
            video_segment.status = SegmentStatus.UPLOADED
            db.commit()
            logger.debug(f"{log_ctx} 步骤4完成: 数据库更新成功, status=UPLOADED")

            # 5. 检查是否是最后一个分片,更新 room 表统计信息
            logger.debug(f"{log_ctx} 步骤5: 开始更新session统计")
            self._update_session_completion_if_needed(db, video_segment)
            logger.debug(f"{log_ctx} 步骤5完成: session统计更新完成")

            # 6. 异步发送分片完成通知（fire-and-forget，不阻塞主流程）
            try:
                from app.services.segment_notifier import segment_notifier
                # 提交到线程池异步执行，不等待结果
                self.recording_pool.submit(
                    self._send_notification_async,
                    segment_id,
                    log_ctx
                )
                logger.info(f"{log_ctx} 📤 分片通知已提交到后台线程")
            except Exception as notify_error:
                logger.error(f"{log_ctx} ❌ 提交分片通知任务失败: {notify_error}", exc_info=True)

            # 7. 删除本地文件（上传成功并落库后，清理所有临时文件）
            try:
                files_cleaned = []

                # 删除原始TS文件（如果与MP4文件路径不同）
                if original_ts_path and os.path.exists(original_ts_path):
                    # 避免重复删除（格式相同时，TS和MP4是同一文件）
                    if original_ts_path != video_path:
                        os.remove(original_ts_path)
                        files_cleaned.append(f"TS: {os.path.basename(original_ts_path)}")

                # 删除MP4文件（video_path在第1187行已更新为converted_video_path）
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                    files_cleaned.append(f"MP4: {os.path.basename(video_path)}")

                # 删除音频文件
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    files_cleaned.append(f"MP3: {os.path.basename(audio_path)}")

                # HLS模式：删除m3u8播放列表文件
                if settings.segment_method == "hls" and original_ts_path:
                    # 从TS文件路径推导m3u8文件路径
                    # TS: /path/to/20251023_091211_seg000.ts
                    # M3U8: /path/to/20251023_091211_playlist.m3u8
                    ts_basename = os.path.basename(original_ts_path)
                    # 提取时间戳部分（例如：20251023_091211）
                    timestamp_part = ts_basename.split('_seg')[0] if '_seg' in ts_basename else ts_basename.rsplit('.', 1)[0]
                    m3u8_filename = f"{timestamp_part}_playlist.m3u8"
                    m3u8_path = os.path.join(os.path.dirname(original_ts_path), m3u8_filename)

                    if os.path.exists(m3u8_path):
                        os.remove(m3u8_path)
                        files_cleaned.append(f"M3U8: {os.path.basename(m3u8_path)}")

                if files_cleaned:
                    logger.info(f"{log_ctx} ✅ 本地文件已清理: {', '.join(files_cleaned)}")
                else:
                    logger.warning(f"{log_ctx} ⚠️ 没有文件需要清理")
            except Exception as cleanup_error:
                logger.error(f"{log_ctx} ❌ 清理本地文件失败: {cleanup_error}", exc_info=True)

            logger.info(f"{log_ctx} 分片处理完成")
        except Exception as e:
            # ✅ 确保即使 log_ctx 未定义也能输出错误
            ctx_str = log_ctx if log_ctx else f"[segment_id={segment_id}]"
            # ✅ 使用参数化日志避免二次格式化问题
            import traceback
            logger.error(
                "{} 分片上传处理失败:\n  异常类型: {}\n  异常内容: {}\n  完整堆栈:\n{}",
                ctx_str,
                type(e).__name__,
                str(e),
                traceback.format_exc()
            )

            # ✅ 重新查询并更新失败状态
            try:
                failed_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
                if failed_segment:
                    failed_segment.status = SegmentStatus.FAILED.value  # ✅ 使用 .value 确保是字符串
                    failed_segment.error_message = f"上传处理失败: {str(e)}"
                    db.commit()
                    logger.debug(f"{ctx_str} 分片状态已更新为 FAILED")
            except Exception as update_error:
                logger.error(f"{ctx_str} 更新失败状态时出错: {update_error}", exc_info=True)
            
            # 失败时清理临时文件（MP4和MP3），但保留原始TS文件以便重试
            try:
                temp_files_removed = []
                
                # 删除MP4文件（如果已生成且与TS文件不同）
                if video_path and os.path.exists(video_path) and video_path != original_ts_path:
                    os.remove(video_path)
                    temp_files_removed.append(f"MP4: {os.path.basename(video_path)}")
                
                # 删除音频文件（如果已生成）
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    temp_files_removed.append(f"MP3: {os.path.basename(audio_path)}")
                
                if temp_files_removed:
                    logger.info(f"{ctx_str} 已清理临时文件: {', '.join(temp_files_removed)} (保留TS文件)")
            except Exception as cleanup_err:
                logger.warning(f"{ctx_str} 清理临时文件失败: {cleanup_err}")
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

            # 创建录制停止事件
            with self.lock:
                recording_stop_event = threading.Event()
                self.recording_stop_flags[room_id] = recording_stop_event

            # 启动录制线程
            thread = threading.Thread(
                target=self._recording_worker,
                args=(session_id, room_id, recording_stop_event),
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
