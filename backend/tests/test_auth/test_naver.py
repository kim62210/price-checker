"""16.6 네이버 OAuth — respx 스텁으로 토큰 교환·userinfo 테스트."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USERINFO_URL = "https://openapi.naver.com/v1/nid/me"


@pytest.mark.asyncio
async def test_exchange_code_success(settings):
    """네이버 토큰 교환 성공 → access_token 반환."""
    from app.auth.naver import exchange_code

    with respx.mock:
        respx.get(NAVER_TOKEN_URL).mock(
            return_value=Response(
                200,
                json={"access_token": "naver-access-abc", "token_type": "bearer"},
            )
        )
        token = await exchange_code("auth-code", "my-state", settings=settings)

    assert token == "naver-access-abc"


@pytest.mark.asyncio
async def test_exchange_code_failure_raises(settings):
    """네이버 토큰 서버 401 → NaverTokenExchangeError."""
    from app.auth.naver import NaverTokenExchangeError, exchange_code

    with respx.mock:
        respx.get(NAVER_TOKEN_URL).mock(return_value=Response(401))
        with pytest.raises(NaverTokenExchangeError):
            await exchange_code("bad-code", "state", settings=settings)


@pytest.mark.asyncio
async def test_exchange_code_missing_access_token(settings):
    """네이버 응답에 access_token 없음 → NaverTokenExchangeError."""
    from app.auth.naver import NaverTokenExchangeError, exchange_code

    with respx.mock:
        respx.get(NAVER_TOKEN_URL).mock(
            return_value=Response(200, json={"token_type": "bearer"})
        )
        with pytest.raises(NaverTokenExchangeError):
            await exchange_code("code", "state", settings=settings)


@pytest.mark.asyncio
async def test_fetch_userinfo_success():
    """네이버 userinfo 조회 성공 → NaverUserInfo 반환."""
    from app.auth.naver import NaverUserInfo, fetch_userinfo

    with respx.mock:
        respx.get(NAVER_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "resultcode": "00",
                    "message": "success",
                    "response": {
                        "id": "naver-uid-001",
                        "email": "user@naver.com",
                        "nickname": "네이버유저",
                    },
                },
            )
        )
        info = await fetch_userinfo("naver-access-abc")

    assert isinstance(info, NaverUserInfo)
    assert info.provider_user_id == "naver-uid-001"
    assert info.email == "user@naver.com"
    assert info.nickname == "네이버유저"


@pytest.mark.asyncio
async def test_fetch_userinfo_result_code_not_00():
    """resultcode 가 00이 아니면 NaverUserinfoError."""
    from app.auth.naver import NaverUserinfoError, fetch_userinfo

    with respx.mock:
        respx.get(NAVER_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={"resultcode": "01", "message": "error"},
            )
        )
        with pytest.raises(NaverUserinfoError):
            await fetch_userinfo("token")


@pytest.mark.asyncio
async def test_fetch_userinfo_no_email():
    """네이버 응답에 email 없음 → NaverEmailConsentRequiredError."""
    from app.auth.naver import NaverEmailConsentRequiredError, fetch_userinfo

    with respx.mock:
        respx.get(NAVER_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "resultcode": "00",
                    "message": "success",
                    "response": {"id": "naver-uid-002"},
                },
            )
        )
        with pytest.raises(NaverEmailConsentRequiredError):
            await fetch_userinfo("token-no-email")


@pytest.mark.asyncio
async def test_fetch_userinfo_server_error():
    """네이버 API 500 → NaverUserinfoError."""
    from app.auth.naver import NaverUserinfoError, fetch_userinfo

    with respx.mock:
        respx.get(NAVER_USERINFO_URL).mock(return_value=Response(500))
        with pytest.raises(NaverUserinfoError):
            await fetch_userinfo("any-token")


@pytest.mark.asyncio
async def test_build_authorize_url(settings):
    """authorize URL 에 client_id·response_type·state 포함."""
    from app.auth.naver import build_authorize_url

    url = build_authorize_url("naver-state", settings=settings)
    assert "nid.naver.com/oauth2.0/authorize" in url
    assert "state=naver-state" in url
    assert "response_type=code" in url
