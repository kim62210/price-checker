"""네이버 쇼핑 검색 API 수집기."""

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.collectors.base import Collector, DetailDTO, ListingDTO
from app.collectors.http_client import get_http_client
from app.collectors.rate_limiter import get_rate_limiter
from app.core.config import Settings, get_settings
from app.core.exceptions import QuotaExceededError, UpstreamError, UpstreamTimeoutError
from app.core.logging import get_logger
from app.services.quota_service import incr_quota, is_quota_exceeded

logger = get_logger(__name__)

NAVER_SHOP_ENDPOINT = "https://openapi.naver.com/v1/search/shop.json"
_TAG_RE = re.compile(r"</?b>")


def _strip_tags(value: str) -> str:
    return unescape(_TAG_RE.sub("", value)).strip()


def _to_int(value: Any) -> int | None:
    if value in (None, "", "0"):
        return None if value in (None, "") else 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


class NaverCollector(Collector):
    platform = "naver"

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client or get_http_client()
        rate_limiter = get_rate_limiter()
        rate_limiter.register("naver", self.settings.naver_rpm)

    async def search(self, query: str, limit: int) -> list[ListingDTO]:
        if not query.strip():
            return []

        if await is_quota_exceeded("naver", self.settings):
            logger.info("naver_quota_exceeded")
            raise QuotaExceededError(detail="naver_quota_exceeded", code="QUOTA_EXCEEDED")

        await get_rate_limiter().acquire("naver")

        try:
            items = await self._call_api(query, min(max(limit, 1), 100))
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError(detail="naver_timeout") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(detail=f"naver_http_error:{exc}") from exc

        await incr_quota("naver")
        return [self._to_listing(item) for item in items]

    async def fetch_detail(self, listing: ListingDTO) -> DetailDTO:
        from app.collectors.naver_detail import fetch_naver_detail

        return await fetch_naver_detail(listing, self.settings)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    async def _call_api(self, query: str, display: int) -> list[dict[str, Any]]:
        params = {"query": query, "display": display, "start": 1, "sort": "asc"}
        headers = {
            "X-Naver-Client-Id": self.settings.naver_client_id.get_secret_value(),
            "X-Naver-Client-Secret": self.settings.naver_client_secret.get_secret_value(),
            "Accept": "application/json",
        }
        response = await self.http_client.get(
            NAVER_SHOP_ENDPOINT, params=params, headers=headers
        )
        if response.status_code == 429:
            raise QuotaExceededError(detail="naver_rate_limited")
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("items", []))

    def _to_listing(self, item: dict[str, Any]) -> ListingDTO:
        title = _strip_tags(item.get("title", ""))
        lprice = _to_int(item.get("lprice"))
        return ListingDTO(
            platform="naver",
            platform_product_id=str(item.get("productId", "")),
            raw_title=title,
            product_url=str(item.get("link", "")),
            seller_id=str(item.get("mallName", "") or "") or None,
            mall_name=str(item.get("mallName", "") or "") or None,
            representative_price=lprice,
            thumbnail_url=str(item.get("image", "") or "") or None,
            raw_payload=item,
        )
