"""테넌트·소매점·사용자 서비스 레이어.

모든 조회/수정 쿼리에 `WHERE tenant_id = :current_tenant_id` 를 강제해 크로스
테넌트 데이터 유출을 스키마 레벨 이전에 애플리케이션 레벨에서 차단한다.

서비스 메서드 시그니처에 `tenant_id: int` 가 필수 인자로 들어가 있어야 하며,
누락 시 타입 체크로 실패한다 (design.md §1 참고).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ServiceError
from app.core.logging import get_logger
from app.tenancy.models import Shop, Tenant, User
from app.tenancy.schemas import ShopCreate, TenantCreate

logger = get_logger(__name__)


class TenantNotFoundError(ServiceError):
    """요청된 테넌트를 찾을 수 없음 — 라우트에서 404 로 매핑."""

    code = "NOT_FOUND"
    http_status = 404
    detail = "tenant_not_found"


class ShopNotFoundError(ServiceError):
    code = "NOT_FOUND"
    http_status = 404
    detail = "shop_not_found"


class UserNotFoundError(ServiceError):
    code = "NOT_FOUND"
    http_status = 404
    detail = "user_not_found"


class TenantAlreadyExistsError(ServiceError):
    code = "CONFLICT"
    http_status = 409
    detail = "tenant_already_exists"


def _default_quota(settings: Settings | None = None) -> int:
    """Wave 2 에서 `DEFAULT_TENANT_API_QUOTA_MONTHLY` 설정이 추가될 예정.

    현재 `core/config.py` 에 해당 필드가 없을 수 있으므로 방어적으로 조회한다.
    """
    cfg = settings or get_settings()
    return int(getattr(cfg, "default_tenant_api_quota_monthly", 10000))


class TenantService:
    """테넌트 CRUD — 주로 인증/온보딩 경로에서 사용."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def get_tenant(self, tenant_id: int) -> Tenant | None:
        """테넌트 id 로 단건 조회. 없으면 None."""
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_tenant_or_404(self, tenant_id: int) -> Tenant:
        tenant = await self.get_tenant(tenant_id)
        if tenant is None:
            raise TenantNotFoundError()
        return tenant

    async def get_tenant_by_name(self, name: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_tenant(self, payload: TenantCreate) -> Tenant:
        """테넌트 신규 생성 — 이름 중복 시 409."""
        quota = (
            payload.api_quota_monthly
            if payload.api_quota_monthly is not None
            else _default_quota(self._settings)
        )
        tenant = Tenant(
            name=payload.name,
            plan=payload.plan,
            api_quota_monthly=quota,
        )
        self._session.add(tenant)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise TenantAlreadyExistsError() from exc
        await self._session.refresh(tenant)
        logger.info(
            "tenant_created",
            tenant_id=tenant.id,
            name=tenant.name,
            plan=tenant.plan,
        )
        return tenant


class ShopService:
    """소매점 CRUD — 모든 경로가 `tenant_id` 로 필터링된다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_shops(
        self, *, tenant_id: int, limit: int = 50, offset: int = 0
    ) -> list[Shop]:
        """현재 테넌트 소속 매장 목록."""
        stmt = (
            select(Shop)
            .where(Shop.tenant_id == tenant_id)
            .order_by(Shop.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_shop(self, *, tenant_id: int, shop_id: int) -> Shop | None:
        """테넌트 격리된 단건 조회 — 타 테넌트 shop 은 None."""
        stmt = select(Shop).where(Shop.id == shop_id, Shop.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_shop_or_404(self, *, tenant_id: int, shop_id: int) -> Shop:
        shop = await self.get_shop(tenant_id=tenant_id, shop_id=shop_id)
        if shop is None:
            raise ShopNotFoundError()
        return shop

    async def create_shop(self, *, tenant_id: int, payload: ShopCreate) -> Shop:
        """요청자의 `tenant_id` 로 shop 생성."""
        shop = Shop(
            tenant_id=tenant_id,
            name=payload.name,
            business_number=payload.business_number,
        )
        self._session.add(shop)
        await self._session.flush()
        await self._session.refresh(shop)
        logger.info("shop_created", tenant_id=tenant_id, shop_id=shop.id, name=shop.name)
        return shop


class UserService:
    """사용자 조회 — auth 모듈이 프로바이더 로그인 시 함께 사용."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user(self, user_id: int) -> User | None:
        """tenant 필터 없는 단건 조회 — 의존성(`get_current_user`) 경로에서만 사용."""
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_or_404(self, user_id: int) -> User:
        user = await self.get_user(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def get_user_in_tenant(self, *, tenant_id: int, user_id: int) -> User | None:
        """테넌트 격리된 사용자 조회."""
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_provider(
        self, *, auth_provider: str, provider_user_id: str
    ) -> User | None:
        """OAuth 프로바이더 id 로 조회 (재로그인 경로)."""
        stmt = select(User).where(
            User.auth_provider == auth_provider,
            User.provider_user_id == provider_user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users_in_tenant(
        self, *, tenant_id: int, limit: int = 50, offset: int = 0
    ) -> list[User]:
        stmt = (
            select(User)
            .where(User.tenant_id == tenant_id)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def touch_last_login(self, user_id: int) -> None:
        """재로그인 시 `last_login_at` 갱신."""
        user = await self.get_user(user_id)
        if user is None:
            raise UserNotFoundError()
        user.last_login_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
