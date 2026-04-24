"""최저가 수집 설정 테스트."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.price_collection.service import CollectionConfigError


def test_naver_collection_settings_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAVER_SEARCH_CLIENT_ID", "naver-search-id")
    monkeypatch.setenv("NAVER_SEARCH_CLIENT_SECRET", "naver-search-secret")
    monkeypatch.setenv("NAVER_SEARCH_DISPLAY_LIMIT", "30")
    monkeypatch.setenv("PRICE_COLLECTION_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("PRICE_COLLECTION_RETRY_BASE_SECONDS", "90")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.naver_search_client_id.get_secret_value() == "naver-search-id"
    assert settings.naver_search_client_secret.get_secret_value() == "naver-search-secret"
    assert settings.naver_search_display_limit == 30
    assert settings.price_collection_max_attempts == 4
    assert settings.price_collection_retry_base_seconds == 90


def test_collection_fails_fast_without_naver_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NAVER_SEARCH_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_SEARCH_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(CollectionConfigError):
        get_settings().validate_price_collection_config()
