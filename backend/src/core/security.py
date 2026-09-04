"""Password hashing/verification (bcrypt) and JWT issuance/decoding (PyJWT), E2-S1.

No secret literal lives here: every caller passes `Settings().jwt_secret` in
explicitly. `verify_password` always goes through `bcrypt.checkpw` — a
constant-time comparison against the salt embedded in the stored hash — never a
plain `==` on the hash string. `decode_access_token` lets PyJWT's own
`jwt.ExpiredSignatureError`/`jwt.InvalidTokenError` propagate unwrapped on an
expired or invalid token; callers catch those directly rather than a
WealthWise-specific wrapper.
"""

from __future__ import annotations

import time

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    """Hash `plain` with bcrypt, returning a UTF-8 string safe to store in a column."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt comparison of `plain` against a stored `hashed` value."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str, role: str, *, expiry_minutes: int, secret: str) -> str:
    """Issue an HS256 JWT with `sub`, `role`, `iat` and `exp` claims."""
    issued_at = int(time.time())
    payload: dict[str, str | int] = {
        "sub": subject,
        "role": role,
        "iat": issued_at,
        "exp": issued_at + expiry_minutes * 60,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> dict[str, str | int]:
    """Decode and verify `token`. Raises `jwt.ExpiredSignatureError` if expired,
    `jwt.InvalidTokenError` (or a subclass) for any other signature/claim failure."""
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
