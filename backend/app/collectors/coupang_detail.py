"""쿠팡 상세 수집 (Mac mini CDP 스크레이퍼 위임).

- 상세 페이지의 JSON-LD Product 로부터 가격/배송비/상품명을 얻는다.
- 스크레이퍼가 explicit 배송비를 주면 그대로, unknown 이면 로켓배송 정책으로 추정.
"""

from __future__ import annotations

from typing import Any

from app.collectors.base import DetailDTO, FetchMethod, ListingDTO, OptionDTO
from app.collectors.circuit_breaker import record_failure, record_success
from app.collectors.remote_scraper import remote_coupang_detail
from app.core.config import Settings
from app.core.exceptions import ServiceError
from app.core.logging import get_logger
from app.services.detail_cache_service import get_cached_detail, set_cached_detail
from app.services.shipping_policy import ShippingEstimate, estimate_coupang_rocket

logger = get_logger(__name__)


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


def _to_option(option_payload: dict[str, Any], listing: ListingDTO) -> OptionDTO:
    attrs_raw = option_payload.get("attrs") or {}
    if isinstance(attrs_raw, dict):
        attrs = {str(k): str(v) for k, v in attrs_raw.items()}
    else:
        attrs = {}
    return OptionDTO(
        platform_option_id=option_payload.get("platform_option_id")
        or (listing.raw_payload or {}).get("vendorItemId")
        or None,
        option_name_text=str(option_payload.get("option_name_text") or listing.raw_title),
        attrs=attrs,
        price=int(option_payload.get("price") or listing.representative_price or 0),
        stock=option_payload.get("stock") if isinstance(option_payload.get("stock"), int) else None,
        usable=bool(option_payload.get("usable", True)),
    )


def _resolve_shipping(
    shipping_fee: int,
    shipping_confidence: str,
    subtotal: int,
    is_rocket: bool,
) -> ShippingEstimate:
    if shipping_confidence == "explicit":
        return ShippingEstimate(
            fee=int(shipping_fee),
            confidence="explicit",
            free_threshold=None,
        )
    if is_rocket:
        return estimate_coupang_rocket(subtotal)
    return estimate_coupang_rocket(subtotal)


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

    try:
        payload = await remote_coupang_detail(listing.product_url, settings=settings)
    except ServiceError as exc:
        logger.info("coupang_detail_remote_failed fallback=static err=%s", exc.detail)
        await record_failure("coupang")
        detail = _fallback_detail(listing)
        await set_cached_detail("coupang", listing.product_url, detail)
        return detail

    await record_success("coupang")

    raw_options = payload.get("options") or []
    options: list[OptionDTO] = [
        _to_option(o, listing) for o in raw_options if isinstance(o, dict)
    ]
    if not options:
        detail = _fallback_detail(listing)
        await set_cached_detail("coupang", listing.product_url, detail)
        return detail

    subtotal = options[0].price
    shipping_fee = int(payload.get("shipping_fee") or 0)
    shipping_confidence = str(payload.get("shipping_confidence") or "unknown")
    free_threshold_raw = payload.get("free_shipping_threshold")
    try:
        free_threshold: int | None = (
            int(free_threshold_raw) if free_threshold_raw is not None else None
        )
    except (TypeError, ValueError):
        free_threshold = None

    shipping = _resolve_shipping(
        shipping_fee,
        shipping_confidence,
        subtotal,
        is_rocket=bool(listing.is_rocket),
    )

    fetch_method: FetchMethod = "playwright"  # remote 스크레이퍼가 Playwright/CDP 사용
    detail = DetailDTO(
        listing=listing,
        options=options,
        shipping_fee=shipping.fee,
        shipping_confidence=shipping.confidence,
        free_shipping_threshold=free_threshold or shipping.free_threshold,
        fetch_method=fetch_method,
    )
    await set_cached_detail("coupang", listing.product_url, detail)
    return detail
