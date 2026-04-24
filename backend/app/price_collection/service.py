"""최저가 수집 job 서비스."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.notifications.service import NotificationDeliveryService
from app.price_collection.exceptions import (
    CollectionConfigError,
    NaverClientRateLimitError,
    NaverClientTimeoutError,
)
from app.price_collection.models import PriceCollectionAttempt, PriceCollectionJob
from app.price_collection.normalization import CanonicalCollectedResult, normalize_naver_item
from app.price_collection.schemas import PriceCollectionJobCreate
from app.procurement.models import ProcurementOrder, ProcurementResult


class PriceCollectionOrderNotFoundError(Exception):
    """현재 테넌트에서 접근할 수 없는 order."""


class NaverSearchClientProtocol(Protocol):
    async def search(self, *, query: str) -> list[object]: ...


class PriceCollectionService:
    """최저가 수집 job 생성/조회."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        tenant_id: int,
        order_id: int,
        payload: PriceCollectionJobCreate,
    ) -> tuple[PriceCollectionJob, bool]:
        order = await self._get_order(tenant_id=tenant_id, order_id=order_id)
        if order is None:
            raise PriceCollectionOrderNotFoundError

        existing = await self._get_job_by_idempotency(payload.idempotency_key)
        if existing is not None:
            return existing, False

        job = PriceCollectionJob(
            tenant_id=tenant_id,
            order_id=order_id,
            source="naver",
            status="pending",
            attempts=0,
            idempotency_key=payload.idempotency_key,
        )
        self._session.add(job)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            recovered = await self._get_job_by_idempotency(payload.idempotency_key)
            if recovered is None:
                raise
            return recovered, False
        await self._session.refresh(job)
        return job, True

    async def list_jobs(self, *, tenant_id: int, order_id: int) -> list[PriceCollectionJob]:
        order = await self._get_order(tenant_id=tenant_id, order_id=order_id)
        if order is None:
            raise PriceCollectionOrderNotFoundError
        result = await self._session.execute(
            select(PriceCollectionJob)
            .where(
                PriceCollectionJob.tenant_id == tenant_id,
                PriceCollectionJob.order_id == order_id,
            )
            .order_by(PriceCollectionJob.id.desc())
        )
        return list(result.scalars().all())

    async def record_attempt(
        self,
        *,
        job_id: int,
        tenant_id: int,
        source: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PriceCollectionAttempt:
        attempt = PriceCollectionAttempt(
            tenant_id=tenant_id,
            job_id=job_id,
            source=source,
            status=status,
            error_code=error_code,
            error_message=error_message,
            attempted_at=datetime.now(tz=UTC),
        )
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt)
        return attempt

    async def run_job(
        self,
        *,
        job_id: int,
        tenant_id: int,
        client: NaverSearchClientProtocol,
        parser_version: int,
    ) -> PriceCollectionJob:
        job = await self._get_job(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise PriceCollectionOrderNotFoundError
        order = await self._get_order(tenant_id=tenant_id, order_id=job.order_id)
        if order is None:
            raise PriceCollectionOrderNotFoundError

        job.status = "running"
        job.last_error_code = None
        job.last_error_message = None
        job.next_retry_at = None
        await self._session.flush()

        try:
            items = await client.search(query=self._build_query(order))
        except (NaverClientTimeoutError, NaverClientRateLimitError) as exc:
            job.attempts += 1
            job.status = "pending"
            job.last_error_code = str(exc)
            job.last_error_message = str(exc)
            job.next_retry_at = datetime.now(tz=UTC) + timedelta(
                seconds=get_settings().price_collection_retry_base_seconds
            )
            await self.record_attempt(
                job_id=job.id,
                tenant_id=tenant_id,
                source=job.source,
                status="retryable_failure",
                error_code=str(exc),
                error_message=str(exc),
            )
            await self._session.flush()
            return job

        await self._replace_canonical_results(
            tenant_id=tenant_id,
            order=order,
            job=job,
            normalized_results=[
                normalize_naver_item(order=order, item=item, parser_version=parser_version)
                for item in items
            ],
        )
        job.status = "succeeded" if await self._has_eligible_results(job.id) else "partial_failed"
        job.attempts += 1
        await self.record_attempt(
            job_id=job.id,
            tenant_id=tenant_id,
            source=job.source,
            status="success",
        )
        await self._emit_best_result_notification_if_needed(tenant_id=tenant_id, order=order, job_id=job.id)
        await self._session.flush()
        return job

    async def _get_order(self, *, tenant_id: int, order_id: int) -> ProcurementOrder | None:
        result = await self._session.execute(
            select(ProcurementOrder).where(
                ProcurementOrder.tenant_id == tenant_id,
                ProcurementOrder.id == order_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_job_by_idempotency(self, idempotency_key: str) -> PriceCollectionJob | None:
        result = await self._session.execute(
            select(PriceCollectionJob).where(PriceCollectionJob.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def _get_job(self, *, tenant_id: int, job_id: int) -> PriceCollectionJob | None:
        result = await self._session.execute(
            select(PriceCollectionJob).where(
                PriceCollectionJob.tenant_id == tenant_id,
                PriceCollectionJob.id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def _replace_canonical_results(
        self,
        *,
        tenant_id: int,
        order: ProcurementOrder,
        job: PriceCollectionJob,
        normalized_results: list[CanonicalCollectedResult],
    ) -> None:
        existing = list(
            (
                await self._session.execute(
                    select(ProcurementResult).where(
                        ProcurementResult.tenant_id == tenant_id,
                        ProcurementResult.order_id == order.id,
                        ProcurementResult.source == job.source,
                        ProcurementResult.source_method == "naver_openapi",
                    )
                )
            ).scalars()
        )
        for row in existing:
            await self._session.delete(row)
        await self._session.flush()

        for normalized in normalized_results:
            self._session.add(
                ProcurementResult(
                    order_id=order.id,
                    tenant_id=tenant_id,
                    source=normalized.source,
                    product_url=normalized.product_url,
                    seller_name=normalized.seller_name,
                    listed_price=normalized.listed_price,
                    per_unit_price=normalized.per_unit_price or Decimal("0.00"),
                    shipping_fee=normalized.shipping_fee,
                    unit_count=normalized.unit_count,
                    job_id=job.id,
                    source_method=normalized.source_method,
                    external_offer_id=normalized.external_offer_id,
                    compare_eligible=normalized.compare_eligible,
                    parser_version=normalized.parser_version,
                    raw_excerpt=normalized.raw_excerpt,
                )
            )
        await self._session.flush()

    async def _has_eligible_results(self, job_id: int) -> bool:
        result = await self._session.execute(
            select(ProcurementResult.id).where(
                ProcurementResult.job_id == job_id,
                ProcurementResult.compare_eligible.is_(True),
            )
        )
        return result.scalars().first() is not None

    async def _emit_best_result_notification_if_needed(
        self,
        *,
        tenant_id: int,
        order: ProcurementOrder,
        job_id: int,
    ) -> None:
        if order.status != "completed":
            return
        result = (
            await self._session.execute(
                select(ProcurementResult)
                .where(
                    ProcurementResult.job_id == job_id,
                    ProcurementResult.compare_eligible.is_(True),
                )
                .order_by(ProcurementResult.per_unit_price.asc(), ProcurementResult.id.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if result is None:
            return
        await NotificationDeliveryService(self._session).create_procurement_result_event(
            tenant_id=tenant_id,
            order_id=order.id,
            result_id=result.id,
            shop_id=order.shop_id,
            product_name=order.product_name,
            best_price=result.per_unit_price,
        )

    @staticmethod
    def _build_query(order: ProcurementOrder) -> str:
        if order.option_text:
            return f"{order.product_name} {order.option_text}".strip()
        return order.product_name.strip()


__all__ = [
    "CollectionConfigError",
    "PriceCollectionOrderNotFoundError",
    "PriceCollectionService",
]
