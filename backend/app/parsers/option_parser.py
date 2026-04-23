"""옵션 텍스트 파서 오케스트레이터 (이중 캐시 + 규칙 → LLM 폴백).

입력 소스는 피벗 후 **클라이언트(Tauri 앱·브라우저 확장)가 업로드한 옵션 텍스트**
(예: ``procurement_results.product_data.options[].name``) 이며, 백엔드가 직접
크롤러로 HTML 을 fetch 하지 않는다. 파서 로직·캐시 스키마는 회귀 방지를 위해
동일하게 유지된다.

캐시는 결정론적이므로 테넌트 격리가 불필요 — Redis/PostgreSQL 모두 전역 네임스페이스
유지. 다만 감사/텔레메트리 목적으로 ``tenant_id`` 를 받으면 로그 필드에 기록한다.

설계 참고:
- ``openspec/changes/pivot-backend-multi-tenant/specs/option-quantity-parser/spec.md``
- ``openspec/changes/pivot-backend-multi-tenant/design.md`` §8
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.option_cache import OptionTextCache
from app.parsers.llm_parser import parse_with_llm
from app.parsers.regex_parser import ParseResult, parse_option_text
from app.services.cache_service import (
    cache_get_json_raw,
    cache_set_json_raw,
    make_option_text_key,
)

logger = get_logger(__name__)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


async def _get_from_postgres(
    session: AsyncSession | None, text_hash: str, parser_version: int
) -> ParseResult | None:
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
    tenant_id: int | None = None,
) -> ParseResult | None:
    """클라이언트 업로드 옵션 텍스트를 규칙 → LLM 순으로 파싱하고 결과를 캐시.

    Args:
        text: 파싱 대상 옵션 텍스트 (예: "500g x 2팩"). 비어 있으면 ``None`` 반환.
        db_session: Postgres 영구 캐시용 세션. ``None`` 이면 PG 캐시 단계 생략.
        tenant_id: 로그·감사용 테넌트 ID (선택). 실제 캐시 분리는 하지 않으며
            ``option_text_cache`` 는 전역 테이블로 유지된다.

    Returns:
        파싱 성공 시 :class:`ParseResult`, 실패 시 ``None``.
    """
    if not text or not text.strip():
        return None

    settings = get_settings()
    text_hash = _hash_text(text)
    parser_version = settings.parser_version
    log_ctx = {"tenant_id": tenant_id, "text_hash": text_hash}

    # 1. Redis 캐시 (전역 네임스페이스)
    redis_key = make_option_text_key(text, parser_version)
    cached = await cache_get_json_raw(redis_key)
    if isinstance(cached, dict) and "unit" in cached:
        logger.debug("option_parse_cache_hit", source="redis", **log_ctx)
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
        logger.debug("option_parse_cache_hit", source="postgres", **log_ctx)
        await cache_set_json_raw(
            redis_key,
            pg_cached.to_dict(),
            ttl_seconds=settings.option_cache_ttl_seconds,
        )
        return pg_cached

    # 3. 규칙 파서
    parsed = parse_option_text(text)
    model_used = "regex"

    # 4. LLM 폴백
    if parsed is None:
        logger.info("option_parse_llm_fallback", **log_ctx)
        parsed = await parse_with_llm(text, settings)
        model_used = "llm"

    if parsed is None:
        logger.info("option_parse_failed", **log_ctx)
        return None

    # 5. 캐시 저장
    await cache_set_json_raw(
        redis_key,
        parsed.to_dict(),
        ttl_seconds=settings.option_cache_ttl_seconds,
    )
    try:
        await _upsert_postgres(
            db_session, text, text_hash, parsed, model_used, parser_version
        )
    except Exception as exc:
        logger.debug("option_cache_upsert_fail", error=str(exc), **log_ctx)
    logger.debug(
        "option_parse_stored", model_used=model_used, confidence=parsed.confidence, **log_ctx
    )
    return parsed


__all__ = ["parse_option", "ParseResult"]
