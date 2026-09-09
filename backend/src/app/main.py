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
from fastapi.middleware.cors import CORSMiddleware

from src.app.error_handlers import register_error_handlers
from src.app.middleware.request_id import RequestIDMiddleware
from src.app.middleware.request_log import RequestLogMiddleware
from src.app.routers.admin import router as admin_router
from src.app.routers.advisor import router as advisor_router
from src.app.routers.audit import router as audit_router
from src.app.routers.auth import router as auth_router
from src.app.routers.goals import router as goals_router
from src.app.routers.health import router as health_router
from src.app.routers.holdings import router as holdings_router
from src.app.routers.rebalancing import router as rebalancing_router
from src.app.routers.recommendation import router as recommendation_router
from src.app.routers.risk_profile import router as risk_profile_router
from src.core.config import Settings
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
    app.include_router(risk_profile_router)
    app.include_router(goals_router)
    app.include_router(rebalancing_router)
    app.include_router(recommendation_router)
    app.include_router(advisor_router)
    # Registration order matters: Starlette wraps middleware in reverse of
    # registration order, so the LAST one added runs FIRST. RequestIDMiddleware
    # must run before RequestLogMiddleware so the request id it stamps onto
    # `request.state` is already set when the log line is emitted. CORSMiddleware
    # is added last so it is outermost: it must see (and short-circuit) the
    # browser's OPTIONS preflight before any other middleware or router runs,
    # and it must wrap every response — including error responses — with the
    # Access-Control-Allow-Origin header (deployment.md §1.1).
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    settings = Settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    return app


app = create_app()
