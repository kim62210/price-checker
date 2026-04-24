"""네이버 쇼핑 검색 API client 테스트."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.config import get_settings
from app.price_collection.client import (
    NaverClientRateLimitError,
    NaverClientTimeoutError,
    NaverShoppingSearchClient,
)


@pytest.mark.asyncio
@respx.mock
async def test_naver_shop_response_maps_to_offer_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAVER_SEARCH_CLIENT_ID", "naver-search-id")
    monkeypatch.setenv("NAVER_SEARCH_CLIENT_SECRET", "naver-search-secret")
    get_settings.cache_clear()

    route = respx.get("https://openapi.naver.com/v1/search/shop.json").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "title": "<b>서울우유</b> 1L 12개",
                        "link": "https://shopping.naver.com/test-product",
                        "lprice": "12900",
                        "hprice": "15000",
                        "mallName": "테스트몰",
                        "productId": "12345",
                        "productType": "2",
                        "maker": "서울우유",
                        "brand": "서울우유",
                        "category1": "식품",
                        "category2": "유제품",
                        "category3": "우유",
                        "category4": "멸균우유",
                    }
                ]
            },
        )
    )

    client = NaverShoppingSearchClient()
    items = await client.search(query="서울우유 1L 12개")

    assert route.called is True
    assert len(items) == 1
    assert items[0].title == "서울우유 1L 12개"
    assert items[0].product_id == "12345"
    assert items[0].mall_name == "테스트몰"
    assert items[0].product_url == "https://shopping.naver.com/test-product"
    assert items[0].listed_price == 12900
    assert items[0].product_type == "2"


@pytest.mark.asyncio
@respx.mock
async def test_naver_client_maps_rate_limit_and_timeout_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NAVER_SEARCH_CLIENT_ID", "naver-search-id")
    monkeypatch.setenv("NAVER_SEARCH_CLIENT_SECRET", "naver-search-secret")
    get_settings.cache_clear()

    respx.get("https://openapi.naver.com/v1/search/shop.json").mock(
        return_value=Response(429, json={"errorMessage": "too many requests"})
    )
    client = NaverShoppingSearchClient()

    with pytest.raises(NaverClientRateLimitError):
        await client.search(query="서울우유")

    respx.reset()
    respx.get("https://openapi.naver.com/v1/search/shop.json").mock(side_effect=TimeoutError("timeout"))

    with pytest.raises(NaverClientTimeoutError):
        await client.search(query="서울우유")
