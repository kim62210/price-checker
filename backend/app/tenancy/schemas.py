"""테넌트·소매점·사용자 Pydantic v2 DTO."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TenantPlan = Literal["starter", "pro", "enterprise"]
UserRole = Literal["owner", "staff"]
AuthProvider = Literal["kakao", "naver", "local"]


class TenantRead(BaseModel):
    """테넌트 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    plan: TenantPlan
    api_quota_monthly: int
    created_at: datetime
    updated_at: datetime


class TenantCreate(BaseModel):
    """테넌트 신규 생성 입력 (내부 프로비저닝에서 사용)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    plan: TenantPlan = "starter"
    api_quota_monthly: int | None = Field(default=None, ge=0)


class ShopRead(BaseModel):
    """소매점 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    business_number: str | None = None
    created_at: datetime
    updated_at: datetime


class ShopCreate(BaseModel):
    """소매점 생성 입력."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    business_number: str | None = Field(default=None, max_length=20)

    @field_validator("business_number")
    @classmethod
    def _normalize_business_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class UserRead(BaseModel):
    """사용자 조회 응답 (password_hash 미노출)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    email: EmailStr
    auth_provider: AuthProvider
    provider_user_id: str
    role: UserRole
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
