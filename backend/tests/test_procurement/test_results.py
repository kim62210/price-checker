"""16.9 발주 결과 업로드·집계 테스트."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def shop_a(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_a.id, name="결과 테스트 매장")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def order_a(client: AsyncClient, auth_headers_a, shop_a, fake_redis):
    """발주 생성 fixture — HTTP 경유."""
    response = await client.post(
        "/api/v1/procurement/orders",
        json={
            "shop_id": shop_a.id,
            "product_name": "우유",
            "quantity": 10,
            "unit": "개",
            "target_unit_price": "2000.00",
        },
        headers=auth_headers_a,
    )
    assert response.status_code == 201
    return response.json()


RESULT_PAYLOAD = {
    "source": "naver",
    "product_url": "https://smartstore.naver.com/test/products/1",
    "seller_name": "테스트판매자",
    "listed_price": "18000.00",
    "per_unit_price": "1800.00",
    "shipping_fee": "0.00",
    "unit_count": 10,
}


@pytest.mark.asyncio
async def test_upload_result_success(
    client: AsyncClient,
    auth_headers_a,
    order_a,
    fake_redis,
):
    """결과 업로드 성공 → 201 + tenant_id 복제 확인."""
    response = await client.post(
        f"/api/v1/procurement/orders/{order_a['id']}/results",
        json=RESULT_PAYLOAD,
        headers=auth_headers_a,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["order_id"] == order_a["id"]
    assert body["tenant_id"] == order_a["tenant_id"]
    assert body["source"] == "naver"


@pytest.mark.asyncio
async def test_upload_result_wrong_order_404(
    client: AsyncClient,
    auth_headers_a,
    fake_redis,
):
    """존재하지 않는 order → 404."""
    response = await client.post(
        "/api/v1/procurement/orders/99999/results",
        json=RESULT_PAYLOAD,
        headers=auth_headers_a,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_results_sorted_by_per_unit_price(
    client: AsyncClient,
    auth_headers_a,
    order_a,
    fake_redis,
):
    """결과 목록이 per_unit_price 오름차순으로 정렬된다."""
    for price in ["2500.00", "1800.00", "2000.00"]:
        await client.post(
            f"/api/v1/procurement/orders/{order_a['id']}/results",
            json={**RESULT_PAYLOAD, "per_unit_price": price},
            headers=auth_headers_a,
        )

    response = await client.get(
        f"/api/v1/procurement/orders/{order_a['id']}/results",
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    prices = [Decimal(item["per_unit_price"]) for item in response.json()]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_summary_savings_calculation(
    client: AsyncClient,
    auth_headers_a,
    order_a,
    fake_redis,
):
    """절감액 집계 — (target - best) * quantity."""
    # target_unit_price=2000, best=1800, quantity=10 → savings=2000
    await client.post(
        f"/api/v1/procurement/orders/{order_a['id']}/results",
        json={**RESULT_PAYLOAD, "per_unit_price": "1800.00"},
        headers=auth_headers_a,
    )

    response = await client.get(
        "/api/v1/procurement/reports/summary",
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["total_savings"]) == Decimal("2000.00")
    assert body["orders_count"] >= 1


@pytest.mark.asyncio
async def test_summary_no_savings_when_best_price_above_target(
    client: AsyncClient,
    auth_headers_a,
    shop_a,
    fake_redis,
):
    """best 가격이 target 이상이면 절감액 0."""
    create_r = await client.post(
        "/api/v1/procurement/orders",
        json={
            "shop_id": shop_a.id,
            "product_name": "비싼상품",
            "quantity": 5,
            "unit": "개",
            "target_unit_price": "1000.00",
        },
        headers=auth_headers_a,
    )
    order = create_r.json()
    await client.post(
        f"/api/v1/procurement/orders/{order['id']}/results",
        json={**RESULT_PAYLOAD, "per_unit_price": "1500.00"},
        headers=auth_headers_a,
    )

    today = date.today().isoformat()
    response = await client.get(
        f"/api/v1/procurement/reports/summary?from={today}&to={today}",
        headers=auth_headers_a,
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["total_savings"]) == Decimal("0")
