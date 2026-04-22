"""Rate limiter 기본 동작 테스트."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.collectors.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_acquires_within_capacity():
    limiter = RateLimiter()
    limiter.register("x", capacity_per_min=120)  # 2 RPS
    started = time.monotonic()
    await asyncio.gather(limiter.acquire("x"), limiter.acquire("x"))
    elapsed = time.monotonic() - started
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_rate_limiter_waits_when_exceeded():
    limiter = RateLimiter()
    limiter.register("y", capacity_per_min=60)  # 1 RPS
    # 2개 바로 소진 후 3번째는 ~1초 대기 필요
    for _ in range(60):
        await limiter.acquire("y")
    start = time.monotonic()
    await limiter.acquire("y")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.5


@pytest.mark.asyncio
async def test_rate_limiter_unregistered_key_noop():
    limiter = RateLimiter()
    # 등록되지 않은 키는 대기 없이 반환되어야 한다.
    start = time.monotonic()
    await limiter.acquire("none")
    assert time.monotonic() - start < 0.05
