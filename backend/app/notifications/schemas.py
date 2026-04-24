"""notification 도메인 Pydantic 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NotificationRecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    phone_e164: str
    display_name: str
    is_active: bool
