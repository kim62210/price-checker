"""JWT 인코딩·디코딩 (HS256)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypedDict
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.core.config import Settings, get_settings


class AccessTokenPayload(TypedDict):
    """Access token claim 구조."""

    sub: str  # user_id 문자열
    tenant_id: int
    type: Literal["access"]
    iat: int
    exp: int
    jti: str


class RefreshTokenPayload(TypedDict):
    """Refresh token claim 구조."""

    sub: str
    type: Literal["refresh"]
    iat: int
    exp: int
    jti: str


class InvalidJWTError(ValueError):
    """디코딩·서명 검증 실패 공통 예외."""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def encode_access_token(
    *,
    user_id: int,
    tenant_id: int,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime, UUID]:
    """Access token 발급. 반환: (token, exp, jti)."""
    settings = settings or get_settings()
    issued_at = now or _now_utc()
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_ttl_minutes)
    jti = uuid4()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "type": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(jti),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at, jti


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> AccessTokenPayload:
    """Access token 디코드 + 서명·만료 검증."""
    settings = settings or get_settings()
    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as e:
        raise InvalidJWTError("access_token_expired") from e
    except InvalidTokenError as e:
        raise InvalidJWTError("invalid_access_token") from e

    if decoded.get("type") != "access":
        raise InvalidJWTError("token_type_mismatch")
    if "sub" not in decoded or "tenant_id" not in decoded:
        raise InvalidJWTError("malformed_access_token")
    return AccessTokenPayload(
        sub=str(decoded["sub"]),
        tenant_id=int(decoded["tenant_id"]),
        type="access",
        iat=int(decoded["iat"]),
        exp=int(decoded["exp"]),
        jti=str(decoded["jti"]),
    )


def encode_refresh_token(
    *,
    user_id: int,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime, UUID]:
    """Refresh token 발급. 반환: (token, exp, jti)."""
    settings = settings or get_settings()
    issued_at = now or _now_utc()
    expires_at = issued_at + timedelta(days=settings.jwt_refresh_ttl_days)
    jti = uuid4()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(jti),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at, jti


def decode_refresh_token(
    token: str,
    settings: Settings | None = None,
) -> RefreshTokenPayload:
    """Refresh token 디코드 + 서명·만료 검증."""
    settings = settings or get_settings()
    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as e:
        raise InvalidJWTError("refresh_token_expired") from e
    except InvalidTokenError as e:
        raise InvalidJWTError("invalid_refresh_token") from e

    if decoded.get("type") != "refresh":
        raise InvalidJWTError("token_type_mismatch")
    if "sub" not in decoded or "jti" not in decoded:
        raise InvalidJWTError("malformed_refresh_token")
    return RefreshTokenPayload(
        sub=str(decoded["sub"]),
        type="refresh",
        iat=int(decoded["iat"]),
        exp=int(decoded["exp"]),
        jti=str(decoded["jti"]),
    )
