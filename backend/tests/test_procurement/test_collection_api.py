"""최저가 수집 job API 테스트."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenancy.models import Shop


@pytest.fixture
async def collection_shop_a(db_session: AsyncSession, test_tenant_a):
    shop = Shop(tenant_id=test_tenant_a.id, name="수집 매장 A")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def collection_shop_b(db_session: AsyncSession, test_tenant_b):
    shop = Shop(tenant_id=test_tenant_b.id, name="수집 매장 B")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def collection_order_a(
    client: AsyncClient,
    auth_headers_a,
    collection_shop_a,
    fake_redis,
):
    response = await client.post(
        "/api/v1/procurement/orders",
        json={
            "shop_id": collection_shop_a.id,
            "product_name": "서울우유 1L",
            "option_text": "1L 12개",
            "quantity": 12,
            "unit": "개",
            "status": "collecting",
        },
        headers=auth_headers_a,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def collection_order_b(
    client: AsyncClient,
    auth_headers_b,
    collection_shop_b,
    fake_redis,
):
    response = await client.post(
        "/api/v1/procurement/orders",
        json={
            "shop_id": collection_shop_b.id,
            "product_name": "두유 190ml",
            "option_text": "190ml 24팩",
            "quantity": 24,
            "unit": "개",
            "status": "collecting",
        },
        headers=auth_headers_b,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_collection_job(
    client: AsyncClient,
    auth_headers_a,
    collection_order_a,
):
    response = await client.post(
        f"/api/v1/procurement/orders/{collection_order_a['id']}/collect",
        headers={**auth_headers_a, "Idempotency-Key": "collect-a-1"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["order_id"] == collection_order_a["id"]
    assert body["tenant_id"] == collection_order_a["tenant_id"]
    assert body["source"] == "naver"
    assert body["status"] == "pending"
    assert body["attempts"] == 0
    assert body["idempotency_key"] == "collect-a-1"


@pytest.mark.asyncio
async def test_create_collection_job_cross_tenant_404(
    client: AsyncClient,
    auth_headers_a,
    collection_order_b,
):
    response = await client.post(
        f"/api/v1/procurement/orders/{collection_order_b['id']}/collect",
        headers=auth_headers_a,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_trigger_reuses_existing_job(
    client: AsyncClient,
    auth_headers_a,
    collection_order_a,
):
    url = f"/api/v1/procurement/orders/{collection_order_a['id']}/collect"
    first = await client.post(url, headers={**auth_headers_a, "Idempotency-Key": "same-key"})
    second = await client.post(url, headers={**auth_headers_a, "Idempotency-Key": "same-key"})

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_list_collection_jobs_returns_latest_first(
    client: AsyncClient,
    auth_headers_a,
    collection_order_a,
):
    url = f"/api/v1/procurement/orders/{collection_order_a['id']}/collect"
    await client.post(url, headers={**auth_headers_a, "Idempotency-Key": "job-1"})
    await client.post(url, headers={**auth_headers_a, "Idempotency-Key": "job-2"})

    response = await client.get(
        f"/api/v1/procurement/orders/{collection_order_a['id']}/collect/jobs",
        headers=auth_headers_a,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["idempotency_key"] for item in body] == ["job-2", "job-1"]
