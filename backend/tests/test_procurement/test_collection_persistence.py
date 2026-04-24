"""최저가 수집 job 영속성/멱등성 테스트."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.price_collection.models import PriceCollectionAttempt, PriceCollectionJob
from app.price_collection.schemas import PriceCollectionJobCreate
from app.price_collection.service import PriceCollectionService
from app.procurement.models import ProcurementOrder, ProcurementResult
from app.tenancy.models import Shop


@pytest.fixture
async def persistence_order(db_session: AsyncSession, test_tenant_a):
    shop = Shop(tenant_id=test_tenant_a.id, name="수집 영속 매장")
    db_session.add(shop)
    await db_session.flush()

    order = ProcurementOrder(
        tenant_id=test_tenant_a.id,
        shop_id=shop.id,
        product_name="멸균우유",
        option_text="1L 12개",
        quantity=12,
        unit="개",
        status="collecting",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_collection_job_schema_and_result_provenance(
    db_session: AsyncSession,
    test_tenant_a,
    persistence_order,
) -> None:
    service = PriceCollectionService(db_session)

    job, created = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=persistence_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="persist-1"),
    )
    assert created is True
    await service.record_attempt(
        job_id=job.id,
        tenant_id=test_tenant_a.id,
        source="naver",
        status="success",
    )

    result = ProcurementResult(
        order_id=persistence_order.id,
        tenant_id=test_tenant_a.id,
        source="naver",
        product_url="https://shopping.naver.com/test-product",
        seller_name="네이버판매자",
        listed_price="12000.00",
        per_unit_price="1000.00",
        shipping_fee="0.00",
        unit_count=12,
        job_id=job.id,
        source_method="naver_openapi",
        external_offer_id="12345",
        compare_eligible=True,
        parser_version=1,
        raw_excerpt={"productId": "12345", "mallName": "네이버판매자"},
    )
    db_session.add(result)
    await db_session.flush()

    saved_job = await db_session.get(PriceCollectionJob, job.id)
    saved_attempts = list(
        (
            await db_session.execute(
                select(PriceCollectionAttempt).where(PriceCollectionAttempt.job_id == job.id)
            )
        ).scalars()
    )
    saved_result = await db_session.get(ProcurementResult, result.id)

    assert saved_job is not None
    assert len(saved_attempts) == 1
    assert saved_result is not None
    assert saved_result.job_id == job.id
    assert saved_result.source_method == "naver_openapi"
    assert saved_result.external_offer_id == "12345"
    assert saved_result.compare_eligible is True
    assert saved_result.parser_version == 1
    assert saved_result.raw_excerpt == {"productId": "12345", "mallName": "네이버판매자"}


@pytest.mark.asyncio
async def test_collection_job_idempotency_key_reuses_existing_job(
    db_session: AsyncSession,
    test_tenant_a,
    persistence_order,
) -> None:
    service = PriceCollectionService(db_session)

    first, created_first = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=persistence_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="dup-key"),
    )
    second, created_second = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=persistence_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="dup-key"),
    )

    rows = list((await db_session.execute(select(PriceCollectionJob))).scalars())

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert len(rows) == 1
