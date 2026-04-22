"""상세 페이지 응답 캐시."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.collectors.base import DetailDTO, ListingDTO, OptionDTO
from app.core.config import get_settings
from app.services.cache_service import (
    cache_get_json,
    cache_set_json,
    make_detail_key,
)


def _detail_to_json(detail: DetailDTO) -> dict[str, Any]:
    if not is_dataclass(detail):  # pragma: no cover
        raise TypeError("detail must be a DetailDTO dataclass")
    data = asdict(detail)
    data["listing"]["fetched_at"] = detail.listing.fetched_at.isoformat()
    data.pop("raw_html", None)
    return data


def _json_to_detail(data: dict[str, Any]) -> DetailDTO:
    listing_data = dict(data["listing"])
    from datetime import datetime

    fetched_at = listing_data.pop("fetched_at", None)
    listing = ListingDTO(**listing_data)
    if fetched_at:
        listing.fetched_at = datetime.fromisoformat(fetched_at)
    options = [OptionDTO(**opt) for opt in data.get("options", [])]
    return DetailDTO(
        listing=listing,
        options=options,
        shipping_fee=data.get("shipping_fee", 0),
        shipping_confidence=data.get("shipping_confidence", "unknown"),
        free_shipping_threshold=data.get("free_shipping_threshold"),
        fetch_method=data.get("fetch_method", "static"),
        raw_html=None,
    )


async def get_cached_detail(platform: str, url: str) -> DetailDTO | None:
    key = make_detail_key(platform, url)
    raw = await cache_get_json(key)
    if raw is None:
        return None
    return _json_to_detail(raw)


async def set_cached_detail(platform: str, url: str, detail: DetailDTO) -> None:
    ttl = get_settings().detail_cache_ttl_seconds
    await cache_set_json(make_detail_key(platform, url), _detail_to_json(detail), ttl_seconds=ttl)
