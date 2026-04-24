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
NotificationChannel = Literal["kakao_alimtalk", "kakao_brand_message", "sms", "lms"]
MessagePurpose = Literal["transactional", "marketing", "fallback"]
TemplateReviewStatus = Literal["draft", "pending", "approved", "rejected", "archived"]


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


class NotificationTemplateCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    template_code: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class NotificationTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    template_code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationTemplateVersionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    channel: NotificationChannel
    purpose: MessagePurpose
    provider_template_key: str | None = Field(default=None, max_length=255)
    review_status: TemplateReviewStatus = "draft"
    locale: str = Field(default="ko-KR", min_length=2, max_length=16)
    title: str | None = Field(default=None, max_length=255)
    body: str = Field(..., min_length=1)
    fallback_body: str | None = None
    variables: list[str] = Field(default_factory=list)


class NotificationTemplateVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    tenant_id: int
    version: int
    channel: NotificationChannel
    purpose: MessagePurpose
    provider_template_key: str | None
    review_status: TemplateReviewStatus
    locale: str
    title: str | None
    body: str
    fallback_body: str | None
    variables: dict[str, object]
    created_at: datetime
    updated_at: datetime


class RenderedNotification(BaseModel):
    title: str | None = None
    body: str
    fallback_body: str | None = None
    variables: dict[str, object]
