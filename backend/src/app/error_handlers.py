"""Exception-to-HTTP-status mapping — the single place a status code is chosen.

Domain/service code raises typed exceptions from `types.errors`; no router or
service module ever raises `HTTPException` directly (system-design.md §2.1). Every
non-2xx body follows api-contracts.md §1.4's envelope: `{"error": {"code",
"message", "details"}}`, `details` omitted when the exception carries none.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.types.errors import ConflictError, DomainError, NotFoundError, ValidationError


def register_error_handlers(app: FastAPI) -> None:
    """Attach the domain error hierarchy's status mapping plus a generic 500 fallback."""

    @app.exception_handler(ValidationError)
    async def _handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        del request
        return _envelope(422, exc)

    @app.exception_handler(NotFoundError)
    async def _handle_not_found_error(request: Request, exc: NotFoundError) -> JSONResponse:
        del request
        return _envelope(404, exc)

    @app.exception_handler(ConflictError)
    async def _handle_conflict_error(request: Request, exc: ConflictError) -> JSONResponse:
        del request
        return _envelope(409, exc)

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                }
            },
        )


def _envelope(status_code: int, exc: DomainError) -> JSONResponse:
    body: dict[str, object] = {"code": exc.code, "message": exc.message}
    if exc.details is not None:
        body["details"] = dict(exc.details)
    return JSONResponse(status_code=status_code, content={"error": body})
