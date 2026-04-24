"""notification 도메인 모델 계약 테스트."""

from __future__ import annotations

import app.procurement.models  # noqa: F401
import app.tenancy.models  # noqa: F401
from app.models.base import Base
from app.notifications import models


def test_notification_models_register_expected_tables() -> None:
    expected_tables = {
        "notification_recipients",
        "notification_consents",
        "notification_templates",
        "notification_template_versions",
        "notification_outbox_events",
        "notification_deliveries",
        "notification_delivery_attempts",
        "provider_callbacks",
        "notification_dead_letters",
    }

    assert expected_tables.issubset(Base.metadata.tables)


def test_delivery_has_idempotency_unique_constraint() -> None:
    table = models.NotificationDelivery.__table__

    unique_names = {constraint.name for constraint in table.constraints}

    assert "uq_notification_deliveries_idempotency" in unique_names


def test_recipient_model_keeps_phone_normalized() -> None:
    recipient = models.NotificationRecipient(
        tenant_id=1,
        phone_e164="+821012345678",
        display_name="테스트 매장",
    )

    assert recipient.phone_e164 == "+821012345678"
    assert recipient.is_active is True
