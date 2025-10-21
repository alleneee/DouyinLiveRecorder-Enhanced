"""直播间管理API - 异步版本（符合Python-Pro规范）"""
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import asyncio

from app.logger import logger
from app.dependencies import get_db
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.schemas.live_room import (
    LiveRoomCreate,
    LiveRoomResponse,
    LiveRoomListResponse,
    LiveStatusCheckRequest,
    LiveStatusCheckResponse,
    ActivateRecordingRequest,
    StopRecordingRequest,
    StopRecordingResponse
)
from app.services.recording_manager import recording_manager
from app.services.live_room_service import live_room_service

router = APIRouter(prefix="/api/live-rooms", tags=["直播间管理"])


@router.post(
    "/create",
    response_model=LiveRoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增监控直播间",
    description="创建新的直播间监控，自动启动持续监听线程"
)
async def create_live_room(
    room: LiveRoomCreate,
    db: AsyncSession = Depends(get_db)
) -> LiveRoomResponse:
    """新增监控直播间（异步）
    
    创建后会自动执行以下操作：
    1. 验证URL是否已存在
    2. 识别直播平台
    3. 创建数据库记录
    4. 启动持续监听线程（如果enabled=True）
    5. 检测到开播自动录制
    6. 自动切片并上传OSS
    
    Args:
        room: 直播间创建请求数据
        db: 异步数据库会话（自动注入）
        
    Returns:
        创建成功的直播间详细信息
        
    Raises:
        HTTPException: 400 - URL已存在
        HTTPException: 500 - 内部服务器错误
    """
    # 检查URL是否已存在
    existing = await live_room_service.check_url_exists(db, room.url)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "room_already_exists",
                "message": "该直播间URL已存在",
                "existing_room_id": existing.id
            }
        )
    
    # 调用服务层创建直播间
    db_room = await live_room_service.create_live_room(db, room)
    
    # 如果启用，启动监听线程
    if db_room.is_enabled:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                recording_manager.start_monitor,
                db_room.id
            )
            logger.info("启动监听", extra={"room_id": db_room.id})
        except Exception as e:
            logger.error(
                "启动监听失败",
                extra={"room_id": db_room.id, "error": str(e)},
                exc_info=True
            )
    
    return db_room


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除监控直播间",
    description="停止监听并删除直播间记录（级联删除所有视频切片）"
)
async def delete_live_room(
    room_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """删除监控直播间（异步）
    
    删除操作会执行以下步骤：
    1. 停止监听线程
    2. 停止正在进行的录制
    3. 删除数据库记录
    4. 级联删除所有相关的视频切片记录
    
    Args:
        room_id: 直播间ID
        db: 异步数据库会话（自动注入）
        
    Raises:
        HTTPException: 404 - 直播间不存在
    """
    # 异步查询
    result = await db.execute(
        select(LiveRoom).where(LiveRoom.id == room_id)
    )
    room = result.scalar_one_or_none()
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "room_not_found",
                "message": "直播间不存在",
                "room_id": room_id
            }
        )
    
    # 异步停止监听（在executor中运行同步代码）
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            recording_manager.stop_monitor,
            room_id
        )
        logger.info("停止监听", extra={"room_id": room_id})
    except Exception as e:
        logger.error(
            "停止监听失败",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
    
    # 异步删除记录
    await db.delete(room)
    await db.commit()
    
    logger.info(
        "删除直播间",
        extra={"room_id": room_id, "url": room.url}
    )


@router.get(
    "/status",
    response_model=LiveRoomListResponse,
    summary="查看所有直播间状态",
    description="获取所有直播间的实时录制状态"
)
async def get_rooms_status(
    db: AsyncSession = Depends(get_db)
) -> LiveRoomListResponse:
    """查看所有直播间录制状态（异步）
    
    返回信息包括：
    - 基本信息：平台、主播、URL
    - 实时状态：直播状态、录制状态
    - 当前会话：会话ID、标题、开始时间
    - 统计信息：总会话数、总切片数、总时长等
    - 上次直播：上次会话信息
    
    Args:
        db: 异步数据库会话（自动注入）
        
    Returns:
        所有直播间的列表和统计信息
    """
    # 异步查询，按更新时间倒序(最近活跃的在前面)
    result = await db.execute(
        select(LiveRoom)
        .order_by(LiveRoom.updated_at.desc())
    )
    rooms = result.scalars().all()
    
    return LiveRoomListResponse(
        total=len(rooms),
        page=1,
        page_size=len(rooms),
        items=list(rooms)
    )


@router.get(
    "/{room_id}/status",
    response_model=LiveRoomResponse,
    summary="查看单个直播间状态",
    description="获取指定直播间的详细录制状态"
)
async def get_room_status(
    room_id: int,
    db: AsyncSession = Depends(get_db)
) -> LiveRoomResponse:
    """查看单个直播间录制状态（异步）
    
    返回详细信息：
    - 实时状态：是否在线、是否录制中
    - 当前会话：会话ID、标题、已录制时长
    - 历史统计：总共录制了多少次、多少时间
    - FFmpeg进程：进程PID
    - 错误信息：如果有错误会显示
    
    Args:
        room_id: 直播间ID
        db: 异步数据库会话（自动注入）
        
    Returns:
        直播间详细信息
        
    Raises:
        HTTPException: 404 - 直播间不存在
    """
    result = await db.execute(
        select(LiveRoom).where(LiveRoom.id == room_id)
    )
    room = result.scalar_one_or_none()
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "room_not_found",
                "message": "直播间不存在",
                "room_id": room_id
            }
        )
    
    return room


@router.post(
    "/activate",
    response_model=LiveRoomResponse,
    summary="激活录制",
    description="手动激活指定直播间的录制任务"
)
async def activate_recording(
    request: ActivateRecordingRequest,
    db: AsyncSession = Depends(get_db)
) -> LiveRoomResponse:
    """激活录制（异步）
    
    通过直播间URL激活录制任务。
    URL会被解析为平台和房间ID，然后通过业务主键查询。
    
    手动触发录制任务，录制状态流转：
    1. PENDING/FINISHED → PENDING（待录制）
    2. PENDING → RECORDING（录制中）
    3. RECORDING → FINISHED（录制结束）
    
    Args:
        request: 激活录制请求，包含直播间URL
        db: 异步数据库会话（自动注入）
        
    Returns:
        更新后的直播间信息
        
    Raises:
        HTTPException: 404 - 直播间不存在
        HTTPException: 400 - 录制已在进行中
    """
    # 通过URL解析查询直播间（使用 platform + platform_room_id）
    room = await live_room_service.get_room_by_url_parsed(db, request.url)
    
    if not room:
        # 提取平台和房间ID用于错误提示
        platform = live_room_service.extract_platform_from_url(request.url)
        platform_room_id = live_room_service.extract_room_id_from_url(request.url)
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "room_not_found",
                "message": "直播间不存在，请先创建监控",
                "url": request.url,
                "platform": platform,
                "platform_room_id": platform_room_id
            }
        )
    
    # 检查当前录制状态
    if room.record_status == RecordStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "already_recording",
                "message": "录制已在进行中",
                "platform": room.platform,
                "platform_room_id": room.platform_room_id,
                "current_status": room.record_status
            }
        )
    
    if room.record_status == RecordStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "already_pending",
                "message": "录制任务已在待录制队列中",
                "platform": room.platform,
                "platform_room_id": room.platform_room_id,
                "current_status": room.record_status
            }
        )
    
    # 设置为待录制状态
    room.record_status = RecordStatus.PENDING
    room.is_enabled = True  # 确保启用
    await db.commit()
    await db.refresh(room)
    
    logger.info(
        "激活录制",
        extra={
            "db_id": room.id,
            "platform": room.platform,
            "platform_room_id": room.platform_room_id,
            "url": request.url,
            "status": "pending"
        }
    )
    
    # 在后台线程中启动录制,传入外部提供的 session_id
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            recording_manager.activate_recording,
            room.id,
            request.session_id  # 传入外部 session_id
        )
        logger.info(
            "录制任务已提交",
            extra={
                "db_id": room.id,
                "platform": room.platform,
                "platform_room_id": room.platform_room_id
            }
        )
    except Exception as e:
        logger.error(
            "启动录制失败",
            extra={
                "db_id": room.id,
                "platform": room.platform,
                "platform_room_id": room.platform_room_id,
                "error": str(e)
            },
            exc_info=True
        )
        room.record_status = RecordStatus.ERROR
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "recording_start_failed",
                "message": f"启动录制失败: {str(e)}",
                "platform": room.platform,
                "platform_room_id": room.platform_room_id
            }
        )
    
    return room


@router.post(
    "/stop",
    response_model=StopRecordingResponse,
    summary="停止录制",
    description="手动停止指定直播间的录制任务"
)
async def stop_recording(
    request: StopRecordingRequest,
    db: AsyncSession = Depends(get_db)
) -> StopRecordingResponse:
    """停止录制（异步）

    通过直播间URL停止录制任务。
    URL会被解析为平台和房间ID，然后通过业务主键查询。

    手动停止正在进行的录制任务：
    - RECORDING → FINISHED（录制结束）

    Args:
        request: 停止录制请求，包含直播间URL
        db: 异步数据库会话（自动注入）

    Returns:
        是否成功停止录制（true/false）

    Raises:
        HTTPException: 404 - 直播间不存在
        HTTPException: 400 - 没有正在进行的录制
    """
    # 通过URL解析查询直播间（使用 platform + platform_room_id）
    room = await live_room_service.get_room_by_url_parsed(db, request.url)

    if not room:
        # 提取平台和房间ID用于错误提示
        platform = live_room_service.extract_platform_from_url(request.url)
        platform_room_id = live_room_service.extract_room_id_from_url(request.url)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "room_not_found",
                "message": "直播间不存在，请先创建监控",
                "url": request.url,
                "platform": platform,
                "platform_room_id": platform_room_id
            }
        )

    # 检查当前录制状态
    if room.record_status != RecordStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "not_recording",
                "message": "没有正在进行的录制",
                "platform": room.platform,
                "platform_room_id": room.platform_room_id,
                "current_status": room.record_status,
                "url": request.url
            }
        )

    logger.info(
        "停止录制",
        extra={
            "db_id": room.id,
            "platform": room.platform,
            "platform_room_id": room.platform_room_id,
            "url": request.url,
            "session_id": room.current_session_id
        }
    )

    # 直接通知录制线程停止(即时响应)
    from app.services.recording_manager import recording_manager
    stopped = recording_manager.stop_recording_manually(room.id)

    if stopped:
        # 设置状态为FINISHED
        room.record_status = RecordStatus.FINISHED
        await db.commit()
        await db.refresh(room)

        logger.info(
            "录制已停止",
            extra={
                "db_id": room.id,
                "platform": room.platform,
                "platform_room_id": room.platform_room_id
            }
        )
        return StopRecordingResponse(success=True)
    else:
        # 录制线程不存在,但仍更新状态
        room.record_status = RecordStatus.FINISHED
        await db.commit()

        logger.warning(
            "录制线程不存在,已更新状态",
            extra={
                "db_id": room.id,
                "platform": room.platform,
                "platform_room_id": room.platform_room_id
            }
        )
        return StopRecordingResponse(success=True)


@router.get(
    "/monitor/status",
    summary="查看监听器状态",
    description="获取系统监听线程和录制线程的运行状态"
)
async def get_monitor_status() -> Dict:
    """查看监听器状态（异步）
    
    返回系统级监控信息：
    - 总监听线程数
    - 总录制线程数
    - 正在监听的房间ID列表
    - 正在录制的房间ID列表
    
    Returns:
        监听器状态信息字典
    """
    # 在executor中运行同步代码
    import asyncio
    loop = asyncio.get_event_loop()
    status_info = await loop.run_in_executor(
        None,
        recording_manager.get_monitor_status
    )
    
    return {
        "status": "running",
        "monitor_threads": status_info["total_monitors"],
        "recording_threads": status_info["total_recordings"],
        "monitoring_rooms": status_info["monitor_rooms"],
        "recording_rooms": status_info["recording_rooms"]
    }


@router.post(
    "/check-live-status",
    response_model=LiveStatusCheckResponse,
    summary="检测直播状态",
    description="快速检测指定直播间是否正在直播，支持50+平台"
)
async def check_live_status(
    request: LiveStatusCheckRequest
) -> LiveStatusCheckResponse:
    """检测直播间状态（异步）
    
    无需预先添加直播间，即可快速检测任意平台直播间的实时状态。
    
    支持平台：
    - 国内：抖音、快手、B站、虎牙、斗鱼、YY、小红书等
    - 国际：TikTok、Twitch、YouTube等
    
    Args:
        request: 直播状态检测请求（只需URL）
        
    Returns:
        是否正在直播（true/false）
        
    Raises:
        HTTPException: 500 - 检测失败（网络错误、平台不支持等）
    """
    from app.services.live_recorder import LiveRecorder
    
    try:
        # 创建 LiveRecorder 实例
        recorder = LiveRecorder(proxy_addr=None, cookies={})
        
        # 检测直播状态（使用默认画质）
        is_live = await recorder.check_live_status(url=request.url)
        
        logger.info(
            "检测直播状态",
            extra={
                "url": request.url,
                "is_live": is_live
            }
        )
        
        return LiveStatusCheckResponse(is_live=is_live)
        
    except Exception as e:
        logger.error(
            "检测直播状态失败",
            extra={"url": request.url, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "check_failed",
                "message": f"检测直播状态失败: {str(e)}",
                "url": request.url
            }
        )


@router.post(
    "/query-by-url",
    response_model=Dict,
    summary="基于URL查询直播间完整信息",
    description="""
    通过直播间URL查询room表和segment表的全部信息
    
    **功能**:
    - 解析URL提取平台和房间ID
    - 查询直播间基础信息
    - 查询所有视频分片信息
    - 返回统计数据
    
    **支持平台**:
    - 抖音 (douyin)
    - 快手 (kuaishou)  
    - B站 (bilibili)
    - 斗鱼 (douyu)
    - 虎牙 (huya)
    - 其他平台...
    """
)
async def query_room_by_url(
    url: str,
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    基于URL查询直播间完整信息
    
    Args:
        url: 直播间URL
        db: 数据库会话
        
    Returns:
        包含room和segments完整信息的响应
    """
    from app.utils.url_parser import parse_live_url
    from app.models.video_segment import VideoSegment
    from app.schemas.room_detail import (
        LiveRoomDetail, 
        VideoSegmentDetail, 
        RoomDetailResponse
    )
    
    # 1. 解析URL
    platform, room_id = parse_live_url(url)
    
    if not platform or not room_id:
        return {
            "success": False,
            "message": "无法解析URL,请检查URL格式是否正确",
            "data": None,
            "parsed_platform": platform,
            "parsed_room_id": room_id
        }
    
    # 2. 查询直播间信息
    result = await db.execute(
        select(LiveRoom)
        .where(LiveRoom.platform == platform)
        .where(LiveRoom.platform_room_id == room_id)
    )
    room = result.scalar_one_or_none()
    
    if not room:
        return {
            "success": False,
            "message": f"未找到对应的直播间 (平台:{platform}, 房间ID:{room_id})",
            "data": None,
            "parsed_platform": platform,
            "parsed_room_id": room_id
        }
    
    # 3. 查询所有视频分片
    segments_result = await db.execute(
        select(VideoSegment)
        .where(VideoSegment.room_id == room.id and VideoSegment.platform == platform)
        .order_by(VideoSegment.created_at.desc(), VideoSegment.segment_index.asc())
    )
    segments = segments_result.scalars().all()

    # 4. 计算统计信息
    stats_result = await db.execute(
        select(
            func.count(func.distinct(VideoSegment.session_id)).label('total_sessions'),
            func.count(VideoSegment.id).label('total_segments'),
            func.sum(VideoSegment.duration).label('total_duration'),
            func.min(VideoSegment.segment_started_at).label('first_segment_at'),
            func.max(VideoSegment.segment_ended_at).label('last_segment_at')
        )
        .where(VideoSegment.room_id == room.id)
    )
    stats = stats_result.first()
    
    # 5. 构建响应
    room_detail = LiveRoomDetail.model_validate(room)
    segment_details = [VideoSegmentDetail.model_validate(seg) for seg in segments]
    
    statistics = {
        "total_sessions": stats.total_sessions or 0,
        "total_segments": stats.total_segments or 0,
        "total_duration_seconds": stats.total_duration or 0,
        "total_duration_hours": round((stats.total_duration or 0) / 3600, 2),
        "first_segment_at": stats.first_segment_at.isoformat() if stats.first_segment_at else None,
        "last_segment_at": stats.last_segment_at.isoformat() if stats.last_segment_at else None,
    }
    
    detail_response = RoomDetailResponse(
        room=room_detail,
        segments=segment_details,
        total_segments=len(segment_details),
        statistics=statistics
    )
    
    return {
        "success": True,
        "message": "查询成功",
        "data": detail_response.model_dump(),
        "parsed_platform": platform,
        "parsed_room_id": room_id
    }
