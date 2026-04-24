"""notification 도메인 스키마 추가.

Revision ID: 002_notification_domain
Revises: 001_pivot_multi_tenant
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002_notification_domain"
down_revision: str | None = "001_pivot_multi_tenant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine[object]:
    return JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "notification_recipients",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("shop_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_recipients_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], name="fk_notification_recipients_shop_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notification_recipients_user_id", ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "phone_e164", name="uq_notification_recipients_phone"),
    )
    op.create_index("ix_notification_recipients_tenant_id", "notification_recipients", ["tenant_id"])
    op.create_index("ix_notification_recipients_tenant_created", "notification_recipients", ["tenant_id", "created_at"])
    op.create_index("ix_notification_recipients_tenant_active", "notification_recipients", ["tenant_id", "is_active"])

    op.create_table(
        "notification_consents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("consent_type", sa.String(length=32), nullable=False),
        sa.Column("consent_source", sa.String(length=128), nullable=False),
        sa.Column("evidence", _json_type(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_consents_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["notification_recipients.id"], name="fk_notification_consents_recipient_id", ondelete="CASCADE"),
        sa.UniqueConstraint("recipient_id", "consent_type", name="uq_notification_consents_type"),
        sa.CheckConstraint("consent_type IN ('kakao_transactional', 'kakao_marketing', 'sms_marketing', 'nighttime_ads')", name="ck_notification_consents_type"),
    )
    op.create_index("ix_notification_consents_tenant_id", "notification_consents", ["tenant_id"])
    op.create_index("ix_notification_consents_tenant_type", "notification_consents", ["tenant_id", "consent_type"])

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("template_code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_templates_tenant_id", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "template_code", name="uq_notification_templates_code"),
    )
    op.create_index("ix_notification_templates_tenant_id", "notification_templates", ["tenant_id"])
    op.create_index("ix_notification_templates_tenant", "notification_templates", ["tenant_id"])

    op.create_table(
        "notification_template_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("template_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("provider_template_key", sa.String(length=255), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("fallback_body", sa.Text(), nullable=True),
        sa.Column("variables", _json_type(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"], name="fk_notification_template_versions_template_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_template_versions_tenant_id", ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "version", name="uq_notification_template_versions_version"),
        sa.CheckConstraint("channel IN ('kakao_alimtalk', 'kakao_brand_message', 'sms', 'lms')", name="ck_notification_template_versions_channel"),
        sa.CheckConstraint("purpose IN ('transactional', 'marketing', 'fallback')", name="ck_notification_template_versions_purpose"),
        sa.CheckConstraint("review_status IN ('draft', 'pending', 'approved', 'rejected', 'archived')", name="ck_notification_template_versions_review_status"),
    )
    op.create_index("ix_notification_template_versions_tenant_id", "notification_template_versions", ["tenant_id"])
    op.create_index("ix_notification_template_versions_template", "notification_template_versions", ["template_id"])

    op.create_table(
        "notification_outbox_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", _json_type(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_outbox_events_tenant_id", ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_notification_outbox_events_idempotency"),
        sa.CheckConstraint("status IN ('pending', 'processing', 'published', 'retry_scheduled', 'dead_lettered')", name="ck_notification_outbox_events_status"),
    )
    op.create_index("ix_notification_outbox_events_tenant_id", "notification_outbox_events", ["tenant_id"])
    op.create_index("ix_notification_outbox_events_pending", "notification_outbox_events", ["status", "next_retry_at"])
    op.create_index("ix_notification_outbox_events_tenant_created", "notification_outbox_events", ["tenant_id", "created_at"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("outbox_event_id", sa.BigInteger(), nullable=True),
        sa.Column("procurement_order_id", sa.BigInteger(), nullable=True),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("template_version_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("rendered_title", sa.String(length=255), nullable=True),
        sa.Column("rendered_body", sa.Text(), nullable=False),
        sa.Column("rendered_link", sa.Text(), nullable=True),
        sa.Column("rendered_fallback_body", sa.Text(), nullable=True),
        sa.Column("variable_payload", _json_type(), nullable=False),
        sa.Column("provider_account", sa.String(length=128), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_deliveries_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["notification_outbox_events.id"], name="fk_notification_deliveries_outbox_event_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["procurement_order_id"], ["procurement_orders.id"], name="fk_notification_deliveries_procurement_order_id", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recipient_id"], ["notification_recipients.id"], name="fk_notification_deliveries_recipient_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_version_id"], ["notification_template_versions.id"], name="fk_notification_deliveries_template_version_id", ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key", name="uq_notification_deliveries_idempotency"),
        sa.CheckConstraint("channel IN ('kakao_alimtalk', 'kakao_brand_message', 'sms', 'lms')", name="ck_notification_deliveries_channel"),
        sa.CheckConstraint("purpose IN ('transactional', 'marketing', 'fallback')", name="ck_notification_deliveries_purpose"),
        sa.CheckConstraint("status IN ('queued', 'rendering', 'ready', 'sending', 'sent', 'delivered', 'failed', 'blocked', 'retry_scheduled', 'dead_lettered')", name="ck_notification_deliveries_status"),
    )
    op.create_index("ix_notification_deliveries_tenant_id", "notification_deliveries", ["tenant_id"])
    op.create_index("ix_notification_deliveries_tenant_status", "notification_deliveries", ["tenant_id", "status"])
    op.create_index("ix_notification_deliveries_provider_message", "notification_deliveries", ["provider_account", "provider_message_id"])

    op.create_table(
        "notification_delivery_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_response", _json_type(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_delivery_attempts_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_id"], ["notification_deliveries.id"], name="fk_notification_delivery_attempts_delivery_id", ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('success', 'retryable_failure', 'permanent_failure')", name="ck_notification_delivery_attempts_status"),
    )
    op.create_index("ix_notification_delivery_attempts_tenant_id", "notification_delivery_attempts", ["tenant_id"])
    op.create_index("ix_notification_delivery_attempts_delivery", "notification_delivery_attempts", ["delivery_id", "attempted_at"])

    op.create_table(
        "provider_callbacks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_account", sa.String(length=128), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("callback_type", sa.String(length=128), nullable=False),
        sa.Column("raw_payload", _json_type(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_provider_callbacks_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_id"], ["notification_deliveries.id"], name="fk_provider_callbacks_delivery_id", ondelete="SET NULL"),
    )
    op.create_index("ix_provider_callbacks_tenant_id", "provider_callbacks", ["tenant_id"])
    op.create_index("ix_provider_callbacks_provider_message", "provider_callbacks", ["provider_account", "provider_message_id"])
    op.create_index("ix_provider_callbacks_tenant_received", "provider_callbacks", ["tenant_id", "received_at"])

    op.create_table(
        "notification_dead_letters",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("outbox_event_id", sa.BigInteger(), nullable=True),
        sa.Column("delivery_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("envelope", _json_type(), nullable=False),
        sa.Column("recoverable", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_notification_dead_letters_tenant_id", ondelete="CASCADE"),
    )
    op.create_index("ix_notification_dead_letters_tenant_id", "notification_dead_letters", ["tenant_id"])
    op.create_index("ix_notification_dead_letters_tenant_created", "notification_dead_letters", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_dead_letters_tenant_created", table_name="notification_dead_letters")
    op.drop_index("ix_notification_dead_letters_tenant_id", table_name="notification_dead_letters")
    op.drop_table("notification_dead_letters")

    op.drop_index("ix_provider_callbacks_tenant_received", table_name="provider_callbacks")
    op.drop_index("ix_provider_callbacks_provider_message", table_name="provider_callbacks")
    op.drop_index("ix_provider_callbacks_tenant_id", table_name="provider_callbacks")
    op.drop_table("provider_callbacks")

    op.drop_index("ix_notification_delivery_attempts_delivery", table_name="notification_delivery_attempts")
    op.drop_index("ix_notification_delivery_attempts_tenant_id", table_name="notification_delivery_attempts")
    op.drop_table("notification_delivery_attempts")

    op.drop_index("ix_notification_deliveries_provider_message", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_tenant_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_tenant_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("ix_notification_outbox_events_tenant_created", table_name="notification_outbox_events")
    op.drop_index("ix_notification_outbox_events_pending", table_name="notification_outbox_events")
    op.drop_index("ix_notification_outbox_events_tenant_id", table_name="notification_outbox_events")
    op.drop_table("notification_outbox_events")

    op.drop_index("ix_notification_template_versions_template", table_name="notification_template_versions")
    op.drop_index("ix_notification_template_versions_tenant_id", table_name="notification_template_versions")
    op.drop_table("notification_template_versions")

    op.drop_index("ix_notification_templates_tenant", table_name="notification_templates")
    op.drop_index("ix_notification_templates_tenant_id", table_name="notification_templates")
    op.drop_table("notification_templates")

    op.drop_index("ix_notification_consents_tenant_type", table_name="notification_consents")
    op.drop_index("ix_notification_consents_tenant_id", table_name="notification_consents")
    op.drop_table("notification_consents")

    op.drop_index("ix_notification_recipients_tenant_active", table_name="notification_recipients")
    op.drop_index("ix_notification_recipients_tenant_created", table_name="notification_recipients")
    op.drop_index("ix_notification_recipients_tenant_id", table_name="notification_recipients")
    op.drop_table("notification_recipients")
