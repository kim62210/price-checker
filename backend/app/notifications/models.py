"""notification 도메인 SQLAlchemy 모델."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.procurement.models import ProcurementOrder
    from app.tenancy.models import Shop, Tenant, User

_bigint = BigInteger().with_variant(Integer(), "sqlite")
_json = JSONB().with_variant(JSON(), "sqlite")

NOTIFICATION_CHANNEL_VALUES = (
    "kakao_alimtalk",
    "kakao_brand_message",
    "sms",
    "lms",
)
MESSAGE_PURPOSE_VALUES = ("transactional", "marketing", "fallback")
CONSENT_TYPE_VALUES = (
    "kakao_transactional",
    "kakao_marketing",
    "sms_marketing",
    "nighttime_ads",
)
TEMPLATE_REVIEW_STATUS_VALUES = ("draft", "pending", "approved", "rejected", "archived")
OUTBOX_STATUS_VALUES = ("pending", "processing", "published", "retry_scheduled", "dead_lettered")
DELIVERY_STATUS_VALUES = (
    "queued",
    "rendering",
    "ready",
    "sending",
    "sent",
    "delivered",
    "failed",
    "blocked",
    "retry_scheduled",
    "dead_lettered",
)
ATTEMPT_STATUS_VALUES = ("success", "retryable_failure", "permanent_failure")


class NotificationRecipient(Base, TimestampMixin):
    """테넌트 스코프 알림 수신자."""

    __tablename__ = "notification_recipients"
    __table_args__ = (
        Index("ix_notification_recipients_tenant_created", "tenant_id", "created_at"),
        Index("ix_notification_recipients_tenant_active", "tenant_id", "is_active"),
        UniqueConstraint("tenant_id", "phone_e164", name="uq_notification_recipients_phone"),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shop_id: Mapped[int | None] = mapped_column(
        _bigint,
        ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        _bigint,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    phone_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")
    shop: Mapped[Shop | None] = relationship("Shop", lazy="raise")
    user: Mapped[User | None] = relationship("User", lazy="raise")
    consents: Mapped[list[NotificationConsent]] = relationship(
        "NotificationConsent",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("is_active", True)
        super().__init__(**kwargs)


class NotificationConsent(Base, TimestampMixin):
    """수신자별 채널/목적 동의 상태."""

    __tablename__ = "notification_consents"
    __table_args__ = (
        UniqueConstraint("recipient_id", "consent_type", name="uq_notification_consents_type"),
        Index("ix_notification_consents_tenant_type", "tenant_id", "consent_type"),
        CheckConstraint(
            f"consent_type IN {CONSENT_TYPE_VALUES}",
            name="ck_notification_consents_type",
        ),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("notification_recipients.id", ondelete="CASCADE"),
        nullable=False,
    )
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_source: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(_json, nullable=False, default=dict)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")
    recipient: Mapped[NotificationRecipient] = relationship(
        "NotificationRecipient",
        back_populates="consents",
    )


class NotificationTemplate(Base, TimestampMixin):
    """안정적인 템플릿 코드 카탈로그."""

    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_code", name="uq_notification_templates_code"),
        Index("ix_notification_templates_tenant", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")
    versions: Mapped[list[NotificationTemplateVersion]] = relationship(
        "NotificationTemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
    )


class NotificationTemplateVersion(Base, TimestampMixin):
    """심사/승인 단위의 불변 템플릿 버전."""

    __tablename__ = "notification_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_notification_template_versions_version"),
        Index("ix_notification_template_versions_template", "template_id"),
        CheckConstraint(
            f"channel IN {NOTIFICATION_CHANNEL_VALUES}",
            name="ck_notification_template_versions_channel",
        ),
        CheckConstraint(
            f"purpose IN {MESSAGE_PURPOSE_VALUES}",
            name="ck_notification_template_versions_purpose",
        ),
        CheckConstraint(
            f"review_status IN {TEMPLATE_REVIEW_STATUS_VALUES}",
            name="ck_notification_template_versions_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("notification_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_template_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="ko-KR")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[dict[str, object]] = mapped_column(_json, nullable=False, default=dict)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped[NotificationTemplate] = relationship(
        "NotificationTemplate",
        back_populates="versions",
    )
    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")


class NotificationOutboxEvent(Base, TimestampMixin):
    """트랜잭션 내구성을 위한 알림 outbox event."""

    __tablename__ = "notification_outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notification_outbox_events_idempotency"),
        Index("ix_notification_outbox_events_pending", "status", "next_retry_at"),
        Index("ix_notification_outbox_events_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(f"status IN {OUTBOX_STATUS_VALUES}", name="ck_notification_outbox_events_status"),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[int] = mapped_column(_bigint, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(_json, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")


class NotificationDelivery(Base, TimestampMixin):
    """수신자·채널·템플릿별 발송 단위."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notification_deliveries_idempotency"),
        Index("ix_notification_deliveries_tenant_status", "tenant_id", "status"),
        Index("ix_notification_deliveries_provider_message", "provider_account", "provider_message_id"),
        CheckConstraint(f"channel IN {NOTIFICATION_CHANNEL_VALUES}", name="ck_notification_deliveries_channel"),
        CheckConstraint(f"purpose IN {MESSAGE_PURPOSE_VALUES}", name="ck_notification_deliveries_purpose"),
        CheckConstraint(f"status IN {DELIVERY_STATUS_VALUES}", name="ck_notification_deliveries_status"),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outbox_event_id: Mapped[int | None] = mapped_column(
        _bigint,
        ForeignKey("notification_outbox_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    procurement_order_id: Mapped[int | None] = mapped_column(
        _bigint,
        ForeignKey("procurement_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("notification_recipients.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_version_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("notification_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    rendered_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rendered_body: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_fallback_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    variable_payload: Mapped[dict[str, object]] = mapped_column(_json, nullable=False, default=dict)
    provider_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")
    recipient: Mapped[NotificationRecipient] = relationship("NotificationRecipient", lazy="raise")
    template_version: Mapped[NotificationTemplateVersion] = relationship(
        "NotificationTemplateVersion",
        lazy="raise",
    )
    procurement_order: Mapped[ProcurementOrder | None] = relationship(
        "ProcurementOrder",
        lazy="raise",
    )


class NotificationDeliveryAttempt(Base):
    """Provider 호출 1회 시도 로그."""

    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        Index("ix_notification_delivery_attempts_delivery", "delivery_id", "attempted_at"),
        CheckConstraint(f"status IN {ATTEMPT_STATUS_VALUES}", name="ck_notification_delivery_attempts_status"),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delivery_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("notification_deliveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict[str, object] | None] = mapped_column(_json, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProviderCallback(Base):
    """Provider receipt/status callback 원본 기록."""

    __tablename__ = "provider_callbacks"
    __table_args__ = (
        Index("ix_provider_callbacks_provider_message", "provider_account", "provider_message_id"),
        Index("ix_provider_callbacks_tenant_received", "tenant_id", "received_at"),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delivery_id: Mapped[int | None] = mapped_column(
        _bigint,
        ForeignKey("notification_deliveries.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_account: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    callback_type: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(_json, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationDeadLetter(Base):
    """최종 실패한 알림 event/delivery 보관."""

    __tablename__ = "notification_dead_letters"
    __table_args__ = (Index("ix_notification_dead_letters_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outbox_event_id: Mapped[int | None] = mapped_column(_bigint, nullable=True)
    delivery_id: Mapped[int | None] = mapped_column(_bigint, nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    envelope: Mapped[dict[str, object]] = mapped_column(_json, nullable=False, default=dict)
    recoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
