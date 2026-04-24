"""notification API 라우터."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.notifications.schemas import (
    ConsentType,
    NotificationConsentGrant,
    NotificationConsentRead,
    NotificationRecipientCreate,
    NotificationRecipientRead,
    NotificationRecipientUpdate,
)
from app.notifications.service import NotificationConsentService, NotificationRecipientService
from app.tenancy.dependencies import get_current_tenant
from app.tenancy.models import Tenant

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]


@router.post(
    "/recipients",
    response_model=NotificationRecipientRead,
    status_code=status.HTTP_201_CREATED,
    summary="알림 수신자 생성",
)
async def create_recipient(
    payload: NotificationRecipientCreate,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationRecipientRead:
    recipient = await NotificationRecipientService(session).create_recipient(
        tenant_id=tenant.id,
        payload=payload,
    )
    await session.commit()
    await session.refresh(recipient)
    return NotificationRecipientRead.model_validate(recipient)


@router.get(
    "/recipients",
    response_model=list[NotificationRecipientRead],
    summary="알림 수신자 목록",
)
async def list_recipients(
    tenant: CurrentTenant,
    session: DbSession,
    active_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationRecipientRead]:
    recipients = await NotificationRecipientService(session).list_recipients(
        tenant_id=tenant.id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return [NotificationRecipientRead.model_validate(recipient) for recipient in recipients]


@router.get(
    "/recipients/{recipient_id}",
    response_model=NotificationRecipientRead,
    summary="알림 수신자 단건 조회",
)
async def get_recipient(
    recipient_id: int,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationRecipientRead:
    recipient = await NotificationRecipientService(session).get_recipient_or_404(
        tenant_id=tenant.id,
        recipient_id=recipient_id,
    )
    return NotificationRecipientRead.model_validate(recipient)


@router.patch(
    "/recipients/{recipient_id}",
    response_model=NotificationRecipientRead,
    summary="알림 수신자 수정",
)
async def update_recipient(
    recipient_id: int,
    payload: NotificationRecipientUpdate,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationRecipientRead:
    recipient = await NotificationRecipientService(session).update_recipient(
        tenant_id=tenant.id,
        recipient_id=recipient_id,
        payload=payload,
    )
    await session.commit()
    await session.refresh(recipient)
    return NotificationRecipientRead.model_validate(recipient)


@router.delete(
    "/recipients/{recipient_id}",
    response_model=NotificationRecipientRead,
    summary="알림 수신자 비활성화",
)
async def deactivate_recipient(
    recipient_id: int,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationRecipientRead:
    recipient = await NotificationRecipientService(session).deactivate_recipient(
        tenant_id=tenant.id,
        recipient_id=recipient_id,
    )
    await session.commit()
    await session.refresh(recipient)
    return NotificationRecipientRead.model_validate(recipient)


@router.post(
    "/recipients/{recipient_id}/consents",
    response_model=NotificationConsentRead,
    status_code=status.HTTP_201_CREATED,
    summary="알림 수신 동의 부여",
)
async def grant_consent(
    recipient_id: int,
    payload: NotificationConsentGrant,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationConsentRead:
    consent = await NotificationConsentService(session).grant_consent(
        tenant_id=tenant.id,
        recipient_id=recipient_id,
        payload=payload,
    )
    await session.commit()
    await session.refresh(consent)
    return NotificationConsentRead.model_validate(consent)


@router.delete(
    "/recipients/{recipient_id}/consents/{consent_type}",
    response_model=NotificationConsentRead,
    summary="알림 수신 동의 철회",
)
async def revoke_consent(
    recipient_id: int,
    consent_type: ConsentType,
    tenant: CurrentTenant,
    session: DbSession,
) -> NotificationConsentRead:
    consent = await NotificationConsentService(session).revoke_consent(
        tenant_id=tenant.id,
        recipient_id=recipient_id,
        consent_type=consent_type,
    )
    await session.commit()
    await session.refresh(consent)
    return NotificationConsentRead.model_validate(consent)
