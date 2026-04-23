"""캐시 키 빌더 테스트."""

from __future__ import annotations

import pytest

from app.services.cache_service import (
    make_option_text_key,
    make_search_key,
    tenant_namespace,
)


def test_search_key_is_case_insensitive() -> None:
    assert make_search_key(1, "코카콜라", 20) == make_search_key(1, "  코카콜라 ", 20)


def test_search_key_differs_by_limit() -> None:
    assert make_search_key(1, "코카콜라", 20) != make_search_key(1, "코카콜라", 30)


def test_search_key_includes_tenant_namespace() -> None:
    k1 = make_search_key(1, "코카콜라", 20)
    k2 = make_search_key(2, "코카콜라", 20)
    assert k1 != k2
    assert k1.startswith("search:1:")
    assert k2.startswith("search:2:")


def test_option_key_includes_parser_version() -> None:
    k1 = make_option_text_key("500g x 2팩", parser_version=1)
    k2 = make_option_text_key("500g x 2팩", parser_version=2)
    assert k1 != k2
    assert k1.startswith("option:1:")
    assert k2.startswith("option:2:")


def test_tenant_namespace_rejects_invalid_tenant_id() -> None:
    with pytest.raises(ValueError):
        tenant_namespace(0, "foo")
    with pytest.raises(ValueError):
        tenant_namespace(-1, "foo")


def test_tenant_namespace_applies_prefix() -> None:
    assert tenant_namespace(42, "search:abc") == "tenant:42:search:abc"
