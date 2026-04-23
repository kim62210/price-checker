"""테넌트별 월간 API 호출 쿼터 관리.

- Redis 키: ``quota:tenant:{tenant_id}:{YYYYMM}`` (KST 기준 연월)
- 처음 생성된 카운터는 ``EXPIREAT <다음달 1일 00:00 KST>`` 로 자동 만료
- ``check_and_consume`` 호출이 월간 한도를 초과하면 :class:`QuotaExceededError` 발생

설계 참고: ``openspec/changes/pivot-backend-multi-tenant/design.md`` §5.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from app.core.exceptions import QuotaExceededError
from app.core.logging import get_logger
from app.db.redis import get_redis

logger = get_logger(__name__)

KST = timezone(timedelta(hours=9))


def _current_year_month_kst(now: datetime | None = None) -> str:
    """KST 기준 현재 연월 문자열 (``YYYYMM``)."""
    return (now or datetime.now(KST)).astimezone(KST).strftime("%Y%m")


def _next_month_first_kst_epoch(now: datetime | None = None) -> int:
    """KST 기준 다음달 1일 00:00 의 Unix timestamp."""
    current = (now or datetime.now(KST)).astimezone(KST)
    if current.month == 12:
        nxt_year = current.year + 1
        nxt_month = 1
    else:
        nxt_year = current.year
        nxt_month = current.month + 1
    expiry = datetime(nxt_year, nxt_month, 1, 0, 0, 0, tzinfo=KST)
    return int(expiry.timestamp())


def tenant_quota_key(tenant_id: int, year_month: str | None = None) -> str:
    """테넌트 월간 쿼터 Redis 키."""
    return f"quota:tenant:{tenant_id}:{year_month or _current_year_month_kst()}"


async def check_and_consume(
    tenant_id: int,
    monthly_quota: int,
    *,
    amount: int = 1,
    redis: Redis | None = None,
) -> int:
    """현재 테넌트의 월간 쿼터를 ``amount`` 만큼 소모하고 누적값을 반환.

    초과 시 :class:`QuotaExceededError` 를 발생시키며, 카운터는 롤백하지 않는다
    (중복 호출 방지의 단순화 전략 — spec 명시).
    """
    if monthly_quota < 0:
        raise ValueError("monthly_quota must be >= 0")
    if amount < 1:
        raise ValueError("amount must be >= 1")

    client = redis or get_redis()
    key = tenant_quota_key(tenant_id)
    current = int(await client.incrby(key, amount))
    if current == amount:
        await client.expireat(key, _next_month_first_kst_epoch())

    if current > monthly_quota:
        logger.warning(
            "tenant_quota_exceeded",
            tenant_id=tenant_id,
            current=current,
            monthly_quota=monthly_quota,
        )
        raise QuotaExceededError(
            detail=(
                f"tenant_quota_exceeded tenant_id={tenant_id} "
                f"current={current} quota={monthly_quota}"
            ),
            code="QUOTA_EXCEEDED",
        )
    return current


async def get_current_usage(
    tenant_id: int,
    *,
    redis: Redis | None = None,
) -> int:
    """현재 월 누적 사용량을 조회 (카운터 없으면 0)."""
    client = redis or get_redis()
    value = await client.get(tenant_quota_key(tenant_id))
    return int(value) if value else 0


async def remaining_quota(
    tenant_id: int,
    monthly_quota: int,
    *,
    redis: Redis | None = None,
) -> int:
    """남은 월간 쿼터. 음수면 0 으로 클램프."""
    current = await get_current_usage(tenant_id, redis=redis)
    return max(monthly_quota - current, 0)


__all__ = [
    "KST",
    "QuotaExceededError",
    "check_and_consume",
    "get_current_usage",
    "remaining_quota",
    "tenant_quota_key",
]
