"""검색 엔드포인트."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.schemas.search import SearchResponse
from app.services.search_service import run_search

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="네이버/쿠팡 최저가 검색",
)
async def search_endpoint(
    q: Annotated[str, Query(min_length=1, max_length=120, description="검색어")],
    limit: Annotated[int, Query(ge=1, le=60)] = 20,
    force_refresh: Annotated[bool, Query(description="캐시 무시 후 재수집")] = False,
) -> SearchResponse:
    return await run_search(q, limit, force_refresh=force_refresh)
