"""쿠팡 검색 수집기 (Mac mini CDP 스크레이퍼 위임)."""

from __future__ import annotations

from app.collectors.base import Collector, DetailDTO, ListingDTO
from app.collectors.circuit_breaker import is_open, record_failure, record_success
from app.collectors.rate_limiter import get_rate_limiter
from app.collectors.remote_scraper import remote_coupang_search
from app.core.config import Settings, get_settings
from app.core.exceptions import BotBlockedError, ServiceError
from app.core.logging import get_logger
from app.core.security import random_jitter_sleep

logger = get_logger(__name__)


class CoupangCollector(Collector):
    platform = "coupang"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        rate_limiter = get_rate_limiter()
        rate_limiter.register("coupang", self.settings.coupang_rpm)

    async def search(self, query: str, limit: int) -> list[ListingDTO]:
        if not query.strip():
            return []
        if await is_open(self.platform):
            logger.warning("coupang_circuit_open")
            raise BotBlockedError(detail="coupang_circuit_open")

        await get_rate_limiter().acquire("coupang")
        await random_jitter_sleep(self.settings)

        effective_limit = min(max(limit, 1), 60)
        try:
            items = await remote_coupang_search(query, effective_limit, settings=self.settings)
        except ServiceError:
            await record_failure(self.platform)
            raise

        await record_success(self.platform)
        return [self._to_listing_dto(item) for item in items][:limit]

    async def fetch_detail(self, listing: ListingDTO) -> DetailDTO:
        from app.collectors.coupang_detail import fetch_coupang_detail

        return await fetch_coupang_detail(listing, self.settings)

    @staticmethod
    def _to_listing_dto(item: dict) -> ListingDTO:
        return ListingDTO(
            platform="coupang",
            platform_product_id=str(item.get("platform_product_id") or ""),
            raw_title=str(item.get("raw_title") or ""),
            product_url=str(item.get("product_url") or ""),
            representative_price=item.get("representative_price"),
            thumbnail_url=item.get("thumbnail_url"),
            is_rocket=bool(item.get("is_rocket") or False),
            raw_payload={
                "productId": item.get("platform_product_id"),
                "vendorItemId": item.get("vendor_item_id"),
                "itemId": item.get("item_id"),
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
            },
        )
