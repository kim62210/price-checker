"""FastAPI 앱 팩토리."""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__


def create_app() -> FastAPI:
    app = FastAPI(
        title="lowest-price",
        version=__version__,
        description="친구용 비공개 네이버/쿠팡 최저가 비교 서비스",
        docs_url="/docs",
        redoc_url=None,
    )

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    return app


app = create_app()
