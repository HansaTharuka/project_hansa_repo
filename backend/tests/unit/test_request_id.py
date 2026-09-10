"""`app/middleware/request_id.py`'s `get_request_id` helper (E1-S4 AC2)."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from src.app.middleware.request_id import get_request_id


def test_get_request_id_raises_if_the_middleware_never_ran() -> None:
    scope = {"type": "http", "headers": []}
    request = Request(scope)

    with pytest.raises(RuntimeError):
        get_request_id(request)
