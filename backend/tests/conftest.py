"""공통 pytest 픽스처."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("NAVER_CLIENT_ID", "test-client-id")
os.environ.setdefault("NAVER_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENVIRONMENT", "local")


@pytest.fixture
def settings():
    from app.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()
