"""옵션 텍스트 정규식 파서 (7가지 패턴)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.parsers.unit_dictionary import (
    COUNT_UNIT_RE,
    MASS_VOLUME_UNIT_RE,
    UnitCode,
    convert_to_base,
)


@dataclass(slots=True)
class ParseResult:
    unit: UnitCode
    unit_quantity: float
    piece_count: int
    pack_count: int
    bonus_quantity: int
    confidence: str
    raw_match: str

    def to_dict(self) -> dict[str, object]:
        return {
            "unit": self.unit,
            "unit_quantity": self.unit_quantity,
            "piece_count": self.piece_count,
            "pack_count": self.pack_count,
            "bonus_quantity": self.bonus_quantity,
            "confidence": self.confidence,
            "raw_match": self.raw_match,
        }


# 명시적 "총 N개" 병기 (검증용)
_TOTAL_EXPLICIT = re.compile(r"총\s*(\d+)\s*(개입|개|팩)")

# P5: 대용량(세부) 예: "1kg(500g x 2팩)"
_PARENTHESIS_DETAIL = re.compile(
    rf"(\d+(?:\.\d+)?)\s*({MASS_VOLUME_UNIT_RE})\s*\(\s*[^)]+\)"
)

# P3: NxM팩 (+ 총 K개입)  예: "5개입 x 8팩(총 40개입)"
_NxM_WITH_TOTAL = re.compile(
    rf"(\d+)\s*({COUNT_UNIT_RE})\s*[x×X]\s*(\d+)\s*({COUNT_UNIT_RE})"
    rf"(?:\s*\(?\s*총\s*(\d+)\s*({COUNT_UNIT_RE})\s*\)?)?"
)

# P4: 용량 X N (팩) 예: "500g x 2팩", "1L x3개"
_VOLUME_X_COUNT = re.compile(
    rf"(\d+(?:\.\d+)?)\s*({MASS_VOLUME_UNIT_RE})\s*[x×X]\s*(\d+)\s*({COUNT_UNIT_RE})?"
)

# P2: 용량 N개입 예: "2L 12개입", "150g 3개"
_VOLUME_SPACE_COUNT = re.compile(
    rf"(\d+(?:\.\d+)?)\s*({MASS_VOLUME_UNIT_RE})\s+(\d+)\s*({COUNT_UNIT_RE})"
)

# P1: 단순 개수 예: "12개입", "30롤"
_SIMPLE_COUNT = re.compile(rf"(\d+)\s*({COUNT_UNIT_RE})")

# P6: 증정 결합 예: "3개 + 펌프 2개", "1+1"
_BONUS_COMBO = re.compile(
    rf"(\d+)\s*({COUNT_UNIT_RE})\s*\+\s*(?:펌프|증정|추가|사은품|선물)?\s*(\d+)\s*({COUNT_UNIT_RE})?"
)

# P7: 쉼표 결합 예: "150g, 3개"
_COMMA_COMBO = re.compile(
    rf"(\d+(?:\.\d+)?)\s*({MASS_VOLUME_UNIT_RE})\s*,\s*(\d+)\s*({COUNT_UNIT_RE})"
)


def _to_float(value: str) -> float:
    return float(value)


def _to_int(value: str) -> int:
    return int(float(value))


def _convert(value: float, unit: str) -> tuple[UnitCode, float] | None:
    return convert_to_base(value, unit)


def _normalize(text: str) -> str:
    return text.replace("X", "x").replace("×", "x")


def parse_option_text(text: str) -> ParseResult | None:
    """규칙 기반 파서. 실패 시 None."""
    if not text or not text.strip():
        return None
    normalized = _normalize(text)
    total_match = _TOTAL_EXPLICIT.search(normalized)
    explicit_total = _to_int(total_match.group(1)) if total_match else None

    # 1. 괄호 세부 (중복 합산 방지)
    p5 = _PARENTHESIS_DETAIL.search(normalized)
    if p5:
        value = _to_float(p5.group(1))
        converted = _convert(value, p5.group(2))
        if converted:
            base, qty = converted
            return ParseResult(
                unit=base,
                unit_quantity=qty,
                piece_count=1,
                pack_count=1,
                bonus_quantity=0,
                confidence="rule",
                raw_match=p5.group(0),
            )

    # 2. 쉼표 결합 (용량, 개수)
    p7 = _COMMA_COMBO.search(normalized)
    if p7:
        volume = _to_float(p7.group(1))
        converted = _convert(volume, p7.group(2))
        count = _to_int(p7.group(3))
        if converted:
            base, per_qty = converted
            return ParseResult(
                unit=base,
                unit_quantity=per_qty * count,
                piece_count=count,
                pack_count=1,
                bonus_quantity=0,
                confidence="rule",
                raw_match=p7.group(0),
            )

    # 3. NxM팩 (+ 총량 병기)
    p3 = _NxM_WITH_TOTAL.search(normalized)
    if p3:
        per_pack = _to_int(p3.group(1))
        pack_count = _to_int(p3.group(3))
        piece_count = explicit_total or p3.group(5)
        if isinstance(piece_count, str):
            piece_count = _to_int(piece_count)
        if piece_count is None:
            piece_count = per_pack * pack_count
        return ParseResult(
            unit="ct",
            unit_quantity=float(piece_count),
            piece_count=piece_count,
            pack_count=pack_count,
            bonus_quantity=0,
            confidence="rule",
            raw_match=p3.group(0),
        )

    # 4. 용량 X N
    p4 = _VOLUME_X_COUNT.search(normalized)
    if p4:
        volume = _to_float(p4.group(1))
        count = _to_int(p4.group(3))
        converted = _convert(volume, p4.group(2))
        if converted:
            base, per_qty = converted
            return ParseResult(
                unit=base,
                unit_quantity=per_qty * count,
                piece_count=count,
                pack_count=count,
                bonus_quantity=0,
                confidence="rule",
                raw_match=p4.group(0),
            )

    # 5. 용량 + 공백 + 개수 ("2L 12개입")
    p2 = _VOLUME_SPACE_COUNT.search(normalized)
    if p2:
        volume = _to_float(p2.group(1))
        count = _to_int(p2.group(3))
        converted = _convert(volume, p2.group(2))
        if converted:
            base, per_qty = converted
            return ParseResult(
                unit=base,
                unit_quantity=per_qty * count,
                piece_count=count,
                pack_count=1,
                bonus_quantity=0,
                confidence="rule",
                raw_match=p2.group(0),
            )

    # 6. 증정 결합
    p6 = _BONUS_COMBO.search(normalized)
    if p6:
        main_count = _to_int(p6.group(1))
        bonus = _to_int(p6.group(3))
        return ParseResult(
            unit="ct",
            unit_quantity=float(main_count),
            piece_count=main_count,
            pack_count=1,
            bonus_quantity=bonus,
            confidence="rule",
            raw_match=p6.group(0),
        )

    # 7. 단순 개수
    p1 = _SIMPLE_COUNT.search(normalized)
    if p1:
        count = _to_int(p1.group(1))
        converted = _convert(float(count), p1.group(2))
        if converted:
            base, qty = converted
            return ParseResult(
                unit=base,
                unit_quantity=qty,
                piece_count=count,
                pack_count=1,
                bonus_quantity=0,
                confidence="rule",
                raw_match=p1.group(0),
            )

    return None
