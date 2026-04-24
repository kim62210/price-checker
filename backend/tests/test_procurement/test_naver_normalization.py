"""네이버 응답 정규화 테스트."""

from __future__ import annotations

from decimal import Decimal

import pytest

import app.price_collection.models  # noqa: F401
import app.tenancy.models  # noqa: F401
from app.price_collection.client import NaverShoppingItem
from app.price_collection.normalization import normalize_naver_item
from app.procurement.models import ProcurementOrder


@pytest.mark.asyncio
async def test_naver_candidate_normalizes_to_canonical_procurement_result() -> None:
    order = ProcurementOrder(
        tenant_id=1,
        shop_id=1,
        product_name="서울우유",
        option_text="1L 12개",
        quantity=12,
        unit="개",
        status="collecting",
    )
    item = NaverShoppingItem(
        title="서울우유 1L 12개",
        product_url="https://shopping.naver.com/test-product",
        listed_price=12900,
        mall_name="테스트몰",
        product_id="12345",
        product_type="2",
        maker="서울우유",
        brand="서울우유",
        category1="식품",
        category2="유제품",
        category3="우유",
        category4="멸균우유",
    )

    normalized = normalize_naver_item(order=order, item=item, parser_version=1)

    assert normalized.compare_eligible is True
    assert normalized.external_offer_id == "12345"
    assert normalized.source_method == "naver_openapi"
    assert normalized.parser_version == 1
    assert normalized.unit_count == 12
    assert normalized.per_unit_price == Decimal("1075.00")


@pytest.mark.asyncio
async def test_naver_candidate_with_unparsed_unit_becomes_partial_result() -> None:
    order = ProcurementOrder(
        tenant_id=1,
        shop_id=1,
        product_name="서울우유",
        option_text="옵션 없음",
        quantity=12,
        unit="개",
        status="collecting",
    )
    item = NaverShoppingItem(
        title="서울우유 기획상품",
        product_url="https://shopping.naver.com/test-product",
        listed_price=12900,
        mall_name="테스트몰",
        product_id="12345",
        product_type="2",
        maker="서울우유",
        brand="서울우유",
        category1="식품",
        category2="유제품",
        category3="우유",
        category4="멸균우유",
    )

    normalized = normalize_naver_item(order=order, item=item, parser_version=1)

    assert normalized.compare_eligible is False
    assert normalized.failure_code == "unit_unparsed"
    assert normalized.per_unit_price is None
    assert normalized.unit_count == 1
