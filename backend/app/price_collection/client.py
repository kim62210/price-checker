"""네이버 쇼핑 검색 API client."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.price_collection.exceptions import (
    NaverClientRateLimitError,
    NaverClientResponseError,
    NaverClientTimeoutError,
)

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class NaverShoppingItem:
    title: str
    product_url: str
    listed_price: int
    mall_name: str | None
    product_id: str | None
    product_type: str | None
    maker: str | None
    brand: str | None
    category1: str | None
    category2: str | None
    category3: str | None
    category4: str | None


class NaverShoppingSearchClient:
    """네이버 공식 쇼핑 검색 API 조회."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._settings.validate_price_collection_config()

    async def search(self, *, query: str) -> list[NaverShoppingItem]:
        headers = {
            "X-Naver-Client-Id": self._settings.naver_search_client_id.get_secret_value(),
            "X-Naver-Client-Secret": self._settings.naver_search_client_secret.get_secret_value(),
        }
        params = {
            "query": query,
            "display": self._settings.naver_search_display_limit,
            "start": 1,
            "sort": "asc",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self._settings.naver_search_base_url}/v1/search/shop.json",
                    headers=headers,
                    params=params,
                )
            except TimeoutError as exc:
                raise NaverClientTimeoutError("naver_search_timeout") from exc
            except httpx.TimeoutException as exc:
                raise NaverClientTimeoutError("naver_search_timeout") from exc

        if response.status_code == 429:
            raise NaverClientRateLimitError("naver_search_rate_limited")
        if response.status_code >= 500:
            raise NaverClientRateLimitError("naver_search_upstream_retryable")
        if response.status_code >= 400:
            raise NaverClientResponseError(f"naver_search_http_{response.status_code}")

        payload = response.json()
        items = payload.get("items")
        if not isinstance(items, list):
            raise NaverClientResponseError("naver_search_items_missing")
        return [self._map_item(item) for item in items]

    def _map_item(self, payload: dict[str, object]) -> NaverShoppingItem:
        lprice = int(str(payload.get("lprice", "0") or "0"))
        return NaverShoppingItem(
            title=_TAG_RE.sub("", str(payload.get("title", ""))).strip(),
            product_url=str(payload.get("link", "")).strip(),
            listed_price=lprice,
            mall_name=_optional_str(payload.get("mallName")),
            product_id=_optional_str(payload.get("productId")),
            product_type=_optional_str(payload.get("productType")),
            maker=_optional_str(payload.get("maker")),
            brand=_optional_str(payload.get("brand")),
            category1=_optional_str(payload.get("category1")),
            category2=_optional_str(payload.get("category2")),
            category3=_optional_str(payload.get("category3")),
            category4=_optional_str(payload.get("category4")),
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


__all__ = [
    "NaverClientRateLimitError",
    "NaverClientTimeoutError",
    "NaverShoppingItem",
    "NaverShoppingSearchClient",
]
