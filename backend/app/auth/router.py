"""OAuth 로그인 · 토큰 갱신 · 로그아웃 라우터."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import kakao, naver
from app.auth.schemas import LogoutRequest, RefreshRequest, TokenPair
from app.auth.service import AuthService
from app.db.redis import get_redis
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

Provider = Literal["kakao", "naver"]


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AuthService:
    return AuthService(session=session, redis=redis)


@router.get("/kakao/login", status_code=status.HTTP_302_FOUND)
async def login_with_kakao(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> RedirectResponse:
    """카카오 authorize URL 로 302 redirect."""
    state = await service.create_state("kakao")
    url = kakao.build_authorize_url(state)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/kakao/callback", response_model=TokenPair)
async def callback_from_kakao(
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> TokenPair:
    """카카오 콜백 → state 검증 → 토큰 교환 → userinfo → JWT 발급."""
    await service.consume_state("kakao", state)
    tokens = await service.login_with_kakao(code)
    await session.commit()
    return tokens


@router.get("/naver/login", status_code=status.HTTP_302_FOUND)
async def login_with_naver(
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> RedirectResponse:
    """네이버 authorize URL 로 302 redirect."""
    state = await service.create_state("naver")
    url = naver.build_authorize_url(state)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/naver/callback", response_model=TokenPair)
async def callback_from_naver(
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
) -> TokenPair:
    """네이버 콜백 → state 검증 → 토큰 교환 → userinfo → JWT 발급."""
    await service.consume_state("naver", state)
    tokens = await service.login_with_naver(code, state)
    await session.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPair:
    """refresh token 검증 → 기존 jti revoke + 신규 토큰 발급 (회전)."""
    tokens = await service.refresh_tokens(payload.refresh_token)
    await session.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    """현재 refresh token revoke (멱등)."""
    try:
        await service.logout(payload.refresh_token)
    except Exception as e:  # pragma: no cover - safety net
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "logout_failed", "code": "INTERNAL"},
        ) from e
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
