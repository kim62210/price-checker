"""헬스 체크 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette import status

from app.db.redis import ping_redis
from app.db.session import session_scope

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="프로세스 생존")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", summary="DB/Redis 연결 준비 상태")
async def ready() -> JSONResponse:
    detail: dict[str, str] = {}
    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        detail["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        detail["postgres"] = f"error:{exc}"

    detail["redis"] = "ok" if await ping_redis() else "error"

    ok = all(value == "ok" for value in detail.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ok else "not_ready", **detail},
    )
