"""录制管理器 - 核心服务"""
import asyncio
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.models.video_segment import VideoSegment, SegmentStatus
from app.config import settings


class RecordingManager:
    """录制管理器 - 负责持续监听和录制管理"""
    
    def __init__(self):
        self.monitor_threads: Dict[int, threading.Thread] = {}  # {room_id: monitor_thread}
        self.recording_threads: Dict[int, threading.Thread] = {}  # {room_id: recording_thread}
        self.stop_flags: Dict[int, threading.Event] = {}  # {room_id: stop_event}
        self.lock = threading.Lock()
    
    def start_monitor(self, room_id: int):
        """启动直播间监听 - 持续循环直到删除或禁用"""
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
                
                # 等待线程结束
                if room_id in self.monitor_threads:
                    self.monitor_threads[room_id].join(timeout=5)
                    del self.monitor_threads[room_id]
                
                del self.stop_flags[room_id]
                
                # 停止录制线程
                if room_id in self.recording_threads:
                    del self.recording_threads[room_id]
    
    def _monitor_worker(self, room_id: int, stop_event: threading.Event):
        """监听工作线程 - 持续循环监听直播状态"""
        logger.info(f"监听线程启动: room_id={room_id}")
        db = SessionLocal()
        
        try:
            while not stop_event.is_set():
                try:
                    # 获取直播间信息
                    room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
                    if not room:
                        logger.warning(f"直播间不存在，退出监听: room_id={room_id}")
                        break
                    
                    if not room.is_enabled:
                        logger.info(f"直播间已禁用，退出监听: room_id={room_id}")
                        break
                    
                    # 更新最后检查时间
                    room.last_check_time = datetime.now()
                    
                    # 检查直播状态
                    is_live = self._check_live_status(room)
                    old_status = room.live_status
                    room.live_status = LiveStatus.LIVE if is_live else LiveStatus.OFFLINE
                    
                    if is_live and old_status != LiveStatus.LIVE:
                        # 刚开播，启动录制
                        logger.info(f"检测到开播: room_id={room_id}, url={room.url}")
                        room.last_live_time = datetime.now()
                        self._start_recording(db, room)
                    
                    elif not is_live and old_status == LiveStatus.LIVE:
                        # 刚下播，停止录制
                        logger.info(f"检测到下播: room_id={room_id}")
                        self._stop_recording(db, room)
                    
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"监听异常: room_id={room_id}, error={e}")
                    db.rollback()
                
                # 等待下次检查（可中断）
                stop_event.wait(settings.check_interval)
        
        finally:
            db.close()
            logger.info(f"监听线程退出: room_id={room_id}")
    
    def _check_live_status(self, room: LiveRoom) -> bool:
        """检查直播状态 - 使用LiveRecorder"""
        try:
            from app.services.live_recorder import LiveRecorder
            
            recorder = LiveRecorder(proxy_addr=None, cookies={})
            is_live = asyncio.run(recorder.check_live_status(room.url))
            return is_live
            
        except Exception as e:
            logger.error(f"检查直播状态失败: room_id={room.id}, error={e}")
            return False
    
    def _start_recording(self, db: Session, room: LiveRoom):
        """启动录制任务 - 2表设计：使用session_id标识会话"""
        # 生成新的会话ID
        session_id = str(uuid.uuid4())
        session_started_at = datetime.now()
        
        # 更新房间的当前会话信息
        room.current_session_id = session_id
        room.current_session_started_at = session_started_at
        room.record_status = RecordStatus.RECORDING
        db.commit()
        
        # 启动录制线程
        thread = threading.Thread(
            target=self._recording_worker,
            args=(session_id, room.id),
            daemon=True,
            name=f"Record-Session-{session_id[:8]}"
        )
        thread.start()
        self.recording_threads[room.id] = thread
        
        logger.info(f"创建录制会话: session_id={session_id}, room_id={room.id}")
    
    def _stop_recording(self, db: Session, room: LiveRoom):
        """停止录制任务 - 2表设计：更新会话结束信息"""
        if room.current_session_id:
            # 计算本次会话统计
            session_ended_at = datetime.now()
            session_duration = 0
            if room.current_session_started_at:
                session_duration = int((session_ended_at - room.current_session_started_at).total_seconds())
            
            # 统计本次会话的切片数
            segment_count = db.query(VideoSegment).filter(
                VideoSegment.room_id == room.id,
                VideoSegment.session_id == room.current_session_id
            ).count()
            
            # 更新"上次会话"信息
            room.last_session_id = room.current_session_id
            room.last_session_title = room.current_session_title
            room.last_session_started_at = room.current_session_started_at
            room.last_session_ended_at = session_ended_at
            room.last_session_duration = session_duration
            room.last_session_segment_count = segment_count
            
            # 更新总统计
            room.total_duration += session_duration
            
            # 清空当前会话信息
            room.current_session_id = None
            room.current_session_title = None
            room.current_session_started_at = None
            room.current_stream_url = None
            room.current_ffmpeg_pid = None
        
        room.record_status = RecordStatus.IDLE
        db.commit()
        
        logger.info(f"停止录制会话: session_id={room.last_session_id}, room_id={room.id}")
    
    def _recording_worker(self, session_id: str, room_id: int):
        """录制工作线程 - 执行实际的FFmpeg录制"""
        db = SessionLocal()
        logger.info(f"录制线程启动: session_id={session_id}, room_id={room_id}")
        
        try:
            from app.services.live_recorder import LiveRecorder
            import subprocess
            import os
            
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            
            if not room:
                logger.error(f"房间不存在: room_id={room_id}")
                return
            
            # 获取直播流信息 - 使用完整URL让spider解析平台和房间ID
            recorder = LiveRecorder()
            logger.info(
                f"获取直播流信息: room_id={room_id}, url={room.url}, "
                f"platform={room.platform}, platform_room_id={room.platform_room_id}, quality={room.quality}"
            )
            stream_info = asyncio.run(recorder.get_live_stream_info(room.url, room.quality))

            if not stream_info['is_live'] or not stream_info['stream_url']:
                logger.warning(
                    f"直播未开播或获取流地址失败: room_id={room_id}, url={room.url}, "
                    f"platform={room.platform}, platform_room_id={room.platform_room_id}"
                )
                room.record_status = RecordStatus.ERROR
                room.last_error_message = "直播未开播或获取流地址失败"
                db.commit()
                return

            # 保存流地址和会话标题
            room.current_stream_url = stream_info['stream_url']
            room.current_session_title = stream_info.get('title', '')
            logger.info(f"流地址获取成功: stream_url={stream_info['stream_url'][:50]}...")
            db.commit()
            
            # 创建保存目录 - 使用绝对路径
            project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            save_dir = os.path.join(
                project_root,
                settings.video_save_path.lstrip('./'),
                room.streamer_name or f"room_{room_id}"
            )
            os.makedirs(save_dir, exist_ok=True)
            logger.info(f"保存目录: {save_dir}")
            
            # 启动FFmpeg录制(分段录制)
            segment_index = 0
            ffmpeg_process = None
            
            try:
                while room.live_status == LiveStatus.LIVE:
                    # 记录分片开始时间
                    segment_start_time = datetime.now()
                    
                    # 生成文件名 - 使用录制格式
                    timestamp = segment_start_time.strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}_seg{segment_index}.{settings.video_record_format.lower()}"
                    file_path = os.path.join(save_dir, filename)

                    # FFmpeg命令(分段录制,最长录制segment_duration秒)
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-i', stream_info['stream_url'],
                        '-c', 'copy',
                        '-t', str(settings.segment_duration),  # 最长录制时长
                        '-f', settings.ffmpeg_format,  # 使用正确的FFmpeg格式参数
                        file_path
                    ]
                    
                    # 启动FFmpeg
                    logger.info(f"启动FFmpeg录制: segment={segment_index}, file={filename}")
                    logger.info(f"FFmpeg命令: {' '.join(ffmpeg_cmd)}")
                    
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # 保存进程PID
                    room.current_ffmpeg_pid = ffmpeg_process.pid
                    db.commit()
                    
                    # 等待FFmpeg完成并获取输出
                    stdout, stderr = ffmpeg_process.communicate()
                    return_code = ffmpeg_process.returncode
                    
                    # 记录FFmpeg输出
                    if return_code != 0:
                        logger.error(f"FFmpeg执行失败: return_code={return_code}")
                        logger.error(f"FFmpeg stderr: {stderr[-1000:]}")  # 只记录最后1000字符
                        break
                    else:
                        logger.info(f"FFmpeg执行成功: segment={segment_index}")
                    
                    # 记录分片结束时间
                    segment_end_time = datetime.now()
                    
                    # 检查文件是否生成
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        logger.info(f"切片文件生成成功: {file_path}, size={file_size} bytes")
                        
                        # 计算实际录制时长
                        actual_duration = int((segment_end_time - segment_start_time).total_seconds())
                        
                        # 创建视频切片记录
                        self.on_segment_created(
                            db=db,
                            session_id=session_id,
                            room_id=room_id,
                            file_path=file_path,
                            segment_index=segment_index,
                            segment_start_time=segment_start_time,
                            segment_end_time=segment_end_time,
                            duration=actual_duration
                        )
                        
                        segment_index += 1
                    else:
                        logger.error(f"切片文件未生成: {file_path}")
                        break
                    
                    # 刷新房间状态
                    db.refresh(room)
                    
            finally:
                # 确保FFmpeg进程被终止
                if ffmpeg_process and ffmpeg_process.poll() is None:
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait(timeout=5)
            
        except Exception as e:
            logger.error(f"录制异常: session_id={session_id}, error={e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if room:
                room.record_status = RecordStatus.ERROR
                room.last_error_message = str(e)
                room.error_count += 1
                room.last_error_time = datetime.now()
                db.commit()
        
        finally:
            db.close()
            logger.info(f"录制线程退出: session_id={session_id}")
    
    def on_segment_created(self, db: Session, session_id: str, room_id: int, 
                          file_path: str, segment_index: int,
                          segment_start_time: datetime, segment_end_time: datetime,
                          duration: int):
        """切片创建回调 - 创建video_segments记录并触发OSS上传"""
        import os
        from app.services.oss_uploader import oss_uploader
        
        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                return
            
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 创建切片记录
            video_segment = VideoSegment(
                room_id=room_id,
                session_id=session_id,
                segment_index=segment_index,
                segment_started_at=segment_start_time,
                segment_ended_at=segment_end_time,
                duration=duration,
                status=SegmentStatus.COMPLETED,
                completed_at=datetime.now()
            )
            db.add(video_segment)
            
            # 更新房间统计
            room.total_segment_count += 1
            room.total_file_size += file_size
            
            db.commit()
            db.refresh(video_segment)
            
            logger.info(f"切片记录创建: segment_id={video_segment.id}, index={segment_index}")
            
            # 异步上传视频和音频（一起处理）
            threading.Thread(
                target=self._upload_video_and_audio,
                args=(video_segment.id, file_path),
                daemon=True
            ).start()
        
        except Exception as e:
            logger.error(f"切片记录创建失败: error={e}")
    
    def _upload_video_and_audio(self, segment_id: int, video_path: str):
        """录制完成后处理：抽取音频 → 上传音视频 → 回写数据库 → 删除本地文件
        
        处理流程：
        1. 抽取音频（从视频中提取音频文件）
        2. 并行上传视频和音频到OSS
        3. 回写数据库（oss_video_url, oss_audio_url）
        4. 删除本地文件（视频+音频）
        
        Args:
            segment_id: 视频分片ID
            video_path: 视频文件路径
        """
        from app.services.oss_uploader import oss_uploader
        from app.services.audio_extractor import audio_extractor
        import os
        import concurrent.futures
        
        db = SessionLocal()
        audio_path = None
        
        try:
            video_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if not video_segment:
                logger.warning(f"视频分片不存在: segment_id={segment_id}")
                return
            
            # 更新状态为处理中
            video_segment.status = SegmentStatus.UPLOADING
            db.commit()
            
            logger.info(f"开始处理分片: segment_id={segment_id}, video={video_path}")
            
            # ========== 1. 抽取音频 ==========
            logger.info(f"[1/4] 抽取音频: segment_id={segment_id}")
            audio_path = audio_extractor.extract_audio(
                video_path=video_path,
                delete_source=False
            )
            
            if not audio_path:
                raise Exception("音频抽取失败")
            
            logger.info(f"音频抽取成功: {audio_path}")
            
            # ========== 2. 并行上传视频和音频到OSS ==========
            logger.info(f"[2/4] 并行上传视频和音频到OSS: segment_id={segment_id}")
            
            video_url = None
            audio_url = None
            
            # 使用线程池并行上传
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # 提交上传任务
                video_future = executor.submit(oss_uploader.upload_file, video_path)
                audio_future = executor.submit(oss_uploader.upload_file, audio_path)
                
                # 等待视频上传完成
                try:
                    video_result = video_future.result()
                    video_url = video_result.get('url')
                    logger.info(
                        "视频上传成功",
                        extra={
                            "segment_id": segment_id,
                            "url": video_url,
                            "size": video_result.get('size'),
                            "upload_type": video_result.get('upload_type')
                        }
                    )
                except Exception as e:
                    logger.error(f"视频上传失败: {e}")
                    raise
                
                # 等待音频上传完成
                try:
                    audio_result = audio_future.result()
                    audio_url = audio_result.get('url')
                    logger.info(
                        "音频上传成功",
                        extra={
                            "segment_id": segment_id,
                            "url": audio_url,
                            "size": audio_result.get('size')
                        }
                    )
                except Exception as e:
                    logger.error(f"音频上传失败: {e}")
                    raise
            
            logger.info(f"音视频上传全部完成: segment_id={segment_id}")
            
            # ========== 3. 回写数据库 ==========
            logger.info(f"[3/4] 回写数据库: segment_id={segment_id}")
            video_segment.oss_video_url = video_url
            video_segment.oss_audio_url = audio_url
            video_segment.status = SegmentStatus.UPLOADED
            db.commit()
            
            logger.info(
                "数据库更新成功",
                extra={
                    "segment_id": segment_id,
                    "video_url": video_url,
                    "audio_url": audio_url
                }
            )
            
            # ========== 4. 删除本地文件 ==========
            logger.info(f"[4/4] 删除本地文件: segment_id={segment_id}")
            
            # 删除视频
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"本地视频已删除: {video_path}")
            
            # 删除音频
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"本地音频已删除: {audio_path}")
            
            logger.info(f"✅ 分片处理完成: segment_id={segment_id}")
        
        except Exception as e:
            logger.error(
                "分片上传处理失败",
                extra={
                    "segment_id": segment_id,
                    "video": video_path,
                    "audio": audio_path,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # 更新失败状态
            video_segment = db.query(VideoSegment).filter(VideoSegment.id == segment_id).first()
            if video_segment:
                video_segment.status = SegmentStatus.FAILED
                video_segment.error_message = f"上传处理失败: {str(e)}"
                db.commit()
            
            # 失败时也尝试清理临时音频文件
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info(f"清理临时音频文件: {audio_path}")
                except:
                    pass
        
        finally:
            db.close()
    
    def activate_recording(self, room_id: int):
        """手动激活录制 - 直接启动录制任务"""
        db = SessionLocal()
        
        try:
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if not room:
                logger.error(f"房间不存在: room_id={room_id}")
                return
            
            # 检查是否已在录制
            if room.record_status == RecordStatus.RECORDING:
                logger.warning(f"录制已在进行中: room_id={room_id}")
                return
            
            # 更新状态为录制中
            room.record_status = RecordStatus.RECORDING
            
            # 生成新的会话ID
            session_id = str(uuid.uuid4())
            session_started_at = datetime.now()
            
            # 更新房间的当前会话信息
            room.current_session_id = session_id
            room.current_session_started_at = session_started_at
            db.commit()
            
            logger.info(f"手动激活录制: room_id={room_id}, session_id={session_id}")
            
            # 启动录制线程
            thread = threading.Thread(
                target=self._manual_recording_worker,
                args=(session_id, room_id),
                daemon=True,
                name=f"ManualRecord-{session_id[:8]}"
            )
            thread.start()
            self.recording_threads[room_id] = thread
            
        except Exception as e:
            logger.error(f"激活录制失败: room_id={room_id}, error={e}")
            if room:
                room.record_status = RecordStatus.ERROR
                room.last_error_message = str(e)
                db.commit()
        finally:
            db.close()
    
    def _manual_recording_worker(self, session_id: str, room_id: int):
        """手动录制工作线程 - 执行实际的FFmpeg录制"""
        db = SessionLocal()
        logger.info(f"手动录制线程启动: session_id={session_id}, room_id={room_id}")
        
        try:
            from app.services.live_recorder import LiveRecorder
            import subprocess
            import os
            
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            
            if not room:
                logger.error(f"房间不存在: room_id={room_id}")
                return
            
            # 获取直播流信息 - 使用完整URL让spider解析平台和房间ID
            recorder = LiveRecorder()
            logger.info(
                f"获取直播流信息: room_id={room_id}, url={room.url}, "
                f"platform={room.platform}, platform_room_id={room.platform_room_id}, quality={room.quality}"
            )
            stream_info = asyncio.run(recorder.get_live_stream_info(room.url, room.quality))

            if not stream_info['is_live'] or not stream_info['stream_url']:
                logger.warning(
                    f"直播未开播或获取流地址失败: room_id={room_id}, url={room.url}, "
                    f"platform={room.platform}, platform_room_id={room.platform_room_id}, "
                    f"is_live={stream_info.get('is_live')}, stream_url={'有' if stream_info.get('stream_url') else '无'}"
                )
                room.record_status = RecordStatus.ERROR
                room.last_error_message = "直播未开播或获取流地址失败"
                db.commit()
                return

            # 保存流地址和会话标题
            room.current_stream_url = stream_info['stream_url']
            room.current_session_title = stream_info.get('title', '')
            room.live_status = LiveStatus.LIVE
            logger.info(f"流地址获取成功: stream_url={stream_info['stream_url'][:50]}...")
            db.commit()
            
            # 创建保存目录 - 使用绝对路径
            project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            save_dir = os.path.join(
                project_root,
                settings.video_save_path.lstrip('./'),
                room.streamer_name or f"room_{room_id}"
            )
            os.makedirs(save_dir, exist_ok=True)
            logger.info(f"保存目录: {save_dir}")
            
            # 启动FFmpeg录制(分段录制)
            segment_index = 0
            ffmpeg_process = None
            
            try:
                # 持续录制直到直播结束或手动停止
                while room.record_status == RecordStatus.RECORDING:
                    # 记录分片开始时间
                    segment_start_time = datetime.now()
                    
                    # 生成文件名 - 使用录制格式
                    timestamp = segment_start_time.strftime("%Y%m%d_%H%M%S")
                    filename = f"{timestamp}_seg{segment_index}.{settings.video_record_format.lower()}"
                    file_path = os.path.join(save_dir, filename)

                    # FFmpeg命令(分段录制,最长录制segment_duration秒)
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-i', stream_info['stream_url'],
                        '-c', 'copy',
                        '-t', str(settings.segment_duration),  # 最长录制时长
                        '-f', settings.ffmpeg_format,  # 使用正确的FFmpeg格式参数
                        file_path
                    ]
                    
                    # 启动FFmpeg
                    logger.info(f"启动FFmpeg录制: segment={segment_index}, file={filename}")
                    logger.info(f"FFmpeg命令: {' '.join(ffmpeg_cmd)}")
                    
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # 保存进程PID
                    room.current_ffmpeg_pid = ffmpeg_process.pid
                    db.commit()
                    
                    # 等待FFmpeg完成并获取输出
                    stdout, stderr = ffmpeg_process.communicate()
                    return_code = ffmpeg_process.returncode
                    
                    # 记录FFmpeg输出
                    if return_code != 0:
                        logger.error(f"FFmpeg执行失败: return_code={return_code}")
                        logger.error(f"FFmpeg stderr: {stderr[-1000:]}")  # 只记录最后1000字符
                        break
                    else:
                        logger.info(f"FFmpeg执行成功: segment={segment_index}")
                    
                    # 记录分片结束时间
                    segment_end_time = datetime.now()
                    
                    # 检查文件是否生成
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        logger.info(f"切片文件生成成功: {file_path}, size={file_size} bytes")
                        
                        # 计算实际录制时长
                        actual_duration = int((segment_end_time - segment_start_time).total_seconds())
                        
                        # 创建视频切片记录
                        self.on_segment_created(
                            db=db,
                            session_id=session_id,
                            room_id=room_id,
                            file_path=file_path,
                            segment_index=segment_index,
                            segment_start_time=segment_start_time,
                            segment_end_time=segment_end_time,
                            duration=actual_duration
                        )
                        
                        segment_index += 1
                    else:
                        logger.error(f"切片文件未生成: {file_path}")
                        break
                    
                    # 刷新房间状态
                    db.refresh(room)
                    
            finally:
                # 确保FFmpeg进程被终止
                if ffmpeg_process and ffmpeg_process.poll() is None:
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait(timeout=5)
                
                # 更新录制结束状态
                self._finish_recording(db, room)
            
        except Exception as e:
            logger.error(f"手动录制异常: session_id={session_id}, error={e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            room = db.query(LiveRoom).filter(LiveRoom.id == room_id).first()
            if room:
                room.record_status = RecordStatus.ERROR
                room.last_error_message = str(e)
                room.error_count += 1
                room.last_error_time = datetime.now()
                db.commit()
        
        finally:
            db.close()
            logger.info(f"手动录制线程退出: session_id={session_id}")
    
    def _finish_recording(self, db: Session, room: LiveRoom):
        """结束录制任务 - 更新为FINISHED状态"""
        if room.current_session_id:
            # 计算本次会话统计
            session_ended_at = datetime.now()
            session_duration = 0
            if room.current_session_started_at:
                session_duration = int((session_ended_at - room.current_session_started_at).total_seconds())
            
            # 统计本次会话的切片数
            segment_count = db.query(VideoSegment).filter(
                VideoSegment.room_id == room.id,
                VideoSegment.session_id == room.current_session_id
            ).count()
            
            # 更新"上次会话"信息
            room.last_session_id = room.current_session_id
            room.last_session_title = room.current_session_title
            room.last_session_started_at = room.current_session_started_at
            room.last_session_ended_at = session_ended_at
            room.last_session_duration = session_duration
            room.last_session_segment_count = segment_count
            
            # 更新总统计
            room.total_duration += session_duration
            
            # 清空当前会话信息
            room.current_session_id = None
            room.current_session_title = None
            room.current_session_started_at = None
            room.current_stream_url = None
            room.current_ffmpeg_pid = None
        
        # 设置为录制结束状态
        room.record_status = RecordStatus.FINISHED
        room.live_status = LiveStatus.OFFLINE
        db.commit()
        
        logger.info(f"录制结束: session_id={room.last_session_id}, room_id={room.id}")
    
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
