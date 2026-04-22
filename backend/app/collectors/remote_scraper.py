"""Mac mini CDP 스크레이퍼 HTTP 클라이언트.

OCI backend 는 Akamai 때문에 쿠팡에 직접 접속할 수 없다.
대신 Tailnet 의 개인 Chrome + CDP 기반 Mac mini 스크레이퍼에 위임한다.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import BotBlockedError, UpstreamError, UpstreamTimeoutError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.coupang_scraper_url,
        timeout=httpx.Timeout(
            connect=5.0,
            read=settings.coupang_scraper_timeout_seconds,
            write=5.0,
            pool=5.0,
        ),
    )


async def remote_coupang_search(
    query: str,
    limit: int,
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """원격 스크레이퍼에 /coupang/search 호출.

    반환 형식: scraper 가 돌려주는 `items` 리스트 (platform_product_id, raw_title, ...).
    """
    cfg = settings or get_settings()
    async with _build_client(cfg) as client:
        try:
            resp = await client.get(
                "/coupang/search",
                params={"q": query, "limit": limit},
            )
        except httpx.TimeoutException as exc:
            logger.warning("remote_scraper_timeout endpoint=search q=%s", query)
            raise UpstreamTimeoutError(detail="coupang_scraper_timeout") from exc
        except httpx.HTTPError as exc:
            logger.warning("remote_scraper_error endpoint=search err=%s", exc)
            raise UpstreamError(detail=f"coupang_scraper_error:{exc}") from exc

    _raise_for_scraper_status(resp, context="search")
    data = resp.json()
    items = data.get("items")
    if not isinstance(items, list):
        raise UpstreamError(detail="coupang_scraper_bad_response")
    return items


async def remote_coupang_detail(
    url: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """원격 스크레이퍼에 /coupang/detail 호출.

    반환 형식: scraper DetailResponse (options, shipping_fee, shipping_confidence, ...).
    """
    cfg = settings or get_settings()
    async with _build_client(cfg) as client:
        try:
            resp = await client.post("/coupang/detail", json={"url": url})
        except httpx.TimeoutException as exc:
            logger.warning("remote_scraper_timeout endpoint=detail url=%s", url)
            raise UpstreamTimeoutError(detail="coupang_scraper_timeout") from exc
        except httpx.HTTPError as exc:
            logger.warning("remote_scraper_error endpoint=detail err=%s", exc)
            raise UpstreamError(detail=f"coupang_scraper_error:{exc}") from exc

    _raise_for_scraper_status(resp, context="detail")
    return resp.json()


def _raise_for_scraper_status(resp: httpx.Response, *, context: str) -> None:
    """scraper 응답 상태 코드를 서비스 예외로 승격."""
    if resp.status_code < 400:
        return

    detail: str = resp.text[:200]
    try:
        body = resp.json()
        detail = str(body.get("detail", detail))
    except Exception:  # noqa: BLE001
        pass

    if resp.status_code == 502 and "coupang_block_page" in detail:
        logger.warning("scraper_reported_bot_block context=%s", context)
        raise BotBlockedError(detail="coupang_block_page")
    if resp.status_code == 504 or "timeout" in detail.lower():
        raise UpstreamTimeoutError(detail=f"coupang_scraper_timeout:{context}")
    raise UpstreamError(detail=f"coupang_scraper_{context}_http_{resp.status_code}:{detail}")
