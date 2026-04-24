"""v1 라우터 집계.

- ``/api/v1/auth/**`` 와 ``/api/v1/health/**`` 는 인증 없이 노출 (OAuth·생존 확인)
- 그 외 모든 라우트는 각 서브 라우터에서 ``Depends(get_current_tenant)`` 로
  테넌트 격리를 강제하거나 의존성 리스트에서 보장한다.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, search
from app.auth.router import router as auth_router
from app.notifications.router import router as notifications_router
from app.price_collection.router import router as price_collection_router
from app.procurement.router import router as procurement_router
from app.tenancy.router import router as tenancy_router

api_router = APIRouter()

# --- 공개 라우트 (인증 면제) ---
api_router.include_router(health.router)
api_router.include_router(auth_router, prefix="/api/v1")

# --- 인증 필요 라우트 ---
# 각 서브 라우터는 내부적으로 Depends(get_current_tenant) 또는 CurrentTenant/CurrentUser
# Annotated 타입을 통해 인증을 강제한다.
api_router.include_router(tenancy_router)
api_router.include_router(procurement_router)
api_router.include_router(price_collection_router)
api_router.include_router(notifications_router)
api_router.include_router(search.router)
