"""FastAPI 应用启动入口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from .api.router import api_router
from .core.config import settings
from .runtime import bootstrap_runtime, shutdown_runtime


def create_app() -> FastAPI:
    """构建 FastAPI 应用并挂载路由。"""

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Douyin Live Recorder API",
    )
    app.include_router(api_router)

    @app.on_event("startup")
    async def _startup() -> None:
        bootstrap_runtime()
        logging.getLogger(__name__).info("Application startup completed")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        shutdown_runtime()
        logging.getLogger(__name__).info("Application shutdown initiated")

    return app


app = create_app()


def get_application() -> FastAPI:
    """兼容旧入口。"""

    return app


__all__ = ["create_app", "app", "get_application"]
