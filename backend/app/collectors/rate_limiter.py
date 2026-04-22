"""플랫폼별 분당 요청 한도 관리 (토큰 버킷)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    capacity: float
    tokens: float
    refill_rate_per_sec: float
    last_refill: float


class RateLimiter:
    """프로세스 로컬 토큰 버킷.

    - `capacity_per_min` 요청/분 기준으로 토큰을 충전한다.
    - `acquire()` 호출이 토큰이 부족하면 필요한 시간만큼 sleep 한 뒤 진행한다.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    def register(self, key: str, capacity_per_min: int) -> None:
        rate = max(capacity_per_min / 60.0, 1e-6)
        self._buckets[key] = _Bucket(
            capacity=float(capacity_per_min),
            tokens=float(capacity_per_min),
            refill_rate_per_sec=rate,
            last_refill=time.monotonic(),
        )

    async def acquire(self, key: str, amount: float = 1.0) -> None:
        bucket = self._buckets.get(key)
        if bucket is None:
            return
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - bucket.last_refill
                if elapsed > 0:
                    bucket.tokens = min(
                        bucket.capacity,
                        bucket.tokens + elapsed * bucket.refill_rate_per_sec,
                    )
                    bucket.last_refill = now
                if bucket.tokens >= amount:
                    bucket.tokens -= amount
                    return
                shortfall = amount - bucket.tokens
                wait_seconds = shortfall / bucket.refill_rate_per_sec
            await asyncio.sleep(max(wait_seconds, 0.01))


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
