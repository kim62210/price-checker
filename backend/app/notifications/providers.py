"""notification provider adapter 계약."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    provider_message_id: str | None = None
    retryable: bool = False
    error_code: str | None = None
    error_message: str | None = None
