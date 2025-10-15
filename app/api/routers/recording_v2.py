"""录制 API v2 - 使用新的模块化架构。"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.runtime import ensure_runtime
from app.core.platforms.legacy_adapter import LegacyPlatformHandler
from app.core.processing import VideoConverter, PushNotifier
from app.core.recording.models import Room
from app.core.recording.segment_worker import SegmentRecordingWorker, SegmentConfig
from app.core.recording.continuous_worker import ContinuousRecordingWorker, ContinuousConfig
from app.core.config import settings
from app.db.session import get_db
from app.models.room import RoomORM
from app.legacy.utils import logger

router = APIRouter(prefix="/recording", tags=["recording"])


# 请求/响应模型
class StartRecordingRequest(BaseModel):
    """启动录制请求。"""
    
    room_id: int = Field(..., description="房间ID（必须先通过 /rooms 接口创建房间）")


class StopRecordingRequest(BaseModel):
    """停止录制请求。"""
    
    room_id: int = Field(..., description="房间ID")


class RecordingStatus(BaseModel):
    """录制状态响应。"""
    
    status: str = Field(..., description="状态: started/running/stopped/error")
    room_id: int
    url: str
    nickname: str
    message: Optional[str] = None


class PlatformTestRequest(BaseModel):
    """平台测试请求。"""
    
    url: str = Field(..., description="直播间 URL")
    quality: str = Field("OD", description="画质代码")


class StreamInfoResponse(BaseModel):
    """直播流信息响应。"""
    
    platform: str
    is_live: bool
    real_url: Optional[str] = None
    anchor_name: Optional[str] = None
    title: Optional[str] = None
    quality: Optional[str] = None


# 全局工作器管理
_active_workers: dict[str, tuple[RecordingWorker, threading.Thread, threading.Event]] = {}


@router.post("/start", response_model=RecordingStatus)
async def start_recording_v2(
    request: StartRecordingRequest,
    background_tasks: BackgroundTasks,
) -> RecordingStatus:
    """启动录制（基于房间ID）。
    
    流程：
    1. 根据 room_id 查询房间信息
    2. 获取房间的录制配置
    3. 启动录制工作器
    """
    try:
        # 从数据库查询房间信息
        db = next(get_db())
        try:
            from app.models.room import RoomORM
            room_orm = db.query(RoomORM).filter(RoomORM.id == request.room_id).first()
            if not room_orm:
                raise HTTPException(status_code=404, detail=f"房间 ID {request.room_id} 不存在")
        finally:
            db.close()
        
        # 检查是否已在录制
        if room_orm.url in _active_workers:
            return RecordingStatus(
                status="running",
                room_id=room_orm.id,
                url=room_orm.url,
                nickname=room_orm.nickname,
                message="该直播间已在录制中",
            )
        
        # 创建平台处理器
        handler = LegacyPlatformHandler(
            cookies_map={},  # 可以从配置读取
        )
        
        # 创建房间对象
        room = Room(
            url=room_orm.url,
            nickname=room_orm.nickname,
            quality=room_orm.quality,
        )
        
        # 创建停止事件
        stop_event = threading.Event()
        
        # 根据房间配置选择录制模式
        if room_orm.enable_segment_recording:
            # 分段录制模式（时长由配置决定）
            logger.info(f"使用分段录制模式: room_id={room_orm.id}, url={room_orm.url}, segment_duration={room_orm.segment_duration}秒")
            
            # 使用房间配置
            segment_duration = room_orm.segment_duration
            
            config = SegmentConfig(
                segment_duration=segment_duration,
                video_save_path="downloads",
                video_save_type=room_orm.video_save_type,
                folder_by_author=True,
                oss_enabled=settings.oss_enabled,  # 使用全局配置
                oss_access_key_id=settings.oss_access_key_id,
                oss_access_key_secret=settings.oss_access_key_secret,
                oss_endpoint=settings.oss_endpoint,
                oss_bucket_name=settings.oss_bucket_name,
            )
            
            def on_segment_complete(file_path: str, segment_data: dict) -> None:
                logger.info(f"分段录制完成: {file_path}")
                logger.info(f"分段信息: segment_index={segment_data['segment_index']}, "
                          f"file_size={segment_data['file_size']}, "
                          f"oss_url={segment_data.get('oss_url', 'N/A')}")
            
            worker = SegmentRecordingWorker(
                room=room,
                handler=handler,
                config=config,
                on_segment_complete=on_segment_complete,
            )
        else:
            # 连续录制模式（录制到直播结束）
            logger.info(f"使用连续录制模式（录制到直播结束）: room_id={room_orm.id}, url={room_orm.url}")
            
            config = ContinuousConfig(
                video_save_path="downloads",
                video_save_type=room_orm.video_save_type,
                folder_by_author=True,
                converts_to_mp4=room_orm.run_post_process,
                delete_origin_file=True,
            )
            
            def on_complete(file_path: str) -> None:
                logger.info(f"连续录制完成，已触发后处理: {file_path}")
            
            worker = ContinuousRecordingWorker(
                room=room,
                handler=handler,
                config=config,
                on_complete=on_complete,
            )
        
        # 在后台线程中运行工作器
        def run_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(worker.start(stop_event))
            finally:
                loop.close()
                # 清理
                if room_orm.url in _active_workers:
                    del _active_workers[room_orm.url]
        
        thread = threading.Thread(target=run_worker, name=f"Worker-{room_orm.nickname}")
        thread.daemon = True
        thread.start()
        
        # 保存到活跃工作器列表
        _active_workers[room_orm.url] = (worker, thread, stop_event)
        
        return RecordingStatus(
            status="started",
            room_id=room_orm.id,
            url=room_orm.url,
            nickname=room_orm.nickname,
            message="录制已启动",
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动录制失败: {str(e)}")


@router.post("/stop", response_model=RecordingStatus)
async def stop_recording_v2(request: StopRecordingRequest) -> RecordingStatus:
    """停止录制（基于房间ID）。"""
    # 从数据库查询房间信息
    db = next(get_db())
    try:
        from app.models.room import RoomORM
        room_orm = db.query(RoomORM).filter(RoomORM.id == request.room_id).first()
        if not room_orm:
            raise HTTPException(status_code=404, detail=f"房间 ID {request.room_id} 不存在")
    finally:
        db.close()
    
    if room_orm.url not in _active_workers:
        raise HTTPException(status_code=404, detail="未找到该直播间的录制任务")
    
    worker, thread, stop_event = _active_workers[room_orm.url]
    stop_event.set()
    thread.join(timeout=5)
    del _active_workers[room_orm.url]
    
    return RecordingStatus(
        status="stopped",
        room_id=room_orm.id,
        url=room_orm.url,
        nickname=room_orm.nickname,
        message="录制已停止",
    )


@router.get("/status", response_model=list[RecordingStatus])
async def list_recording_status_v2() -> list[RecordingStatus]:
    """列出所有活跃的录制任务。"""
    results = []
    
    # 从数据库查询房间信息来获取room_id
    db = next(get_db())
    try:
        from app.models.room import RoomORM
        for url, (worker, thread, stop_event) in _active_workers.items():
            room_orm = db.query(RoomORM).filter(RoomORM.url == url).first()
            if room_orm:
                results.append(RecordingStatus(
                    status="running",
                    room_id=room_orm.id,
                    url=url,
                    nickname=worker.room.nickname,
                    message="录制中",
                ))
    finally:
        db.close()
    
    return results


@router.post("/test-platform", response_model=StreamInfoResponse)
async def test_platform_v2(request: PlatformTestRequest) -> StreamInfoResponse:
    """测试平台连接并获取直播流信息。
    
    用于调试和验证平台处理器是否正常工作。
    """
    try:
        # 创建平台处理器
        handler = LegacyPlatformHandler(
            cookies_map={},  # 可以从配置读取
        )
        
        # 获取流信息
        stream_info = await handler.get_stream_info(request.url, request.quality)
        
        if not stream_info:
            return StreamInfoResponse(
                platform=handler.platform_name,
                is_live=False,
            )
        
        return StreamInfoResponse(
            platform=handler.platform_name,
            is_live=stream_info.is_live,
            real_url=stream_info.real_url,
            anchor_name=stream_info.anchor_name,
            title=stream_info.title,
            quality=stream_info.quality,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流信息失败: {str(e)}")


@router.post("/convert")
async def convert_video_v2(
    file_path: str = Query(..., description="视频文件路径"),
    to_h264: bool = Query(False, description="是否重新编码为 H264"),
    background_tasks: BackgroundTasks = None,
) -> dict:
    """转换视频格式。"""
    try:
        converter = VideoConverter(
            convert_to_h264=to_h264,
            delete_origin=True,
        )
        
        # 在后台任务中执行转换
        background_tasks.add_task(converter.convert_to_mp4, file_path)
        
        return {
            "status": "converting",
            "source": file_path,
            "message": "转换任务已启动",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动转换失败: {str(e)}")


__all__ = ["router"]
