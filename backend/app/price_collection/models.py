"""최저가 수집 job/attempt 모델."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.procurement.models import ProcurementOrder, ProcurementResult
    from app.tenancy.models import Tenant

_bigint = BigInteger().with_variant(Integer(), "sqlite")

PRICE_COLLECTION_SOURCE_VALUES = ("naver", "coupang")
PRICE_COLLECTION_JOB_STATUS_VALUES = (
    "pending",
    "running",
    "succeeded",
    "partial_failed",
    "failed",
)
PRICE_COLLECTION_ATTEMPT_STATUS_VALUES = ("success", "retryable_failure", "permanent_failure")


class PriceCollectionJob(Base, TimestampMixin):
    """주문별 최저가 수집 실행 단위."""

    __tablename__ = "price_collection_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_price_collection_jobs_idempotency"),
        CheckConstraint(
            f"source IN {PRICE_COLLECTION_SOURCE_VALUES}",
            name="ck_price_collection_jobs_source",
        ),
        CheckConstraint(
            f"status IN {PRICE_COLLECTION_JOB_STATUS_VALUES}",
            name="ck_price_collection_jobs_status",
        ),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("procurement_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="naver", server_default="naver")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")
    order: Mapped[ProcurementOrder] = relationship("ProcurementOrder", lazy="raise")
    attempts_rel: Mapped[list[PriceCollectionAttempt]] = relationship(
        "PriceCollectionAttempt",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    results: Mapped[list[ProcurementResult]] = relationship(
        "ProcurementResult",
        back_populates="collection_job",
        lazy="selectin",
    )


class PriceCollectionAttempt(Base):
    """수집 실행 시도 로그."""

    __tablename__ = "price_collection_attempts"
    __table_args__ = (
        CheckConstraint(
            f"status IN {PRICE_COLLECTION_ATTEMPT_STATUS_VALUES}",
            name="ck_price_collection_attempts_status",
        ),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("price_collection_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped[Tenant] = relationship("Tenant", lazy="raise")
    job: Mapped[PriceCollectionJob] = relationship("PriceCollectionJob", back_populates="attempts_rel")
