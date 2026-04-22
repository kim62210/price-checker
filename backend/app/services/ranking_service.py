"""검색 결과 정렬 + comparable_group 계산."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.parsers.unit_price import UnitPrice

ComparableGroup = Literal["by_weight", "by_volume", "by_count", "mixed", "unknown"]


@dataclass(slots=True)
class RankItem:
    """랭킹 입력/출력용 중립 표현."""

    unit_price: UnitPrice
    payload: dict[str, Any] = field(default_factory=dict)


def _null_last_key(item: RankItem) -> tuple[int, float]:
    price = item.unit_price.unit_price
    if price is None:
        return (1, 0.0)
    return (0, price)


def rank_by_unit_price(items: list[RankItem]) -> list[RankItem]:
    return sorted(items, key=_null_last_key)


def compute_comparable_group(items: list[RankItem]) -> ComparableGroup:
    if not items:
        return "unknown"
    units = {i.unit_price.display_base_unit for i in items if i.unit_price.unit_quantity}
    if not units:
        return "unknown"
    if units == {"g"}:
        return "by_weight"
    if units == {"ml"}:
        return "by_volume"
    if units == {"ct"} or units == {"sheet"}:
        return "by_count"
    return "mixed"
