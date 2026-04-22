"""애플리케이션 공유 httpx 비동기 클라이언트."""

from __future__ import annotations

import httpx

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(connect=3.0, read=10.0, write=3.0, pool=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
            follow_redirects=True,
        )
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
