"""카카오 OAuth 2.0 래퍼 (httpx).

공식 문서: https://developers.kakao.com/docs/ko/kakaologin/rest-api
- authorize: https://kauth.kakao.com/oauth/authorize
- token:     https://kauth.kakao.com/oauth/token
- userinfo:  https://kapi.kakao.com/v2/user/me
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

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

_PROVIDER = "kakao"
_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@dataclass(slots=True)
class KakaoUserInfo:
    """정규화된 카카오 사용자 정보."""

    provider_user_id: str  # kakao_id
    email: str | None
    nickname: str | None


class KakaoEmailConsentRequiredError(UpstreamError):
    """이메일 동의가 없거나 값이 없을 때."""

    code = "EMAIL_REQUIRED"
    http_status = 400
    detail = "email_consent_required"


class KakaoTokenExchangeError(UpstreamError):
    """토큰 교환 실패."""

    code = "UPSTREAM_ERROR"
    http_status = 502
    detail = "kakao_token_exchange_failed"


class KakaoUserinfoError(UpstreamError):
    """사용자 정보 조회 실패."""

    code = "UPSTREAM_ERROR"
    http_status = 502
    detail = "kakao_userinfo_failed"


def build_authorize_url(state: str, settings: Settings | None = None) -> str:
    """카카오 authorize URL 생성."""
    settings = settings or get_settings()
    params = {
        "client_id": settings.kakao_client_id.get_secret_value(),
        "redirect_uri": settings.kakao_redirect_uri,
        "response_type": "code",
        "state": state,
    }
    return f"{KAKAO_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(
    code: str,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """인가 코드 → access_token 교환. access_token 만 반환."""
    settings = settings or get_settings()
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao_client_id.get_secret_value(),
        "redirect_uri": settings.kakao_redirect_uri,
        "code": code,
    }
    secret = settings.kakao_client_secret.get_secret_value()
    if secret:
        data["client_secret"] = secret
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}

    async def _do(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(KAKAO_TOKEN_URL, data=data, headers=headers)

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
                response = await _do(c)
        else:
            response = await _do(client)
    except httpx.HTTPError as e:
        logger.warning("kakao_token_http_error", provider=_PROVIDER, error=str(e))
        raise KakaoTokenExchangeError() from e

    if response.status_code >= 400:
        logger.warning(
            "kakao_token_exchange_failed",
            provider=_PROVIDER,
            status=response.status_code,
            body=response.text[:300],
        )
        raise KakaoTokenExchangeError()

    payload: dict[str, Any] = response.json()
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise KakaoTokenExchangeError()
    return access_token


async def fetch_userinfo(
    access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> KakaoUserInfo:
    """카카오 사용자 정보 조회 → KakaoUserInfo 반환."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }

    async def _do(c: httpx.AsyncClient) -> httpx.Response:
        return await c.get(KAKAO_USERINFO_URL, headers=headers)

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
                response = await _do(c)
        else:
            response = await _do(client)
    except httpx.HTTPError as e:
        logger.warning("kakao_userinfo_http_error", provider=_PROVIDER, error=str(e))
        raise KakaoUserinfoError() from e

    if response.status_code >= 400:
        logger.warning(
            "kakao_userinfo_failed",
            provider=_PROVIDER,
            status=response.status_code,
            body=response.text[:300],
        )
        raise KakaoUserinfoError()

    payload: dict[str, Any] = response.json()
    kakao_id = payload.get("id")
    if kakao_id is None:
        raise KakaoUserinfoError()

    account: dict[str, Any] = payload.get("kakao_account") or {}
    profile: dict[str, Any] = account.get("profile") or {}
    email = account.get("email")
    email_needs_agreement = bool(account.get("email_needs_agreement", False))
    if email_needs_agreement or not email:
        raise KakaoEmailConsentRequiredError()

    nickname = profile.get("nickname")
    return KakaoUserInfo(
        provider_user_id=str(kakao_id),
        email=str(email),
        nickname=str(nickname) if nickname else None,
    )
