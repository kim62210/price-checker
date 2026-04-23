"""Redis cache-aside 헬퍼.

- 모든 테넌트 격리 캐시는 ``tenant:{tenant_id}:`` 접두사를 강제한다.
- 옵션 파싱 등 결정론적·전역 캐시는 테넌트 격리 대상이 아니므로 접두사 없이
  ``make_option_text_key`` 같은 전용 빌더가 별도 네임스페이스를 쓴다.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.db.redis import get_redis

logger = get_logger(__name__)

TENANT_PREFIX = "tenant"


def _require_tenant_id(tenant_id: int) -> int:
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise ValueError(f"tenant_id must be positive int, got {tenant_id!r}")
    return tenant_id


def tenant_namespace(tenant_id: int, key: str) -> str:
    """``tenant:{tenant_id}:`` 접두사를 적용한 full Redis 키."""
    _require_tenant_id(tenant_id)
    return f"{TENANT_PREFIX}:{tenant_id}:{key}"


def make_search_key(tenant_id: int, query: str, limit: int) -> str:
    """테넌트 격리 검색 결과 캐시 키.

    spec: ``search:{tenant_id}:{md5(normalized_query|limit)}``
    """
    _require_tenant_id(tenant_id)
    norm = query.strip().lower()
    digest = hashlib.md5(f"{norm}|{limit}".encode()).hexdigest()
    return f"search:{tenant_id}:{digest}"


def make_option_text_key(text: str, parser_version: int) -> str:
    """옵션 텍스트 파싱 결과 캐시 키 (전역 네임스페이스).

    옵션 텍스트 파싱 결과는 결정론적이므로 테넌트 격리 대상이 아니다.
    spec: ``parse:option:{sha256}`` (parser_version 포함) — ``option-quantity-parser``.
    """
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return f"option:{parser_version}:{digest}"


async def cache_get_json(
    tenant_id: int,
    key: str,
    *,
    redis: Redis | None = None,
) -> Any:
    """테넌트 스코프 JSON 캐시 조회. 디코딩 실패 시 자동 삭제."""
    _require_tenant_id(tenant_id)
    client = redis or get_redis()
    full_key = tenant_namespace(tenant_id, key)
    payload = await client.get(full_key)
    if payload is None:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("cache_decode_error", key=full_key, tenant_id=tenant_id)
        await client.delete(full_key)
        return None


async def cache_set_json(
    tenant_id: int,
    key: str,
    value: Any,
    *,
    ttl_seconds: int,
    redis: Redis | None = None,
) -> None:
    """테넌트 스코프 JSON 캐시 저장 (TTL 필수)."""
    _require_tenant_id(tenant_id)
    client = redis or get_redis()
    full_key = tenant_namespace(tenant_id, key)
    await client.set(
        full_key,
        json.dumps(value, default=str, ensure_ascii=False),
        ex=ttl_seconds,
    )


async def cache_delete(
    tenant_id: int,
    key: str,
    *,
    redis: Redis | None = None,
) -> None:
    """테넌트 스코프 캐시 삭제."""
    _require_tenant_id(tenant_id)
    client = redis or get_redis()
    await client.delete(tenant_namespace(tenant_id, key))


async def cache_get_json_raw(
    key: str,
    *,
    redis: Redis | None = None,
) -> Any:
    """전역 네임스페이스 조회 (옵션 파싱 결정론적 캐시 전용).

    테넌트 격리가 필요 없는 결정론적 캐시에만 사용한다. 일반 캐시는 반드시
    ``cache_get_json(tenant_id, ...)`` 을 써야 한다.
    """
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


async def cache_set_json_raw(
    key: str,
    value: Any,
    *,
    ttl_seconds: int,
    redis: Redis | None = None,
) -> None:
    """전역 네임스페이스 저장 (옵션 파싱 결정론적 캐시 전용)."""
    client = redis or get_redis()
    await client.set(
        key,
        json.dumps(value, default=str, ensure_ascii=False),
        ex=ttl_seconds,
    )


__all__ = [
    "TENANT_PREFIX",
    "cache_delete",
    "cache_get_json",
    "cache_get_json_raw",
    "cache_set_json",
    "cache_set_json_raw",
    "make_option_text_key",
    "make_search_key",
    "tenant_namespace",
]
