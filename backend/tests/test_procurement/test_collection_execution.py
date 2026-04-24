"""최저가 수집 실행과 notification 연동 테스트."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.price_collection.models  # noqa: F401
import app.tenancy.models  # noqa: F401
from app.notifications.models import NotificationOutboxEvent
from app.notifications.schemas import (
    NotificationRecipientCreate,
    NotificationTemplateCreate,
    NotificationTemplateVersionCreate,
)
from app.notifications.service import NotificationRecipientService, NotificationTemplateService
from app.price_collection.client import NaverShoppingItem
from app.price_collection.schemas import PriceCollectionJobCreate
from app.price_collection.service import PriceCollectionService
from app.procurement.models import ProcurementOrder
from app.tenancy.models import Shop


class _SuccessClient:
    async def search(self, *, query: str) -> list[NaverShoppingItem]:
        return [
            NaverShoppingItem(
                title="서울우유 1L 12개",
                product_url="https://shopping.naver.com/best-product",
                listed_price=12000,
                mall_name="최저가몰",
                product_id="best-1",
                product_type="2",
                maker="서울우유",
                brand="서울우유",
                category1="식품",
                category2="유제품",
                category3="우유",
                category4="멸균우유",
            ),
            NaverShoppingItem(
                title="서울우유 1L 12개",
                product_url="https://shopping.naver.com/expensive-product",
                listed_price=14400,
                mall_name="비싼몰",
                product_id="high-1",
                product_type="2",
                maker="서울우유",
                brand="서울우유",
                category1="식품",
                category2="유제품",
                category3="우유",
                category4="멸균우유",
            ),
        ]


class _PartialClient:
    async def search(self, *, query: str) -> list[NaverShoppingItem]:
        return [
            NaverShoppingItem(
                title="서울우유 기획상품",
                product_url="https://shopping.naver.com/partial-product",
                listed_price=12000,
                mall_name="부분몰",
                product_id="partial-1",
                product_type="2",
                maker="서울우유",
                brand="서울우유",
                category1="식품",
                category2="유제품",
                category3="우유",
                category4="멸균우유",
            )
        ]


async def _create_procurement_template(db_session: AsyncSession, tenant_id: int) -> None:
    service = NotificationTemplateService(db_session)
    template = await service.create_template(
        tenant_id=tenant_id,
        payload=NotificationTemplateCreate(template_code="procurement_result", name="조달 결과"),
    )
    await service.create_version(
        tenant_id=tenant_id,
        template_id=template.id,
        payload=NotificationTemplateVersionCreate(
            channel="kakao_alimtalk",
            purpose="transactional",
            provider_template_key="PROCUREMENT_RESULT_V1",
            review_status="approved",
            body="{{shop_name}} {{product_name}} 최저가 {{best_price}}원",
            fallback_body="{{shop_name}} {{product_name}} {{best_price}}원",
            variables=["shop_name", "product_name", "best_price"],
        ),
    )


@pytest.fixture
async def completed_order(db_session: AsyncSession, test_tenant_a):
    shop = Shop(tenant_id=test_tenant_a.id, name="알림 수집 매장")
    db_session.add(shop)
    await db_session.flush()

    order = ProcurementOrder(
        tenant_id=test_tenant_a.id,
        shop_id=shop.id,
        product_name="서울우유",
        option_text="1L 12개",
        quantity=12,
        unit="개",
        status="completed",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_collection_completion_emits_one_best_result_notification_for_completed_order(
    db_session: AsyncSession,
    test_tenant_a,
    completed_order,
) -> None:
    await NotificationRecipientService(db_session).create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(phone="010-2222-3333", display_name="알림 수신자"),
    )
    await _create_procurement_template(db_session, test_tenant_a.id)

    service = PriceCollectionService(db_session)
    job, _ = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=completed_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="notify-best"),
    )
    await service.run_job(
        job_id=job.id,
        tenant_id=test_tenant_a.id,
        client=_SuccessClient(),
        parser_version=1,
    )

    outbox_events = list(
        (
            await db_session.execute(
                select(NotificationOutboxEvent).where(NotificationOutboxEvent.tenant_id == test_tenant_a.id)
            )
        ).scalars()
    )

    assert len(outbox_events) == 1
    assert outbox_events[0].payload["best_price"] == "1000.00"


@pytest.mark.asyncio
async def test_collection_completion_without_eligible_result_emits_no_notification(
    db_session: AsyncSession,
    test_tenant_a,
    completed_order,
) -> None:
    await NotificationRecipientService(db_session).create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(phone="010-2222-3333", display_name="알림 수신자"),
    )
    await _create_procurement_template(db_session, test_tenant_a.id)

    service = PriceCollectionService(db_session)
    job, _ = await service.create_job(
        tenant_id=test_tenant_a.id,
        order_id=completed_order.id,
        payload=PriceCollectionJobCreate(idempotency_key="notify-none"),
    )
    await service.run_job(
        job_id=job.id,
        tenant_id=test_tenant_a.id,
        client=_PartialClient(),
        parser_version=1,
    )

    outbox_events = list(
        (
            await db_session.execute(
                select(NotificationOutboxEvent).where(NotificationOutboxEvent.tenant_id == test_tenant_a.id)
            )
        ).scalars()
    )

    assert outbox_events == []
