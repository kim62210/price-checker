"""테넌트 격리용 FastAPI 의존성.

- `get_current_user`: `Authorization: Bearer <JWT>` 헤더에서 access token 을 파싱해
  해당 사용자를 반환. 토큰 누락/위조/만료/사용자 미존재 시 HTTP 401.
- `get_current_tenant`: 사용자의 `tenant_id` 로 테넌트를 조회해 주입. 미존재 시 401.

auth 모듈(Wave 1 병렬)이 `backend/app/auth/jwt.py` 에 아래 함수를 제공한다고 가정:

    def decode_access_token(token: str) -> dict[str, Any]:
        '''{sub: str|int, tenant_id: int, exp: int, ...}'''

auth 모듈이 아직 반영되지 않은 빌드에서는 `ImportError` 가 발생하므로 지연 import 로
처리하고, 해당 경로에서 501 NotImplemented 로 명시 실패시킨다.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.contextvars import bind_contextvars

from app.core.logging import get_logger
from app.db.session import get_db
from app.tenancy.models import Tenant, User
from app.tenancy.service import TenantService, UserService

logger = get_logger(__name__)


def _raise_unauthorized(detail: str) -> None:
    """일관된 401 에러 포맷."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": detail, "code": "UNAUTHORIZED"},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer_token(request: Request) -> str:
    """Authorization 헤더에서 Bearer 토큰 문자열만 추출."""
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        _raise_unauthorized("missing_bearer")
    token = authorization[7:].strip()
    if not token:
        _raise_unauthorized("missing_bearer")
    return token


def _decode_access_token(token: str) -> dict[str, Any]:
    """auth 모듈의 `decode_access_token` 을 지연 import 하여 호출.

    - 서명/만료 등 이유로 실패 시 `ValueError` 가 발생한다고 가정.
    - auth 모듈 자체가 아직 없으면 501 NotImplemented 로 명시 실패.
    """
    try:
        from app.auth.jwt import decode_access_token
    except ImportError as exc:
        logger.error("auth_module_missing", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={"detail": "auth_module_unavailable", "code": "NOT_IMPLEMENTED"},
        ) from exc

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        message = str(exc).lower()
        if "expired" in message:
            _raise_unauthorized("token_expired")
        _raise_unauthorized("invalid_token")
        raise  # pragma: no cover — unreachable, _raise_unauthorized raises
    except Exception as exc:  # 알 수 없는 디코딩 에러는 401 로 축약
        logger.warning("token_decode_failed", error=str(exc))
        _raise_unauthorized("invalid_token")
        raise  # pragma: no cover
    if not isinstance(payload, dict):
        _raise_unauthorized("invalid_token")
    return payload


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """현재 로그인한 사용자를 반환.

    실패 시 HTTP 401 `{detail, code: "UNAUTHORIZED"}`.
    """
    token = _extract_bearer_token(request)
    payload = _decode_access_token(token)

    sub = payload.get("sub")
    if sub is None:
        _raise_unauthorized("invalid_token")

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        _raise_unauthorized("invalid_token")
        raise  # pragma: no cover

    user = await UserService(session).get_user(user_id)
    if user is None:
        _raise_unauthorized("user_not_found")
        raise  # pragma: no cover — _raise_unauthorized never returns

    request.state.user_id = user.id
    request.state.tenant_id = user.tenant_id
    # 이후 발생하는 모든 structlog 이벤트에 tenant_id / user_id 가 자동 포함된다.
    bind_contextvars(tenant_id=user.tenant_id, user_id=user.id)
    return user


async def get_current_tenant(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    """현재 사용자의 소속 테넌트를 반환."""
    tenant = await TenantService(session).get_tenant(user.tenant_id)
    if tenant is None:
        _raise_unauthorized("tenant_not_found")
        raise  # pragma: no cover
    return tenant


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
