"""procurement 결과에서 notification delivery 생성 테스트."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import (
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationOutboxEvent,
)
from app.notifications.schemas import (
    NotificationRecipientCreate,
    NotificationTemplateCreate,
    NotificationTemplateVersionCreate,
)
from app.notifications.service import NotificationRecipientService, NotificationTemplateService
from app.tenancy.models import Shop


@pytest.fixture
async def notification_shop(db_session: AsyncSession, test_tenant_a):
    shop = Shop(tenant_id=test_tenant_a.id, name="알림 테스트 매장")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


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


@pytest.mark.asyncio
async def test_completed_procurement_result_creates_alimtalk_delivery(
    client: AsyncClient,
    auth_headers_a,
    db_session: AsyncSession,
    test_tenant_a,
    notification_shop,
) -> None:
    await NotificationRecipientService(db_session).create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(phone="010-1111-2222", display_name="알림 수신자"),
    )
    await _create_procurement_template(db_session, test_tenant_a.id)
    await db_session.commit()

    order_response = await client.post(
        "/api/v1/procurement/orders",
        json={
            "shop_id": notification_shop.id,
            "product_name": "우유",
            "quantity": 10,
            "unit": "개",
            "target_unit_price": "2000.00",
            "status": "completed",
        },
        headers=auth_headers_a,
    )
    assert order_response.status_code == 201, order_response.text
    order_id = order_response.json()["id"]

    result_response = await client.post(
        f"/api/v1/procurement/orders/{order_id}/results",
        json={
            "source": "naver",
            "product_url": "https://example.com/milk",
            "seller_name": "네이버 판매자",
            "listed_price": "15000.00",
            "per_unit_price": "1500.00",
            "shipping_fee": "3000.00",
            "unit_count": 10,
        },
        headers=auth_headers_a,
    )
    assert result_response.status_code == 201, result_response.text

    outbox_events = list(
        (
            await db_session.execute(
                select(NotificationOutboxEvent).where(NotificationOutboxEvent.tenant_id == test_tenant_a.id)
            )
        ).scalars()
    )
    deliveries = list(
        (
            await db_session.execute(
                select(NotificationDelivery).where(NotificationDelivery.tenant_id == test_tenant_a.id)
            )
        ).scalars()
    )

    assert len(outbox_events) == 1
    assert outbox_events[0].event_type == "procurement.result.completed"
    assert len(deliveries) == 1
    assert deliveries[0].channel == "kakao_alimtalk"
    assert deliveries[0].purpose == "transactional"
    assert deliveries[0].rendered_body == "알림 테스트 매장 우유 최저가 1500.00원"


@pytest.mark.asyncio
async def test_missing_active_recipient_skips_delivery_with_dead_letter(
    client: AsyncClient,
    auth_headers_a,
    db_session: AsyncSession,
    test_tenant_a,
    notification_shop,
) -> None:
    await _create_procurement_template(db_session, test_tenant_a.id)
    await db_session.commit()

    order_response = await client.post(
        "/api/v1/procurement/orders",
        json={
            "shop_id": notification_shop.id,
            "product_name": "두유",
            "quantity": 5,
            "unit": "개",
            "target_unit_price": "1000.00",
            "status": "completed",
        },
        headers=auth_headers_a,
    )
    assert order_response.status_code == 201, order_response.text
    order_id = order_response.json()["id"]

    result_response = await client.post(
        f"/api/v1/procurement/orders/{order_id}/results",
        json={
            "source": "manual",
            "product_url": "https://example.com/soy",
            "listed_price": "4500.00",
            "per_unit_price": "900.00",
            "shipping_fee": "0.00",
            "unit_count": 5,
        },
        headers=auth_headers_a,
    )
    assert result_response.status_code == 201, result_response.text

    delivery_count = (
        await db_session.execute(
            select(NotificationDelivery).where(NotificationDelivery.tenant_id == test_tenant_a.id)
        )
    ).scalars().all()
    dead_letters = list(
        (
            await db_session.execute(
                select(NotificationDeadLetter).where(NotificationDeadLetter.tenant_id == test_tenant_a.id)
            )
        ).scalars()
    )

    assert delivery_count == []
    assert len(dead_letters) == 1
    assert dead_letters[0].reason == "no_active_recipients"
    assert dead_letters[0].recoverable is True
