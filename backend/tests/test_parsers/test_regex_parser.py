"""정규식 기반 옵션 파서 단위 테스트."""

from __future__ import annotations

import pytest

from app.parsers.regex_parser import parse_option_text


@pytest.mark.parametrize(
    ("text", "unit", "unit_quantity", "piece_count", "pack_count"),
    [
        # P1 단순 개수
        ("12개입", "ct", 12, 12, 1),
        ("30롤", "ct", 30, 30, 1),
        ("5캔", "ct", 5, 5, 1),
        # P2 용량 + 개수 (낱개당 용량)
        ("2L 12개입", "ml", 24_000, 12, 1),
        ("150g 3개", "g", 450, 3, 1),
        ("500ml 6캔", "ml", 3_000, 6, 1),
        # P4 용량 X N (곱연산)
        ("500g x 2팩", "g", 1_000, 2, 2),
        ("1L x3개", "ml", 3_000, 3, 3),
        ("250ml X 10", "ml", 2_500, 10, 10),
        # P3 NxM팩 (총 K개입 병기) — 총량 우선
        ("5개입 x 8팩(총 40개입)", "ct", 40, 40, 8),
        # P5 대용량(세부) — 괄호 안 중복 합산 금지
        ("1kg(500g x 2팩)", "g", 1_000, 1, 1),
    ],
)
def test_parse_ok(text, unit, unit_quantity, piece_count, pack_count):
    result = parse_option_text(text)
    assert result is not None, f"파싱 실패: {text}"
    assert result.unit == unit
    assert result.unit_quantity == pytest.approx(unit_quantity)
    assert result.piece_count == piece_count
    assert result.pack_count == pack_count
    assert result.confidence == "rule"


def test_parse_bonus_combo():
    result = parse_option_text("3개 + 펌프 2개")
    assert result is not None
    assert result.piece_count == 3
    assert result.bonus_quantity == 2
    assert result.unit == "ct"


def test_parse_comma_combo():
    result = parse_option_text("150g, 3개")
    assert result is not None
    assert result.unit == "g"
    assert result.unit_quantity == pytest.approx(450)
    assert result.piece_count == 3


def test_parse_empty_returns_none():
    assert parse_option_text("") is None
    assert parse_option_text("   ") is None


def test_parse_unrecognized_returns_none():
    assert parse_option_text("스페셜 에디션 프리미엄 패키지") is None
