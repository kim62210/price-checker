"""랭킹 서비스 테스트."""

from __future__ import annotations

from app.parsers.unit_price import UnitPrice
from app.services.ranking_service import RankItem, compute_comparable_group, rank_by_unit_price


def _item(unit_price: float | None, unit: str = "ct") -> RankItem:
    return RankItem(
        unit_price=UnitPrice(
            total_price=10_000,
            unit_quantity=1 if unit_price else None,
            unit_price=unit_price,
            unit_price_display=unit_price,
            display_base_value=1,
            display_base_unit=unit,  # type: ignore[arg-type]
            unit_price_confidence="high" if unit_price else "low",
        ),
        payload={"name": str(unit_price)},
    )


def test_rank_by_unit_price_null_last():
    items = [_item(1_200), _item(None), _item(900), _item(1_500), _item(None), _item(800)]
    ranked = rank_by_unit_price(items)
    prices = [i.unit_price.unit_price for i in ranked]
    assert prices[:4] == [800, 900, 1_200, 1_500]
    assert all(p is None for p in prices[4:])


def test_comparable_group_pure_weight():
    items = [_item(100, "g"), _item(200, "g")]
    assert compute_comparable_group(items) == "by_weight"


def test_comparable_group_mixed():
    items = [_item(100, "g"), _item(200, "ct")]
    assert compute_comparable_group(items) == "mixed"


def test_comparable_group_unknown_when_empty():
    assert compute_comparable_group([]) == "unknown"
