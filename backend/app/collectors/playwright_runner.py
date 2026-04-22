"""헤드리스 렌더 폴백 (Playwright, stealth 경량 패치)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import random_user_agent

logger = get_logger(__name__)

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().playwright_concurrency)
    return _semaphore


STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters)
);
"""


@asynccontextmanager
async def rendered_page(
    url: str,
    *,
    wait_selector: str | None = None,
    timeout_ms: int = 25_000,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """세마포어로 동시성을 제한하며 Playwright 페이지를 yield."""
    sem = _get_semaphore()
    async with sem:
        try:
            from playwright.async_api import async_playwright  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("playwright 가 설치되지 않았습니다.") from exc

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=random_user_agent(),
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                viewport={"width": 1366, "height": 900},
                extra_http_headers=extra_headers or {},
            )
            await context.add_init_script(STEALTH_INIT_SCRIPT)
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=timeout_ms)
                yield page
            finally:
                await context.close()
                await browser.close()
