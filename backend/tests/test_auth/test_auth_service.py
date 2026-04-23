"""AuthService 추가 커버리지 — create_state, consume_state, login_with_kakao."""

from __future__ import annotations

import pytest
import respx
from httpx import Response


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_USERINFO_URL = "https://openapi.naver.com/v1/nid/me"


@pytest.fixture(autouse=True)
def patch_redis_module(fake_redis, monkeypatch):
    import app.db.redis as _m

    monkeypatch.setattr(_m, "_redis", fake_redis)


@pytest.mark.asyncio
async def test_create_and_consume_state(db_session, fake_redis, settings):
    from app.auth.service import AuthService

    svc = AuthService(session=db_session, redis=fake_redis, settings=settings)

    state = await svc.create_state("kakao")
    assert isinstance(state, str) and len(state) > 0

    # 정상 소비
    await svc.consume_state("kakao", state)

    # 재소비 시 오류
    from app.auth.service import OAuthStateInvalidError
    with pytest.raises(OAuthStateInvalidError):
        await svc.consume_state("kakao", state)


@pytest.mark.asyncio
async def test_login_with_kakao(db_session, fake_redis, settings):
    """카카오 로그인 플로우 — tenant+user 신규 생성 → TokenPair 반환."""
    from app.auth.service import AuthService
    from app.auth.schemas import TokenPair

    svc = AuthService(session=db_session, redis=fake_redis, settings=settings)

    with respx.mock:
        respx.post(KAKAO_TOKEN_URL).mock(
            return_value=Response(200, json={"access_token": "kt-abc"})
        )
        respx.get(KAKAO_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "id": 77777,
                    "kakao_account": {
                        "email": "new-kakao@example.com",
                        "email_needs_agreement": False,
                        "profile": {"nickname": "카카오신규"},
                    },
                },
            )
        )
        token_pair = await svc.login_with_kakao("kakao-code")

    assert isinstance(token_pair, TokenPair)
    assert token_pair.access_token
    assert token_pair.refresh_token

    await db_session.flush()


@pytest.mark.asyncio
async def test_login_with_kakao_existing_user(db_session, fake_redis, settings, test_user_a):
    """기존 유저 재로그인 — last_login_at 갱신."""
    from app.auth.service import AuthService

    svc = AuthService(session=db_session, redis=fake_redis, settings=settings)

    with respx.mock:
        respx.post(KAKAO_TOKEN_URL).mock(
            return_value=Response(200, json={"access_token": "kt-existing"})
        )
        respx.get(KAKAO_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "id": "kakao-111",  # test_user_a의 provider_user_id
                    "kakao_account": {
                        "email": test_user_a.email,
                        "email_needs_agreement": False,
                        "profile": {},
                    },
                },
            )
        )
        token_pair = await svc.login_with_kakao("kakao-existing-code")

    assert token_pair.access_token


@pytest.mark.asyncio
async def test_login_with_naver(db_session, fake_redis, settings):
    """네이버 로그인 플로우 — TokenPair 반환."""
    from app.auth.service import AuthService
    from app.auth.schemas import TokenPair

    svc = AuthService(session=db_session, redis=fake_redis, settings=settings)

    with respx.mock:
        respx.get(NAVER_TOKEN_URL).mock(
            return_value=Response(200, json={"access_token": "nt-abc"})
        )
        respx.get(NAVER_USERINFO_URL).mock(
            return_value=Response(
                200,
                json={
                    "resultcode": "00",
                    "message": "success",
                    "response": {
                        "id": "naver-newuid",
                        "email": "naver-new@example.com",
                        "nickname": "네이버신규",
                    },
                },
            )
        )
        token_pair = await svc.login_with_naver("naver-code", "some-state")

    assert isinstance(token_pair, TokenPair)

    await db_session.flush()
