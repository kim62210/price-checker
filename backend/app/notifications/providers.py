"""notification provider adapter 계약."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ProviderResultStatus(StrEnum):
    SUCCESS = "success"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True)
class NotificationProviderRequest:
    delivery_id: int
    channel: str
    recipient_phone: str
    body: str
    title: str | None = None
    template_key: str | None = None
    fallback_body: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    status: ProviderResultStatus
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        return self.status == ProviderResultStatus.SUCCESS

    @property
    def retryable(self) -> bool:
        return self.status == ProviderResultStatus.RETRYABLE_FAILURE


class NotificationProvider(Protocol):
    async def send(self, request: NotificationProviderRequest) -> ProviderResult:
        """Provider-specific send operation."""


class FakeNotificationProvider:
    def __init__(self, *, status: ProviderResultStatus = ProviderResultStatus.SUCCESS) -> None:
        self._status = status

    async def send(self, request: NotificationProviderRequest) -> ProviderResult:
        if self._status == ProviderResultStatus.SUCCESS:
            return ProviderResult(
                status=ProviderResultStatus.SUCCESS,
                provider_message_id=f"fake-{request.delivery_id}",
            )
        if self._status == ProviderResultStatus.RETRYABLE_FAILURE:
            return ProviderResult(
                status=ProviderResultStatus.RETRYABLE_FAILURE,
                error_code="FAKE_RETRYABLE",
                error_message="fake retryable failure",
            )
        return ProviderResult(
            status=ProviderResultStatus.PERMANENT_FAILURE,
            error_code="FAKE_PERMANENT",
            error_message="fake permanent failure",
        )


class KakaoAlimtalkProvider(FakeNotificationProvider):
    """Kakao Alimtalk adapter boundary.

    실제 딜러사 API는 후속 설정에서 주입한다. 도메인 서비스는 이 경계만 의존한다.
    """


class SmsProvider(FakeNotificationProvider):
    """SMS/LMS adapter boundary."""
