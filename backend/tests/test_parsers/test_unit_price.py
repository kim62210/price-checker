"""개당 실가 계산 테스트."""

from __future__ import annotations

import pytest

from app.parsers.regex_parser import ParseResult
from app.parsers.unit_price import calculate_unit_price


@pytest.fixture
def parsed_12ct() -> ParseResult:
    return ParseResult(
        unit="ct",
        unit_quantity=12,
        piece_count=12,
        pack_count=1,
        bonus_quantity=0,
        confidence="rule",
        raw_match="12개입",
    )


@pytest.fixture
def parsed_500g() -> ParseResult:
    return ParseResult(
        unit="g",
        unit_quantity=500,
        piece_count=1,
        pack_count=1,
        bonus_quantity=0,
        confidence="rule",
        raw_match="500g",
    )


def test_unit_price_basic(parsed_12ct):
    up = calculate_unit_price(
        option_price=10_000,
        shipping_fee=3_000,
        parsed=parsed_12ct,
        shipping_confidence="explicit",
    )
    assert up.total_price == 13_000
    assert up.unit_price == pytest.approx(13_000 / 12)
    assert up.display_base_unit == "ct"
    assert up.display_base_value == 1
    assert up.unit_price_confidence == "high"


def test_unit_price_weight_display_base_100g(parsed_500g):
    up = calculate_unit_price(
        option_price=5_000,
        shipping_fee=0,
        parsed=parsed_500g,
        shipping_confidence="explicit",
    )
    assert up.display_base_unit == "g"
    assert up.display_base_value == 100
    assert up.unit_price_display == pytest.approx(1_000.0)  # 5000/500 * 100


def test_unit_price_nullable_when_no_parse():
    up = calculate_unit_price(
        option_price=9_900,
        shipping_fee=3_000,
        parsed=None,
        shipping_confidence="unknown",
    )
    assert up.total_price == 12_900
    assert up.unit_price is None
    assert up.unit_price_display is None
    assert up.unit_price_confidence == "low"


def test_unit_price_confidence_downgraded_with_estimated_shipping(parsed_12ct):
    up = calculate_unit_price(
        option_price=10_000,
        shipping_fee=3_000,
        parsed=parsed_12ct,
        shipping_confidence="estimated",
    )
    assert up.unit_price_confidence == "medium"
