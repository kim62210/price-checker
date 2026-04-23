"""procurement 도메인 Pydantic v2 DTO."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OrderStatus = Literal["draft", "collecting", "completed", "cancelled"]
ResultSource = Literal["naver", "coupang", "manual"]


class OrderCreate(BaseModel):
    """발주 생성 요청 본문."""

    model_config = ConfigDict(extra="forbid")

    shop_id: int = Field(..., ge=1, description="발주를 등록할 소매점 ID")
    product_name: str = Field(..., min_length=1, max_length=500)
    option_text: str | None = Field(default=None, max_length=2000)
    quantity: int = Field(..., ge=1)
    unit: str = Field(..., min_length=1, max_length=32, description="단위 (예: 개, ml, g)")
    target_unit_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        description="단위당 목표 가격 (KRW)",
    )
    memo: str | None = Field(default=None, max_length=1000)
    status: OrderStatus = Field(default="draft")


class OrderRead(BaseModel):
    """발주 단건 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    shop_id: int
    product_name: str
    option_text: str | None
    quantity: int
    unit: str
    target_unit_price: Decimal | None
    memo: str | None
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class ResultUpload(BaseModel):
    """수집 결과 업로드 요청 본문.

    서버는 ``tenant_id`` 를 주문에서 복제하므로 클라이언트가 보낸 tenant_id 는 무시한다.
    """

    model_config = ConfigDict(extra="forbid")

    source: ResultSource = Field(..., description="수집 플랫폼")
    product_url: Annotated[str, Field(min_length=1, max_length=2000)]
    seller_name: str | None = Field(default=None, max_length=255)
    listed_price: Decimal = Field(..., ge=Decimal("0"))
    per_unit_price: Decimal = Field(..., ge=Decimal("0"))
    shipping_fee: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    unit_count: int = Field(..., ge=1)
    collected_at: datetime | None = Field(
        default=None, description="클라이언트 수집 시각 (미지정 시 서버 NOW)"
    )

    @field_validator("product_url")
    @classmethod
    def _validate_product_url(cls, value: str) -> str:
        stripped = value.strip()
        if not (stripped.startswith("http://") or stripped.startswith("https://")):
            raise ValueError("product_url must start with http:// or https://")
        return stripped


class ResultRead(BaseModel):
    """수집 결과 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    tenant_id: int
    source: ResultSource
    product_url: str
    seller_name: str | None
    listed_price: Decimal
    per_unit_price: Decimal
    shipping_fee: Decimal
    unit_count: int
    collected_at: datetime
    created_at: datetime


class SummaryReport(BaseModel):
    """기간별 절감액 집계 리포트."""

    model_config = ConfigDict(extra="forbid")

    date_from: date | None = Field(default=None, description="집계 시작일 (KST, inclusive)")
    date_to: date | None = Field(default=None, description="집계 종료일 (KST, inclusive)")
    orders_count: int = Field(..., ge=0)
    completed_orders_count: int = Field(..., ge=0)
    results_count: int = Field(..., ge=0)
    total_savings: Decimal = Field(..., description="총 절감액 KRW")
