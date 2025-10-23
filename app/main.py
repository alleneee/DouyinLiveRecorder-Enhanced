"""FastAPI应用主入口 - 异步版本"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select

from app.logger import logger
from app.database_async import init_async_db, AsyncSessionLocal
from app.routes import live_rooms_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（异步）"""
    # 启动时初始化
    logger.info("初始化异步数据库...")
    await init_async_db()
    
    logger.info("加载已启用的直播间监听...")
    from app.models.live_room import LiveRoom
    from app.services.recording_manager import recording_manager
    import asyncio
    
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(LiveRoom).where(LiveRoom.is_enabled == True)
            )
            enabled_rooms = result.scalars().all()
            
            # 在后台线程中启动监听（recording_manager是同步的）
            loop = asyncio.get_event_loop()
            for room in enabled_rooms:
                try:
                    await loop.run_in_executor(
                        None,
                        recording_manager.start_monitor,
                        room.id
                    )
                    logger.info(
                        "恢复监听",
                        extra={"room_id": room.id, "url": room.url}
                    )
                except Exception as e:
                    logger.error(
                        "恢复监听失败",
                        extra={"room_id": room.id, "error": str(e)},
                        exc_info=True
                    )
        except Exception as e:
            logger.error(f"加载监听失败: {e}", exc_info=True)
    
    logger.info(
        "API服务启动成功",
        extra={
            "host": settings.api_host,
            "port": settings.api_port,
            "mode": "async"
        }
    )
    
    yield

    # 关闭时清理
    logger.info("停止所有监听和录制任务...")
    from app.services.recording_manager import recording_manager
    recording_manager.shutdown()  # ✅ 使用新的优雅关闭方法

    logger.info("API服务已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="DouyinLiveRecorder API",
    description="直播录制管理系统API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（仅核心功能）
app.include_router(live_rooms_router)


@app.get("/")
def root():
    """根路径"""
    return {
        "name": "DouyinLiveRecorder API",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """健康检查"""
    from app.services.recording_manager import recording_manager
    monitor_status = recording_manager.get_monitor_status()
    
    return {
        "status": "healthy",
        "database": "connected",
        "monitors": monitor_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )
