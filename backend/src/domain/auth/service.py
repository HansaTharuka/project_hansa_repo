"""Login: bcrypt-verify a seeded user's password, then issue a signed JWT (E2-S1).

`authenticate` is the ONLY way to obtain a token — there is no registration path
(AC5); the only accounts that can ever authenticate are rows already present via
`domain.auth.repository.create_user` (seeding, group B). Unknown email and wrong
password raise the identical `AuthenticationError` (AC2) so a caller can never
distinguish the two by exception type, message, or response shape. No plaintext
password is ever passed to a logging call anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.security import create_access_token, verify_password
from src.domain.auth.repository import get_customer_by_user_id, get_user_by_email, get_user_by_id
from src.types.enums import Role
from src.types.errors import AuthenticationError

INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password."


@dataclass(frozen=True)
class AuthenticationResult:
    """The signed JWT plus the identifiers a caller needs without re-decoding it."""

    token: str
    user_id: int
    role: str
    expiry_minutes: int


@dataclass(frozen=True)
class UserDetails:
    """The caller-identity fields GET /api/auth/me returns (AC5) — never
    `password_hash` or any other credential material (AC4)."""

    user_id: int
    email: str
    role: str


def get_user_details(session: Session, user_id: int) -> UserDetails | None:
    """Look up a user's own-record identity fields for session restore (AC5).

    Returns `None` if the user row no longer exists (e.g. deleted after the
    token was issued) — the caller (the /me router) maps that to 404.
    """
    row = get_user_by_id(session, user_id)
    if row is None:
        return None
    return UserDetails(user_id=row.id, email=row.email, role=row.role)


def authenticate(
    session: Session, *, email: str, password: str, settings: Settings
) -> AuthenticationResult:
    """Verify `email`/`password` against a seeded user and issue an access token.

    Raises `AuthenticationError` for both an unknown email and a wrong password —
    the same exception type and message either way (AC2). `email` is matched
    case-insensitively (api-contracts.md §5.1).
    """
    user = get_user_by_email(session, email.lower())
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)

    customer_id: int | None = None
    if user.role == Role.CUSTOMER.value:
        customer = get_customer_by_user_id(session, user.id)
        customer_id = customer.id if customer is not None else None

    token = create_access_token(
        str(user.id),
        user.role,
        expiry_minutes=settings.jwt_access_token_expiry_minutes,
        secret=settings.jwt_secret,
        customer_id=customer_id,
    )
    return AuthenticationResult(
        token=token,
        user_id=user.id,
        role=user.role,
        expiry_minutes=settings.jwt_access_token_expiry_minutes,
    )
