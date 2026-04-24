"""notification 도메인 Pydantic 스키마."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ConsentType = Literal[
    "kakao_transactional",
    "kakao_marketing",
    "sms_marketing",
    "nighttime_ads",
]


class NotificationRecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    shop_id: int | None = None
    user_id: int | None = None
    phone_e164: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationRecipientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    phone: str = Field(..., min_length=1, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=255)
    shop_id: int | None = Field(default=None, ge=1)
    user_id: int | None = Field(default=None, ge=1)


class NotificationRecipientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    phone: str | None = Field(default=None, min_length=1, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    shop_id: int | None = Field(default=None, ge=1)
    user_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class NotificationConsentGrant(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    consent_type: ConsentType
    consent_source: str = Field(..., min_length=1, max_length=128)
    evidence: dict[str, object] = Field(default_factory=dict)
    granted_at: datetime | None = None


class NotificationConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    recipient_id: int
    consent_type: ConsentType
    consent_source: str
    evidence: dict[str, object]
    granted_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime
