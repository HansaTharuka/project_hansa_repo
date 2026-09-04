"""Deterministic test-data builders (testing SKILL.md — "factory functions, not
inline object literals").
"""

from __future__ import annotations

from dataclasses import dataclass

# A syntactically-valid bcrypt hash shape, but not a real credential — synthetic
# fixture data only (Synthetic-Data rule).
DEFAULT_PASSWORD_HASH = (
    "$2b$12$KixT4fWzQe7hR0mYqvE5b.s3JXo1uQd6nZp8LxGmC2AbFe9RstWk6"  # pragma: allowlist secret
)
DEFAULT_CREATED_AT = "2026-09-01T09:00:00Z"


@dataclass(frozen=True)
class UserSeed:
    email: str
    password_hash: str
    role: str
    created_at: str


@dataclass(frozen=True)
class CustomerSeed:
    user_id: int
    kyc_verified: bool
    created_at: str


def build_user(
    *,
    email: str = "morgan.reyes@wealthwise.test",
    password_hash: str = DEFAULT_PASSWORD_HASH,
    role: str = "customer",
    created_at: str = DEFAULT_CREATED_AT,
) -> UserSeed:
    """A deterministic `User` row builder — overrideable per test via keyword args."""
    return UserSeed(email=email, password_hash=password_hash, role=role, created_at=created_at)


def build_customer(
    *,
    user_id: int,
    kyc_verified: bool = True,
    created_at: str = DEFAULT_CREATED_AT,
) -> CustomerSeed:
    """A deterministic `Customer` row builder tied to an existing `user_id`."""
    return CustomerSeed(user_id=user_id, kyc_verified=kyc_verified, created_at=created_at)
