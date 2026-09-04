"""GET /health — public, no auth (E1-S4 AC1, AC4, AC5; api-contracts.md §4.1).

The connectivity probe touches only `db.session` (which itself wraps `db.engine`)
— never `db.models` and never any `domain.*.repository` module, per
architecture_checks.layering's resolution: an API-layer module may open a session
through `db/session.py`/`db/engine.py` directly, but must never import an ORM
table class or a repository function. The module is imported (`import ... as
db_session`), not name-imported, so a test can monkeypatch
`src.db.session.get_session_factory`/`session_scope` and have this probe observe
the patched behaviour. The 503 body intentionally mirrors
api-contracts.schema.json's `HealthResponse` shape exactly — no `error` envelope
wrapper here, unlike every other non-2xx response, since `HealthResponse` sets
`additionalProperties: false` and has no `error` field.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

import src.db.session as db_session

router = APIRouter(tags=["system"])


@router.get("/health")
def get_health() -> JSONResponse:
    """Return 200 `{"status": "ok", "database": "connected"}` if the DB responds,
    else 503 `{"status": "degraded", "database": "unavailable"}`."""
    if _database_is_reachable():
        return JSONResponse(status_code=200, content={"status": "ok", "database": "connected"})
    return JSONResponse(
        status_code=503, content={"status": "degraded", "database": "unavailable"}
    )


def _database_is_reachable() -> bool:
    """Run a trivial `SELECT 1`; any failure (connection, timeout, ...) is `False`.

    Broad `except Exception` is deliberate here: a health probe must degrade
    gracefully regardless of which failure mode the database presents, never
    propagate an exception and turn a 503 into an unhandled 500.
    """
    try:
        with db_session.session_scope(db_session.get_session_factory()) as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
