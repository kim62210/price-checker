"""최저가 수집 예외."""

from __future__ import annotations


class CollectionConfigError(Exception):
    """필수 수집 설정이 누락된 경우."""


class NaverClientError(Exception):
    """네이버 쇼핑 검색 API 기본 예외."""


class NaverClientRateLimitError(NaverClientError):
    """네이버 API rate limit 또는 일시 제한."""


class NaverClientTimeoutError(NaverClientError):
    """네이버 API timeout."""


class NaverClientResponseError(NaverClientError):
    """네이버 API malformed/unexpected response."""
