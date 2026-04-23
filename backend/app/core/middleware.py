"""요청 미들웨어 (correlation_id + tenant_id 구조화 로그 주입).

- ``correlation_id``: 매 요청마다 ``X-Correlation-ID`` 헤더를 echo 하고 structlog
  contextvars 에 바인딩한다.
- ``tenant_id``: 인증 의존성(``app.tenancy.dependencies.get_current_user``) 이
  ``request.state.tenant_id`` 와 ``structlog.contextvars`` 에 직접 바인딩한다.
  이 미들웨어는 요청 처리 경계에서만 컨텍스트를 초기화·정리한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

CORRELATION_HEADER = "X-Correlation-ID"


def register_middleware(app: FastAPI) -> None:
    """FastAPI 앱에 구조화 로그 contextvars 주입 미들웨어를 등록."""

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cid = request.headers.get(CORRELATION_HEADER, uuid.uuid4().hex)
        clear_contextvars()
        bind_contextvars(
            correlation_id=cid,
            path=request.url.path,
            method=request.method,
        )
        try:
            response = await call_next(request)
        finally:
            clear_contextvars()
        response.headers[CORRELATION_HEADER] = cid
        return response
