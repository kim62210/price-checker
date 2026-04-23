"""멀티테넌시 피벗 초기 스키마.

Revision ID: 001_pivot_multi_tenant
Revises:
Create Date: 2026-04-23

친구용 단일 사용자 스키마를 폐기하고 B2B 조달 SaaS 용 멀티테넌시 스키마로
재초기화한다. 기존 마이그레이션은 전부 제거되고 본 리비전이 유일한 head 가
된다.

주요 변경 사항
- tenants, shops, users, refresh_tokens, procurement_orders,
  procurement_results 테이블 신규 생성
- listings 테이블에 tenant_id 외래키 컬럼 추가 (NOT NULL, CASCADE)
- 테넌트 격리 조회용 복합 인덱스 추가
    * ix_procurement_orders_tenant_created (tenant_id, created_at DESC)
    * ix_procurement_orders_tenant_id      (tenant_id, id)
    * ix_procurement_results_tenant_order  (tenant_id, order_id)
- 상태 컬럼(status, role, plan, auth_provider, source)은 DB 중립성을 위해
  VARCHAR + CHECK constraint 로 구현한다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001_pivot_multi_tenant"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # tenants
    # ------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "plan",
            sa.String(length=32),
            nullable=False,
            server_default="starter",
        ),
        sa.Column(
            "api_quota_monthly",
            sa.Integer(),
            nullable=False,
            server_default="10000",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_tenants_name"),
        sa.CheckConstraint(
            "plan IN ('starter', 'pro', 'enterprise')",
            name="ck_tenants_plan",
        ),
    )
    op.create_index("ix_tenants_plan", "tenants", ["plan"])

    # ------------------------------------------------------------------
    # shops
    # ------------------------------------------------------------------
    op.create_table(
        "shops",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("business_number", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_shops_tenant_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_shops_tenant_id", "shops", ["tenant_id"])
    op.create_index(
        "ix_shops_tenant_created",
        "shops",
        ["tenant_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("auth_provider", sa.String(length=32), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default="owner",
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_users_tenant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "auth_provider",
            "provider_user_id",
            name="uq_users_provider",
        ),
        sa.CheckConstraint(
            "auth_provider IN ('kakao', 'naver', 'local')",
            name="ck_users_auth_provider",
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'staff')",
            name="ck_users_role",
        ),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index(
        "ix_users_tenant_created",
        "users",
        ["tenant_id", "created_at"],
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ------------------------------------------------------------------
    # refresh_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "jti",
            UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_refresh_tokens_user_expires",
        "refresh_tokens",
        ["user_id", "expires_at"],
    )

    # ------------------------------------------------------------------
    # procurement_orders
    # ------------------------------------------------------------------
    op.create_table(
        "procurement_orders",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("shop_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column(
            "target_unit_price",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_procurement_orders_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name="fk_procurement_orders_shop_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'collecting', 'completed', 'cancelled')",
            name="ck_procurement_orders_status",
        ),
    )
    op.create_index(
        "ix_procurement_orders_tenant_created",
        "procurement_orders",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_procurement_orders_tenant_id",
        "procurement_orders",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_procurement_orders_shop_created",
        "procurement_orders",
        ["shop_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # procurement_results
    # ------------------------------------------------------------------
    op.create_table(
        "procurement_results",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("seller_name", sa.String(length=255), nullable=True),
        sa.Column(
            "listed_price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "per_unit_price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "shipping_fee",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("unit_count", sa.Integer(), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["procurement_orders.id"],
            name="fk_procurement_results_order_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_procurement_results_tenant_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "source IN ('naver', 'coupang', 'manual')",
            name="ck_procurement_results_source",
        ),
    )
    op.create_index(
        "ix_procurement_results_tenant_order",
        "procurement_results",
        ["tenant_id", "order_id"],
    )
    op.create_index(
        "ix_procurement_results_order_per_unit",
        "procurement_results",
        ["order_id", "per_unit_price"],
    )

    # ------------------------------------------------------------------
    # listings (기존 테이블: 기존 데이터 없음 가정, tenant_id NOT NULL 추가)
    # ------------------------------------------------------------------
    op.create_table(
        "listings",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("seller_id", sa.String(length=128), nullable=True),
        sa.Column(
            "platform_product_id", sa.String(length=128), nullable=False
        ),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("raw_title", sa.Text(), nullable=False),
        sa.Column("representative_price", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column(
            "raw_payload",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_listings_tenant_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_listings_platform", "listings", ["platform"])
    op.create_index("ix_listings_tenant_id", "listings", ["tenant_id"])
    op.create_index(
        "ix_listings_platform_product",
        "listings",
        ["platform", "platform_product_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # options
    # ------------------------------------------------------------------
    op.create_table(
        "options",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("platform_option_id", sa.String(length=128), nullable=True),
        sa.Column("option_name_text", sa.Text(), nullable=False),
        sa.Column(
            "attrs",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "parsed",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("usable", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name="fk_options_listing_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_options_listing_id", "options", ["listing_id"])
    op.create_index(
        "ix_options_platform_option_id",
        "options",
        ["platform_option_id"],
    )

    # ------------------------------------------------------------------
    # price_quotes (append-only)
    # ------------------------------------------------------------------
    op.create_table(
        "price_quotes",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            primary_key=True,
        ),
        sa.Column("option_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("discount_price", sa.Integer(), nullable=True),
        sa.Column("shipping_fee", sa.Integer(), nullable=False),
        sa.Column(
            "shipping_confidence", sa.String(length=16), nullable=False
        ),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column(
            "unit_quantity", sa.Numeric(precision=18, scale=4), nullable=True
        ),
        sa.Column(
            "unit_price", sa.Numeric(precision=18, scale=4), nullable=True
        ),
        sa.Column(
            "unit_base",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetch_method", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["options.id"],
            name="fk_price_quotes_option_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_price_quotes_option_captured",
        "price_quotes",
        ["option_id", "captured_at"],
    )

    # ------------------------------------------------------------------
    # option_text_cache (파서 결과 영구 캐시)
    # ------------------------------------------------------------------
    op.create_table(
        "option_text_cache",
        sa.Column(
            "text_hash", sa.String(length=64), nullable=False, primary_key=True
        ),
        sa.Column("raw_text", sa.String(length=4096), nullable=False),
        sa.Column(
            "parsed_json",
            JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("model_used", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("option_text_cache")

    op.drop_index("ix_price_quotes_option_captured", table_name="price_quotes")
    op.drop_table("price_quotes")

    op.drop_index("ix_options_platform_option_id", table_name="options")
    op.drop_index("ix_options_listing_id", table_name="options")
    op.drop_table("options")

    op.drop_index("ix_listings_platform_product", table_name="listings")
    op.drop_index("ix_listings_tenant_id", table_name="listings")
    op.drop_index("ix_listings_platform", table_name="listings")
    op.drop_table("listings")

    op.drop_index(
        "ix_procurement_results_order_per_unit",
        table_name="procurement_results",
    )
    op.drop_index(
        "ix_procurement_results_tenant_order",
        table_name="procurement_results",
    )
    op.drop_table("procurement_results")

    op.drop_index(
        "ix_procurement_orders_shop_created",
        table_name="procurement_orders",
    )
    op.drop_index(
        "ix_procurement_orders_tenant_id",
        table_name="procurement_orders",
    )
    op.drop_index(
        "ix_procurement_orders_tenant_created",
        table_name="procurement_orders",
    )
    op.drop_table("procurement_orders")

    op.drop_index(
        "ix_refresh_tokens_user_expires",
        table_name="refresh_tokens",
    )
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_tenant_created", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_shops_tenant_created", table_name="shops")
    op.drop_index("ix_shops_tenant_id", table_name="shops")
    op.drop_table("shops")

    op.drop_index("ix_tenants_plan", table_name="tenants")
    op.drop_table("tenants")
