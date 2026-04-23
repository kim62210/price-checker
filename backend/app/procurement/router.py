"""procurement 라우터.

모든 엔드포인트는 ``Depends(get_current_tenant)`` 로 테넌트 격리를 강제한다.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.procurement.schemas import (
    OrderCreate,
    OrderRead,
    OrderStatus,
    ResultRead,
    ResultUpload,
    SummaryReport,
)
from app.procurement.service import (
    OrderNotFoundError,
    ProcurementService,
    ShopNotFoundError,
)
from app.tenancy.dependencies import get_current_tenant
from app.tenancy.models import Tenant

router = APIRouter(prefix="/api/v1/procurement", tags=["procurement"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]


def _service(session: AsyncSession) -> ProcurementService:
    return ProcurementService(session)


@router.post(
    "/orders",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="발주 주문 생성",
)
async def create_order(
    payload: OrderCreate,
    tenant: CurrentTenant,
    session: DbSession,
) -> OrderRead:
    service = _service(session)
    try:
        order = await service.create_order(
            tenant_id=tenant.id,
            monthly_quota=tenant.api_quota_monthly,
            payload=payload,
        )
    except ShopNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "shop_not_found", "code": "NOT_FOUND"},
        ) from exc
    await session.commit()
    await session.refresh(order)
    return OrderRead.model_validate(order)


@router.get(
    "/orders",
    response_model=list[OrderRead],
    summary="발주 주문 목록",
)
async def list_orders(
    tenant: CurrentTenant,
    session: DbSession,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    shop_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrderRead]:
    service = _service(session)
    orders = await service.list_orders(
        tenant_id=tenant.id,
        status=status_filter,
        shop_id=shop_id,
        limit=limit,
        offset=offset,
    )
    return [OrderRead.model_validate(order) for order in orders]


@router.get(
    "/orders/{order_id}",
    response_model=OrderRead,
    summary="발주 주문 단건 조회",
)
async def get_order_detail(
    order_id: int,
    tenant: CurrentTenant,
    session: DbSession,
) -> OrderRead:
    service = _service(session)
    order = await service.get_order(tenant_id=tenant.id, order_id=order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "order_not_found", "code": "NOT_FOUND"},
        )
    return OrderRead.model_validate(order)


@router.post(
    "/orders/{order_id}/results",
    response_model=ResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="발주 결과 업로드",
)
async def upload_order_result(
    order_id: int,
    payload: ResultUpload,
    tenant: CurrentTenant,
    session: DbSession,
) -> ResultRead:
    service = _service(session)
    try:
        record = await service.upload_result(
            tenant_id=tenant.id,
            monthly_quota=tenant.api_quota_monthly,
            order_id=order_id,
            payload=payload,
        )
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "order_not_found", "code": "NOT_FOUND"},
        ) from exc
    await session.commit()
    await session.refresh(record)
    return ResultRead.model_validate(record)


@router.get(
    "/orders/{order_id}/results",
    response_model=list[ResultRead],
    summary="발주 결과 목록 (per_unit_price 오름차순)",
)
async def list_order_results(
    order_id: int,
    tenant: CurrentTenant,
    session: DbSession,
) -> list[ResultRead]:
    service = _service(session)
    try:
        records = await service.list_results_by_order(
            tenant_id=tenant.id, order_id=order_id
        )
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "order_not_found", "code": "NOT_FOUND"},
        ) from exc
    return [ResultRead.model_validate(record) for record in records]


@router.get(
    "/reports/summary",
    response_model=SummaryReport,
    summary="기간별 절감액 집계 리포트",
)
async def get_summary_report(
    tenant: CurrentTenant,
    session: DbSession,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> SummaryReport:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "invalid_date_range", "code": "INVALID_REQUEST"},
        )
    service = _service(session)
    return await service.aggregate_savings(
        tenant_id=tenant.id,
        date_from=date_from,
        date_to=date_to,
    )
