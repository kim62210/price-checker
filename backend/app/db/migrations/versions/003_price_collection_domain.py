"""price collection 도메인 추가.

Revision ID: 003_price_collection_domain
Revises: 002_notification_domain
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003_price_collection_domain"
down_revision: str | None = "002_notification_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine[object]:
    return JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "price_collection_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="naver"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_price_collection_jobs_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["procurement_orders.id"], name="fk_price_collection_jobs_order_id", ondelete="CASCADE"),
        sa.UniqueConstraint("idempotency_key", name="uq_price_collection_jobs_idempotency"),
        sa.CheckConstraint("source IN ('naver', 'coupang')", name="ck_price_collection_jobs_source"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'partial_failed', 'failed')",
            name="ck_price_collection_jobs_status",
        ),
    )
    op.create_index("ix_price_collection_jobs_tenant_id", "price_collection_jobs", ["tenant_id"])
    op.create_index("ix_price_collection_jobs_order_id", "price_collection_jobs", ["order_id"])

    op.create_table(
        "price_collection_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, primary_key=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_price_collection_attempts_tenant_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["price_collection_jobs.id"], name="fk_price_collection_attempts_job_id", ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('success', 'retryable_failure', 'permanent_failure')",
            name="ck_price_collection_attempts_status",
        ),
    )
    op.create_index("ix_price_collection_attempts_tenant_id", "price_collection_attempts", ["tenant_id"])
    op.create_index("ix_price_collection_attempts_job_id", "price_collection_attempts", ["job_id"])

    with op.batch_alter_table("procurement_results") as batch_op:
        batch_op.add_column(sa.Column("job_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("source_method", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("external_offer_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("compare_eligible", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("parser_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("raw_excerpt", _json_type(), nullable=True))
        batch_op.create_foreign_key(
            "fk_procurement_results_job_id",
            "price_collection_jobs",
            ["job_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("procurement_results") as batch_op:
        batch_op.drop_constraint("fk_procurement_results_job_id", type_="foreignkey")
        batch_op.drop_column("raw_excerpt")
        batch_op.drop_column("parser_version")
        batch_op.drop_column("compare_eligible")
        batch_op.drop_column("external_offer_id")
        batch_op.drop_column("source_method")
        batch_op.drop_column("job_id")

    op.drop_index("ix_price_collection_attempts_job_id", table_name="price_collection_attempts")
    op.drop_index("ix_price_collection_attempts_tenant_id", table_name="price_collection_attempts")
    op.drop_table("price_collection_attempts")

    op.drop_index("ix_price_collection_jobs_order_id", table_name="price_collection_jobs")
    op.drop_index("ix_price_collection_jobs_tenant_id", table_name="price_collection_jobs")
    op.drop_table("price_collection_jobs")
