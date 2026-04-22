"""요청 미들웨어 (correlation_id)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

CORRELATION_HEADER = "X-Correlation-ID"


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cid = request.headers.get(CORRELATION_HEADER, uuid.uuid4().hex)
        clear_contextvars()
        bind_contextvars(correlation_id=cid, path=request.url.path, method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_contextvars()
        response.headers[CORRELATION_HEADER] = cid
        return response
