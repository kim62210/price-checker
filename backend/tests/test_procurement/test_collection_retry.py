"""최저가 수집 orchestration/retry 테스트."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.price_collection.models  # noqa: F401
import app.tenancy.models  # noqa: F401
from app.price_collection.client import NaverShoppingItem
from app.price_collection.exceptions import NaverClientTimeoutError
from app.price_collection.models import PriceCollectionAttempt
from app.price_collection.schemas import PriceCollectionJobCreate
from app.price_collection.service import PriceCollectionService
from app.procurement.models import ProcurementOrder, ProcurementResult
from app.tenancy.models import Shop


class _StubSuccessClient:
    async def search(self, *, query: str) -> list[NaverShoppingItem]:
        return [
            NaverShoppingItem(
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
        ]


class _StubTimeoutClient:
    async def search(self, *, query: str) -> list[NaverShoppingItem]:
        raise NaverClientTimeoutError("naver_search_timeout")


@pytest.fixture
async def retry_order(db_session: AsyncSession, test_tenant_a):
    shop = Shop(tenant_id=test_tenant_a.id, name="재시도 수집 매장")
    db_session.add(shop)
    await db_session.flush()

    order = ProcurementOrder(
        tenant_id=test_tenant_a.id,
        shop_id=shop.id,
        product_name="서울우유",
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
async def test_collection_rerun_replaces_existing_canonical_rows_without_duplicates(
    db_session: AsyncSession,
    test_tenant_a,
    retry_order,
) -> None:
    service = PriceCollectionService(db_session)
    job, _ = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=retry_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="rerun-key"),
    )

    await service.run_job(
        job_id=job.id,
        tenant_id=test_tenant_a.id,
        client=_StubSuccessClient(),
        parser_version=1,
    )
    await service.run_job(
        job_id=job.id,
        tenant_id=test_tenant_a.id,
        client=_StubSuccessClient(),
        parser_version=1,
    )

    rows = list(
        (
            await db_session.execute(
                select(ProcurementResult).where(ProcurementResult.order_id == retry_order.id)
            )
        ).scalars()
    )

    assert len(rows) == 1
    assert rows[0].external_offer_id == "12345"
    assert rows[0].source_method == "naver_openapi"


@pytest.mark.asyncio
async def test_retryable_timeout_updates_job_attempts_and_next_retry(
    db_session: AsyncSession,
    test_tenant_a,
    retry_order,
) -> None:
    service = PriceCollectionService(db_session)
    job, _ = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=retry_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="timeout-key"),
    )

    await service.run_job(
        job_id=job.id,
        tenant_id=test_tenant_a.id,
        client=_StubTimeoutClient(),
        parser_version=1,
    )

    await db_session.refresh(job)
    attempts = list(
        (
            await db_session.execute(
                select(PriceCollectionAttempt).where(PriceCollectionAttempt.job_id == job.id)
            )
        ).scalars()
    )

    assert job.status == "pending"
    assert job.attempts == 1
    assert job.next_retry_at is not None
    assert job.last_error_code == "naver_search_timeout"
    assert attempts[0].status == "retryable_failure"
    assert attempts[0].attempted_at is not None
