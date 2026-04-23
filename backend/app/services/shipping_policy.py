"""플랫폼별 배송비 정책 추정.

- 실측 데이터가 없으면 정책 기반 추정값을 반환하고 shipping_confidence 로 불확실성을 노출한다.
- 2026-04 기준 쿠팡 일반회원 무료배송 임계치: 실결제액 19,800원 이상.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# TODO(wave3): search_service 재설계 후 타입 공유 위치를 도메인 모듈로 이관
ShippingConfidence = Literal["explicit", "estimated", "unknown"]

COUPANG_ROCKET_FREE_THRESHOLD = 19_800
COUPANG_ROCKET_DEFAULT_FEE = 3_000
NAVER_SMARTSTORE_DEFAULT_FEE = 3_000
NAVER_SMARTSTORE_DEFAULT_THRESHOLD = 50_000


@dataclass(slots=True)
class ShippingEstimate:
    fee: int
    confidence: ShippingConfidence
    free_threshold: int | None = None


def estimate_coupang_rocket(subtotal: int, *, is_wow_member: bool = False) -> ShippingEstimate:
    if is_wow_member:
        return ShippingEstimate(
            fee=0, confidence="explicit", free_threshold=0
        )
    if subtotal >= COUPANG_ROCKET_FREE_THRESHOLD:
        return ShippingEstimate(
            fee=0, confidence="estimated", free_threshold=COUPANG_ROCKET_FREE_THRESHOLD
        )
    return ShippingEstimate(
        fee=COUPANG_ROCKET_DEFAULT_FEE,
        confidence="estimated",
        free_threshold=COUPANG_ROCKET_FREE_THRESHOLD,
    )


def estimate_smartstore_generic(
    subtotal: int,
    *,
    seller_default_fee: int | None = None,
    seller_free_threshold: int | None = None,
) -> ShippingEstimate:
    fee = seller_default_fee if seller_default_fee is not None else NAVER_SMARTSTORE_DEFAULT_FEE
    threshold = (
        seller_free_threshold
        if seller_free_threshold is not None
        else NAVER_SMARTSTORE_DEFAULT_THRESHOLD
    )
    if subtotal >= threshold:
        return ShippingEstimate(fee=0, confidence="estimated", free_threshold=threshold)
    confidence: ShippingConfidence = (
        "explicit"
        if (seller_default_fee is not None or seller_free_threshold is not None)
        else "estimated"
    )
    return ShippingEstimate(fee=fee, confidence=confidence, free_threshold=threshold)
