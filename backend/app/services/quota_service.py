"""네이버 일일 쿼터 카운터 (Redis INCR + KST 00:00 EXPIREAT)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.db.redis import get_redis

KST = timezone(timedelta(hours=9))


def _today_kst() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _tomorrow_midnight_kst_epoch() -> int:
    now = datetime.now(KST)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(tomorrow.timestamp())


def quota_key(platform: str, day: str | None = None) -> str:
    return f"quota:{platform}:{day or _today_kst()}"


async def incr_quota(platform: str, amount: int = 1, redis: Redis | None = None) -> int:
    """오늘 카운터를 amount 만큼 증가시키고 현재 값을 반환한다."""
    client = redis or get_redis()
    key = quota_key(platform)
    current = await client.incrby(key, amount)
    if current == amount:
        await client.expireat(key, _tomorrow_midnight_kst_epoch())
    return int(current)


async def get_quota(platform: str, redis: Redis | None = None) -> int:
    client = redis or get_redis()
    value = await client.get(quota_key(platform))
    return int(value) if value else 0


async def is_quota_exceeded(
    platform: str,
    settings: Settings | None = None,
    redis: Redis | None = None,
) -> bool:
    settings = settings or get_settings()
    caps = {"naver": settings.naver_daily_quota}
    cap = caps.get(platform)
    if cap is None:
        return False
    current = await get_quota(platform, redis=redis)
    return current >= cap


async def remaining_quota(
    platform: str,
    settings: Settings | None = None,
    redis: Redis | None = None,
) -> int | None:
    settings = settings or get_settings()
    caps = {"naver": settings.naver_daily_quota}
    cap = caps.get(platform)
    if cap is None:
        return None
    current = await get_quota(platform, redis=redis)
    return max(cap - current, 0)
