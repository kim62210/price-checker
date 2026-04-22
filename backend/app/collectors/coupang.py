"""쿠팡 검색 페이지 저빈도 수집기."""

from __future__ import annotations

import re
from urllib.parse import quote, urljoin

import httpx
from selectolax.parser import HTMLParser, Node
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.collectors.base import Collector, DetailDTO, ListingDTO
from app.collectors.circuit_breaker import is_open, record_failure, record_success
from app.collectors.http_client import get_http_client
from app.collectors.rate_limiter import get_rate_limiter
from app.collectors.selectors_loader import platform_selectors
from app.core.config import Settings, get_settings
from app.core.exceptions import BotBlockedError, UpstreamError, UpstreamTimeoutError
from app.core.logging import get_logger
from app.core.security import browser_like_headers, random_jitter_sleep

logger = get_logger(__name__)

COUPANG_BASE = "https://www.coupang.com"
COUPANG_SEARCH = f"{COUPANG_BASE}/np/search"
BLOCK_MARKERS = ("Pardon Our Interruption", "Access Denied", "Reference #")

_PRICE_RE = re.compile(r"[^\d]")


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = _PRICE_RE.sub("", value)
    return int(cleaned) if cleaned else None


def _text_of(node: Node | None) -> str:
    return node.text(deep=True, strip=True) if node is not None else ""


class CoupangCollector(Collector):
    platform = "coupang"

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client or get_http_client()
        self.selectors = platform_selectors("coupang")
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

        try:
            html = await self._fetch_search_html(query, min(max(limit, 1), 60))
        except httpx.TimeoutException as exc:
            await record_failure(self.platform)
            raise UpstreamTimeoutError(detail="coupang_timeout") from exc
        except httpx.HTTPError as exc:
            await record_failure(self.platform)
            raise UpstreamError(detail=f"coupang_http_error:{exc}") from exc

        self._raise_if_blocked(html)
        await record_success(self.platform)
        return self._parse_search_html(html, limit)

    async def fetch_detail(self, listing: ListingDTO) -> DetailDTO:
        from app.collectors.coupang_detail import fetch_coupang_detail

        return await fetch_coupang_detail(listing, self.settings)

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential_jitter(initial=0.8, max=5.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    async def _fetch_search_html(self, query: str, list_size: int) -> str:
        url = f"{COUPANG_SEARCH}?q={quote(query)}&listSize={list_size}&component=&channel=user"
        response = await self.http_client.get(url, headers=browser_like_headers(COUPANG_BASE))
        if response.status_code == 403:
            raise BotBlockedError(detail="coupang_403")
        response.raise_for_status()
        return response.text

    def _raise_if_blocked(self, html: str) -> None:
        snippet = html[:3000]
        if any(marker in snippet for marker in BLOCK_MARKERS):
            raise BotBlockedError(detail="coupang_block_page")

    def _parse_search_html(self, html: str, limit: int) -> list[ListingDTO]:
        tree = HTMLParser(html)
        sel = self.selectors["search"]
        items: list[ListingDTO] = []

        for node in tree.css(sel["list_item"]):
            if node.attributes.get("data-sponsored") == "true":
                continue
            if node.css_first(sel["ad_badge"]) is not None:
                continue

            product_id = node.attributes.get("data-product-id") or ""
            vendor_item_id = node.attributes.get("data-vendor-item-id") or ""
            item_id = node.attributes.get("data-item-id") or ""
            if not product_id:
                continue

            link_node = node.css_first(sel["product_link"])
            href = link_node.attributes.get("href") if link_node else None
            if not href:
                continue
            product_url = urljoin(COUPANG_BASE, href)

            name = _text_of(node.css_first(sel["name"]))
            price = _parse_int(_text_of(node.css_first(sel["price_value"])))
            thumb_node = node.css_first(sel["thumbnail"])
            thumbnail = (
                thumb_node.attributes.get("src") or thumb_node.attributes.get("data-img-src")
                if thumb_node
                else None
            )
            is_rocket = node.css_first(sel["rocket_badge"]) is not None

            items.append(
                ListingDTO(
                    platform="coupang",
                    platform_product_id=product_id,
                    raw_title=name,
                    product_url=product_url,
                    representative_price=price,
                    thumbnail_url=thumbnail,
                    is_rocket=is_rocket,
                    raw_payload={
                        "productId": product_id,
                        "vendorItemId": vendor_item_id,
                        "itemId": item_id,
                    },
                )
            )
            if len(items) >= limit:
                break
        return items
