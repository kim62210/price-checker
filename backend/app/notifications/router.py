"""notification API 라우터."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
