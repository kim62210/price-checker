"""네이버 스마트스토어 상세 페이지 수집.

- 스마트스토어는 SPA + CAPTCHA/봇 탐지 때문에 기본 경로는 Playwright.
- 우선 페이지 내 window.__PRELOADED_STATE__ 또는 \\`__NEXT_DATA__\\` JSON 을 추출 시도.
- 실패 시 표시 가격·배송비 기반으로 최소 옵션 1개 fallback 을 생성한다(upstream 파이프라인 가용성 유지).
- 외부 판매처(스마트스토어 아닌) 링크는 representative_price 기반 fallback 만 수행.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.collectors.base import DetailDTO, ListingDTO, OptionDTO
from app.collectors.playwright_runner import rendered_page
from app.core.config import Settings
from app.core.logging import get_logger
from app.services.detail_cache_service import get_cached_detail, set_cached_detail
from app.services.shipping_policy import estimate_smartstore_generic

logger = get_logger(__name__)

_STATE_RE = re.compile(
    r"window\.__PRELOADED_STATE__\s*=\s*JSON\.parse\([\"'](.+?)[\"']\)\s*;", re.DOTALL
)
_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>', re.DOTALL
)


def _looks_like_smartstore(url: str) -> bool:
    return "smartstore.naver.com" in url or "shopping.naver.com" in url


def _fallback_detail(listing: ListingDTO) -> DetailDTO:
    subtotal = listing.representative_price or 0
    shipping = estimate_smartstore_generic(subtotal)
    option = OptionDTO(
        platform_option_id=None,
        option_name_text=listing.raw_title,
        attrs={},
        price=subtotal,
        stock=None,
        usable=True,
    )
    return DetailDTO(
        listing=listing,
        options=[option],
        shipping_fee=shipping.fee,
        shipping_confidence=shipping.confidence,
        free_shipping_threshold=shipping.free_threshold,
        fetch_method="static",
    )


def _parse_options_from_state(state: dict[str, Any]) -> list[OptionDTO]:
    """window.__PRELOADED_STATE__ 에서 옵션 리스트를 시도 추출.

    스마트스토어는 스토어·상품마다 데이터 구조가 조금씩 달라, 공통적으로 쓰이는
    optionCombinations 또는 productOptionCombinations 키를 best-effort 로 찾아본다.
    """
    options: list[OptionDTO] = []
    candidates: list[list[dict[str, Any]]] = []

    def _collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, list) and key in {
                    "optionCombinations",
                    "productOptionCombinations",
                    "optionSimpleList",
                }:
                    candidates.append([v for v in value if isinstance(v, dict)])
                elif isinstance(value, dict | list):
                    _collect(value)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(state)

    for bucket in candidates:
        for item in bucket:
            price = item.get("price")
            if price is None:
                continue
            name_parts: list[str] = []
            for idx in range(1, 5):
                value = item.get(f"optionName{idx}")
                if value:
                    name_parts.append(str(value))
            option_text = " ".join(name_parts) or str(item.get("optionName") or "")
            if not option_text:
                continue
            options.append(
                OptionDTO(
                    platform_option_id=str(item.get("id")) if item.get("id") else None,
                    option_name_text=option_text,
                    attrs={f"axis_{i}": name_parts[i] for i in range(len(name_parts))},
                    price=int(price),
                    stock=int(item.get("stockQuantity") or 0) or None,
                    usable=bool(item.get("usable", True)),
                )
            )
    return options


def _parse_shipping_fee(state: dict[str, Any]) -> int | None:
    """best-effort: 자유 키 탐색으로 baseFee/deliveryFee 수치 추출."""

    def _walk(obj: Any) -> int | None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"baseFee", "deliveryFee", "baseDeliveryFee"} and isinstance(
                    value, int | float
                ):
                    return int(value)
                found = _walk(value)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = _walk(item)
                if found is not None:
                    return found
        return None

    return _walk(state)


async def fetch_naver_detail(
    listing: ListingDTO,
    settings: Settings,
    *,
    force_refresh: bool = False,
) -> DetailDTO:
    if not force_refresh:
        cached = await get_cached_detail("naver", listing.product_url)
        if cached is not None:
            return cached

    if not _looks_like_smartstore(listing.product_url):
        detail = _fallback_detail(listing)
        await set_cached_detail("naver", listing.product_url, detail)
        return detail

    detail = await _render_and_extract(listing)
    await set_cached_detail("naver", listing.product_url, detail)
    return detail


async def _render_and_extract(listing: ListingDTO) -> DetailDTO:
    try:
        async with rendered_page(listing.product_url, wait_selector="body") as page:
            html = await page.content()
    except Exception as exc:  # noqa: BLE001
        logger.warning("naver_playwright_failed", error=str(exc), url=listing.product_url)
        return _fallback_detail(listing)

    state_match = _STATE_RE.search(html)
    state: dict[str, Any] | None = None
    if state_match:
        try:
            raw = bytes(state_match.group(1), "utf-8").decode("unicode_escape")
            state = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.debug("naver_state_decode_fail", error=str(exc))
            state = None
    if state is None:
        next_match = _NEXT_DATA_RE.search(html)
        if next_match:
            try:
                state = json.loads(next_match.group(1))
            except json.JSONDecodeError as exc:
                logger.debug("naver_next_data_decode_fail", error=str(exc))
                state = None

    if state is None:
        return _fallback_detail(listing)

    options = _parse_options_from_state(state)
    if not options:
        return _fallback_detail(listing)

    shipping_fee_raw = _parse_shipping_fee(state)
    subtotal = options[0].price
    shipping = estimate_smartstore_generic(
        subtotal,
        seller_default_fee=shipping_fee_raw,
    )
    return DetailDTO(
        listing=listing,
        options=options,
        shipping_fee=shipping.fee,
        shipping_confidence=shipping.confidence,
        free_shipping_threshold=shipping.free_threshold,
        fetch_method="playwright",
    )
