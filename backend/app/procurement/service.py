"""procurement 도메인 서비스 계층.

모든 메서드는 ``tenant_id`` 를 필수 인자로 받아 row-level 격리를 강제한다.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.procurement.models import ProcurementOrder, ProcurementResult
from app.procurement.schemas import OrderCreate, ResultUpload, SummaryReport
from app.services.quota_service import check_and_consume

logger = get_logger(__name__)

KST = ZoneInfo("Asia/Seoul")
_ONE_DAY = timedelta(days=1)


class ShopNotFoundError(Exception):
    """요청된 ``shop_id`` 가 현재 테넌트 소속이 아닐 때."""


class OrderNotFoundError(Exception):
    """요청된 ``order_id`` 가 현재 테넌트 소속이 아닐 때."""


class ProcurementService:
    """발주·수집 결과 CRUD 및 집계."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ----- 발주 주문 -----
    async def create_order(
        self,
        *,
        tenant_id: int,
        monthly_quota: int,
        payload: OrderCreate,
    ) -> ProcurementOrder:
        """발주 생성.

        - ``payload.shop_id`` 가 현재 테넌트 소속인지 검증 후 생성한다.
        - 소속 검증 실패 시 :class:`ShopNotFoundError` 를 발생시킨다.
        - 월간 쿼터 초과 시 :class:`QuotaExceededError` 를 발생시킨다.
        """

        await check_and_consume(tenant_id, monthly_quota)
        await self._ensure_shop_belongs_to_tenant(
            tenant_id=tenant_id, shop_id=payload.shop_id
        )

        order = ProcurementOrder(
            tenant_id=tenant_id,
            shop_id=payload.shop_id,
            product_name=payload.product_name,
            option_text=payload.option_text,
            quantity=payload.quantity,
            unit=payload.unit,
            target_unit_price=payload.target_unit_price,
            memo=payload.memo,
            status=payload.status,
        )
        self._session.add(order)
        await self._session.flush()
        await self._session.refresh(order)
        logger.info(
            "procurement_order_created",
            tenant_id=tenant_id,
            order_id=order.id,
            shop_id=order.shop_id,
        )
        return order

    async def list_orders(
        self,
        *,
        tenant_id: int,
        status: str | None = None,
        shop_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ProcurementOrder]:
        """테넌트 소속 발주 목록 조회. 최신 정렬."""

        stmt = (
            select(ProcurementOrder)
            .where(ProcurementOrder.tenant_id == tenant_id)
            .order_by(ProcurementOrder.created_at.desc(), ProcurementOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(ProcurementOrder.status == status)
        if shop_id is not None:
            stmt = stmt.where(ProcurementOrder.shop_id == shop_id)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_order(
        self,
        *,
        tenant_id: int,
        order_id: int,
    ) -> ProcurementOrder | None:
        """발주 단건 조회. 크로스 테넌트면 ``None`` 반환."""

        stmt = select(ProcurementOrder).where(
            ProcurementOrder.id == order_id,
            ProcurementOrder.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ----- 발주 결과 -----
    async def upload_result(
        self,
        *,
        tenant_id: int,
        monthly_quota: int,
        order_id: int,
        payload: ResultUpload,
    ) -> ProcurementResult:
        """발주 결과 업로드.

        서버가 ``tenant_id`` 를 주문에서 복제하므로 클라이언트 body 값은 무시된다.
        월간 쿼터 초과 시 :class:`QuotaExceededError` 를 발생시킨다.
        """

        await check_and_consume(tenant_id, monthly_quota)
        order = await self.get_order(tenant_id=tenant_id, order_id=order_id)
        if order is None:
            raise OrderNotFoundError

        collected_at = payload.collected_at
        if collected_at is None:
            collected_at = datetime.now(tz=UTC)
        elif collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=UTC)

        record = ProcurementResult(
            order_id=order.id,
            tenant_id=order.tenant_id,  # order 로부터 복제 (스푸핑 차단)
            source=payload.source,
            product_url=payload.product_url,
            seller_name=payload.seller_name,
            listed_price=payload.listed_price,
            per_unit_price=payload.per_unit_price,
            shipping_fee=payload.shipping_fee,
            unit_count=payload.unit_count,
            collected_at=collected_at,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        logger.info(
            "procurement_result_uploaded",
            tenant_id=tenant_id,
            order_id=order.id,
            result_id=record.id,
            source=record.source,
        )
        return record

    async def list_results_by_order(
        self,
        *,
        tenant_id: int,
        order_id: int,
    ) -> list[ProcurementResult]:
        """해당 발주의 수집 결과 목록. ``per_unit_price`` 오름차순."""

        order = await self.get_order(tenant_id=tenant_id, order_id=order_id)
        if order is None:
            raise OrderNotFoundError

        stmt = (
            select(ProcurementResult)
            .where(
                ProcurementResult.order_id == order_id,
                ProcurementResult.tenant_id == tenant_id,
            )
            .order_by(
                ProcurementResult.per_unit_price.asc(),
                ProcurementResult.id.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ----- 집계 리포트 -----
    async def aggregate_savings(
        self,
        *,
        tenant_id: int,
        date_from: date | None,
        date_to: date | None,
    ) -> SummaryReport:
        """기간별 절감액 집계.

        절감액 공식: ``(target_unit_price - MIN(per_unit_price)) * quantity``.

        - ``target_unit_price`` 가 없거나, 결과가 없거나, best 단가가 target 이상이면 절감액 0.
        - 기간은 KST 기준으로 ``created_at`` 에 적용된다.
        """

        # 기간 범위를 UTC 경계로 변환 (KST 하루 기준)
        from_utc, to_utc = self._kst_range_to_utc(date_from, date_to)

        order_stmt = select(ProcurementOrder).where(
            ProcurementOrder.tenant_id == tenant_id
        )
        if from_utc is not None:
            order_stmt = order_stmt.where(ProcurementOrder.created_at >= from_utc)
        if to_utc is not None:
            order_stmt = order_stmt.where(ProcurementOrder.created_at < to_utc)

        orders = list((await self._session.execute(order_stmt)).scalars().all())

        orders_count = len(orders)
        completed_count = sum(1 for order in orders if order.status == "completed")
        results_count = 0
        total_savings = Decimal("0")

        for order in orders:
            best_stmt = select(func.min(ProcurementResult.per_unit_price)).where(
                ProcurementResult.tenant_id == tenant_id,
                ProcurementResult.order_id == order.id,
            )
            count_stmt = select(func.count(ProcurementResult.id)).where(
                ProcurementResult.tenant_id == tenant_id,
                ProcurementResult.order_id == order.id,
            )
            best_unit_price = (await self._session.execute(best_stmt)).scalar_one_or_none()
            count = (await self._session.execute(count_stmt)).scalar_one() or 0
            results_count += int(count)

            if order.target_unit_price is None or best_unit_price is None:
                continue
            diff = order.target_unit_price - best_unit_price
            if diff <= Decimal("0"):
                continue
            total_savings += diff * Decimal(order.quantity)

        return SummaryReport(
            date_from=date_from,
            date_to=date_to,
            orders_count=orders_count,
            completed_orders_count=completed_count,
            results_count=results_count,
            total_savings=total_savings,
        )

    # ----- 내부 헬퍼 -----
    async def _ensure_shop_belongs_to_tenant(
        self, *, tenant_id: int, shop_id: int
    ) -> None:
        from app.tenancy.models import Shop  # 런타임 지연 import

        stmt = select(Shop.id).where(Shop.id == shop_id, Shop.tenant_id == tenant_id)
        found = (await self._session.execute(stmt)).scalar_one_or_none()
        if found is None:
            raise ShopNotFoundError

    @staticmethod
    def _kst_range_to_utc(
        date_from: date | None, date_to: date | None
    ) -> tuple[datetime | None, datetime | None]:
        """KST 날짜 범위를 [from 00:00 KST, to+1 00:00 KST) UTC 로 변환."""

        from_utc: datetime | None = None
        to_utc: datetime | None = None
        if date_from is not None:
            from_utc = datetime.combine(date_from, time.min, tzinfo=KST).astimezone(
                UTC
            )
        if date_to is not None:
            # 종료일 포함이 되도록 +1일 00:00 KST 로 확장
            start_of_next = datetime.combine(date_to, time.min, tzinfo=KST) + _ONE_DAY
            to_utc = start_of_next.astimezone(UTC)
        return from_utc, to_utc
