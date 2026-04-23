"""16.4 JWT 인코딩·디코딩·만료·서명 검증 테스트."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_access_token_round_trip(settings):
    """access token 발급 → 디코딩 round-trip."""
    from app.auth.jwt import decode_access_token, encode_access_token

    token, expires_at, jti = encode_access_token(
        user_id=42,
        tenant_id=7,
        settings=settings,
    )
    payload = decode_access_token(token, settings=settings)

    assert payload["sub"] == "42"
    assert payload["tenant_id"] == 7
    assert payload["type"] == "access"
    assert payload["jti"] == str(jti)


@pytest.mark.asyncio
async def test_access_token_expiry(settings):
    """만료된 access token → InvalidJWTError."""
    from app.auth.jwt import InvalidJWTError, encode_access_token, decode_access_token

    past = datetime.now(UTC) - timedelta(minutes=settings.jwt_access_ttl_minutes + 5)
    token, _, _ = encode_access_token(
        user_id=1,
        tenant_id=1,
        settings=settings,
        now=past,
    )
    with pytest.raises(InvalidJWTError) as exc_info:
        decode_access_token(token, settings=settings)
    assert "expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_access_token_invalid_signature(settings):
    """서명이 틀린 토큰 → InvalidJWTError."""
    from app.auth.jwt import InvalidJWTError, decode_access_token
    from app.core.config import Settings

    token_settings = Settings(
        jwt_secret="original-secret",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    from app.auth.jwt import encode_access_token
    token, _, _ = encode_access_token(user_id=1, tenant_id=1, settings=token_settings)

    wrong_settings = Settings(
        jwt_secret="wrong-secret",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    with pytest.raises(InvalidJWTError):
        decode_access_token(token, settings=wrong_settings)


@pytest.mark.asyncio
async def test_refresh_token_round_trip(settings):
    """refresh token 발급 → 디코딩 round-trip."""
    from app.auth.jwt import decode_refresh_token, encode_refresh_token

    token, expires_at, jti = encode_refresh_token(user_id=10, settings=settings)
    payload = decode_refresh_token(token, settings=settings)

    assert payload["sub"] == "10"
    assert payload["type"] == "refresh"
    assert payload["jti"] == str(jti)


@pytest.mark.asyncio
async def test_refresh_token_expiry(settings):
    """만료된 refresh token → InvalidJWTError."""
    from app.auth.jwt import InvalidJWTError, encode_refresh_token, decode_refresh_token

    past = datetime.now(UTC) - timedelta(days=settings.jwt_refresh_ttl_days + 1)
    token, _, _ = encode_refresh_token(user_id=1, settings=settings, now=past)

    with pytest.raises(InvalidJWTError) as exc_info:
        decode_refresh_token(token, settings=settings)
    assert "expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_wrong_token_type_mismatch(settings):
    """access token 을 refresh decoder 로 디코딩 → InvalidJWTError."""
    from app.auth.jwt import InvalidJWTError, encode_access_token, decode_refresh_token

    token, _, _ = encode_access_token(user_id=1, tenant_id=1, settings=settings)
    with pytest.raises(InvalidJWTError):
        decode_refresh_token(token, settings=settings)


@pytest.mark.asyncio
async def test_access_token_contains_tenant_id(settings):
    """access token payload 에 tenant_id 가 포함된다."""
    from app.auth.jwt import decode_access_token, encode_access_token

    token, _, _ = encode_access_token(user_id=5, tenant_id=99, settings=settings)
    payload = decode_access_token(token, settings=settings)
    assert payload["tenant_id"] == 99


@pytest.mark.asyncio
async def test_each_token_has_unique_jti(settings):
    """연속 발급 시 jti 가 다르다."""
    from app.auth.jwt import encode_access_token

    _, _, jti1 = encode_access_token(user_id=1, tenant_id=1, settings=settings)
    _, _, jti2 = encode_access_token(user_id=1, tenant_id=1, settings=settings)
    assert jti1 != jti2
