"""Domain exception hierarchy carrying the api-contracts.md §1.4 envelope fields.

Nothing here imports FastAPI or names an HTTP status: `app/error_handlers.py`
owns the single exception-to-status mapping. Services raise these; routers never
construct a status code ad hoc.
"""

from collections.abc import Mapping
from typing import ClassVar

ErrorDetails = Mapping[str, object]


class DomainError(Exception):
    """Base for every error the domain raises.

    `code` is the machine-readable UPPER_SNAKE_CASE value placed in the error
    envelope. Each subclass sets a default; a call site may narrow it to a more
    specific code from the api-contracts.md §1.4 vocabulary.
    """

    default_code: ClassVar[str] = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: ErrorDetails | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details: ErrorDetails | None = details


class ValidationError(DomainError):
    """Body or parameters are well-formed but semantically invalid (422)."""

    default_code: ClassVar[str] = "VALIDATION_ERROR"


class NotFoundError(DomainError):
    """Resource absent, or not visible to this actor (404)."""

    default_code: ClassVar[str] = "NOT_FOUND"


class ConflictError(DomainError):
    """Request conflicts with existing state (409)."""

    default_code: ClassVar[str] = "CONFLICT"


class AuthenticationError(DomainError):
    """Unknown email or wrong password, or a missing/malformed/expired token
    on a protected endpoint (401). E2-S1 AC2: an unknown email and a wrong
    password are raised identically. `code` is narrowed per api-contracts.md
    §1.4 by the raising call site: `INVALID_CREDENTIALS` (login),
    `TOKEN_MISSING`, `TOKEN_EXPIRED`, `TOKEN_INVALID` (the `require_role`
    dependency, E2-S2 AC5)."""

    default_code: ClassVar[str] = "INVALID_CREDENTIALS"


class AuthorizationError(DomainError):
    """Authenticated, but the caller's role is not permitted for this endpoint
    (403) — system-design.md §9.2, the `require_role` dependency."""

    default_code: ClassVar[str] = "ROLE_NOT_PERMITTED"
