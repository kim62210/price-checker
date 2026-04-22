"""Redis 비동기 클라이언트 싱글턴."""

from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import Settings, get_settings

_redis: Redis | None = None


def get_redis(settings: Settings | None = None) -> Redis:
    global _redis
    if _redis is None:
        settings = settings or get_settings()
        _redis = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def ping_redis(settings: Settings | None = None) -> bool:
    try:
        return bool(await get_redis(settings).ping())
    except Exception:  # noqa: BLE001
        return False
