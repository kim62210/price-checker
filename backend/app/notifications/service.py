"""notification 도메인 서비스."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceError
from app.core.logging import get_logger
from app.notifications.models import NotificationConsent, NotificationRecipient
from app.notifications.policy import normalize_phone_e164
from app.notifications.schemas import (
    NotificationConsentGrant,
    NotificationRecipientCreate,
    NotificationRecipientUpdate,
)
from app.tenancy.models import Shop, User

logger = get_logger(__name__)


class RecipientNotFoundError(ServiceError):
    code = "NOT_FOUND"
    http_status = 404
    detail = "recipient_not_found"


class ConsentNotFoundError(ServiceError):
    code = "NOT_FOUND"
    http_status = 404
    detail = "consent_not_found"


class RecipientAlreadyExistsError(ServiceError):
    code = "CONFLICT"
    http_status = 409
    detail = "recipient_already_exists"


class NotificationRecipientService:
    """알림 수신자 CRUD — 모든 조회는 tenant_id 로 격리한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_recipient(
        self,
        *,
        tenant_id: int,
        payload: NotificationRecipientCreate,
    ) -> NotificationRecipient:
        await self._ensure_optional_refs_belong_to_tenant(
            tenant_id=tenant_id,
            shop_id=payload.shop_id,
            user_id=payload.user_id,
        )
        recipient = NotificationRecipient(
            tenant_id=tenant_id,
            shop_id=payload.shop_id,
            user_id=payload.user_id,
            phone_e164=normalize_phone_e164(payload.phone),
            display_name=payload.display_name,
        )
        self._session.add(recipient)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise RecipientAlreadyExistsError() from exc
        await self._session.refresh(recipient)
        logger.info("notification_recipient_created", tenant_id=tenant_id, recipient_id=recipient.id)
        return recipient

    async def list_recipients(
        self,
        *,
        tenant_id: int,
        active_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationRecipient]:
        stmt = (
            select(NotificationRecipient)
            .where(NotificationRecipient.tenant_id == tenant_id)
            .order_by(NotificationRecipient.created_at.desc(), NotificationRecipient.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if active_only:
            stmt = stmt.where(NotificationRecipient.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recipient(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
    ) -> NotificationRecipient | None:
        stmt = select(NotificationRecipient).where(
            NotificationRecipient.id == recipient_id,
            NotificationRecipient.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recipient_or_404(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
    ) -> NotificationRecipient:
        recipient = await self.get_recipient(tenant_id=tenant_id, recipient_id=recipient_id)
        if recipient is None:
            raise RecipientNotFoundError()
        return recipient

    async def update_recipient(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
        payload: NotificationRecipientUpdate,
    ) -> NotificationRecipient:
        recipient = await self.get_recipient_or_404(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
        )
        await self._ensure_optional_refs_belong_to_tenant(
            tenant_id=tenant_id,
            shop_id=payload.shop_id if "shop_id" in payload.model_fields_set else None,
            user_id=payload.user_id if "user_id" in payload.model_fields_set else None,
        )
        if payload.phone is not None:
            recipient.phone_e164 = normalize_phone_e164(payload.phone)
        if payload.display_name is not None:
            recipient.display_name = payload.display_name
        if "shop_id" in payload.model_fields_set:
            recipient.shop_id = payload.shop_id
        if "user_id" in payload.model_fields_set:
            recipient.user_id = payload.user_id
        if payload.is_active is not None:
            recipient.is_active = payload.is_active
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise RecipientAlreadyExistsError() from exc
        await self._session.refresh(recipient)
        logger.info("notification_recipient_updated", tenant_id=tenant_id, recipient_id=recipient.id)
        return recipient

    async def deactivate_recipient(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
    ) -> NotificationRecipient:
        recipient = await self.get_recipient_or_404(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
        )
        recipient.is_active = False
        await self._session.flush()
        await self._session.refresh(recipient)
        logger.info("notification_recipient_deactivated", tenant_id=tenant_id, recipient_id=recipient.id)
        return recipient

    async def _ensure_optional_refs_belong_to_tenant(
        self,
        *,
        tenant_id: int,
        shop_id: int | None,
        user_id: int | None,
    ) -> None:
        if shop_id is not None:
            shop = (
                await self._session.execute(
                    select(Shop.id).where(Shop.id == shop_id, Shop.tenant_id == tenant_id)
                )
            ).scalar_one_or_none()
            if shop is None:
                raise RecipientNotFoundError()
        if user_id is not None:
            user = (
                await self._session.execute(
                    select(User.id).where(User.id == user_id, User.tenant_id == tenant_id)
                )
            ).scalar_one_or_none()
            if user is None:
                raise RecipientNotFoundError()


class NotificationConsentService:
    """수신자 동의 grant/revoke 서비스."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recipients = NotificationRecipientService(session)

    async def grant_consent(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
        payload: NotificationConsentGrant,
    ) -> NotificationConsent:
        await self._recipients.get_recipient_or_404(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
        )
        consent = await self._get_consent(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            consent_type=payload.consent_type,
        )
        granted_at = payload.granted_at or datetime.now(tz=UTC)
        if consent is None:
            consent = NotificationConsent(
                tenant_id=tenant_id,
                recipient_id=recipient_id,
                consent_type=payload.consent_type,
                consent_source=payload.consent_source,
                evidence=payload.evidence,
                granted_at=granted_at,
            )
            self._session.add(consent)
        else:
            consent.consent_source = payload.consent_source
            consent.evidence = payload.evidence
            consent.granted_at = granted_at
            consent.revoked_at = None
        await self._session.flush()
        await self._session.refresh(consent)
        logger.info(
            "notification_consent_granted",
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            consent_type=payload.consent_type,
        )
        return consent

    async def revoke_consent(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
        consent_type: str,
    ) -> NotificationConsent:
        await self._recipients.get_recipient_or_404(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
        )
        consent = await self._get_consent(
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            consent_type=consent_type,
        )
        if consent is None:
            raise ConsentNotFoundError()
        consent.revoked_at = datetime.now(tz=UTC)
        await self._session.flush()
        await self._session.refresh(consent)
        logger.info(
            "notification_consent_revoked",
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            consent_type=consent_type,
        )
        return consent

    async def _get_consent(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
        consent_type: str,
    ) -> NotificationConsent | None:
        stmt = select(NotificationConsent).where(
            NotificationConsent.tenant_id == tenant_id,
            NotificationConsent.recipient_id == recipient_id,
            NotificationConsent.consent_type == consent_type,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
