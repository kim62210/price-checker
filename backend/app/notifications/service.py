"""notification 도메인 서비스."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotificationPolicyError, ServiceError
from app.core.logging import get_logger
from app.notifications.models import (
    NotificationConsent,
    NotificationDeadLetter,
    NotificationDelivery,
    NotificationOutboxEvent,
    NotificationRecipient,
    NotificationTemplate,
    NotificationTemplateVersion,
)
from app.notifications.policy import normalize_phone_e164
from app.notifications.schemas import (
    NotificationConsentGrant,
    NotificationRecipientCreate,
    NotificationRecipientUpdate,
    NotificationTemplateCreate,
    NotificationTemplateVersionCreate,
    RenderedNotification,
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


class TemplateNotFoundError(ServiceError):
    code = "NOT_FOUND"
    http_status = 404
    detail = "template_not_found"


class TemplateAlreadyExistsError(ServiceError):
    code = "CONFLICT"
    http_status = 409
    detail = "template_already_exists"


class TemplateRenderError(ServiceError):
    code = "TEMPLATE_RENDER_ERROR"
    http_status = 400
    detail = "template_render_error"


_VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


@dataclass(frozen=True)
class _TemplateVariables:
    required: tuple[str, ...]

    @classmethod
    def from_payload(cls, variables: list[str]) -> _TemplateVariables:
        return cls(required=tuple(dict.fromkeys(variables)))

    def as_json(self) -> dict[str, object]:
        return {"required": list(self.required)}


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


class NotificationTemplateService:
    """템플릿 카탈로그와 불변 버전 관리 서비스."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_template(
        self,
        *,
        tenant_id: int,
        payload: NotificationTemplateCreate,
    ) -> NotificationTemplate:
        template = NotificationTemplate(
            tenant_id=tenant_id,
            template_code=payload.template_code,
            name=payload.name,
        )
        self._session.add(template)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise TemplateAlreadyExistsError() from exc
        await self._session.refresh(template)
        logger.info("notification_template_created", tenant_id=tenant_id, template_id=template.id)
        return template

    async def create_version(
        self,
        *,
        tenant_id: int,
        template_id: int,
        payload: NotificationTemplateVersionCreate,
    ) -> NotificationTemplateVersion:
        template = await self.get_template_or_404(tenant_id=tenant_id, template_id=template_id)
        self._validate_channel_purpose(channel=payload.channel, purpose=payload.purpose)
        version_number = await self._next_version(template_id=template.id)
        version = NotificationTemplateVersion(
            template_id=template.id,
            tenant_id=tenant_id,
            version=version_number,
            channel=payload.channel,
            purpose=payload.purpose,
            provider_template_key=payload.provider_template_key,
            review_status=payload.review_status,
            locale=payload.locale,
            title=payload.title,
            body=payload.body,
            fallback_body=payload.fallback_body,
            variables=_TemplateVariables.from_payload(payload.variables).as_json(),
        )
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        logger.info(
            "notification_template_version_created",
            tenant_id=tenant_id,
            template_id=template.id,
            version=version.version,
        )
        return version

    async def get_template_or_404(
        self,
        *,
        tenant_id: int,
        template_id: int,
    ) -> NotificationTemplate:
        stmt = select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.tenant_id == tenant_id,
        )
        template = (await self._session.execute(stmt)).scalar_one_or_none()
        if template is None:
            raise TemplateNotFoundError()
        return template

    def render_version(
        self,
        version: NotificationTemplateVersion,
        *,
        variables: dict[str, object],
    ) -> RenderedNotification:
        required = self._required_variables(version)
        missing = [name for name in required if name not in variables]
        if missing:
            raise TemplateRenderError(f"missing_template_variables:{','.join(missing)}")
        return RenderedNotification(
            title=self._render_text(version.title, variables) if version.title else None,
            body=self._render_text(version.body, variables),
            fallback_body=(
                self._render_text(version.fallback_body, variables)
                if version.fallback_body is not None
                else None
            ),
            variables=variables,
        )

    async def _next_version(self, template_id: int) -> int:
        stmt = select(func.max(NotificationTemplateVersion.version)).where(
            NotificationTemplateVersion.template_id == template_id
        )
        current = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(current or 0) + 1

    @staticmethod
    def _validate_channel_purpose(*, channel: str, purpose: str) -> None:
        if channel == "kakao_alimtalk" and purpose == "marketing":
            raise NotificationPolicyError("marketing_alimtalk_not_allowed")

    @staticmethod
    def _required_variables(version: NotificationTemplateVersion) -> tuple[str, ...]:
        raw = version.variables or {}
        values = raw.get("required", [])
        if not isinstance(values, list):
            raise TemplateRenderError("invalid_template_variables")
        return tuple(str(value) for value in values)

    @staticmethod
    def _render_text(text: str, variables: dict[str, object]) -> str:
        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                raise TemplateRenderError(f"missing_template_variables:{name}")
            return str(variables[name])

        return _VARIABLE_PATTERN.sub(_replace, text)


class NotificationDeliveryService:
    """도메인 이벤트를 delivery 로 확장하는 서비스."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._templates = NotificationTemplateService(session)

    async def create_procurement_result_event(
        self,
        *,
        tenant_id: int,
        order_id: int,
        result_id: int,
        shop_id: int,
        product_name: str,
        best_price: object,
        failure_state: str | None = None,
    ) -> NotificationOutboxEvent:
        shop_name = await self._get_shop_name(tenant_id=tenant_id, shop_id=shop_id)
        payload = {
            "status": "failed" if failure_state else "success",
            "failure_state": failure_state,
            "order_id": order_id,
            "result_id": result_id,
            "shop_id": shop_id,
            "shop_name": shop_name,
            "product_name": product_name,
            "best_price": str(best_price),
        }
        event = NotificationOutboxEvent(
            tenant_id=tenant_id,
            event_type="procurement.result.completed",
            aggregate_type="procurement_result",
            aggregate_id=result_id,
            payload=payload,
            idempotency_key=f"procurement_result:{tenant_id}:{result_id}",
            status="pending",
        )
        self._session.add(event)
        try:
            await self._session.flush()
        except IntegrityError:
            existing = await self._get_outbox_by_idempotency(event.idempotency_key)
            if existing is None:
                raise
            return existing

        await self.expand_procurement_result_event(event)
        await self._session.refresh(event)
        return event

    async def expand_procurement_result_event(
        self, event: NotificationOutboxEvent
    ) -> list[NotificationDelivery]:
        recipients = await self._active_recipients(tenant_id=event.tenant_id)
        if not recipients:
            await self._dead_letter(
                tenant_id=event.tenant_id,
                outbox_event_id=event.id,
                reason="no_active_recipients",
                envelope=event.payload,
                recoverable=True,
            )
            event.status = "published"
            await self._session.flush()
            return []

        template_version = await self._approved_template_version(
            tenant_id=event.tenant_id,
            template_code="procurement_result",
        )
        if template_version is None:
            await self._dead_letter(
                tenant_id=event.tenant_id,
                outbox_event_id=event.id,
                reason="missing_procurement_result_template",
                envelope=event.payload,
                recoverable=True,
            )
            event.status = "published"
            await self._session.flush()
            return []

        deliveries: list[NotificationDelivery] = []
        for recipient in recipients:
            rendered = self._templates.render_version(template_version, variables=event.payload)
            delivery = NotificationDelivery(
                tenant_id=event.tenant_id,
                outbox_event_id=event.id,
                procurement_order_id=int(event.payload["order_id"]),
                recipient_id=recipient.id,
                template_version_id=template_version.id,
                channel=template_version.channel,
                purpose=template_version.purpose,
                status="ready",
                idempotency_key=(
                    f"{event.event_type}:{event.aggregate_id}:{recipient.id}:"
                    f"{template_version.channel}:{template_version.id}"
                ),
                rendered_title=rendered.title,
                rendered_body=rendered.body,
                rendered_fallback_body=rendered.fallback_body,
                variable_payload=rendered.variables,
            )
            self._session.add(delivery)
            deliveries.append(delivery)
        event.status = "published"
        await self._session.flush()
        for delivery in deliveries:
            await self._session.refresh(delivery)
        logger.info(
            "notification_deliveries_created",
            tenant_id=event.tenant_id,
            outbox_event_id=event.id,
            delivery_count=len(deliveries),
        )
        return deliveries

    async def _get_shop_name(self, *, tenant_id: int, shop_id: int) -> str:
        stmt = select(Shop.name).where(Shop.id == shop_id, Shop.tenant_id == tenant_id)
        name = (await self._session.execute(stmt)).scalar_one_or_none()
        return str(name or "매장")

    async def _active_recipients(self, *, tenant_id: int) -> list[NotificationRecipient]:
        stmt = select(NotificationRecipient).where(
            NotificationRecipient.tenant_id == tenant_id,
            NotificationRecipient.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _approved_template_version(
        self,
        *,
        tenant_id: int,
        template_code: str,
    ) -> NotificationTemplateVersion | None:
        stmt = (
            select(NotificationTemplateVersion)
            .join(NotificationTemplate, NotificationTemplate.id == NotificationTemplateVersion.template_id)
            .where(
                NotificationTemplate.tenant_id == tenant_id,
                NotificationTemplate.template_code == template_code,
                NotificationTemplate.is_active.is_(True),
                NotificationTemplateVersion.tenant_id == tenant_id,
                NotificationTemplateVersion.channel == "kakao_alimtalk",
                NotificationTemplateVersion.purpose == "transactional",
                NotificationTemplateVersion.review_status == "approved",
            )
            .order_by(NotificationTemplateVersion.version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_sms_fallback_for_delivery(
        self,
        *,
        tenant_id: int,
        delivery_id: int,
        reason: str,
    ) -> NotificationDelivery | None:
        original = await self._get_delivery(tenant_id=tenant_id, delivery_id=delivery_id)
        if original is None or original.channel != "kakao_alimtalk":
            return None
        if not await self._has_active_consent(
            tenant_id=tenant_id,
            recipient_id=original.recipient_id,
            consent_type="sms_marketing",
        ):
            await self._dead_letter(
                tenant_id=tenant_id,
                outbox_event_id=original.outbox_event_id or 0,
                reason="sms_fallback_consent_missing",
                envelope={"delivery_id": original.id, "fallback_reason": reason},
                recoverable=True,
            )
            return None
        if original.rendered_fallback_body is None:
            await self._dead_letter(
                tenant_id=tenant_id,
                outbox_event_id=original.outbox_event_id or 0,
                reason="sms_fallback_body_missing",
                envelope={"delivery_id": original.id, "fallback_reason": reason},
                recoverable=True,
            )
            return None
        fallback = NotificationDelivery(
            tenant_id=tenant_id,
            outbox_event_id=original.outbox_event_id,
            procurement_order_id=original.procurement_order_id,
            recipient_id=original.recipient_id,
            template_version_id=original.template_version_id,
            channel="sms",
            purpose="fallback",
            status="ready",
            idempotency_key=f"{original.idempotency_key}:sms_fallback",
            rendered_title=original.rendered_title,
            rendered_body=original.rendered_fallback_body,
            rendered_fallback_body=None,
            variable_payload={**original.variable_payload, "fallback_reason": reason},
        )
        self._session.add(fallback)
        try:
            await self._session.flush()
        except IntegrityError:
            existing = await self._get_delivery_by_idempotency(fallback.idempotency_key)
            if existing is None:
                raise
            return existing
        await self._session.refresh(fallback)
        logger.info(
            "notification_sms_fallback_created",
            tenant_id=tenant_id,
            source_delivery_id=original.id,
            fallback_delivery_id=fallback.id,
        )
        return fallback

    async def _get_delivery(
        self,
        *,
        tenant_id: int,
        delivery_id: int,
    ) -> NotificationDelivery | None:
        stmt = select(NotificationDelivery).where(
            NotificationDelivery.tenant_id == tenant_id,
            NotificationDelivery.id == delivery_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_delivery_by_idempotency(self, idempotency_key: str) -> NotificationDelivery | None:
        stmt = select(NotificationDelivery).where(NotificationDelivery.idempotency_key == idempotency_key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _has_active_consent(
        self,
        *,
        tenant_id: int,
        recipient_id: int,
        consent_type: str,
    ) -> bool:
        stmt = select(NotificationConsent.id).where(
            NotificationConsent.tenant_id == tenant_id,
            NotificationConsent.recipient_id == recipient_id,
            NotificationConsent.consent_type == consent_type,
            NotificationConsent.revoked_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def _dead_letter(
        self,
        *,
        tenant_id: int,
        outbox_event_id: int,
        reason: str,
        envelope: dict[str, object],
        recoverable: bool,
    ) -> NotificationDeadLetter:
        dead_letter = NotificationDeadLetter(
            tenant_id=tenant_id,
            outbox_event_id=outbox_event_id,
            reason=reason,
            envelope=envelope,
            recoverable=recoverable,
        )
        self._session.add(dead_letter)
        await self._session.flush()
        await self._session.refresh(dead_letter)
        logger.warning(
            "notification_dead_letter_created",
            tenant_id=tenant_id,
            outbox_event_id=outbox_event_id,
            reason=reason,
        )
        return dead_letter

    async def _get_outbox_by_idempotency(
        self,
        idempotency_key: str,
    ) -> NotificationOutboxEvent | None:
        stmt = select(NotificationOutboxEvent).where(
            NotificationOutboxEvent.idempotency_key == idempotency_key
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
