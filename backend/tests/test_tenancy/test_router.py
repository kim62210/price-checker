"""tenancy router 추가 커버리지 테스트."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def shop_a(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_a.id, name="라우터 테스트 매장")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.mark.asyncio
async def test_get_me_tenant(client: AsyncClient, auth_headers_a, test_tenant_a):
    """GET /api/v1/tenants/me → 현재 테넌트 정보."""
    response = await client.get("/api/v1/tenants/me", headers=auth_headers_a)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == test_tenant_a.id


@pytest.mark.asyncio
async def test_list_shops(client: AsyncClient, auth_headers_a, shop_a):
    """GET /api/v1/shops → 테넌트 A 소속 매장 목록."""
    response = await client.get("/api/v1/shops", headers=auth_headers_a)
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert shop_a.id in ids


@pytest.mark.asyncio
async def test_create_shop(client: AsyncClient, auth_headers_a):
    """POST /api/v1/shops → 매장 생성."""
    response = await client.post(
        "/api/v1/shops",
        json={"name": "새 매장"},
        headers=auth_headers_a,
    )
    assert response.status_code == 201
    assert response.json()["name"] == "새 매장"


@pytest.mark.asyncio
async def test_get_shop_detail(client: AsyncClient, auth_headers_a, shop_a):
    """GET /api/v1/shops/{id} → 매장 단건."""
    response = await client.get(f"/api/v1/shops/{shop_a.id}", headers=auth_headers_a)
    assert response.status_code == 200
    assert response.json()["id"] == shop_a.id


@pytest.mark.asyncio
async def test_get_shop_not_found(client: AsyncClient, auth_headers_a):
    """GET /api/v1/shops/{id} 없는 shop → 404."""
    response = await client.get("/api/v1/shops/99999", headers=auth_headers_a)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, auth_headers_a, test_user_a):
    """GET /api/v1/users → 현재 테넌트 사용자 목록."""
    response = await client.get("/api/v1/users", headers=auth_headers_a)
    assert response.status_code == 200
    ids = [u["id"] for u in response.json()]
    assert test_user_a.id in ids
