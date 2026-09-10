"""CORS (deployment.md §1.1): the backend must allow the Vite dev server
origin, `http://localhost:5173`, or the browser blocks the SPA's login
request at the preflight stage before it ever reaches the server."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import src.db.session as db_session
from src.app.main import app

ALLOWED_ORIGIN = "http://localhost:5173"


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine
    with TestClient(app) as test_client:
        yield test_client


def test_preflight_for_the_allowed_frontend_origin_is_permitted(client: TestClient) -> None:
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_actual_request_from_the_allowed_origin_carries_the_allow_origin_header(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/auth/login",
        headers={"Origin": ALLOWED_ORIGIN},
        json={"email": "nobody@wealthwise.test", "password": "wrong-password"},
    )

    # Even a 401 (bad credentials) must still carry the CORS header, or the
    # browser hides the response body from the SPA's error handling.
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_preflight_from_an_unlisted_origin_is_not_granted_access(client: TestClient) -> None:
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert "access-control-allow-origin" not in {
        key.lower() for key in response.headers.keys()
    }
