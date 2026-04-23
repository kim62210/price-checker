"""16.10 테넌트 월간 쿼터 초과 시 429 테스트."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def small_quota_tenant(db_session: AsyncSession):
    """api_quota_monthly=3 인 미니 쿼터 테넌트."""
    from app.tenancy.models import Tenant

    tenant = Tenant(name="quota-test-tenant", plan="starter", api_quota_monthly=3)
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def small_quota_user(db_session: AsyncSession, small_quota_tenant):
    from app.tenancy.models import User

    user = User(
        tenant_id=small_quota_tenant.id,
        email="quota@example.com",
        auth_provider="kakao",
        provider_user_id="kakao-quota",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def quota_auth_headers(small_quota_user, settings):
    from app.auth.jwt import encode_access_token

    token, _, _ = encode_access_token(
        user_id=small_quota_user.id,
        tenant_id=small_quota_user.tenant_id,
        settings=settings,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def quota_shop(db_session: AsyncSession, small_quota_tenant):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=small_quota_tenant.id, name="쿼터 테스트 매장")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.mark.asyncio
async def test_quota_exceeded_returns_429(
    client: AsyncClient,
    quota_auth_headers,
    quota_shop,
    fake_redis,
):
    """쿼터 소진 후 추가 호출 → 429 QUOTA_EXCEEDED."""
    payload = {
        "shop_id": quota_shop.id,
        "product_name": "쿼터상품",
        "quantity": 1,
        "unit": "개",
    }

    responses = []
    for _ in range(4):
        r = await client.post(
            "/api/v1/procurement/orders",
            json=payload,
            headers=quota_auth_headers,
        )
        responses.append(r.status_code)

    assert 429 in responses, f"429 없음: {responses}"
    last_429 = next(r for r in reversed(responses) if r == 429)
    assert last_429 == 429


@pytest.mark.asyncio
async def test_quota_key_format(fake_redis, small_quota_tenant, settings):
    """Redis 키 형식 quota:tenant:{id}:{YYYYMM} 검증."""
    from app.services.quota_service import check_and_consume, tenant_quota_key

    await check_and_consume(
        small_quota_tenant.id,
        small_quota_tenant.api_quota_monthly,
        redis=fake_redis,
    )

    from app.services.quota_service import _current_year_month_kst

    ym = _current_year_month_kst()
    key = tenant_quota_key(small_quota_tenant.id, ym)
    value = await fake_redis.get(key)
    assert value is not None
    assert int(value) == 1


@pytest.mark.asyncio
async def test_quota_ttl_set_to_next_month(fake_redis, small_quota_tenant):
    """첫 호출 시 TTL 이 다음달 1일 00:00 KST 로 설정된다."""
    from app.services.quota_service import (
        check_and_consume,
        tenant_quota_key,
        _next_month_first_kst_epoch,
        _current_year_month_kst,
    )

    await check_and_consume(
        small_quota_tenant.id,
        1000,
        redis=fake_redis,
    )

    key = tenant_quota_key(small_quota_tenant.id, _current_year_month_kst())
    ttl = await fake_redis.ttl(key)
    expected_epoch = _next_month_first_kst_epoch()
    now_epoch = int(datetime.now(tz=timezone(timedelta(hours=9))).timestamp())

    # TTL > 0 이고 다음달 1일까지 남은 초와 근사 일치 (±10초)
    assert ttl > 0
    remaining = expected_epoch - now_epoch
    assert abs(ttl - remaining) < 10


@pytest.mark.asyncio
async def test_quota_exceeded_error_detail(fake_redis, small_quota_tenant):
    """QuotaExceededError 의 code 가 QUOTA_EXCEEDED 이다."""
    from app.core.exceptions import QuotaExceededError
    from app.services.quota_service import check_and_consume

    # quota=1 로 2번 호출
    await check_and_consume(small_quota_tenant.id, 1, redis=fake_redis)
    with pytest.raises(QuotaExceededError) as exc_info:
        await check_and_consume(small_quota_tenant.id, 1, redis=fake_redis)

    assert exc_info.value.code == "QUOTA_EXCEEDED"
