"""테넌트·소매점·사용자 SQLAlchemy 2.x 모델.

스키마 정의는 `openspec/changes/pivot-backend-multi-tenant/design.md` 의 DDL 을 따른다.
- tenants: 소매점 운영 주체 (플랜·쿼터 보유)
- shops: 테넌트가 운영하는 개별 매장 (N:1 tenants)
- users: 테넌트에 소속된 사용자 (N:1 tenants, OAuth 프로바이더 정보 포함)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeEngine

from app.models.base import Base, TimestampMixin


def _bigint() -> TypeEngine[Any]:
    """SQLite 호환 BigInteger — 테스트(SQLite)에서는 Integer 로 동작."""
    return BigInteger().with_variant(Integer(), "sqlite")


class Tenant(Base, TimestampMixin):
    """테넌트 — 소매점을 운영하는 법인/개인."""

    __tablename__ = "tenants"
    __table_args__ = (Index("ix_tenants_plan", "plan"),)

    id: Mapped[int] = mapped_column(_bigint(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(
        String(32), nullable=False, default="starter", server_default="starter"
    )
    api_quota_monthly: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10000, server_default="10000"
    )

    shops: Mapped[list[Shop]] = relationship(
        "Shop", back_populates="tenant", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(
        "User", back_populates="tenant", cascade="all, delete-orphan"
    )


class Shop(Base, TimestampMixin):
    """소매점 — 하나의 테넌트가 여러 매장을 운영할 수 있다."""

    __tablename__ = "shops"
    __table_args__ = (Index("ix_shops_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(_bigint(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="shops")


class User(Base, TimestampMixin):
    """사용자 — 특정 테넌트에 소속되며 OAuth 프로바이더로 식별된다."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("auth_provider", "provider_user_id", name="uq_users_provider"),
        Index("ix_users_tenant_created", "tenant_id", "created_at"),
        Index("ix_users_email", "email"),
    )

    id: Mapped[int] = mapped_column(_bigint(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        _bigint(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="owner", server_default="owner"
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users")
