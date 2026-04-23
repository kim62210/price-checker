"""검색 서비스 (피벗 후 재설계).

백엔드는 더 이상 외부 크롤링을 수행하지 않는다. 클라이언트(Tauri·브라우저 확장)가
``procurement_results`` 로 업로드한 데이터 중 현재 테넌트 소속 건만 검색해
``per_unit_price`` 오름차순으로 반환한다.

핵심 단계:
1. ``quota_service.check_and_consume`` 로 월간 쿼터 소모
2. ``cache_service`` 로 ``search:{tenant_id}:{md5(q|limit)}`` 캐시 조회
3. 캐시 미스면 DB 에서 ``tenant_id`` 격리 쿼리 실행 (product_name/option_text ILIKE)
4. ``ranking_service`` 로 정렬 후 캐시 저장

설계 참고:
- ``openspec/changes/pivot-backend-multi-tenant/specs/search-api/spec.md``
- ``openspec/changes/pivot-backend-multi-tenant/specs/product-search/spec.md``
- ``openspec/changes/pivot-backend-multi-tenant/design.md`` §5.1
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.procurement.models import ProcurementOrder, ProcurementResult
from app.schemas.search import Platform, SearchResponse, SearchResultItem, SourceStatus
from app.services.cache_service import (
    cache_delete,
    cache_get_json,
    cache_set_json,
    make_search_key,
)
from app.services.quota_service import check_and_consume

logger = get_logger(__name__)


def _escape_like(token: str) -> str:
    """``%``, ``_``, ``\\`` escape 후 ``%token%`` 래핑 준비."""
    return (
        token.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


async def _load_matches(
    session: AsyncSession,
    *,
    tenant_id: int,
    query: str,
    limit: int,
) -> list[tuple[ProcurementResult, ProcurementOrder]]:
    """테넌트 격리 + product_name/option_text ILIKE 매칭 쿼리."""
    needle = f"%{_escape_like(query.strip())}%"

    stmt = (
        select(ProcurementResult, ProcurementOrder)
        .join(
            ProcurementOrder,
            ProcurementOrder.id == ProcurementResult.order_id,
        )
        .options(joinedload(ProcurementResult.order))
        .where(
            ProcurementResult.tenant_id == tenant_id,
            ProcurementOrder.tenant_id == tenant_id,
            or_(
                ProcurementOrder.product_name.ilike(needle, escape="\\"),
                ProcurementOrder.option_text.ilike(needle, escape="\\"),
            ),
        )
        .order_by(
            ProcurementResult.per_unit_price.asc(),
            ProcurementResult.collected_at.desc(),
            ProcurementResult.id.asc(),
        )
        .limit(limit)
    )

    rows = (await session.execute(stmt)).unique().all()
    return [(row[0], row[1]) for row in rows]


def _to_item(result: ProcurementResult, order: ProcurementOrder) -> SearchResultItem:
    return SearchResultItem(
        result_id=result.id,
        order_id=order.id,
        source=result.source,  # type: ignore[arg-type]
        product_url=result.product_url,
        seller_name=result.seller_name,
        listed_price=Decimal(result.listed_price),
        per_unit_price=Decimal(result.per_unit_price),
        shipping_fee=Decimal(result.shipping_fee),
        unit_count=result.unit_count,
        product_name=order.product_name,
        option_text=order.option_text,
    )


def _build_sources(
    items: list[SearchResultItem],
) -> dict[Platform, SourceStatus]:
    present: dict[Platform, SourceStatus] = {}
    for item in items:
        present.setdefault(item.source, "ok")
    return present


async def run_search(
    session: AsyncSession,
    *,
    tenant_id: int,
    monthly_quota: int,
    query: str,
    limit: int = 20,
    force_refresh: bool = False,
    settings: Settings | None = None,
) -> SearchResponse:
    """업로드된 ``procurement_results`` 를 검색해 랭킹된 응답을 반환.

    Args:
        session: DB 세션 (FastAPI ``get_db`` 의존성 주입)
        tenant_id: 현재 인증된 테넌트의 ID (격리 강제)
        monthly_quota: 테넌트의 월간 API 쿼터 (``tenants.api_quota_monthly``)
        query: 정규화 전 검색어
        limit: 최대 결과 수 (1..100)
        force_refresh: True 면 캐시를 무시하고 재집계 후 덮어쓴다
        settings: 주입 가능한 :class:`Settings`

    Raises:
        QuotaExceededError: 월간 쿼터 초과 (HTTP 429)
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    settings = settings or get_settings()

    # 1. 쿼터 소모 — 초과 시 QuotaExceededError
    await check_and_consume(tenant_id, monthly_quota)

    cache_key = make_search_key(tenant_id, query, limit)
    if force_refresh:
        await cache_delete(tenant_id, cache_key)
    else:
        cached = await cache_get_json(tenant_id, cache_key)
        if isinstance(cached, dict):
            try:
                response = SearchResponse.model_validate(
                    {**cached, "cached": True, "tenant_id": tenant_id}
                )
                logger.info(
                    "search_cache_hit",
                    tenant_id=tenant_id,
                    query=query,
                    limit=limit,
                )
                return response
            except Exception as exc:
                logger.warning(
                    "search_cache_invalid",
                    tenant_id=tenant_id,
                    error=str(exc),
                )
                await cache_delete(tenant_id, cache_key)

    # 2. DB 조회 (테넌트 격리)
    rows = await _load_matches(
        session, tenant_id=tenant_id, query=query, limit=limit
    )
    items = [_to_item(result, order) for result, order in rows]

    total_in_tenant = await session.scalar(
        select(func.count(ProcurementResult.id)).where(
            ProcurementResult.tenant_id == tenant_id
        )
    )

    if not items:
        hint = (
            "no_uploaded_results"
            if not total_in_tenant
            else "no_matching_results"
        )
        response = SearchResponse(
            query=query,
            limit=limit,
            tenant_id=tenant_id,
            results=[],
            sources={},
            cached=False,
            hint=hint,
        )
    else:
        response = SearchResponse(
            query=query,
            limit=limit,
            tenant_id=tenant_id,
            results=items,
            sources=_build_sources(items),
            cached=False,
            hint=None,
        )

    # 3. 캐시 저장 (cached=False 로 저장 — 히트 시점에 True 로 바꿔 반환)
    await cache_set_json(
        tenant_id,
        cache_key,
        response.model_dump(mode="json"),
        ttl_seconds=settings.search_cache_ttl_seconds,
    )
    logger.info(
        "search_completed",
        tenant_id=tenant_id,
        query=query,
        limit=limit,
        hit_count=len(items),
    )
    return response


__all__ = ["run_search"]
