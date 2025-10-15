"""统一路由入口。"""

from fastapi import APIRouter

from app.api.routers import recordings, rooms
from app.core.config import settings


api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(rooms.router)
api_router.include_router(recordings.router)


__all__ = ["api_router"]
