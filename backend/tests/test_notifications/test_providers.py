"""notification provider/fallback 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import NotificationDelivery
from app.notifications.providers import (
    FakeNotificationProvider,
    NotificationProviderRequest,
    ProviderResultStatus,
)
from app.notifications.schemas import (
    NotificationConsentGrant,
    NotificationRecipientCreate,
    NotificationTemplateCreate,
    NotificationTemplateVersionCreate,
)
from app.notifications.service import (
    NotificationConsentService,
    NotificationDeliveryService,
    NotificationRecipientService,
    NotificationTemplateService,
)


async def _create_delivery(db_session: AsyncSession, tenant_id: int) -> NotificationDelivery:
    recipient = await NotificationRecipientService(db_session).create_recipient(
        tenant_id=tenant_id,
        payload=NotificationRecipientCreate(phone="010-3333-4444", display_name="fallback 수신자"),
    )
    template_service = NotificationTemplateService(db_session)
    template = await template_service.create_template(
        tenant_id=tenant_id,
        payload=NotificationTemplateCreate(template_code="provider_test", name="provider test"),
    )
    version = await template_service.create_version(
        tenant_id=tenant_id,
        template_id=template.id,
        payload=NotificationTemplateVersionCreate(
            channel="kakao_alimtalk",
            purpose="transactional",
            review_status="approved",
            body="알림톡 본문 {{name}}",
            fallback_body="SMS 본문 {{name}}",
            variables=["name"],
        ),
    )
    delivery = NotificationDelivery(
        tenant_id=tenant_id,
        recipient_id=recipient.id,
        template_version_id=version.id,
        channel="kakao_alimtalk",
        purpose="transactional",
        status="ready",
        idempotency_key="provider-test-delivery",
        rendered_body="알림톡 본문 알파",
        rendered_fallback_body="SMS 본문 알파",
        variable_payload={"name": "알파"},
    )
    db_session.add(delivery)
    await db_session.flush()
    await db_session.refresh(delivery)
    return delivery


@pytest.mark.asyncio
async def test_fake_provider_success_and_failures() -> None:
    request = NotificationProviderRequest(
        delivery_id=1,
        channel="kakao_alimtalk",
        recipient_phone="+821033334444",
        body="본문",
    )

    success = await FakeNotificationProvider(status=ProviderResultStatus.SUCCESS).send(request)
    retryable = await FakeNotificationProvider(status=ProviderResultStatus.RETRYABLE_FAILURE).send(request)
    permanent = await FakeNotificationProvider(status=ProviderResultStatus.PERMANENT_FAILURE).send(request)

    assert success.status == ProviderResultStatus.SUCCESS
    assert success.provider_message_id is not None
    assert retryable.retryable is True
    assert permanent.retryable is False


@pytest.mark.asyncio
async def test_alimtalk_failure_creates_sms_fallback_when_allowed(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    delivery = await _create_delivery(db_session, test_tenant_a.id)
    await NotificationConsentService(db_session).grant_consent(
        tenant_id=test_tenant_a.id,
        recipient_id=delivery.recipient_id,
        payload=NotificationConsentGrant(
            consent_type="sms_marketing",
            consent_source="admin",
            granted_at=datetime.now(tz=UTC),
        ),
    )

    fallback = await NotificationDeliveryService(db_session).create_sms_fallback_for_delivery(
        tenant_id=test_tenant_a.id,
        delivery_id=delivery.id,
        reason="alimtalk_failed",
    )

    assert fallback is not None
    assert fallback.channel == "sms"
    assert fallback.purpose == "fallback"
    assert fallback.rendered_body == "SMS 본문 알파"
    assert fallback.idempotency_key.endswith(":sms_fallback")


@pytest.mark.asyncio
async def test_sms_fallback_blocked_without_sms_consent(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    delivery = await _create_delivery(db_session, test_tenant_a.id)

    fallback = await NotificationDeliveryService(db_session).create_sms_fallback_for_delivery(
        tenant_id=test_tenant_a.id,
        delivery_id=delivery.id,
        reason="alimtalk_failed",
    )

    rows = list(
        (
            await db_session.execute(
                select(NotificationDelivery).where(NotificationDelivery.tenant_id == test_tenant_a.id)
            )
        ).scalars()
    )
    assert fallback is None
    assert len(rows) == 1
