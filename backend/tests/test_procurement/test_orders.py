"""16.8 발주 주문 생성·조회·테넌트 격리 테스트."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def shop_a(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_a.id, name="테스트 매장 A")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def shop_b(db_session: AsyncSession, test_tenant_b):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_b.id, name="테스트 매장 B")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.mark.asyncio
async def test_create_order_success(
    client: AsyncClient,
    auth_headers_a,
    shop_a,
    fake_redis,
):
    """발주 생성 성공 → 201 + 데이터 확인."""
    payload = {
        "shop_id": shop_a.id,
        "product_name": "우유",
        "quantity": 100,
        "unit": "ml",
        "target_unit_price": "1500.00",
    }
    response = await client.post(
        "/api/v1/procurement/orders",
        json=payload,
        headers=auth_headers_a,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["product_name"] == "우유"
    assert body["quantity"] == 100
    assert body["shop_id"] == shop_a.id


@pytest.mark.asyncio
async def test_create_order_cross_tenant_shop_404(
    client: AsyncClient,
    auth_headers_a,
    shop_b,
    fake_redis,
):
    """테넌트 A 토큰으로 테넌트 B shop_id 발주 → 404."""
    payload = {
        "shop_id": shop_b.id,
        "product_name": "불가 상품",
        "quantity": 1,
        "unit": "개",
    }
    response = await client.post(
        "/api/v1/procurement/orders",
        json=payload,
        headers=auth_headers_a,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_orders_empty(client: AsyncClient, auth_headers_a):
    """발주 없는 경우 빈 목록 반환."""
    response = await client.get("/api/v1/procurement/orders", headers=auth_headers_a)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_orders_pagination(
    client: AsyncClient,
    auth_headers_a,
    shop_a,
    fake_redis,
):
    """limit/offset 페이지네이션 검증."""
    for i in range(3):
        await client.post(
            "/api/v1/procurement/orders",
            json={"shop_id": shop_a.id, "product_name": f"상품{i}", "quantity": 1, "unit": "개"},
            headers=auth_headers_a,
        )

    r_limit1 = await client.get(
        "/api/v1/procurement/orders?limit=1", headers=auth_headers_a
    )
    assert len(r_limit1.json()) == 1

    r_offset2 = await client.get(
        "/api/v1/procurement/orders?offset=2", headers=auth_headers_a
    )
    assert len(r_offset2.json()) == 1


@pytest.mark.asyncio
async def test_get_order_success(
    client: AsyncClient,
    auth_headers_a,
    shop_a,
    fake_redis,
):
    """발주 단건 조회 성공."""
    create_r = await client.post(
        "/api/v1/procurement/orders",
        json={"shop_id": shop_a.id, "product_name": "단건상품", "quantity": 2, "unit": "개"},
        headers=auth_headers_a,
    )
    order_id = create_r.json()["id"]

    response = await client.get(
        f"/api/v1/procurement/orders/{order_id}", headers=auth_headers_a
    )
    assert response.status_code == 200
    assert response.json()["id"] == order_id


@pytest.mark.asyncio
async def test_get_order_not_found(client: AsyncClient, auth_headers_a):
    """존재하지 않는 order_id → 404."""
    response = await client.get(
        "/api/v1/procurement/orders/99999", headers=auth_headers_a
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_order_cross_tenant_404(
    client: AsyncClient,
    auth_headers_a,
    db_session: AsyncSession,
    test_tenant_b,
    shop_b,
):
    """테넌트 B 발주를 테넌트 A 토큰으로 조회 → 404."""
    from app.procurement.models import ProcurementOrder

    order = ProcurementOrder(
        tenant_id=test_tenant_b.id,
        shop_id=shop_b.id,
        product_name="B 상품",
        quantity=1,
        unit="개",
        status="draft",
    )
    db_session.add(order)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/procurement/orders/{order.id}", headers=auth_headers_a
    )
    assert response.status_code == 404
