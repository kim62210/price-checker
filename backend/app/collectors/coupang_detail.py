"""쿠팡 상세 페이지 수집 (정적 파싱 → Playwright 폴백).

- 우선 httpx 로 HTML 을 fetch 하고 `exports.sdp = {...};` JSON 블록을 추출해 옵션/가격을 파싱한다.
- 실패 또는 차단 감지 시 Playwright 로 재시도.
- 그래도 실패하면 listing.representative_price 기반 fallback 옵션 1개를 생성한다.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.collectors.base import DetailDTO, FetchMethod, ListingDTO, OptionDTO
from app.collectors.circuit_breaker import record_failure
from app.collectors.http_client import get_http_client
from app.collectors.playwright_runner import rendered_page
from app.core.config import Settings
from app.core.exceptions import BotBlockedError
from app.core.logging import get_logger
from app.core.security import browser_like_headers
from app.services.detail_cache_service import get_cached_detail, set_cached_detail
from app.services.shipping_policy import estimate_coupang_rocket

logger = get_logger(__name__)

_SDP_RE = re.compile(r"exports\.sdp\s*=\s*(\{.+?\});", re.DOTALL)
_BLOCK_MARKERS = (
    "pardon our interruption",
    "access denied",
    "sorry! access denied",
    "reference #",
    "to discuss automated access",
)


def _fallback_detail(listing: ListingDTO) -> DetailDTO:
    price = listing.representative_price or 0
    shipping = estimate_coupang_rocket(price)
    option = OptionDTO(
        platform_option_id=(listing.raw_payload or {}).get("vendorItemId") or None,
        option_name_text=listing.raw_title,
        attrs={},
        price=price,
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


def _parse_sdp(html: str) -> dict[str, Any] | None:
    match = _SDP_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _extract_options(sdp: dict[str, Any]) -> list[OptionDTO]:
    options: list[OptionDTO] = []
    candidates: list[dict[str, Any]] = []
    for key in ("allVendorItems", "vendorItems", "products", "itemOptions", "options"):
        value = sdp.get(key)
        if isinstance(value, list):
            candidates.extend(v for v in value if isinstance(v, dict))
    for item in candidates:
        price = item.get("salesPrice") or item.get("price") or item.get("originalPrice")
        if price is None:
            continue
        name_text = (
            item.get("name")
            or item.get("title")
            or item.get("optionName")
            or item.get("displayName")
            or ""
        )
        attrs_raw = item.get("attributes") or item.get("attributeList") or {}
        attrs: dict[str, str] = {}
        if isinstance(attrs_raw, list):
            for attr in attrs_raw:
                key = attr.get("name") or attr.get("attributeName")
                val = attr.get("value") or attr.get("attributeValue")
                if key and val:
                    attrs[str(key)] = str(val)
        elif isinstance(attrs_raw, dict):
            attrs = {str(k): str(v) for k, v in attrs_raw.items()}

        options.append(
            OptionDTO(
                platform_option_id=str(item.get("vendorItemId") or item.get("itemId") or ""),
                option_name_text=str(name_text),
                attrs=attrs,
                price=int(price),
                stock=item.get("stockQuantity") if isinstance(item.get("stockQuantity"), int) else None,
                usable=item.get("soldOut") is not True,
            )
        )
    return options


def _extract_shipping_fee(sdp: dict[str, Any]) -> int | None:
    for key in ("shippingFee", "deliveryCharge", "shippingCharge"):
        value = sdp.get(key)
        if isinstance(value, int | float):
            return int(value)
    return None


async def fetch_coupang_detail(
    listing: ListingDTO,
    settings: Settings,
    *,
    force_refresh: bool = False,
) -> DetailDTO:
    if not force_refresh:
        cached = await get_cached_detail("coupang", listing.product_url)
        if cached is not None:
            return cached

    html, method = await _fetch_html(listing)
    sdp = _parse_sdp(html) if html else None
    if sdp is None and html is not None and method == "static":
        html2, method = await _render_detail(listing)
        if html2 is not None:
            sdp = _parse_sdp(html2)

    if sdp is None:
        detail = _fallback_detail(listing)
    else:
        options = _extract_options(sdp)
        if not options:
            detail = _fallback_detail(listing)
        else:
            subtotal = options[0].price
            shipping_fee = _extract_shipping_fee(sdp)
            is_rocket = bool(listing.is_rocket)
            if is_rocket:
                shipping = estimate_coupang_rocket(subtotal)
            elif shipping_fee is not None:
                from app.services.shipping_policy import ShippingEstimate

                shipping = ShippingEstimate(
                    fee=shipping_fee,
                    confidence="explicit",
                    free_threshold=None,
                )
            else:
                shipping = estimate_coupang_rocket(subtotal)
            detail = DetailDTO(
                listing=listing,
                options=options,
                shipping_fee=shipping.fee,
                shipping_confidence=shipping.confidence,
                free_shipping_threshold=shipping.free_threshold,
                fetch_method=method,
            )
    await set_cached_detail("coupang", listing.product_url, detail)
    return detail


async def _fetch_html(listing: ListingDTO) -> tuple[str | None, FetchMethod]:
    client = get_http_client()
    try:
        response = await client.get(
            listing.product_url, headers=browser_like_headers("https://www.coupang.com/")
        )
        if response.status_code == 403:
            await record_failure("coupang")
            return None, "static"
        response.raise_for_status()
        html = response.text
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        logger.info("coupang_detail_http_error", error=str(exc))
        return None, "static"

    if any(marker in html[:5000].lower() for marker in _BLOCK_MARKERS):
        await record_failure("coupang")
        raise BotBlockedError(detail="coupang_detail_blocked")
    return html, "static"


async def _render_detail(listing: ListingDTO) -> tuple[str | None, FetchMethod]:
    try:
        async with rendered_page(listing.product_url, wait_selector="body") as page:
            html = await page.content()
        return html, "playwright"
    except Exception as exc:  # noqa: BLE001
        logger.warning("coupang_detail_playwright_fail", error=str(exc))
        return None, "static"
