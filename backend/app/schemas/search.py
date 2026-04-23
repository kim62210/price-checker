"""검색 엔드포인트 요청/응답 스키마.

피벗 후 크롤링 제거 → 클라이언트가 업로드한 ``procurement_results`` 를
테넌트 격리하에 검색·랭킹하는 read-only API.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["naver", "coupang", "manual"]
SourceStatus = Literal["ok", "missing", "error"]


class SearchRequest(BaseModel):
    """``GET /api/v1/search`` 쿼리 파라미터 스키마."""

    model_config = ConfigDict(extra="forbid")

    q: str = Field(..., min_length=1, max_length=120, description="검색어")
    limit: int = Field(default=20, ge=1, le=100, description="반환할 최대 결과 수")
    force_refresh: bool = Field(default=False, description="캐시 무시 후 재집계")


class SearchResultItem(BaseModel):
    """업로드된 ``procurement_results`` 1 건에 대한 랭킹 결과."""

    model_config = ConfigDict(from_attributes=True)

    result_id: int = Field(..., description="procurement_results.id")
    order_id: int = Field(..., description="procurement_orders.id")
    source: Platform
    product_url: str
    seller_name: str | None = None
    listed_price: Decimal
    per_unit_price: Decimal
    shipping_fee: Decimal
    unit_count: int
    product_name: str = Field(..., description="주문의 상품명")
    option_text: str | None = None


class SearchResponse(BaseModel):
    """``GET /api/v1/search`` 응답."""

    model_config = ConfigDict(extra="forbid")

    query: str
    limit: int
    tenant_id: int
    results: list[SearchResultItem]
    sources: dict[Platform, SourceStatus] = Field(default_factory=dict)
    cached: bool = False
    hint: str | None = Field(default=None, description="빈 결과 등 부가 안내 힌트")


__all__ = [
    "Platform",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "SourceStatus",
]
