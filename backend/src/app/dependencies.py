"""Request-scoped FastAPI dependencies: DB session injection and the
`require_role` authorisation boundary (E2-S2 AC5; system-design.md §9.2).

`require_role(*roles)` is the ONE place a JWT is decoded and a role checked —
every router outside `/health` and `POST /api/auth/login` declares it (no
router constructs a 401/403 ad hoc). It rejects a missing/malformed/expired
token with `AuthenticationError` (401) and an authenticated caller whose role
is outside `roles` with `AuthorizationError` (403); `app/error_handlers.py`
maps both to their status codes. When `roles` is empty, any authenticated
role is accepted (used by `GET /api/auth/me`, E2-S3 AC5).
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.security import decode_access_token
from src.db.session import get_session_factory, session_scope
from src.types.errors import AuthenticationError, AuthorizationError

BEARER_PREFIX = "Bearer "


@dataclass(frozen=True)
class CurrentUser:
    """The decoded JWT claims a router needs — never re-decoded downstream."""

    user_id: int
    role: str
    customer_id: int | None


def get_settings() -> Settings:
    """Build `Settings` from the current environment.

    Deliberately not cached: pytest's `migrated_engine` fixture rebinds
    `DATABASE_URL`/`JWT_SECRET` per test via `monkeypatch`, and a cached
    instance would silently keep serving the first test's values.
    """
    return Settings()


def get_session() -> Generator[Session, None, None]:
    """One `Session` per request: commits on success, rolls back on any
    exception raised while handling the request (mirrors `db.session_scope`).

    Every router declares this as `Depends(get_session, scope="function")` —
    without `scope="function"`, FastAPI tears down yield-dependencies on its
    outer, request-scoped `AsyncExitStack`, which closes only *after* the
    response has already been sent to the client (fastapi/routing.py's `app()`
    awaits `response(scope, receive, send)` before closing `request_astack`,
    while `function_astack` closes right after the endpoint returns, before
    that send). That ordering was the root cause of a reproducible read-after-
    write race (pw-h-05/pw-h-09): a client could receive a mutating endpoint's
    2xx response and immediately issue a following GET before this dependency's
    `session.commit()` had actually run. `scope="function"` puts the commit on
    the inner stack, so it is guaranteed to finish before the response goes out.
    """
    with session_scope(get_session_factory()) as session:
        yield session


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """Build a FastAPI dependency callable verifying the caller is
    authenticated and, when `roles` is non-empty, holds one of them.

    Declared in a router's parameter list as `user: CurrentUser =
    Depends(require_role("customer"))`.
    """

    def _dependency(
        request: Request, settings: Settings = Depends(get_settings)
    ) -> CurrentUser:
        token = _extract_bearer_token(request)
        try:
            claims = decode_access_token(token, secret=settings.jwt_secret)
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Access token has expired.", code="TOKEN_EXPIRED") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Access token is invalid.", code="TOKEN_INVALID") from exc

        role = str(claims["role"])
        if roles and role not in roles:
            raise AuthorizationError(
                f"Role {role!r} is not permitted for this endpoint.",
                details={"required_roles": list(roles)},
            )
        customer_id = claims.get("customer_id")
        return CurrentUser(
            user_id=int(claims["sub"]),
            role=role,
            customer_id=int(customer_id) if customer_id is not None else None,
        )

    return _dependency


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.startswith(BEARER_PREFIX):
        raise AuthenticationError(
            "Missing or malformed Authorization header.", code="TOKEN_MISSING"
        )
    token = header[len(BEARER_PREFIX) :].strip()
    if not token:
        raise AuthenticationError(
            "Missing or malformed Authorization header.", code="TOKEN_MISSING"
        )
    return token
