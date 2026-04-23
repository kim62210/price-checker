"""16.1 Tenant/Shop/User CRUD 및 제약 테스트."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_tenant_create_and_read(db_session: AsyncSession):
    """테넌트 생성 후 단건 조회."""
    from app.tenancy.models import Tenant

    tenant = Tenant(name="test-co", plan="starter", api_quota_monthly=10000)
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.name == "test-co"
    assert tenant.plan == "starter"
    assert tenant.api_quota_monthly == 10000


@pytest.mark.asyncio
async def test_tenant_name_unique_constraint(db_session: AsyncSession):
    """동일 이름 테넌트 생성 시 IntegrityError."""
    from app.tenancy.models import Tenant

    db_session.add(Tenant(name="duplicate-name"))
    await db_session.flush()

    db_session.add(Tenant(name="duplicate-name"))
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_tenant_plan_default(db_session: AsyncSession):
    """plan 미지정 시 starter 기본값."""
    from app.tenancy.models import Tenant

    tenant = Tenant(name="default-plan-tenant")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    assert tenant.plan == "starter"


@pytest.mark.asyncio
async def test_tenant_quota_default(db_session: AsyncSession):
    """api_quota_monthly 미지정 시 10000 기본값."""
    from app.tenancy.models import Tenant

    tenant = Tenant(name="default-quota-tenant")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    assert tenant.api_quota_monthly == 10000


@pytest.mark.asyncio
async def test_shop_create_with_tenant_fk(db_session: AsyncSession, test_tenant_a):
    """Shop 생성 — tenant_id FK 확인."""
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_a.id, name="매장 A-1")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)

    assert shop.id is not None
    assert shop.tenant_id == test_tenant_a.id
    assert shop.name == "매장 A-1"


@pytest.mark.asyncio
async def test_shop_cascade_delete(db_session: AsyncSession):
    """테넌트 삭제 시 소속 Shop CASCADE 삭제 확인."""
    from app.tenancy.models import Shop, Tenant

    tenant = Tenant(name="cascade-tenant")
    db_session.add(tenant)
    await db_session.flush()

    shop = Shop(tenant_id=tenant.id, name="삭제될 매장")
    db_session.add(shop)
    await db_session.flush()
    shop_id = shop.id

    await db_session.delete(tenant)
    await db_session.flush()

    found = await db_session.get(Shop, shop_id)
    assert found is None


@pytest.mark.asyncio
async def test_user_create(db_session: AsyncSession, test_tenant_a):
    """User 생성 기본 필드 확인."""
    from app.tenancy.models import User

    user = User(
        tenant_id=test_tenant_a.id,
        email="new@example.com",
        auth_provider="kakao",
        provider_user_id="kakao-999",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.tenant_id == test_tenant_a.id
    assert user.role == "owner"


@pytest.mark.asyncio
async def test_user_provider_unique_constraint(db_session: AsyncSession, test_tenant_a):
    """동일 (auth_provider, provider_user_id) 조합은 UNIQUE 위반."""
    from app.tenancy.models import User

    db_session.add(User(
        tenant_id=test_tenant_a.id,
        email="first@example.com",
        auth_provider="kakao",
        provider_user_id="same-pid",
    ))
    await db_session.flush()

    db_session.add(User(
        tenant_id=test_tenant_a.id,
        email="second@example.com",
        auth_provider="kakao",
        provider_user_id="same-pid",
    ))
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_user_list_in_tenant(db_session: AsyncSession, test_tenant_a, test_tenant_b):
    """테넌트 A 유저 목록에 테넌트 B 유저는 미포함."""
    from app.tenancy.models import User
    from sqlalchemy import select

    u_a = User(
        tenant_id=test_tenant_a.id, email="a@ex.com",
        auth_provider="kakao", provider_user_id="pid-a",
    )
    u_b = User(
        tenant_id=test_tenant_b.id, email="b@ex.com",
        auth_provider="naver", provider_user_id="pid-b",
    )
    db_session.add_all([u_a, u_b])
    await db_session.flush()

    stmt = select(User).where(User.tenant_id == test_tenant_a.id)
    result = list((await db_session.execute(stmt)).scalars().all())

    tenant_ids = {u.tenant_id for u in result}
    assert tenant_ids == {test_tenant_a.id}
