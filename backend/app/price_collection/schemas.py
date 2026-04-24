"""최저가 수집 DTO."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PriceCollectionJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(..., min_length=1, max_length=255)


class PriceCollectionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    order_id: int
    source: str
    status: str
    attempts: int
    next_retry_at: datetime | None
    idempotency_key: str
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
