"""FastAPI 앱 팩토리."""

from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.api.v1.router import api_router
from app.collectors.http_client import close_http_client
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import register_middleware

logger = get_logger(__name__)


def _configure_sentry(dsn: str | None, environment: str) -> None:
    if not dsn:
        return
    sentry_sdk.init(dsn=dsn, environment=environment, traces_sample_rate=0.05)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    _configure_sentry(settings.sentry_dsn, settings.environment)

    app = FastAPI(
        title="lowest-price",
        version=__version__,
        description="친구용 비공개 네이버/쿠팡 최저가 비교 서비스",
        docs_url="/docs" if settings.environment != "prod" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_middleware(app)
    register_exception_handlers(app)
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    app.include_router(api_router)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # pragma: no cover - lifecycle
        logger.info("shutdown_cleanup")
        await close_http_client()

    return app


app = create_app()
