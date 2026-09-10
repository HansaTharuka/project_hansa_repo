"""Emits one structured JSON log line per request, correlated by X-Request-ID
(E1-S4 AC2, AC3). Only structured metadata — request id, method, path, status
code, duration — is ever logged here, never a raw request/response body; NFR-03 is
satisfied by construction (no body field is ever passed to the logger) and, as a
second line of defense, `core.logging.JsonFormatter` redacts any sensitive key that
somehow reached a log record's `extra` fields regardless of the call site.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.app.middleware.request_id import get_request_id
from src.core.logging import get_logger

logger = get_logger("wealthwise.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Logs `{request_id, method, path, status_code, duration_ms}` after each request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started_at = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "request completed",
            extra={
                "request_id": get_request_id(request),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
