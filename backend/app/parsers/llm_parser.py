"""LLM 폴백 파서 (OpenAI)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.redis import get_redis
from app.parsers.regex_parser import ParseResult
from app.parsers.unit_dictionary import UnitCode

logger = get_logger(__name__)

_SYSTEM_PROMPT = """너는 한국어 쇼핑몰 옵션 텍스트에서 수량 정보를 추출하는 도구다.
다음 키를 가진 JSON 객체로만 응답하라:
- unit: 기준단위 ("g", "ml", "ct", "sheet" 중 하나)
- unit_quantity: 총 환산 수량 (숫자, 예: 24000 의미는 24,000 ml)
- piece_count: 낱개 개수 (정수)
- pack_count: 팩/박스 묶음 개수 (정수, 없으면 1)
- bonus_quantity: 증정 수량 (정수, 없으면 0)
- raw_match: 파싱에 사용한 원본 부분 문자열
판단이 불가능하면 {"unit":"ct","unit_quantity":null,...} 을 반환하라."""

_MONTH_KEY_FMT = "llm:tokens:%Y%m"


def _current_month_key() -> str:
    return datetime.now(UTC).strftime(_MONTH_KEY_FMT)


def _month_expireat() -> int:
    now = datetime.now(UTC)
    first_next = (now.replace(day=1) + timedelta(days=32)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return int(first_next.timestamp())


async def _consume_tokens(tokens: int) -> bool:
    client = get_redis()
    key = _current_month_key()
    total = await client.incrby(key, tokens)
    if total == tokens:
        await client.expireat(key, _month_expireat())
    cap = get_settings().llm_monthly_token_cap
    return cap == 0 or total <= cap


def _coerce_result(raw: dict[str, Any], source_text: str, model_label: str) -> ParseResult | None:
    unit = raw.get("unit")
    unit_qty = raw.get("unit_quantity")
    if unit not in ("g", "ml", "ct", "sheet") or unit_qty in (None, 0, 0.0):
        return None
    if not isinstance(unit_qty, str | int | float):
        return None
    try:
        qty_float = float(unit_qty)
    except (TypeError, ValueError):
        return None
    piece = int(raw.get("piece_count") or 0)
    pack = int(raw.get("pack_count") or 1)
    bonus = int(raw.get("bonus_quantity") or 0)
    return ParseResult(
        unit=unit,
        unit_quantity=qty_float,
        piece_count=piece,
        pack_count=pack,
        bonus_quantity=bonus,
        confidence="llm",
        raw_match=str(raw.get("raw_match") or source_text)[:256],
    )


async def parse_with_llm(text: str, settings: Settings | None = None) -> ParseResult | None:
    settings = settings or get_settings()
    if not text.strip():
        return None

    allowed = await _consume_tokens(500)
    if not allowed:
        logger.warning("llm_monthly_cap_exceeded")
        return None

    if settings.openai_api_key:
        try:
            from openai import AsyncOpenAI

            client_oa = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
            resp = await client_oa.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            message = resp.choices[0].message.content or "{}"
            raw = json.loads(message)
            parsed = _coerce_result(raw, text, f"openai/{settings.openai_model}")
            if parsed:
                return parsed
        except Exception as exc:  # noqa: BLE001
            logger.info("openai_fallback_fail", error=str(exc))

    return None


UnitCode = UnitCode  # re-export alias
