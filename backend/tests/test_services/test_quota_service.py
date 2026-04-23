"""quota_service 추가 커버리지 테스트."""

from __future__ import annotations

from contextlib import suppress

import pytest


@pytest.fixture(autouse=True)
def patch_redis_module(fake_redis, monkeypatch):
    import app.db.redis as _m

    monkeypatch.setattr(_m, "_redis", fake_redis)


@pytest.mark.asyncio
async def test_get_current_usage_zero(fake_redis, test_tenant_a):
    from app.services.quota_service import get_current_usage

    usage = await get_current_usage(test_tenant_a.id, redis=fake_redis)
    assert usage == 0


@pytest.mark.asyncio
async def test_get_current_usage_after_consume(fake_redis, test_tenant_a):
    from app.services.quota_service import check_and_consume, get_current_usage

    await check_and_consume(test_tenant_a.id, 1000, redis=fake_redis)
    await check_and_consume(test_tenant_a.id, 1000, redis=fake_redis)
    usage = await get_current_usage(test_tenant_a.id, redis=fake_redis)
    assert usage == 2


@pytest.mark.asyncio
async def test_remaining_quota(fake_redis, test_tenant_a):
    from app.services.quota_service import check_and_consume, remaining_quota

    await check_and_consume(test_tenant_a.id, 10, redis=fake_redis)
    remaining = await remaining_quota(test_tenant_a.id, 10, redis=fake_redis)
    assert remaining == 9


@pytest.mark.asyncio
async def test_remaining_quota_zero_when_exceeded(fake_redis, test_tenant_a):
    from app.core.exceptions import QuotaExceededError
    from app.services.quota_service import check_and_consume, remaining_quota

    for _ in range(5):
        with suppress(QuotaExceededError):
            await check_and_consume(test_tenant_a.id, 3, redis=fake_redis)

    remaining = await remaining_quota(test_tenant_a.id, 3, redis=fake_redis)
    assert remaining == 0


@pytest.mark.asyncio
async def test_check_and_consume_invalid_quota():
    from app.services.quota_service import check_and_consume

    with pytest.raises(ValueError):
        await check_and_consume(1, -1)


@pytest.mark.asyncio
async def test_check_and_consume_invalid_amount():
    from app.services.quota_service import check_and_consume

    with pytest.raises(ValueError):
        await check_and_consume(1, 100, amount=0)
