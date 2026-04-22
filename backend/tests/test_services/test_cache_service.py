"""캐시 키 빌더 테스트."""

from __future__ import annotations

from app.services.cache_service import make_detail_key, make_option_text_key, make_search_key


def test_search_key_is_case_insensitive():
    assert make_search_key("코카콜라", 20) == make_search_key("  코카콜라 ", 20)


def test_search_key_differs_by_limit():
    assert make_search_key("코카콜라", 20) != make_search_key("코카콜라", 30)


def test_detail_key_is_platform_scoped():
    key = make_detail_key("naver", "https://smartstore.naver.com/x")
    assert key.startswith("detail:naver:")


def test_option_key_includes_parser_version():
    k1 = make_option_text_key("500g x 2팩", parser_version=1)
    k2 = make_option_text_key("500g x 2팩", parser_version=2)
    assert k1 != k2
    assert k1.startswith("option:1:")
    assert k2.startswith("option:2:")
