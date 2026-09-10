"""POST /api/auth/login — public, the single entry point for all four
personas (E2-S2 AC1-AC5; api-contracts.md §5.1) — plus GET /api/auth/me, the
session-restore read every other protected router's `require_role` will be
proven against (E2-S2 AC5; system-design.md D14, api-contracts.md §5.2).

Validation of `email`/`password` (non-empty, present) happens at the Pydantic
model boundary before `domain.auth.service.authenticate` is ever called
(AC3). `AuthenticationError` from a wrong password or unknown email is left
to propagate to `app/error_handlers.py`'s registered handler (401) rather
than being caught here — this router never constructs a status code itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, get_settings, require_role
from src.core.config import Settings
from src.domain.auth.service import authenticate, get_user_details
from src.types.errors import NotFoundError

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Both fields required, non-empty (AC3) — `min_length=1` rejects `""`
    the same way FastAPI already rejects a missing field, both as 422."""

    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    """Never carries `password_hash` or any other credential material (AC4) —
    only the fields api-contracts.md §5.1 documents."""

    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int


class CurrentUserResponse(BaseModel):
    """`customer_id` is `null` for every non-customer role (api-contracts.md §5.2)."""

    user_id: int
    email: str
    role: str
    customer_id: int | None


@router.post("/login", status_code=200)
def login(
    body: LoginRequest,
    session: Session = Depends(get_session, scope="function"),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """Verify `email`/`password` and return a signed access token plus role
    (AC1). An unknown email or wrong password raises `AuthenticationError`,
    mapped to 401 with no token in the body (AC2)."""
    result = authenticate(session, email=body.email, password=body.password, settings=settings)
    return LoginResponse(
        access_token=result.token,
        role=result.role,
        expires_in=result.expiry_minutes * 60,
    )


@router.get("/me", status_code=200)
def get_current_user_details(
    user: CurrentUser = Depends(require_role()),
    session: Session = Depends(get_session, scope="function"),
) -> CurrentUserResponse:
    """Any authenticated role (AC5) — server-verified session restore so the
    SPA never trusts a client-side `exp` check alone."""
    details = get_user_details(session, user.user_id)
    if details is None:
        raise NotFoundError(f"User {user.user_id} no longer exists.", code="USER_NOT_FOUND")
    return CurrentUserResponse(
        user_id=details.user_id,
        email=details.email,
        role=details.role,
        customer_id=user.customer_id,
    )
