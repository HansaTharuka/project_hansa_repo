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
from src.domain.auth.repository import get_user_by_email
from src.types.errors import AuthenticationError

INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password."


@dataclass(frozen=True)
class AuthenticationResult:
    """The signed JWT plus the identifiers a caller needs without re-decoding it."""

    token: str
    user_id: int
    role: str


def authenticate(
    session: Session, *, email: str, password: str, settings: Settings
) -> AuthenticationResult:
    """Verify `email`/`password` against a seeded user and issue an access token.

    Raises `AuthenticationError` for both an unknown email and a wrong password —
    the same exception type and message either way (AC2).
    """
    user = get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE)
    token = create_access_token(
        str(user.id),
        user.role,
        expiry_minutes=settings.jwt_access_token_expiry_minutes,
        secret=settings.jwt_secret,
    )
    return AuthenticationResult(token=token, user_id=user.id, role=user.role)
