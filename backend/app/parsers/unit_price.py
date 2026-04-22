"""개당 실가 계산 및 기준단위 표시값 환산."""

from __future__ import annotations

from dataclasses import dataclass

from app.parsers.regex_parser import ParseResult
from app.parsers.unit_dictionary import UnitCode, display_base


@dataclass(slots=True)
class UnitPrice:
    """개당 실가 계산 결과."""

    total_price: int
    unit_quantity: float | None
    unit_price: float | None
    unit_price_display: float | None
    display_base_value: int
    display_base_unit: UnitCode
    unit_price_confidence: str  # "high" | "medium" | "low"


def _confidence_for(parsed: ParseResult | None, shipping_confidence: str) -> str:
    if parsed is None:
        return "low"
    if parsed.confidence == "llm":
        base = "medium"
    elif parsed.confidence == "rule":
        base = "high"
    else:
        base = "low"
    if shipping_confidence == "estimated":
        return "medium" if base == "high" else "low"
    if shipping_confidence == "unknown":
        return "low"
    return base


def calculate_unit_price(
    option_price: int,
    shipping_fee: int,
    parsed: ParseResult | None,
    shipping_confidence: str = "unknown",
) -> UnitPrice:
    total_price = max(int(option_price) + int(shipping_fee), 0)

    if parsed is None or parsed.unit_quantity <= 0:
        return UnitPrice(
            total_price=total_price,
            unit_quantity=None,
            unit_price=None,
            unit_price_display=None,
            display_base_value=1,
            display_base_unit="ct",
            unit_price_confidence="low",
        )

    unit_price_raw = total_price / parsed.unit_quantity
    base_value, base_unit = display_base(parsed.unit)
    unit_price_display = unit_price_raw * base_value

    return UnitPrice(
        total_price=total_price,
        unit_quantity=parsed.unit_quantity,
        unit_price=unit_price_raw,
        unit_price_display=unit_price_display,
        display_base_value=base_value,
        display_base_unit=base_unit,
        unit_price_confidence=_confidence_for(parsed, shipping_confidence),
    )
