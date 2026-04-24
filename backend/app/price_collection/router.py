"""최저가 수집 라우터."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.price_collection.schemas import PriceCollectionJobCreate, PriceCollectionJobRead
from app.price_collection.service import PriceCollectionOrderNotFoundError, PriceCollectionService
from app.tenancy.dependencies import get_current_tenant
from app.tenancy.models import Tenant

router = APIRouter(prefix="/api/v1/procurement", tags=["procurement-collection"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]


@router.post(
    "/orders/{order_id}/collect",
    response_model=PriceCollectionJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="최저가 수집 job 생성",
)
async def create_collection_job(
    order_id: int,
    response: Response,
    tenant: CurrentTenant,
    session: DbSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PriceCollectionJobRead:
    if not idempotency_key:
        idempotency_key = f"collection:{tenant.id}:{order_id}:naver:manual"
    service = PriceCollectionService(session)
    try:
        job, created = await service.create_job(
            tenant_id=tenant.id,
            order_id=order_id,
            payload=PriceCollectionJobCreate(idempotency_key=idempotency_key),
        )
    except PriceCollectionOrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "order_not_found", "code": "NOT_FOUND"},
        ) from exc
    await session.commit()
    await session.refresh(job)
    if not created:
        response.status_code = status.HTTP_200_OK
    return PriceCollectionJobRead.model_validate(job)


@router.get(
    "/orders/{order_id}/collect/jobs",
    response_model=list[PriceCollectionJobRead],
    summary="최저가 수집 job 목록",
)
async def list_collection_jobs(
    order_id: int,
    tenant: CurrentTenant,
    session: DbSession,
) -> list[PriceCollectionJobRead]:
    service = PriceCollectionService(session)
    try:
        jobs = await service.list_jobs(tenant_id=tenant.id, order_id=order_id)
    except PriceCollectionOrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "order_not_found", "code": "NOT_FOUND"},
        ) from exc
    return [PriceCollectionJobRead.model_validate(job) for job in jobs]
