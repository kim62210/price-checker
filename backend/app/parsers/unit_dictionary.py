"""수량/용량 단위 사전.

Google Merchant 단가 표기 스키마를 준용한 기준단위(g·ml·ct·sheet)와,
한국 커머스 자유 텍스트에서 자주 관찰되는 한글 단위를 매핑한다.
"""

from __future__ import annotations

from typing import Literal

UnitCode = Literal["g", "ml", "ct", "sheet"]


WEIGHT_UNITS: dict[str, tuple[UnitCode, float]] = {
    "mg": ("g", 0.001),
    "g": ("g", 1.0),
    "kg": ("g", 1000.0),
}

VOLUME_UNITS: dict[str, tuple[UnitCode, float]] = {
    "ml": ("ml", 1.0),
    "mL": ("ml", 1.0),
    "cc": ("ml", 1.0),
    "cl": ("ml", 10.0),
    "l": ("ml", 1000.0),
    "L": ("ml", 1000.0),
}

COUNT_UNITS: dict[str, tuple[UnitCode, float]] = {
    "개": ("ct", 1.0),
    "개입": ("ct", 1.0),
    "입": ("ct", 1.0),
    "팩": ("ct", 1.0),
    "세트": ("ct", 1.0),
    "박스": ("ct", 1.0),
    "묶음": ("ct", 1.0),
    "봉": ("ct", 1.0),
    "병": ("ct", 1.0),
    "캔": ("ct", 1.0),
    "롤": ("ct", 1.0),
    "장": ("sheet", 1.0),
    "매": ("sheet", 1.0),
    "ea": ("ct", 1.0),
    "ct": ("ct", 1.0),
    "pcs": ("ct", 1.0),
    "pack": ("ct", 1.0),
    "pk": ("ct", 1.0),
    "set": ("ct", 1.0),
    "box": ("ct", 1.0),
}

MASS_VOLUME_UNIT_RE = r"kg|g|mg|ml|mL|cc|cl|L|l"
COUNT_UNIT_RE = r"개입|개|입|팩|세트|박스|묶음|봉|병|캔|롤|장|매|pcs|pack|pk|set|box|ct|ea"


def normalize_unit_name(raw: str) -> str:
    return raw.strip().lower() if raw.lower() in {"ea", "ct", "pcs", "pk", "set", "box", "pack"} else raw


def convert_to_base(value: float, unit: str) -> tuple[UnitCode, float] | None:
    key = unit
    if key in WEIGHT_UNITS:
        base, factor = WEIGHT_UNITS[key]
        return base, value * factor
    if key in VOLUME_UNITS:
        base, factor = VOLUME_UNITS[key]
        return base, value * factor
    lowered = key.lower()
    if lowered in COUNT_UNITS:
        base, factor = COUNT_UNITS[lowered]
        return base, value * factor
    if key in COUNT_UNITS:
        base, factor = COUNT_UNITS[key]
        return base, value * factor
    return None


def display_base(unit: UnitCode) -> tuple[int, UnitCode]:
    """기준단위별 사용자 표시 단위(`N unit`)."""
    if unit == "g" or unit == "ml":
        return 100, unit
    if unit == "ct":
        return 1, unit
    if unit == "sheet":
        return 1, unit
    return 1, unit
