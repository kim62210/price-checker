"""5.4 search_service 재설계 테스트 — procurement_results 기반 검색 + 테넌트 격리 + 캐시."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# ----- 시드 헬퍼 -----


async def _seed_order_and_result(
    db_session: AsyncSession,
    *,
    tenant_id: int,
    shop_id: int,
    product_name: str,
    per_unit_price: str = "1500.00",
) -> tuple:
    """발주 + 결과 1건 생성 후 반환."""
    from app.procurement.models import ProcurementOrder, ProcurementResult

    order = ProcurementOrder(
        tenant_id=tenant_id,
        shop_id=shop_id,
        product_name=product_name,
        quantity=10,
        unit="개",
        status="completed",
    )
    db_session.add(order)
    await db_session.flush()

    result = ProcurementResult(
        order_id=order.id,
        tenant_id=tenant_id,
        source="naver",
        product_url="https://smartstore.naver.com/test",
        listed_price=Decimal(per_unit_price),
        per_unit_price=Decimal(per_unit_price),
        shipping_fee=Decimal("0"),
        unit_count=1,
        collected_at=datetime.now(UTC),
    )
    db_session.add(result)
    await db_session.flush()
    await db_session.refresh(result)
    return order, result


# ----- 픽스처 -----


@pytest.fixture
async def shop_a(db_session: AsyncSession, test_tenant_a):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_a.id, name="검색 매장 A")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def shop_b(db_session: AsyncSession, test_tenant_b):
    from app.tenancy.models import Shop

    shop = Shop(tenant_id=test_tenant_b.id, name="검색 매장 B")
    db_session.add(shop)
    await db_session.flush()
    await db_session.refresh(shop)
    return shop


@pytest.fixture
async def seeded_results(db_session: AsyncSession, test_tenant_a, test_tenant_b, shop_a, shop_b):
    """A 테넌트 3건, B 테넌트 2건 seed."""
    a_orders = []
    for name in ["우유 A1", "우유 A2", "주스 A3"]:
        o, r = await _seed_order_and_result(
            db_session, tenant_id=test_tenant_a.id, shop_id=shop_a.id, product_name=name
        )
        a_orders.append((o, r))

    b_orders = []
    for name in ["우유 B1", "우유 B2"]:
        o, r = await _seed_order_and_result(
            db_session, tenant_id=test_tenant_b.id, shop_id=shop_b.id, product_name=name
        )
        b_orders.append((o, r))

    return {"a": a_orders, "b": b_orders}


@pytest.fixture(autouse=True)
def patch_redis(fake_redis, monkeypatch):
    """search_service/cache_service/quota_service 가 직접 호출하는 get_redis() 패치."""
    import app.db.redis as _redis_module  # noqa: PLC0415

    monkeypatch.setattr(_redis_module, "_redis", fake_redis)


# ----- 테스트 -----


@pytest.mark.asyncio
async def test_search_returns_only_tenant_results(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    seeded_results,
    settings,
):
    """테넌트 A 검색 → A 결과만 반환, B 결과 미포함."""
    from app.services.search_service import run_search

    response = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="우유",
        limit=10,
        settings=settings,
    )

    result_ids = {item.result_id for item in response.results}
    a_result_ids = {r.id for _, r in seeded_results["a"]}
    b_result_ids = {r.id for _, r in seeded_results["b"]}

    # A 의 우유 관련 결과(A1, A2)는 포함
    assert result_ids.issubset(a_result_ids | {-1})
    # B 결과는 하나도 없어야
    assert not result_ids.intersection(b_result_ids)


@pytest.mark.asyncio
async def test_search_tenant_isolation_strict(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    test_tenant_b,
    seeded_results,
    settings,
):
    """B 테넌트 검색 결과에 A 결과가 없다."""
    from app.services.search_service import run_search

    response_b = await run_search(
        db_session,
        tenant_id=test_tenant_b.id,
        monthly_quota=10000,
        query="우유",
        limit=10,
        settings=settings,
    )

    a_result_ids = {r.id for _, r in seeded_results["a"]}
    result_ids_b = {item.result_id for item in response_b.results}
    assert not result_ids_b.intersection(a_result_ids)


@pytest.mark.asyncio
async def test_search_cache_hit_skips_quota(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    seeded_results,
    settings,
):
    """캐시 hit 시 두번째 호출은 캐시를 반환한다 (cached=True)."""
    from app.services.search_service import run_search

    # 첫 번째 — DB 조회 + 캐시 저장
    r1 = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="우유",
        limit=5,
        settings=settings,
    )
    assert r1.cached is False

    # 두 번째 — 캐시 hit
    r2 = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="우유",
        limit=5,
        settings=settings,
    )
    assert r2.cached is True


@pytest.mark.asyncio
async def test_search_cache_miss_on_different_query(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    seeded_results,
    settings,
):
    """다른 query 는 캐시 미스 → cached=False."""
    from app.services.search_service import run_search

    await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="우유",
        limit=5,
        settings=settings,
    )

    r = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="주스",
        limit=5,
        settings=settings,
    )
    assert r.cached is False


@pytest.mark.asyncio
async def test_search_force_refresh_bypasses_cache(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    seeded_results,
    settings,
):
    """force_refresh=True 면 캐시 무시 → cached=False."""
    from app.services.search_service import run_search

    # 캐시 저장
    await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="우유",
        limit=5,
        settings=settings,
    )

    # force_refresh
    r = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="우유",
        limit=5,
        force_refresh=True,
        settings=settings,
    )
    assert r.cached is False


@pytest.mark.asyncio
async def test_search_ignores_compare_ineligible_results(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    shop_a,
    settings,
):
    """compare_eligible=False 결과는 검색 랭킹에서 제외된다."""
    from app.procurement.models import ProcurementOrder, ProcurementResult
    from app.services.search_service import run_search

    order = ProcurementOrder(
        tenant_id=test_tenant_a.id,
        shop_id=shop_a.id,
        product_name="서울우유",
        quantity=10,
        unit="개",
        status="completed",
    )
    db_session.add(order)
    await db_session.flush()

    db_session.add(
        ProcurementResult(
            order_id=order.id,
            tenant_id=test_tenant_a.id,
            source="naver",
            product_url="https://shopping.naver.com/partial",
            listed_price=Decimal("1000.00"),
            per_unit_price=Decimal("100.00"),
            shipping_fee=Decimal("0"),
            unit_count=1,
            compare_eligible=False,
            collected_at=datetime.now(UTC),
        )
    )
    db_session.add(
        ProcurementResult(
            order_id=order.id,
            tenant_id=test_tenant_a.id,
            source="naver",
            product_url="https://shopping.naver.com/eligible",
            listed_price=Decimal("1500.00"),
            per_unit_price=Decimal("150.00"),
            shipping_fee=Decimal("0"),
            unit_count=1,
            compare_eligible=True,
            collected_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    response = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="서울우유",
        limit=10,
        settings=settings,
    )

    assert len(response.results) == 1
    assert response.results[0].product_url == "https://shopping.naver.com/eligible"


@pytest.mark.asyncio
async def test_search_empty_result_hint(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    settings,
):
    """결과 없을 때 hint 가 no_uploaded_results 또는 no_matching_results."""
    from app.services.search_service import run_search

    r = await run_search(
        db_session,
        tenant_id=test_tenant_a.id,
        monthly_quota=10000,
        query="존재하지않는상품XYZ",
        limit=10,
        settings=settings,
    )
    assert r.results == []
    assert r.hint in ("no_uploaded_results", "no_matching_results")


@pytest.mark.asyncio
async def test_search_quota_exceeded_raises(
    db_session: AsyncSession,
    fake_redis,
    test_tenant_a,
    settings,
):
    """쿼터 0 초과 → QuotaExceededError."""
    from app.core.exceptions import QuotaExceededError
    from app.services.search_service import run_search

    with pytest.raises(QuotaExceededError):
        await run_search(
            db_session,
            tenant_id=test_tenant_a.id,
            monthly_quota=0,
            query="우유",
            limit=5,
            settings=settings,
        )
