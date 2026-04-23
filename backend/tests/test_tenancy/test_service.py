"""tenancy service 추가 커버리지 테스트."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_tenant_service_get_tenant(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.service import TenantService

    result = await TenantService(db_session).get_tenant(test_tenant_a.id)
    assert result is not None
    assert result.id == test_tenant_a.id


@pytest.mark.asyncio
async def test_tenant_service_get_tenant_not_found(db_session: AsyncSession):
    from app.tenancy.service import TenantService

    result = await TenantService(db_session).get_tenant(99999)
    assert result is None


@pytest.mark.asyncio
async def test_tenant_service_get_tenant_or_404_found(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.service import TenantService

    result = await TenantService(db_session).get_tenant_or_404(test_tenant_a.id)
    assert result.id == test_tenant_a.id


@pytest.mark.asyncio
async def test_tenant_service_get_tenant_or_404_raises(db_session: AsyncSession):
    from app.tenancy.service import TenantNotFoundError, TenantService

    with pytest.raises(TenantNotFoundError):
        await TenantService(db_session).get_tenant_or_404(99999)


@pytest.mark.asyncio
async def test_tenant_service_get_tenant_by_name(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.service import TenantService

    result = await TenantService(db_session).get_tenant_by_name(test_tenant_a.name)
    assert result is not None
    assert result.name == test_tenant_a.name


@pytest.mark.asyncio
async def test_tenant_service_create_tenant(db_session: AsyncSession):
    from app.tenancy.schemas import TenantCreate
    from app.tenancy.service import TenantService

    payload = TenantCreate(name="new-tenant-xyz", plan="starter")
    tenant = await TenantService(db_session).create_tenant(payload)
    assert tenant.id is not None
    assert tenant.name == "new-tenant-xyz"


@pytest.mark.asyncio
async def test_tenant_service_create_tenant_duplicate(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.schemas import TenantCreate
    from app.tenancy.service import TenantAlreadyExistsError, TenantService

    payload = TenantCreate(name=test_tenant_a.name)
    with pytest.raises(TenantAlreadyExistsError):
        await TenantService(db_session).create_tenant(payload)


@pytest.mark.asyncio
async def test_shop_service_create_and_list(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.schemas import ShopCreate
    from app.tenancy.service import ShopService

    service = ShopService(db_session)
    shop = await service.create_shop(
        tenant_id=test_tenant_a.id,
        payload=ShopCreate(name="서비스 테스트 매장"),
    )
    assert shop.id is not None

    shops = await service.list_shops(tenant_id=test_tenant_a.id)
    assert any(s.id == shop.id for s in shops)


@pytest.mark.asyncio
async def test_shop_service_get_shop(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.schemas import ShopCreate
    from app.tenancy.service import ShopService

    service = ShopService(db_session)
    shop = await service.create_shop(
        tenant_id=test_tenant_a.id,
        payload=ShopCreate(name="단건 조회 매장"),
    )

    found = await service.get_shop(tenant_id=test_tenant_a.id, shop_id=shop.id)
    assert found is not None and found.id == shop.id

    not_found = await service.get_shop(tenant_id=test_tenant_a.id, shop_id=99999)
    assert not_found is None


@pytest.mark.asyncio
async def test_shop_service_get_shop_or_404(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.service import ShopNotFoundError, ShopService

    with pytest.raises(ShopNotFoundError):
        await ShopService(db_session).get_shop_or_404(tenant_id=test_tenant_a.id, shop_id=99999)


@pytest.mark.asyncio
async def test_user_service_get_user_in_tenant(db_session: AsyncSession, test_user_a, test_tenant_a):
    from app.tenancy.service import UserService

    user = await UserService(db_session).get_user_in_tenant(
        tenant_id=test_tenant_a.id, user_id=test_user_a.id
    )
    assert user is not None and user.id == test_user_a.id


@pytest.mark.asyncio
async def test_user_service_get_user_by_provider(db_session: AsyncSession, test_user_a):
    from app.tenancy.service import UserService

    user = await UserService(db_session).get_user_by_provider(
        auth_provider=test_user_a.auth_provider,
        provider_user_id=test_user_a.provider_user_id,
    )
    assert user is not None and user.id == test_user_a.id


@pytest.mark.asyncio
async def test_user_service_list_users_in_tenant(
    db_session: AsyncSession, test_user_a, test_tenant_a
):
    from app.tenancy.service import UserService

    users = await UserService(db_session).list_users_in_tenant(tenant_id=test_tenant_a.id)
    ids = [u.id for u in users]
    assert test_user_a.id in ids


@pytest.mark.asyncio
async def test_user_service_touch_last_login(db_session: AsyncSession, test_user_a):
    from app.tenancy.service import UserService

    await UserService(db_session).touch_last_login(test_user_a.id)
    user = await UserService(db_session).get_user(test_user_a.id)
    assert user is not None and user.last_login_at is not None


@pytest.mark.asyncio
async def test_user_service_get_user_or_404_raises(db_session: AsyncSession):
    from app.tenancy.service import UserNotFoundError, UserService

    with pytest.raises(UserNotFoundError):
        await UserService(db_session).get_user_or_404(99999)


@pytest.mark.asyncio
async def test_user_service_touch_not_found_raises(db_session: AsyncSession):
    from app.tenancy.service import UserNotFoundError, UserService

    with pytest.raises(UserNotFoundError):
        await UserService(db_session).touch_last_login(99999)
