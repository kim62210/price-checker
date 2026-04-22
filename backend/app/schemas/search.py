"""검색 엔드포인트 요청/응답 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["naver", "coupang"]
SourceStatus = Literal["ok", "error", "blocked", "quota_exceeded", "circuit_open", "timeout"]


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=120, description="검색어")
    limit: int = Field(default=20, ge=1, le=60, description="플랫폼당 최대 수집 개수")
    force_refresh: bool = Field(default=False, description="캐시를 무시하고 재수집")


class Sources(BaseModel):
    naver: SourceStatus = "ok"
    naver_detail: str | None = None
    coupang: SourceStatus = "ok"
    coupang_detail: str | None = None


class ResultItem(BaseModel):
    platform: Platform
    seller: str | None
    product_url: str
    raw_title: str
    thumbnail_url: str | None

    option_name: str
    price: int
    shipping_fee: int
    shipping_confidence: str
    total_price: int

    unit_quantity: float | None
    unit: str | None
    unit_price: float | None
    unit_price_display: float | None
    display_base_value: int
    display_base_unit: str
    unit_price_confidence: str
    parsed_confidence: str | None

    is_rocket: bool | None = None
    fetch_method: str
    detail_status: str


class SearchResponse(BaseModel):
    query: str
    limit: int
    sources: Sources
    results: list[ResultItem]
    cached: bool = False
    comparable_group: str = "unknown"
    naver_quota_remaining: int | None = None
