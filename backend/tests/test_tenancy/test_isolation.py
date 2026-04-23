"""16.3 크로스 테넌트 격리 — 테넌트 A 토큰으로 B 리소스 조회 시 404."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def shop_a(db_session: AsyncSession, test_tenant_a):
    """테넌트 A 소속 shop."""
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_a.id, name="A 매장")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def shop_b(db_session: AsyncSession, test_tenant_b):
    """테넌트 B 소속 shop."""
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_b.id, name="B 매장")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def order_a(db_session: AsyncSession, test_tenant_a, shop_a):
    """테넌트 A 발주."""
    from app.procurement.models import ProcurementOrder

    order = ProcurementOrder(
        tenant_id=test_tenant_a.id,
        shop_id=shop_a.id,
        product_name="우유 A",
        quantity=10,
        unit="개",
        status="draft",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    return order


@pytest.fixture
async def order_b(db_session: AsyncSession, test_tenant_b, shop_b):
    """테넌트 B 발주."""
    from app.procurement.models import ProcurementOrder

    order = ProcurementOrder(
        tenant_id=test_tenant_b.id,
        shop_id=shop_b.id,
        product_name="우유 B",
        quantity=5,
        unit="개",
        status="draft",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_cross_tenant_order_get_returns_404(
    client: AsyncClient,
    auth_headers_a,
    order_b,
):
    """테넌트 A 토큰으로 테넌트 B의 발주 단건 조회 → 404."""
    response = await client.get(
        f"/api/v1/procurement/orders/{order_b.id}",
        headers=auth_headers_a,
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_order_list_returns_only_own_tenant(
    client: AsyncClient,
    auth_headers_a,
    order_a,
    order_b,
):
    """테넌트 A 토큰 목록 조회 → A 발주만 반환, B 발주 미포함."""
    response = await client.get("/api/v1/procurement/orders", headers=auth_headers_a)
    assert response.status_code == 200

    ids = [item["id"] for item in response.json()]
    assert order_a.id in ids
    assert order_b.id not in ids


@pytest.mark.asyncio
async def test_create_order_with_cross_tenant_shop_returns_404(
    client: AsyncClient,
    auth_headers_a,
    shop_b,
    fake_redis,
):
    """테넌트 A 토큰으로 테넌트 B shop_id 발주 생성 → 404."""
    payload = {
        "shop_id": shop_b.id,
        "product_name": "크로스 테넌트 상품",
        "quantity": 1,
        "unit": "개",
    }
    response = await client.post(
        "/api/v1/procurement/orders",
        json=payload,
        headers=auth_headers_a,
    )
    assert response.status_code == 404, response.text
