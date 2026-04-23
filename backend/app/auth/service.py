"""AuthService: OAuth 로그인 + 토큰 발급 + 회전·로그아웃."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Literal, Protocol

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import kakao, naver
from app.auth.jwt import (
    InvalidJWTError,
    decode_refresh_token,
    encode_access_token,
    encode_refresh_token,
)
from app.auth.models import RefreshToken
from app.auth.schemas import TokenPair
from app.core.config import Settings, get_settings
from app.core.exceptions import ServiceError, UpstreamError
from app.core.logging import get_logger

# Wave 1 병렬: tenancy 모듈은 별도 worktree 에서 생성되며, 최종 머지 시점에 존재해야 함.
# 컬럼 계약: spec.md 의 `users`, `tenants` 스키마를 따른다.
from app.tenancy.models import Tenant, User

logger = get_logger(__name__)

_STATE_PREFIX = "oauth:state"
_STATE_TTL_SECONDS = 600  # 10 분

Provider = Literal["kakao", "naver"]


class _NormalizedUserInfo(Protocol):
    provider_user_id: str
    email: str | None
    nickname: str | None


class OAuthStateInvalidError(ServiceError):
    """state 검증 실패."""

    code = "CSRF"
    http_status = 400
    detail = "state_mismatch"


class RefreshTokenInvalidError(ServiceError):
    """refresh token 이 유효하지 않음."""

    code = "UNAUTHORIZED"
    http_status = 401
    detail = "invalid_refresh_token"


class RefreshTokenExpiredError(RefreshTokenInvalidError):
    """refresh token 만료."""

    detail = "refresh_token_expired"


class RefreshTokenRevokedError(RefreshTokenInvalidError):
    """revoke 된 refresh token."""

    detail = "refresh_token_revoked"


class AuthService:
    """OAuth 로그인 + JWT 발급·회전·로그아웃 담당 서비스."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings=None,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings or get_settings()

    # ----- state (CSRF) -----

    async def create_state(self, provider: Provider) -> str:
        """랜덤 state 값 생성 + Redis 저장 (TTL 10 분)."""
        state = secrets.token_urlsafe(32)
        key = f"{_STATE_PREFIX}:{provider}:{state}"
        await self._redis.set(key, "1", ex=_STATE_TTL_SECONDS)
        return state

    async def consume_state(self, provider: Provider, state: str) -> None:
        """state 검증 + 일회성 소비 (Redis 키 삭제)."""
        key = f"{_STATE_PREFIX}:{provider}:{state}"
        deleted = await self._redis.delete(key)
        if not deleted:
            raise OAuthStateInvalidError()

    # ----- OAuth 로그인 -----

    async def login_with_kakao(self, code: str) -> TokenPair:
        """카카오 OAuth 콜백 처리 → JWT 발급."""
        access_token = await kakao.exchange_code(code, settings=self._settings)
        userinfo = await kakao.fetch_userinfo(access_token)
        user = await self._find_or_create_tenant_and_user(
            provider="kakao", userinfo=userinfo
        )
        return await self._issue_token_pair(user)

    async def login_with_naver(self, code: str, state: str) -> TokenPair:
        """네이버 OAuth 콜백 처리 → JWT 발급."""
        access_token = await naver.exchange_code(code, state, settings=self._settings)
        userinfo = await naver.fetch_userinfo(access_token)
        user = await self._find_or_create_tenant_and_user(
            provider="naver", userinfo=userinfo
        )
        return await self._issue_token_pair(user)

    # ----- 토큰 회전 -----

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """refresh token 검증 → 기존 jti revoke + 신규 access/refresh 발급."""
        try:
            payload = decode_refresh_token(refresh_token, settings=self._settings)
        except InvalidJWTError as e:
            if str(e) == "refresh_token_expired":
                raise RefreshTokenExpiredError() from e
            raise RefreshTokenInvalidError() from e

        old_jti_str = payload["jti"]
        user_id = int(payload["sub"])

        stored = await self._session.get(RefreshToken, old_jti_str)
        if stored is None:
            raise RefreshTokenInvalidError()
        if stored.revoked_at is not None:
            raise RefreshTokenRevokedError()
        # SQLite 는 timezone-naive 로 저장하므로 tzinfo 가 없으면 UTC 로 간주
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise RefreshTokenExpiredError()

        user = await self._session.get(User, user_id)
        if user is None:
            raise RefreshTokenInvalidError()

        # rotation: 기존 revoke + 신규 발급
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == old_jti_str)
            .values(revoked_at=datetime.now(UTC))
        )
        return await self._issue_token_pair(user)

    # ----- 로그아웃 -----

    async def logout(self, refresh_token: str) -> None:
        """refresh token revoke (멱등)."""
        try:
            payload = decode_refresh_token(refresh_token, settings=self._settings)
        except InvalidJWTError:
            # 이미 만료/위조된 토큰이라도 로그아웃은 멱등으로 처리
            return

        jti_str = payload["jti"]
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti_str, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    # ----- 내부 헬퍼 -----

    async def _find_or_create_tenant_and_user(
        self,
        *,
        provider: Provider,
        userinfo: _NormalizedUserInfo,
    ) -> User:
        """(auth_provider, provider_user_id) 로 조회, 없으면 tenant + user 생성."""
        stmt = select(User).where(
            User.auth_provider == provider,
            User.provider_user_id == userinfo.provider_user_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.last_login_at = datetime.now(UTC)
            await self._session.flush()
            return existing

        if not userinfo.email:
            raise UpstreamError(detail="email_required", code="EMAIL_REQUIRED")

        tenant_name = userinfo.nickname or userinfo.email
        tenant = Tenant(
            name=self._unique_tenant_name(tenant_name),
            plan="starter",
            api_quota_monthly=self._settings.default_tenant_api_quota_monthly,
        )
        self._session.add(tenant)
        await self._session.flush()  # tenant.id 확보

        user = User(
            tenant_id=tenant.id,
            email=userinfo.email,
            auth_provider=provider,
            provider_user_id=userinfo.provider_user_id,
            role="owner",
            last_login_at=datetime.now(UTC),
        )
        self._session.add(user)
        await self._session.flush()
        logger.info(
            "auth_user_provisioned",
            provider=provider,
            user_id=user.id,
            tenant_id=tenant.id,
        )
        return user

    def _unique_tenant_name(self, base: str) -> str:
        """테넌트 이름 중복 회피용 suffix (실제 유일성은 DB unique 제약에 의존)."""
        suffix = secrets.token_hex(3)
        return f"{base}-{suffix}"

    async def _issue_token_pair(self, user: User) -> TokenPair:
        """access + refresh token 쌍을 발급하고 DB 에 refresh 레코드 저장."""
        access_token, access_exp, _ = encode_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            settings=self._settings,
        )
        refresh_token, refresh_exp, refresh_jti = encode_refresh_token(
            user_id=user.id,
            settings=self._settings,
        )
        self._session.add(
            RefreshToken(
                jti=str(refresh_jti),
                user_id=user.id,
                expires_at=refresh_exp,
            )
        )
        await self._session.flush()

        now = datetime.now(UTC)
        expires_in = max(int((access_exp - now).total_seconds()), 0)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
