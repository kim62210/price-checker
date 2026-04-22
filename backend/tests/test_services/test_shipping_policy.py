"""배송비 정책 테스트."""

from __future__ import annotations

from app.services.shipping_policy import (
    COUPANG_ROCKET_FREE_THRESHOLD,
    estimate_coupang_rocket,
    estimate_smartstore_generic,
)


def test_coupang_rocket_wow_member_free():
    est = estimate_coupang_rocket(subtotal=1_000, is_wow_member=True)
    assert est.fee == 0
    assert est.confidence == "explicit"


def test_coupang_rocket_non_member_below_threshold():
    est = estimate_coupang_rocket(subtotal=10_000, is_wow_member=False)
    assert est.fee == 3_000
    assert est.confidence == "estimated"
    assert est.free_threshold == COUPANG_ROCKET_FREE_THRESHOLD


def test_coupang_rocket_non_member_above_threshold():
    est = estimate_coupang_rocket(subtotal=25_000, is_wow_member=False)
    assert est.fee == 0
    assert est.free_threshold == COUPANG_ROCKET_FREE_THRESHOLD


def test_smartstore_default_fee_without_seller_info():
    est = estimate_smartstore_generic(subtotal=10_000)
    assert est.fee == 3_000
    assert est.confidence == "estimated"


def test_smartstore_free_when_seller_threshold_hit():
    est = estimate_smartstore_generic(
        subtotal=60_000,
        seller_default_fee=2_500,
        seller_free_threshold=50_000,
    )
    assert est.fee == 0
    assert est.free_threshold == 50_000


def test_smartstore_explicit_confidence_when_seller_overrides():
    est = estimate_smartstore_generic(
        subtotal=5_000,
        seller_default_fee=2_500,
    )
    assert est.fee == 2_500
    assert est.confidence == "explicit"
