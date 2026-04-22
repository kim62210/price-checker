"""Redis 기반 단순 서킷브레이커."""

from __future__ import annotations

from typing import Literal

from redis.asyncio import Redis

from app.db.redis import get_redis

State = Literal["closed", "open"]

DEFAULT_OPEN_SECONDS = 60
DEFAULT_FAILURE_THRESHOLD = 3


def _key(platform: str) -> str:
    return f"circuit:{platform}:state"


def _failcount_key(platform: str) -> str:
    return f"circuit:{platform}:failcount"


async def is_open(platform: str, redis: Redis | None = None) -> bool:
    client = redis or get_redis()
    return bool(await client.get(_key(platform)))


async def record_failure(
    platform: str,
    *,
    threshold: int = DEFAULT_FAILURE_THRESHOLD,
    open_seconds: int = DEFAULT_OPEN_SECONDS,
    redis: Redis | None = None,
) -> State:
    client = redis or get_redis()
    fc = await client.incr(_failcount_key(platform))
    await client.expire(_failcount_key(platform), open_seconds * 2)
    if fc >= threshold:
        await client.set(_key(platform), "open", ex=open_seconds)
        await client.delete(_failcount_key(platform))
        return "open"
    return "closed"


async def record_success(platform: str, redis: Redis | None = None) -> None:
    client = redis or get_redis()
    await client.delete(_key(platform), _failcount_key(platform))
