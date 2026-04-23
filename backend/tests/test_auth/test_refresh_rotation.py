"""16.7 Refresh 토큰 회전·revoke 테스트."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _issue_refresh_token(
    user,
    db_session: AsyncSession,
    settings,
    *,
    expired: bool = False,
) -> str:
    """테스트용 refresh token 발급 + DB 저장."""
    from app.auth.jwt import encode_refresh_token
    from app.auth.models import RefreshToken

    now = None
    if expired:
        now = datetime.now(UTC) - timedelta(days=settings.jwt_refresh_ttl_days + 1)

    token, exp, jti = encode_refresh_token(user_id=user.id, settings=settings, now=now)
    db_session.add(RefreshToken(jti=str(jti), user_id=user.id, expires_at=exp))
    await db_session.flush()
    return token


@pytest.mark.asyncio
async def test_refresh_rotation_issues_new_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a,
    settings,
):
    """유효한 refresh → 새 access/refresh 쌍 반환."""
    token = await _issue_refresh_token(test_user_a, db_session, settings)

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"payload": {"refresh_token": token}},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["refresh_token"] != token  # 새 refresh 발급


@pytest.mark.asyncio
async def test_refresh_old_token_is_revoked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a,
    settings,
):
    """회전 후 기존 refresh token 재사용 → 401 revoked."""
    token = await _issue_refresh_token(test_user_a, db_session, settings)

    # 1회 정상 사용
    r1 = await client.post("/api/v1/auth/refresh", json={"payload": {"refresh_token": token}})
    assert r1.status_code == 200

    # DB 커밋 (rotation write 반영)
    await db_session.commit()

    # 동일 token 재사용 → 401
    r2 = await client.post("/api/v1/auth/refresh", json={"payload": {"refresh_token": token}})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_expired_refresh_token_returns_401(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a,
    settings,
):
    """만료된 refresh token → 401."""
    token = await _issue_refresh_token(test_user_a, db_session, settings, expired=True)

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"payload": {"refresh_token": token}},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_forged_refresh_token_returns_401(client: AsyncClient):
    """위조된 refresh token → 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"payload": {"refresh_token": "totally.fake.token"}},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a,
    settings,
):
    """logout 후 해당 refresh token 으로 refresh 요청 → 401."""
    token = await _issue_refresh_token(test_user_a, db_session, settings)

    logout_r = await client.post("/api/v1/auth/logout", json={"payload": {"refresh_token": token}})
    assert logout_r.status_code == 204

    await db_session.commit()

    refresh_r = await client.post("/api/v1/auth/refresh", json={"payload": {"refresh_token": token}})
    assert refresh_r.status_code == 401
