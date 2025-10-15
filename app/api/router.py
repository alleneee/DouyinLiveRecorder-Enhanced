"""统一路由入口。"""

from fastapi import APIRouter

from app.api.routers import rooms, recording_v2
from app.core.config import settings


api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(rooms.router)
api_router.include_router(recording_v2.router)  # 新的模块化录制 API


__all__ = ["api_router"]
