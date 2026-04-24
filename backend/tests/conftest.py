"""공통 pytest 픽스처."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-tests-only-32-bytes")
os.environ.setdefault("KAKAO_CLIENT_ID", "test-kakao-id")
os.environ.setdefault("KAKAO_CLIENT_SECRET", "test-kakao-secret")
os.environ.setdefault("NAVER_OAUTH_CLIENT_ID", "test-naver-id")
os.environ.setdefault("NAVER_OAUTH_CLIENT_SECRET", "test-naver-secret")


# ----- 설정 픽스처 -----


@pytest.fixture
def settings():
    from app.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()


# ----- DB 엔진 / 세션 픽스처 -----


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine():
    """SQLite in-memory 비동기 엔진 — 각 테스트마다 새 스키마."""
    import app.auth.models  # noqa: F401, PLC0415
    import app.notifications.models  # noqa: F401, PLC0415
    import app.procurement.models  # noqa: F401, PLC0415

    # 필요한 모델을 임포트해서 Base.metadata 에 등록
    import app.tenancy.models  # noqa: F401, PLC0415
    from app.models.base import Base  # noqa: PLC0415

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """트랜잭션 롤백 방식 격리 세션."""
    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )
    async with factory() as session:
        yield session
        await session.rollback()


# ----- fakeredis 픽스처 -----


@pytest.fixture
async def fake_redis():
    """fakeredis 인메모리 Redis 클라이언트."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


# ----- 테넌트·유저 팩토리 픽스처 -----


@pytest.fixture
async def test_tenant_a(db_session: AsyncSession):
    """테넌트 A."""
    from app.tenancy.models import Tenant  # noqa: PLC0415

    tenant = Tenant(name="tenant-alpha", plan="starter", api_quota_monthly=10000)
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def test_tenant_b(db_session: AsyncSession):
    """테넌트 B."""
    from app.tenancy.models import Tenant  # noqa: PLC0415

    tenant = Tenant(name="tenant-beta", plan="starter", api_quota_monthly=10000)
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def test_user_a(db_session: AsyncSession, test_tenant_a):
    """테넌트 A 소속 유저."""
    from app.tenancy.models import User  # noqa: PLC0415

    user = User(
        tenant_id=test_tenant_a.id,
        email="user-a@example.com",
        auth_provider="kakao",
        provider_user_id="kakao-111",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_b(db_session: AsyncSession, test_tenant_b):
    """테넌트 B 소속 유저."""
    from app.tenancy.models import User  # noqa: PLC0415

    user = User(
        tenant_id=test_tenant_b.id,
        email="user-b@example.com",
        auth_provider="naver",
        provider_user_id="naver-222",
        role="owner",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


# ----- JWT 토큰 픽스처 -----


@pytest.fixture
def access_token_a(test_user_a, settings):
    from app.auth.jwt import encode_access_token  # noqa: PLC0415

    token, _, _ = encode_access_token(
        user_id=test_user_a.id,
        tenant_id=test_user_a.tenant_id,
        settings=settings,
    )
    return token


@pytest.fixture
def access_token_b(test_user_b, settings):
    from app.auth.jwt import encode_access_token  # noqa: PLC0415

    token, _, _ = encode_access_token(
        user_id=test_user_b.id,
        tenant_id=test_user_b.tenant_id,
        settings=settings,
    )
    return token


@pytest.fixture
def auth_headers_a(access_token_a) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token_a}"}


@pytest.fixture
def auth_headers_b(access_token_b) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token_b}"}


# ----- HTTP 클라이언트 픽스처 -----


@pytest.fixture
async def client(db_session: AsyncSession, fake_redis) -> AsyncIterator[AsyncClient]:
    """FastAPI ASGI 클라이언트 — db_session / fake_redis 주입."""
    from app.db.redis import get_redis  # noqa: PLC0415
    from app.db.session import get_db  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = lambda: fake_redis

    # quota_service / cache_service 등이 get_redis() 싱글턴을 직접 호출하므로
    # 모듈 수준 _redis 싱글턴도 fake_redis 로 교체
    import app.db.redis as _redis_module  # noqa: PLC0415

    original_redis = _redis_module._redis
    _redis_module._redis = fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    _redis_module._redis = original_redis
