"""直播间管理API - 异步版本（符合Python-Pro规范）"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger
from typing import Dict

from app.dependencies import get_db
from app.models.live_room import LiveRoom, RecordStatus, LiveStatus
from app.schemas.live_room import (
    LiveRoomCreate,
    LiveRoomResponse,
    LiveRoomListResponse
)
from app.services.recording_manager import recording_manager

router = APIRouter(prefix="/api/live-rooms", tags=["直播间管理"])


# 平台映射常量
PLATFORM_MAP: Dict[str, str] = {
    'douyin.com': '抖音',
    'tiktok.com': 'TikTok',
    'kuaishou.com': '快手',
    'huya.com': '虎牙',
    'douyu.com': '斗鱼',
    'bilibili.com': 'B站',
    'xiaohongshu.com': '小红书',
    'yy.com': 'YY',
    'bigo.tv': 'Bigo',
    'twitch.tv': 'TwitchTV',
    'youtube.com': 'Youtube',
}


def extract_platform_from_url(url: str) -> str:
    """从直播间URL提取平台名称
    
    根据URL中的域名关键字识别直播平台。
    
    Args:
        url: 直播间URL
        
    Returns:
        平台名称（中文），如果无法识别则返回"未知平台"
        
    Examples:
        >>> extract_platform_from_url("https://live.douyin.com/123")
        '抖音'
        >>> extract_platform_from_url("https://unknown.com/live")
        '未知平台'
    """
    for domain, platform in PLATFORM_MAP.items():
        if domain in url:
            return platform
    return '未知平台'


@router.post(
    "",
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
        
    Examples:
        >>> # 请求示例
        >>> POST /api/live-rooms
        >>> {
        >>>     "url": "https://live.douyin.com/745964462470",
        >>>     "streamer_name": "测试主播",
        >>>     "quality": "原画"
        >>> }
    """
    # 异步检查URL是否已存在
    result = await db.execute(
        select(LiveRoom).where(LiveRoom.url == room.url)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "room_already_exists",
                "message": "该直播间URL已存在",
                "existing_room_id": existing.id
            }
        )
    
    # 提取平台
    platform = extract_platform_from_url(room.url)
    
    # 创建直播间记录
    db_room = LiveRoom(
        url=room.url,
        platform=platform,
        quality=room.quality or "原画",
        streamer_name=room.streamer_name,
        is_enabled=room.is_enabled if room.is_enabled is not None else True,
        auto_record=room.auto_record if room.auto_record is not None else True,
        remark=room.remark,
        record_status=RecordStatus.IDLE,
        live_status=LiveStatus.UNKNOWN
    )
    
    db.add(db_room)
    await db.commit()  # ✅ 异步commit
    await db.refresh(db_room)  # ✅ 异步refresh
    
    logger.info(
        "创建直播间",
        extra={
            "room_id": db_room.id,
            "platform": platform,
            "url": room.url,
            "enabled": db_room.is_enabled
        }
    )
    
    # 如果启用，立即启动监听（在后台线程中）
    if db_room.is_enabled:
        try:
            # 注意：recording_manager是同步的，在后台线程中运行
            import asyncio
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
            db_room.record_status = RecordStatus.ERROR
            db_room.last_error_message = str(e)
            await db.commit()
    
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
        
    Examples:
        >>> DELETE /api/live-rooms/1
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
        
    Examples:
        >>> GET /api/live-rooms/status
    """
    # 异步查询，按最后直播时间倒序
    result = await db.execute(
        select(LiveRoom)
        .order_by(LiveRoom.last_live_time.desc().nullslast())
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
        
    Examples:
        >>> GET /api/live-rooms/1/status
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
    "/{room_id}/activate",
    response_model=LiveRoomResponse,
    summary="激活录制",
    description="手动激活指定直播间的录制任务"
)
async def activate_recording(
    room_id: int,
    db: AsyncSession = Depends(get_db)
) -> LiveRoomResponse:
    """激活录制（异步）
    
    手动触发录制任务，录制状态流转：
    1. IDLE/FINISHED → PENDING（待录制）
    2. PENDING → RECORDING（录制中）
    3. RECORDING → FINISHED（录制结束）
    
    Args:
        room_id: 直播间ID
        db: 异步数据库会话（自动注入）
        
    Returns:
        更新后的直播间信息
        
    Raises:
        HTTPException: 404 - 直播间不存在
        HTTPException: 400 - 录制已在进行中
        
    Examples:
        >>> POST /api/live-rooms/1/activate
    """
    # 查询直播间
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
    
    # 检查当前录制状态
    if room.record_status == RecordStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "already_recording",
                "message": "录制已在进行中",
                "room_id": room_id,
                "current_status": room.record_status
            }
        )
    
    if room.record_status == RecordStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "already_pending",
                "message": "录制任务已在待录制队列中",
                "room_id": room_id,
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
            "room_id": room_id,
            "platform": room.platform,
            "status": "pending"
        }
    )
    
    # 在后台线程中启动录制
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            recording_manager.activate_recording,
            room_id
        )
        logger.info("录制任务已提交", extra={"room_id": room_id})
    except Exception as e:
        logger.error(
            "启动录制失败",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        room.record_status = RecordStatus.ERROR
        room.last_error_message = str(e)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "recording_start_failed",
                "message": f"启动录制失败: {str(e)}",
                "room_id": room_id
            }
        )
    
    return room


@router.post(
    "/{room_id}/stop",
    response_model=LiveRoomResponse,
    summary="停止录制",
    description="手动停止指定直播间的录制任务"
)
async def stop_recording(
    room_id: int,
    db: AsyncSession = Depends(get_db)
) -> LiveRoomResponse:
    """停止录制（异步）
    
    手动停止正在进行的录制任务：
    - RECORDING → FINISHED（录制结束）
    
    Args:
        room_id: 直播间ID
        db: 异步数据库会话（自动注入）
        
    Returns:
        更新后的直播间信息
        
    Raises:
        HTTPException: 404 - 直播间不存在
        HTTPException: 400 - 没有正在进行的录制
        
    Examples:
        >>> POST /api/live-rooms/1/stop
    """
    # 查询直播间
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
    
    # 检查当前录制状态
    if room.record_status != RecordStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "not_recording",
                "message": "没有正在进行的录制",
                "room_id": room_id,
                "current_status": room.record_status
            }
        )
    
    logger.info(
        "停止录制",
        extra={
            "room_id": room_id,
            "platform": room.platform,
            "session_id": room.current_session_id
        }
    )
    
    # 设置状态为FINISHED，录制线程会检测到并自动停止
    room.record_status = RecordStatus.FINISHED
    await db.commit()
    await db.refresh(room)
    
    return room


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
        
    Examples:
        >>> GET /api/live-rooms/monitor/status
        >>> {
        >>>     "status": "running",
        >>>     "monitor_threads": 5,
        >>>     "recording_threads": 2,
        >>>     "monitoring_rooms": [1, 2, 3, 4, 5],
        >>>     "recording_rooms": [1, 3]
        >>> }
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
