"""`app/error_handlers.py` — exception-to-HTTP-status mapping (E1-S4).

Builds a throwaway FastAPI app with one route per exception type this module
maps, rather than reusing `src.app.main`'s `app` (which has no route that raises
a domain error yet — the first one lands in E2-S2). Exercises every branch
`register_error_handlers` adds: each `DomainError` subclass's status code, the
`details`-present vs `details`-omitted envelope shapes, and the generic 500
fallback for an untyped exception.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.error_handlers import register_error_handlers
from src.types.errors import ConflictError, NotFoundError, ValidationError


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/validation")
    def _raise_validation() -> None:
        raise ValidationError("Bad input.", details={"field": "email"})

    @app.get("/not-found")
    def _raise_not_found() -> None:
        raise NotFoundError("Customer not found.")

    @app.get("/conflict")
    def _raise_conflict() -> None:
        raise ConflictError("Already resolved.")

    @app.get("/boom")
    def _raise_unexpected() -> None:
        raise RuntimeError("something broke")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_validation_error_maps_to_422_with_code_message_and_details(client: TestClient) -> None:
    response = client.get("/validation")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Bad input.",
            "details": {"field": "email"},
        }
    }


def test_not_found_error_maps_to_404_with_details_omitted_when_none(client: TestClient) -> None:
    response = client.get("/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Customer not found."
    assert "details" not in body["error"]


def test_conflict_error_maps_to_409(client: TestClient) -> None:
    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_unmapped_exception_maps_to_500_internal_error(client: TestClient) -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}
    }
