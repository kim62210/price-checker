"""Listing / Option / PriceQuote 모델."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # 순환 import 방지용 타입 힌트
    from app.tenancy.models import Tenant


class Listing(Base, TimestampMixin):
    __tablename__ = "listings"
    __table_args__ = (
        Index("ix_listings_platform_product", "platform", "platform_product_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    seller_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_title: Mapped[str] = mapped_column(Text, nullable=False)
    representative_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="raise")
    options: Mapped[list["Option"]] = relationship(
        "Option", back_populates="listing", cascade="all, delete-orphan"
    )


class Option(Base, TimestampMixin):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform_option_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    option_name_text: Mapped[str] = mapped_column(Text, nullable=False)
    attrs: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )
    parsed: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    listing: Mapped["Listing"] = relationship("Listing", back_populates="options")
    quotes: Mapped[list["PriceQuote"]] = relationship(
        "PriceQuote", back_populates="option", cascade="all, delete-orphan"
    )


class PriceQuote(Base):
    """Append-only 시계열 가격 스냅샷."""

    __tablename__ = "price_quotes"
    __table_args__ = (Index("ix_price_quotes_option_captured", "option_id", "captured_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    option_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("options.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipping_confidence: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown"
    )
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_base: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetch_method: Mapped[str] = mapped_column(String(16), nullable=False, default="api")

    option: Mapped["Option"] = relationship("Option", back_populates="quotes")
