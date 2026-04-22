"""검색 엔드포인트 오케스트레이션."""

from __future__ import annotations

import asyncio
from typing import Any

from app.collectors.base import Collector, DetailDTO, ListingDTO
from app.collectors.coupang import CoupangCollector
from app.collectors.naver import NaverCollector
from app.core.config import get_settings
from app.core.exceptions import (
    AllSourcesFailedError,
    BotBlockedError,
    QuotaExceededError,
    UpstreamError,
    UpstreamTimeoutError,
)
from app.core.logging import get_logger
from app.db.session import session_scope
from app.parsers.option_parser import parse_option
from app.parsers.unit_price import calculate_unit_price
from app.schemas.search import ResultItem, SearchResponse, Sources, SourceStatus
from app.services.cache_service import cache_get_json, cache_set_json, make_search_key
from app.services.quota_service import remaining_quota
from app.services.ranking_service import RankItem, compute_comparable_group, rank_by_unit_price

logger = get_logger(__name__)


def _map_source_error(exc: BaseException) -> SourceStatus:
    if isinstance(exc, QuotaExceededError):
        return "quota_exceeded"
    if isinstance(exc, BotBlockedError):
        if "circuit" in exc.detail:
            return "circuit_open"
        return "blocked"
    if isinstance(exc, UpstreamTimeoutError):
        return "timeout"
    if isinstance(exc, UpstreamError):
        return "error"
    return "error"


async def _safe_search(collector: Collector, query: str, limit: int) -> tuple[list[ListingDTO], SourceStatus, str | None]:
    try:
        listings = await collector.search(query, limit)
    except Exception as exc:  # noqa: BLE001
        status = _map_source_error(exc)
        detail = getattr(exc, "detail", str(exc))
        logger.info(
            "collector_search_fail",
            platform=collector.platform,
            status=status,
            detail=detail,
        )
        return [], status, detail
    return listings, "ok", None


async def _safe_detail(collector: Collector, listing: ListingDTO) -> tuple[DetailDTO | None, str]:
    try:
        detail = await collector.fetch_detail(listing)
    except BotBlockedError as exc:
        return None, f"blocked:{exc.detail}"
    except (UpstreamError, UpstreamTimeoutError) as exc:
        return None, f"error:{exc.detail}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("detail_unexpected_fail", error=str(exc), platform=collector.platform)
        return None, f"error:{exc}"
    return detail, "ok"


async def _collect_details(collector: Collector, listings: list[ListingDTO]) -> list[tuple[ListingDTO, DetailDTO | None, str]]:
    if not listings:
        return []
    detail_results = await asyncio.gather(
        *(_safe_detail(collector, listing) for listing in listings)
    )
    return [(listing, detail, status) for listing, (detail, status) in zip(listings, detail_results, strict=True)]


async def _build_rank_items(
    details: list[tuple[ListingDTO, DetailDTO | None, str]],
    platform: str,
) -> list[RankItem]:
    items: list[RankItem] = []
    async with session_scope() as session:
        for listing, detail, detail_status in details:
            if detail is None:
                continue
            for option in detail.options:
                parsed = await parse_option(option.option_name_text or listing.raw_title, db_session=session)
                up = calculate_unit_price(
                    option_price=option.price,
                    shipping_fee=detail.shipping_fee,
                    parsed=parsed,
                    shipping_confidence=detail.shipping_confidence,
                )
                items.append(
                    RankItem(
                        unit_price=up,
                        payload={
                            "platform": platform,
                            "seller": listing.seller_id or listing.mall_name,
                            "product_url": listing.product_url,
                            "raw_title": listing.raw_title,
                            "thumbnail_url": listing.thumbnail_url,
                            "option_name": option.option_name_text or listing.raw_title,
                            "price": option.price,
                            "shipping_fee": detail.shipping_fee,
                            "shipping_confidence": detail.shipping_confidence,
                            "is_rocket": listing.is_rocket,
                            "fetch_method": detail.fetch_method,
                            "detail_status": detail_status,
                            "parsed_confidence": parsed.confidence if parsed else None,
                        },
                    )
                )
    return items


def _to_result_item(item: RankItem) -> ResultItem:
    up = item.unit_price
    p = item.payload
    return ResultItem(
        platform=p["platform"],
        seller=p.get("seller"),
        product_url=p["product_url"],
        raw_title=p["raw_title"],
        thumbnail_url=p.get("thumbnail_url"),
        option_name=p["option_name"],
        price=p["price"],
        shipping_fee=p["shipping_fee"],
        shipping_confidence=p["shipping_confidence"],
        total_price=up.total_price,
        unit_quantity=up.unit_quantity,
        unit=up.display_base_unit,
        unit_price=up.unit_price,
        unit_price_display=up.unit_price_display,
        display_base_value=up.display_base_value,
        display_base_unit=up.display_base_unit,
        unit_price_confidence=up.unit_price_confidence,
        parsed_confidence=p.get("parsed_confidence"),
        is_rocket=p.get("is_rocket"),
        fetch_method=p["fetch_method"],
        detail_status=p["detail_status"],
    )


async def run_search(query: str, limit: int, *, force_refresh: bool = False) -> SearchResponse:
    settings = get_settings()
    cache_key = make_search_key(query, limit)

    if not force_refresh:
        cached = await cache_get_json(cache_key)
        if isinstance(cached, dict):
            cached["cached"] = True
            return SearchResponse.model_validate(cached)

    naver = NaverCollector(settings=settings)
    coupang = CoupangCollector(settings=settings)

    (naver_listings, naver_status, naver_detail_note), (coupang_listings, coupang_status, coupang_detail_note) = await asyncio.gather(
        _safe_search(naver, query, limit),
        _safe_search(coupang, query, limit),
    )

    naver_details, coupang_details = await asyncio.gather(
        _collect_details(naver, naver_listings),
        _collect_details(coupang, coupang_listings),
    )

    naver_items = await _build_rank_items(naver_details, "naver")
    coupang_items = await _build_rank_items(coupang_details, "coupang")

    merged = [*naver_items, *coupang_items]
    ranked = rank_by_unit_price(merged)
    group = compute_comparable_group(ranked)

    if naver_status != "ok" and coupang_status != "ok" and not merged:
        raise AllSourcesFailedError(detail=f"naver:{naver_detail_note} coupang:{coupang_detail_note}")

    sources = Sources(
        naver=naver_status,
        naver_detail=naver_detail_note,
        coupang=coupang_status,
        coupang_detail=coupang_detail_note,
    )

    response = SearchResponse(
        query=query,
        limit=limit,
        sources=sources,
        results=[_to_result_item(i) for i in ranked],
        cached=False,
        comparable_group=group,
        naver_quota_remaining=await remaining_quota("naver"),
    )
    await cache_set_json(
        cache_key, response.model_dump(mode="json"), ttl_seconds=settings.search_cache_ttl_seconds
    )
    return response


__all__ = ["run_search"]
_UNUSED: Any = None
