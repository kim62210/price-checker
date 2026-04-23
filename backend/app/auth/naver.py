"""네이버 OAuth 2.0 래퍼 (httpx).

공식 문서: https://developers.naver.com/docs/login/api/api.md
- authorize: https://nid.naver.com/oauth2.0/authorize
- token:     https://nid.naver.com/oauth2.0/token
- userinfo:  https://openapi.naver.com/v1/nid/me
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger

logger = get_logger(__name__)

NAVER_AUTHORIZE_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USERINFO_URL = "https://openapi.naver.com/v1/nid/me"

_PROVIDER = "naver"
_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@dataclass(slots=True)
class NaverUserInfo:
    """정규화된 네이버 사용자 정보."""

    provider_user_id: str
    email: str | None
    nickname: str | None


class NaverEmailConsentRequiredError(UpstreamError):
    """이메일 동의가 없거나 값이 없을 때."""

    code = "EMAIL_REQUIRED"
    http_status = 400
    detail = "email_consent_required"


class NaverTokenExchangeError(UpstreamError):
    """토큰 교환 실패."""

    code = "UPSTREAM_ERROR"
    http_status = 502
    detail = "naver_token_exchange_failed"


class NaverUserinfoError(UpstreamError):
    """사용자 정보 조회 실패."""

    code = "UPSTREAM_ERROR"
    http_status = 502
    detail = "naver_userinfo_failed"


def build_authorize_url(state: str, settings: Settings | None = None) -> str:
    """네이버 authorize URL 생성."""
    settings = settings or get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.naver_oauth_client_id.get_secret_value(),
        "redirect_uri": settings.naver_oauth_redirect_uri,
        "state": state,
    }
    return f"{NAVER_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(
    code: str,
    state: str,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """인가 코드 → access_token 교환."""
    settings = settings or get_settings()
    params = {
        "grant_type": "authorization_code",
        "client_id": settings.naver_oauth_client_id.get_secret_value(),
        "client_secret": settings.naver_oauth_client_secret.get_secret_value(),
        "code": code,
        "state": state,
    }

    async def _do(c: httpx.AsyncClient) -> httpx.Response:
        return await c.get(NAVER_TOKEN_URL, params=params)

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
                response = await _do(c)
        else:
            response = await _do(client)
    except httpx.HTTPError as e:
        logger.warning("naver_token_http_error", provider=_PROVIDER, error=str(e))
        raise NaverTokenExchangeError() from e

    if response.status_code >= 400:
        logger.warning(
            "naver_token_exchange_failed",
            provider=_PROVIDER,
            status=response.status_code,
            body=response.text[:300],
        )
        raise NaverTokenExchangeError()

    payload: dict[str, Any] = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise NaverTokenExchangeError()
    return access_token


async def fetch_userinfo(
    access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> NaverUserInfo:
    """네이버 사용자 정보 조회."""
    headers = {"Authorization": f"Bearer {access_token}"}

    async def _do(c: httpx.AsyncClient) -> httpx.Response:
        return await c.get(NAVER_USERINFO_URL, headers=headers)

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
                response = await _do(c)
        else:
            response = await _do(client)
    except httpx.HTTPError as e:
        logger.warning("naver_userinfo_http_error", provider=_PROVIDER, error=str(e))
        raise NaverUserinfoError() from e

    if response.status_code >= 400:
        logger.warning(
            "naver_userinfo_failed",
            provider=_PROVIDER,
            status=response.status_code,
            body=response.text[:300],
        )
        raise NaverUserinfoError()

    payload: dict[str, Any] = response.json()
    result_code = payload.get("resultcode")
    if result_code != "00":
        logger.warning(
            "naver_userinfo_result_code",
            provider=_PROVIDER,
            resultcode=result_code,
            message=payload.get("message"),
        )
        raise NaverUserinfoError()

    response_obj: dict[str, Any] = payload.get("response") or {}
    naver_id = response_obj.get("id")
    if not naver_id:
        raise NaverUserinfoError()

    email = response_obj.get("email")
    if not email:
        raise NaverEmailConsentRequiredError()

    nickname = response_obj.get("nickname") or response_obj.get("name")
    return NaverUserInfo(
        provider_user_id=str(naver_id),
        email=str(email),
        nickname=str(nickname) if nickname else None,
    )
