"""notification recipient 서비스·라우터 테스트."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.schemas import NotificationRecipientCreate, NotificationRecipientUpdate
from app.notifications.service import (
    NotificationRecipientService,
    RecipientAlreadyExistsError,
    RecipientNotFoundError,
)


@pytest.mark.asyncio
async def test_create_recipient_normalizes_korean_phone(
    db_session: AsyncSession,
    test_tenant_a,
) -> None:
    recipient = await NotificationRecipientService(db_session).create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(
            phone="010-1234-5678",
            display_name="알파 매장",
        ),
    )

    assert recipient.phone_e164 == "+821012345678"
    assert recipient.display_name == "알파 매장"
    assert recipient.is_active is True


@pytest.mark.asyncio
async def test_recipient_crud_is_tenant_scoped(
    db_session: AsyncSession,
    test_tenant_a,
    test_tenant_b,
) -> None:
    service = NotificationRecipientService(db_session)
    recipient = await service.create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(
            phone="010-2222-3333",
            display_name="테넌트 A 수신자",
        ),
    )

    assert await service.get_recipient(tenant_id=test_tenant_b.id, recipient_id=recipient.id) is None
    with pytest.raises(RecipientNotFoundError):
        await service.update_recipient(
            tenant_id=test_tenant_b.id,
            recipient_id=recipient.id,
            payload=NotificationRecipientUpdate(display_name="침범"),
        )

    updated = await service.update_recipient(
        tenant_id=test_tenant_a.id,
        recipient_id=recipient.id,
        payload=NotificationRecipientUpdate(display_name="수정된 수신자"),
    )
    assert updated.display_name == "수정된 수신자"

    deactivated = await service.deactivate_recipient(
        tenant_id=test_tenant_a.id,
        recipient_id=recipient.id,
    )
    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_duplicate_normalized_phone_is_rejected_per_tenant(
    db_session: AsyncSession,
    test_tenant_a,
    test_tenant_b,
) -> None:
    service = NotificationRecipientService(db_session)
    await service.create_recipient(
        tenant_id=test_tenant_a.id,
        payload=NotificationRecipientCreate(phone="010-9999-0000", display_name="첫 수신자"),
    )

    with pytest.raises(RecipientAlreadyExistsError):
        await service.create_recipient(
            tenant_id=test_tenant_a.id,
            payload=NotificationRecipientCreate(phone="010 9999 0000", display_name="중복 수신자"),
        )

    other_tenant_recipient = await service.create_recipient(
        tenant_id=test_tenant_b.id,
        payload=NotificationRecipientCreate(phone="010-9999-0000", display_name="다른 테넌트"),
    )
    assert other_tenant_recipient.phone_e164 == "+821099990000"


@pytest.mark.asyncio
async def test_recipient_router_crud_and_cross_tenant_blocking(
    client: AsyncClient,
    auth_headers_a,
    auth_headers_b,
) -> None:
    create_response = await client.post(
        "/api/v1/notifications/recipients",
        json={"phone": "010 4444 5555", "display_name": "라우터 수신자"},
        headers=auth_headers_a,
    )
    assert create_response.status_code == 201, create_response.text
    recipient_id = create_response.json()["id"]
    assert create_response.json()["phone_e164"] == "+821044445555"

    list_response = await client.get("/api/v1/notifications/recipients", headers=auth_headers_a)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [recipient_id]

    blocked_response = await client.get(
        f"/api/v1/notifications/recipients/{recipient_id}",
        headers=auth_headers_b,
    )
    assert blocked_response.status_code == 404

    update_response = await client.patch(
        f"/api/v1/notifications/recipients/{recipient_id}",
        json={"display_name": "업데이트 수신자"},
        headers=auth_headers_a,
    )
    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == "업데이트 수신자"

    delete_response = await client.delete(
        f"/api/v1/notifications/recipients/{recipient_id}",
        headers=auth_headers_a,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_active"] is False
