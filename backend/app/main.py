"""FastAPI 앱 팩토리."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import register_middleware
from app.db.session import get_engine
from app.models import Base

logger = get_logger(__name__)


def _configure_sentry(dsn: str | None, environment: str) -> None:
    if not dsn:
        return
    sentry_sdk.init(dsn=dsn, environment=environment, traces_sample_rate=0.05)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 수명주기. MVP 단계에서는 Alembic 대신 Base.metadata.create_all 로 초기 스키마를 맞춘다."""
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("schema_ready")
    except Exception as exc:  # noqa: BLE001
        logger.warning("schema_init_failed", error=str(exc))
    try:
        yield
    finally:
        logger.info("shutdown_cleanup")
        await engine.dispose()


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
        lifespan=lifespan,
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

    return app


app = create_app()
