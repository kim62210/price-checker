"""notification consent 서비스·라우터 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.schemas import (
    NotificationConsentGrant,
    NotificationRecipientCreate,
)
from app.notifications.service import NotificationConsentService, NotificationRecipientService


@pytest.mark.asyncio
async def test_grant_and_revoke_consent(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    recipient = await NotificationRecipientService(db_session).create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(phone="010-5555-6666", display_name="동의 수신자"),
    )
    consent_service = NotificationConsentService(db_session)
    granted_at = datetime(2026, 4, 24, 9, 0, tzinfo=UTC)

    consent = await consent_service.grant_consent(
        tenant_id=test_tenant_a.id,
        recipient_id=recipient.id,
        payload=NotificationConsentGrant(
            consent_type="kakao_marketing",
            consent_source="admin_import",
            evidence={"ip": "127.0.0.1"},
            granted_at=granted_at,
        ),
    )

    assert consent.consent_type == "kakao_marketing"
    assert consent.revoked_at is None

    regranted = await consent_service.grant_consent(
        tenant_id=test_tenant_a.id,
        recipient_id=recipient.id,
        payload=NotificationConsentGrant(
            consent_type="kakao_marketing",
            consent_source="admin_import_v2",
            evidence={"ip": "127.0.0.2"},
            granted_at=granted_at,
        ),
    )
    assert regranted.id == consent.id
    assert regranted.consent_source == "admin_import_v2"

    revoked = await consent_service.revoke_consent(
        tenant_id=test_tenant_a.id,
        recipient_id=recipient.id,
        consent_type="kakao_marketing",
    )
    assert revoked.revoked_at is not None


@pytest.mark.asyncio
async def test_consent_router_blocks_cross_tenant_recipient(
    client: AsyncClient,
    auth_headers_a,
    auth_headers_b,
) -> None:
    create_response = await client.post(
        "/api/v1/notifications/recipients",
        json={"phone": "010-7777-8888", "display_name": "동의 라우터 수신자"},
        headers=auth_headers_a,
    )
    assert create_response.status_code == 201, create_response.text
    recipient_id = create_response.json()["id"]

    blocked_response = await client.post(
        f"/api/v1/notifications/recipients/{recipient_id}/consents",
        json={"consent_type": "sms_marketing", "consent_source": "admin"},
        headers=auth_headers_b,
    )
    assert blocked_response.status_code == 404

    grant_response = await client.post(
        f"/api/v1/notifications/recipients/{recipient_id}/consents",
        json={"consent_type": "sms_marketing", "consent_source": "admin"},
        headers=auth_headers_a,
    )
    assert grant_response.status_code == 201, grant_response.text
    assert grant_response.json()["consent_type"] == "sms_marketing"

    revoke_response = await client.delete(
        f"/api/v1/notifications/recipients/{recipient_id}/consents/sms_marketing",
        headers=auth_headers_a,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked_at"] is not None
