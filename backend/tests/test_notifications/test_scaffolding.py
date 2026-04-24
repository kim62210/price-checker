"""notification 도메인 스캐폴드 계약 테스트."""

from __future__ import annotations

from starlette import status

from app.core.config import Settings
from app.core.exceptions import NotificationPolicyError, NotificationProviderError


def test_notification_settings_have_safe_defaults() -> None:
    settings = Settings()

    assert settings.notification_provider_mode == "fake"
    assert settings.notification_retry_max_attempts == 3
    assert settings.notification_webhook_secret.get_secret_value() == ""


def test_notification_errors_use_service_error_contract() -> None:
    policy_error = NotificationPolicyError("missing_consent")
    provider_error = NotificationProviderError("provider_failed")

    assert policy_error.code == "NOTIFICATION_POLICY_ERROR"
    assert policy_error.http_status == status.HTTP_400_BAD_REQUEST
    assert provider_error.code == "NOTIFICATION_PROVIDER_ERROR"
    assert provider_error.http_status == status.HTTP_502_BAD_GATEWAY
