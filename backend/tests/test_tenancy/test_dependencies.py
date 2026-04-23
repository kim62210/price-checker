"""16.2 get_current_tenant 의존성 — 토큰 누락·만료·위조 케이스."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _get_code(body: dict) -> str:
    """HTTPException detail 이 dict 인 경우 중첩 구조 처리."""
    detail = body.get("detail", {})
    if isinstance(detail, dict):
        return detail.get("code", "")
    return body.get("code", "")


@pytest.mark.asyncio
async def test_missing_authorization_header(client: AsyncClient):
    """Authorization 헤더 없음 → 401 missing_bearer."""
    response = await client.get("/api/v1/procurement/orders")
    assert response.status_code == 401
    assert _get_code(response.json()) == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_missing_bearer_scheme(client: AsyncClient):
    """Bearer 스킴 없이 토큰만 → 401."""
    response = await client.get(
        "/api/v1/procurement/orders",
        headers={"Authorization": "Token some-random-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_forged_token(client: AsyncClient):
    """위조된 JWT (잘못된 서명) → 401 invalid_token."""
    response = await client.get(
        "/api/v1/procurement/orders",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert response.status_code == 401
    assert _get_code(response.json()) == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_expired_access_token(client: AsyncClient, test_user_a, settings):
    """만료된 access token → 401 token_expired."""
    from datetime import UTC, datetime, timedelta

    from app.auth.jwt import encode_access_token

    past = datetime.now(UTC) - timedelta(hours=1)
    token, _, _ = encode_access_token(
        user_id=test_user_a.id,
        tenant_id=test_user_a.tenant_id,
        settings=settings,
        now=past - timedelta(minutes=settings.jwt_access_ttl_minutes + 1),
    )
    response = await client.get(
        "/api/v1/procurement/orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert _get_code(response.json()) == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_valid_token_returns_data(client: AsyncClient, auth_headers_a):
    """유효한 토큰 → 200 응답 (빈 목록)."""
    response = await client.get("/api/v1/procurement/orders", headers=auth_headers_a)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
