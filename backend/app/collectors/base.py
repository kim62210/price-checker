"""Collector 공통 타입 및 ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Platform = Literal["naver", "coupang"]
FetchMethod = Literal["api", "static", "playwright"]
ShippingConfidence = Literal["explicit", "estimated", "unknown"]


@dataclass(slots=True)
class ListingDTO:
    """한 상품의 기본 리스팅 정보 (상세 수집 이전 단계)."""

    platform: Platform
    platform_product_id: str
    raw_title: str
    product_url: str
    seller_id: str | None = None
    mall_name: str | None = None
    representative_price: int | None = None
    thumbnail_url: str | None = None
    is_rocket: bool | None = None
    is_free_shipping: bool | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass(slots=True)
class OptionDTO:
    platform_option_id: str | None
    option_name_text: str
    attrs: dict[str, str]
    price: int
    stock: int | None = None
    usable: bool = True


@dataclass(slots=True)
class DetailDTO:
    listing: ListingDTO
    options: list[OptionDTO]
    shipping_fee: int
    shipping_confidence: ShippingConfidence
    free_shipping_threshold: int | None = None
    fetch_method: FetchMethod = "static"
    raw_html: str | None = None


class Collector(ABC):
    """플랫폼별 Collector 인터페이스."""

    platform: Platform

    @abstractmethod
    async def search(self, query: str, limit: int) -> list[ListingDTO]:
        """검색어로 후보 리스팅 목록을 반환한다."""

    @abstractmethod
    async def fetch_detail(self, listing: ListingDTO) -> DetailDTO:
        """리스팅에 대한 상세 정보(옵션·배송비 포함)를 반환한다."""
