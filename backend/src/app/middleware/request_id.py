"""Stamps every request with a stable correlation id, echoed on the response
(E1-S4 AC2). Registered LAST in `app/main.py` so it is the OUTERMOST middleware —
Starlette wraps middleware in reverse of registration order — meaning
`request.state.request_id` is already set before `request_log.py`'s middleware,
registered earlier, runs.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Reads `X-Request-ID` from the request, or generates one, and echoes it back."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def get_request_id(request: Request) -> str:
    """Read the id `RequestIDMiddleware` stamped onto `request.state` for this call."""
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, str):
        raise RuntimeError("RequestIDMiddleware has not run for this request")
    return request_id
