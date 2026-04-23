"""테넌트·소매점·사용자 HTTP 라우터.

모든 라우트는 `get_current_tenant` / `get_current_user` 의존성을 통해
인증이 강제된다. 서비스 레이어는 `tenant_id` 를 필수 인자로 받아 row-level
격리를 수행하므로, 라우트에서 추가 검증은 생략한다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.tenancy.dependencies import CurrentTenant, CurrentUser
from app.tenancy.schemas import ShopCreate, ShopRead, TenantRead, UserRead
from app.tenancy.service import ShopService, UserService

router = APIRouter(prefix="/api/v1", tags=["tenancy"])


@router.get(
    "/tenants/me",
    response_model=TenantRead,
    status_code=status.HTTP_200_OK,
    summary="현재 사용자의 테넌트 조회",
)
async def get_my_tenant(tenant: CurrentTenant) -> TenantRead:
    """로그인한 사용자가 속한 테넌트 정보를 반환."""
    return TenantRead.model_validate(tenant)


@router.post(
    "/shops",
    response_model=ShopRead,
    status_code=status.HTTP_201_CREATED,
    summary="소매점 등록",
)
async def create_shop(
    payload: ShopCreate,
    tenant: CurrentTenant,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ShopRead:
    """요청자의 테넌트 소속으로 새 소매점을 등록."""
    shop = await ShopService(session).create_shop(tenant_id=tenant.id, payload=payload)
    await session.commit()
    await session.refresh(shop)
    return ShopRead.model_validate(shop)


@router.get(
    "/shops",
    response_model=list[ShopRead],
    status_code=status.HTTP_200_OK,
    summary="내 테넌트의 소매점 목록",
)
async def list_shops(
    tenant: CurrentTenant,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[ShopRead]:
    """현재 테넌트 소속 매장 목록 (페이지네이션: limit/offset)."""
    shops = await ShopService(session).list_shops(
        tenant_id=tenant.id, limit=limit, offset=offset
    )
    return [ShopRead.model_validate(shop) for shop in shops]


@router.get(
    "/shops/{shop_id}",
    response_model=ShopRead,
    status_code=status.HTTP_200_OK,
    summary="소매점 단건 조회",
)
async def get_shop(
    shop_id: int,
    tenant: CurrentTenant,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ShopRead:
    """다른 테넌트의 shop_id 로 접근 시 404 (격리)."""
    shop = await ShopService(session).get_shop_or_404(
        tenant_id=tenant.id, shop_id=shop_id
    )
    return ShopRead.model_validate(shop)


@router.get(
    "/users/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="현재 로그인한 사용자 조회",
)
async def get_my_user(user: CurrentUser) -> UserRead:
    """로그인한 사용자의 프로필 정보를 반환 (password_hash 제외)."""
    return UserRead.model_validate(user)


@router.get(
    "/users",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary="내 테넌트의 사용자 목록",
)
async def list_users(
    tenant: CurrentTenant,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[UserRead]:
    """현재 테넌트 소속 사용자 전체 조회 (owner/staff 모두 포함)."""
    users = await UserService(session).list_users_in_tenant(
        tenant_id=tenant.id, limit=limit, offset=offset
    )
    return [UserRead.model_validate(u) for u in users]
