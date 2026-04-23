"""procurement 도메인 SQLAlchemy 모델.

- ``ProcurementOrder`` : 테넌트·소매점 단위의 발주 주문
- ``ProcurementResult`` : 클라이언트(브라우저 확장/Tauri)가 업로드한 플랫폼 수집 결과

테넌트 격리를 위해 ``tenant_id`` 를 비정규화(중복 저장)하고 복합 인덱스를 둔다.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

_bigint = BigInteger().with_variant(Integer(), "sqlite")

if TYPE_CHECKING:  # 순환 import 방지용 타입 힌트
    from app.tenancy.models import Shop, Tenant


ORDER_STATUS_VALUES = ("draft", "collecting", "completed", "cancelled")
RESULT_SOURCE_VALUES = ("naver", "coupang", "manual")


class ProcurementOrder(Base, TimestampMixin):
    """소매점이 등록한 발주 주문.

    - ``target_unit_price`` 는 관리자가 설정한 단위 목표가. 절감액 집계에 사용.
    - ``status`` 는 ``draft`` → ``collecting`` → ``completed`` 흐름을 기본으로 한다.
    """

    __tablename__ = "procurement_orders"
    __table_args__ = (
        Index(
            "ix_procurement_orders_tenant_created",
            "tenant_id",
            "created_at",
        ),
        Index(
            "ix_procurement_orders_shop_created",
            "shop_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    shop_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    option_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    target_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="raise")
    shop: Mapped["Shop"] = relationship("Shop", lazy="raise")
    results: Mapped[list["ProcurementResult"]] = relationship(
        "ProcurementResult",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProcurementResult(Base):
    """발주에 대해 클라이언트가 업로드한 플랫폼별 수집 결과."""

    __tablename__ = "procurement_results"
    __table_args__ = (
        Index(
            "ix_procurement_results_tenant_order",
            "tenant_id",
            "order_id",
        ),
        Index(
            "ix_procurement_results_order_per_unit",
            "order_id",
            "per_unit_price",
        ),
    )

    id: Mapped[int] = mapped_column(_bigint, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("procurement_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(
        _bigint,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    listed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    per_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped["ProcurementOrder"] = relationship(
        "ProcurementOrder", back_populates="results"
    )
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="raise")
