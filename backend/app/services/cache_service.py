"""Redis cache-aside 헬퍼."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.db.redis import get_redis

logger = get_logger(__name__)


def make_search_key(query: str, limit: int) -> str:
    norm = query.strip().lower()
    digest = hashlib.md5(f"{norm}|{limit}".encode()).hexdigest()
    return f"search:{digest}"


def make_detail_key(platform: str, url: str) -> str:
    digest = hashlib.md5(url.encode()).hexdigest()
    return f"detail:{platform}:{digest}"


def make_option_text_key(text: str, parser_version: int) -> str:
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return f"option:{parser_version}:{digest}"


async def cache_get_json(key: str, redis: Redis | None = None) -> Any:
    client = redis or get_redis()
    payload = await client.get(key)
    if payload is None:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("cache_decode_error", key=key)
        await client.delete(key)
        return None


async def cache_set_json(
    key: str, value: Any, ttl_seconds: int, redis: Redis | None = None
) -> None:
    client = redis or get_redis()
    await client.set(key, json.dumps(value, default=str, ensure_ascii=False), ex=ttl_seconds)


async def cache_delete(key: str, redis: Redis | None = None) -> None:
    client = redis or get_redis()
    await client.delete(key)
