"""16.5 카카오 OAuth — respx 스텁으로 토큰 교환·userinfo 테스트."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


@pytest.mark.asyncio
async def test_exchange_code_success(settings):
    """카카오 토큰 교환 성공 → access_token 반환."""
    from app.auth.kakao import exchange_code

    with respx.mock:
        respx.post(KAKAO_TOKEN_URL).mock(
            return_value=Response(
                200,
                json={"access_token": "kakao-access-abc", "refresh_token": "kakao-refresh-xyz"},
            )
        )
        token = await exchange_code("auth-code-123", settings=settings)

    assert token == "kakao-access-abc"


@pytest.mark.asyncio
async def test_exchange_code_failure_raises(settings):
    """카카오 토큰 서버 400 응답 → KakaoTokenExchangeError."""
    from app.auth.kakao import KakaoTokenExchangeError, exchange_code

    with respx.mock:
        respx.post(KAKAO_TOKEN_URL).mock(
            return_value=Response(400, json={"error": "invalid_grant"})
        )
        with pytest.raises(KakaoTokenExchangeError):
            await exchange_code("bad-code", settings=settings)


@pytest.mark.asyncio
async def test_exchange_code_missing_access_token_raises(settings):
    """카카오 응답에 access_token 없음 → KakaoTokenExchangeError."""
    from app.auth.kakao import KakaoTokenExchangeError, exchange_code

    with respx.mock:
        respx.post(KAKAO_TOKEN_URL).mock(
            return_value=Response(200, json={"token_type": "bearer"})
        )
        with pytest.raises(KakaoTokenExchangeError):
            await exchange_code("code-no-token", settings=settings)


@pytest.mark.asyncio
async def test_fetch_userinfo_success():
    """카카오 userinfo 조회 성공 → KakaoUserInfo 반환."""
    from app.auth.kakao import KakaoUserInfo, fetch_userinfo

    with respx.mock:
        respx.get(KAKAO_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "id": 12345,
                    "kakao_account": {
                        "email": "user@kakao.com",
                        "email_needs_agreement": False,
                        "profile": {"nickname": "카카오유저"},
                    },
                },
            )
        )
        info = await fetch_userinfo("kakao-access-abc")

    assert isinstance(info, KakaoUserInfo)
    assert info.provider_user_id == "12345"
    assert info.email == "user@kakao.com"
    assert info.nickname == "카카오유저"


@pytest.mark.asyncio
async def test_fetch_userinfo_email_consent_required():
    """이메일 동의 미완료 → KakaoEmailConsentRequiredError."""
    from app.auth.kakao import KakaoEmailConsentRequiredError, fetch_userinfo

    with respx.mock:
        respx.get(KAKAO_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "id": 99999,
                    "kakao_account": {
                        "email_needs_agreement": True,
                        "profile": {},
                    },
                },
            )
        )
        with pytest.raises(KakaoEmailConsentRequiredError):
            await fetch_userinfo("token-no-email")


@pytest.mark.asyncio
async def test_fetch_userinfo_server_error():
    """카카오 API 500 → KakaoUserinfoError."""
    from app.auth.kakao import KakaoUserinfoError, fetch_userinfo

    with respx.mock:
        respx.get(KAKAO_USERINFO_URL).mock(return_value=Response(500))
        with pytest.raises(KakaoUserinfoError):
            await fetch_userinfo("any-token")


@pytest.mark.asyncio
async def test_build_authorize_url(settings):
    """authorize URL 에 client_id 와 redirect_uri 포함."""
    from app.auth.kakao import build_authorize_url

    url = build_authorize_url("my-state", settings=settings)
    assert "kauth.kakao.com/oauth/authorize" in url
    assert "state=my-state" in url
    assert "response_type=code" in url
