"""FastAPI application factory (E1-S4).

Registers the health and auth routers, the request-id/request-log middleware
pair, and the domain error handlers. Started per project-manifest.json as
`uv run uvicorn src.app.main:app --reload` — the module-level `app` below is
that target. Every router beyond `/health` and `POST /api/auth/login` is
added by its own group-E-and-later story, guarded by `app.dependencies.require_role`.

`configure_logging()` runs from the ASGI lifespan's startup phase, not at
construction time: `alembic/env.py` calls `logging.config.fileConfig()` on every
migration run, which reconfigures the root logger's handlers wholesale. Deferring
our own handler setup to startup — which always runs after any migration a
deployment or test fixture ran first — guarantees our JSON handler is the one left
attached, satisfying AC1's "within 1 second of the application completing
startup" framing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app.error_handlers import register_error_handlers
from src.app.middleware.request_id import RequestIDMiddleware
from src.app.middleware.request_log import RequestLogMiddleware
from src.app.routers.admin import router as admin_router
from src.app.routers.audit import router as audit_router
from src.app.routers.auth import router as auth_router
from src.app.routers.health import router as health_router
from src.app.routers.holdings import router as holdings_router
from src.core.logging import configure_logging


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    configure_logging()
    yield


def create_app() -> FastAPI:
    """Build and return the WealthWise FastAPI application."""
    app = FastAPI(title="WealthWise API", lifespan=_lifespan)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(holdings_router)
    app.include_router(admin_router)
    # Registration order matters: Starlette wraps middleware in reverse of
    # registration order, so the LAST one added runs FIRST. RequestIDMiddleware
    # must run before RequestLogMiddleware so the request id it stamps onto
    # `request.state` is already set when the log line is emitted.
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    register_error_handlers(app)
    return app


app = create_app()
