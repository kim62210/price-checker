"""네이버 스마트스토어 상세 수집 (Mac mini CDP 스크레이퍼 위임).

- 스마트스토어는 SPA + 캡차/봇 탐지 때문에 OCI 내부에서 직접 접근 불가.
- Tailnet 의 개인 Chrome + CDP 기반 Mac mini 스크레이퍼에 위임한다.
- 스크레이퍼가 캡차 등으로 실패하면 (naver_state_missing / timeout) 대표가 기반
  static fallback 으로 복구하여 전체 파이프라인 가용성을 유지한다.
- 외부 판매처(스마트스토어 아닌) 링크는 항상 대표가 fallback 만 수행.
"""

from __future__ import annotations

from typing import Any

from app.collectors.base import DetailDTO, FetchMethod, ListingDTO, OptionDTO
from app.collectors.remote_scraper import remote_naver_detail
from app.core.config import Settings
from app.core.exceptions import BotBlockedError, UpstreamError, UpstreamTimeoutError
from app.core.logging import get_logger
from app.services.detail_cache_service import get_cached_detail, set_cached_detail
from app.services.shipping_policy import ShippingEstimate, estimate_smartstore_generic

logger = get_logger(__name__)


def _looks_like_smartstore(url: str) -> bool:
    # Naver Shopping API 는 seller slug 를 /main/ 으로 돌려주더라도 실제 페이지는
    # 리디렉션 이후 seller slug 로 안착한다. 둘 다 스마트스토어 호스트로 인정.
    return "smartstore.naver.com" in url


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


def _to_option(option_payload: dict[str, Any], listing: ListingDTO) -> OptionDTO:
    attrs_raw = option_payload.get("attrs") or {}
    if isinstance(attrs_raw, dict):
        attrs = {str(k): str(v) for k, v in attrs_raw.items()}
    else:
        attrs = {}
    return OptionDTO(
        platform_option_id=option_payload.get("platform_option_id"),
        option_name_text=str(
            option_payload.get("option_name_text") or listing.raw_title
        ),
        attrs=attrs,
        price=int(option_payload.get("price") or listing.representative_price or 0),
        stock=option_payload.get("stock")
        if isinstance(option_payload.get("stock"), int)
        else None,
        usable=bool(option_payload.get("usable", True)),
    )


def _resolve_shipping(
    shipping_fee: int,
    shipping_confidence: str,
    subtotal: int,
) -> ShippingEstimate:
    """스크레이퍼가 explicit fee 를 주면 해당 값을 그대로 사용, 아니면 정책 추정."""
    if shipping_confidence == "explicit":
        # 판매자 기본 배송비를 정책에 넘겨 free_threshold 로직까지 적용
        return estimate_smartstore_generic(
            subtotal,
            seller_default_fee=int(shipping_fee),
        )
    return estimate_smartstore_generic(subtotal)


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

    try:
        payload = await remote_naver_detail(listing.product_url, settings=settings)
    except (BotBlockedError, UpstreamError, UpstreamTimeoutError) as exc:
        # 캡차·state_missing·타임아웃 모두 대표가 기반 fallback 으로 회복
        logger.info(
            "naver_detail_remote_failed fallback=static err=%s", exc.detail
        )
        detail = _fallback_detail(listing)
        await set_cached_detail("naver", listing.product_url, detail)
        return detail

    raw_options = payload.get("options") or []
    options: list[OptionDTO] = [
        _to_option(o, listing) for o in raw_options if isinstance(o, dict)
    ]
    if not options:
        detail = _fallback_detail(listing)
        await set_cached_detail("naver", listing.product_url, detail)
        return detail

    subtotal = options[0].price
    shipping_fee = int(payload.get("shipping_fee") or 0)
    shipping_confidence = str(payload.get("shipping_confidence") or "unknown")

    shipping = _resolve_shipping(shipping_fee, shipping_confidence, subtotal)

    fetch_method: FetchMethod = "playwright"  # remote scraper = CDP(Playwright client)
    detail = DetailDTO(
        listing=listing,
        options=options,
        shipping_fee=shipping.fee,
        shipping_confidence=shipping.confidence,
        free_shipping_threshold=shipping.free_threshold,
        fetch_method=fetch_method,
    )
    await set_cached_detail("naver", listing.product_url, detail)
    return detail
