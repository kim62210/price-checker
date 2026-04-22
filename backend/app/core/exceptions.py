"""서비스 전역 예외 + FastAPI 핸들러."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from app.core.logging import get_logger

logger = get_logger(__name__)


class ServiceError(Exception):
    """모든 서비스 계층 에러의 공통 부모."""

    code: str = "INTERNAL"
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "internal_error"

    def __init__(self, detail: str | None = None, *, code: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        if code is not None:
            self.code = code
        super().__init__(self.detail)


class UpstreamError(ServiceError):
    code = "UPSTREAM_ERROR"
    http_status = status.HTTP_502_BAD_GATEWAY
    detail = "upstream_error"


class UpstreamTimeoutError(UpstreamError):
    code = "UPSTREAM_TIMEOUT"
    http_status = status.HTTP_504_GATEWAY_TIMEOUT
    detail = "upstream_timeout"


class AllSourcesFailedError(UpstreamError):
    code = "UPSTREAM_DOWN"
    http_status = status.HTTP_502_BAD_GATEWAY
    detail = "all_sources_failed"


class QuotaExceededError(ServiceError):
    code = "QUOTA_EXCEEDED"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "quota_exceeded"


class BotBlockedError(UpstreamError):
    code = "BOT_BLOCKED"
    http_status = status.HTTP_502_BAD_GATEWAY
    detail = "bot_blocked"


class ParsingError(ServiceError):
    code = "PARSE_ERROR"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "parse_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
        logger.warning("service_error", code=exc.code, detail=exc.detail)
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": exc.detail, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "code": "INVALID_REQUEST"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal_error", "code": "INTERNAL"},
        )
