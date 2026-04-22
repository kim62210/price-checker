"""옵션 텍스트 파서 오케스트레이터 (이중 캐시 + 규칙 → LLM 폴백)."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.redis import get_redis
from app.models.option_cache import OptionTextCache
from app.parsers.llm_parser import parse_with_llm
from app.parsers.regex_parser import ParseResult, parse_option_text
from app.services.cache_service import cache_get_json, cache_set_json, make_option_text_key

logger = get_logger(__name__)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def _get_from_postgres(session: AsyncSession | None, text_hash: str, parser_version: int) -> ParseResult | None:
    if session is None:
        return None
    stmt = select(OptionTextCache).where(
        OptionTextCache.text_hash == text_hash,
        OptionTextCache.parser_version == parser_version,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    data = row.parsed_json
    return ParseResult(
        unit=data["unit"],
        unit_quantity=float(data["unit_quantity"]),
        piece_count=int(data.get("piece_count", 0)),
        pack_count=int(data.get("pack_count", 1)),
        bonus_quantity=int(data.get("bonus_quantity", 0)),
        confidence=str(data.get("confidence", "rule")),
        raw_match=str(data.get("raw_match", "")),
    )


async def _upsert_postgres(
    session: AsyncSession | None,
    text: str,
    text_hash: str,
    parsed: ParseResult,
    model_used: str,
    parser_version: int,
) -> None:
    if session is None:
        return
    stmt = pg_insert(OptionTextCache).values(
        text_hash=text_hash,
        raw_text=text[:4096],
        parsed_json=parsed.to_dict(),
        model_used=model_used,
        parser_version=parser_version,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["text_hash"])
    await session.execute(stmt)
    await session.commit()


async def parse_option(
    text: str,
    *,
    db_session: AsyncSession | None = None,
) -> ParseResult | None:
    """규칙 → LLM 순으로 시도하고 결과를 Redis + Postgres 에 캐시."""
    if not text or not text.strip():
        return None

    settings = get_settings()
    text_hash = _hash_text(text)
    parser_version = settings.parser_version

    # 1. Redis 캐시
    redis_key = make_option_text_key(text, parser_version)
    cached = await cache_get_json(redis_key)
    if isinstance(cached, dict) and "unit" in cached:
        return ParseResult(
            unit=cached["unit"],
            unit_quantity=float(cached["unit_quantity"]),
            piece_count=int(cached.get("piece_count", 0)),
            pack_count=int(cached.get("pack_count", 1)),
            bonus_quantity=int(cached.get("bonus_quantity", 0)),
            confidence=str(cached.get("confidence", "rule")),
            raw_match=str(cached.get("raw_match", "")),
        )

    # 2. Postgres 캐시
    pg_cached = await _get_from_postgres(db_session, text_hash, parser_version)
    if pg_cached is not None:
        await cache_set_json(redis_key, pg_cached.to_dict(), ttl_seconds=settings.option_cache_ttl_seconds)
        return pg_cached

    # 3. 규칙 파서
    parsed = parse_option_text(text)
    model_used = "regex"

    # 4. LLM 폴백
    if parsed is None:
        parsed = await parse_with_llm(text, settings)
        model_used = "llm"

    if parsed is None:
        return None

    # 5. 캐시 저장
    await cache_set_json(
        redis_key, parsed.to_dict(), ttl_seconds=settings.option_cache_ttl_seconds
    )
    try:
        await _upsert_postgres(db_session, text, text_hash, parsed, model_used, parser_version)
    except Exception as exc:  # noqa: BLE001
        logger.debug("option_cache_upsert_fail", error=str(exc))
    return parsed


__all__ = ["parse_option", "ParseResult"]
# prevent unused import
_UNUSED = json
