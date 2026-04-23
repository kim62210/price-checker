"""검색 엔드포인트 (업로드된 procurement_results 기반)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.search import SearchResponse
from app.services.search_service import run_search
from app.tenancy.dependencies import CurrentTenant

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="업로드된 수집 결과 기반 최저가 검색",
)
async def search_endpoint(
    tenant: CurrentTenant,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=120, description="검색어")],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    force_refresh: Annotated[bool, Query(description="캐시 무시 후 재집계")] = False,
) -> SearchResponse:
    """현재 테넌트가 업로드한 `procurement_results` 중 매칭 항목을 랭킹해 반환."""
    return await run_search(
        session,
        tenant_id=tenant.id,
        monthly_quota=tenant.api_quota_monthly,
        query=q,
        limit=limit,
        force_refresh=force_refresh,
    )
