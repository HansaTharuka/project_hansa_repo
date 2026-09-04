"""GET /health (E1-S4 AC1, AC2, AC4, AC5; ut-045, ut-046, ut-047)."""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import src.db.session as db_session
from src.app.main import app


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_session_factory()` caches process-wide; force a rebuild for every test
    so a database from a previous test's `migrated_engine` is never reused."""
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine  # activates this test's own DATABASE_URL/JWT_SECRET env
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_200_with_only_seed_data_beyond_migrations(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_requires_no_authentication(client: TestClient) -> None:
    response = client.get("/health")  # no Authorization header sent

    assert response.status_code == 200


def test_health_returns_503_degraded_when_database_connectivity_probe_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_on_use() -> None:
        raise RuntimeError("simulated connectivity failure")

    monkeypatch.setattr(db_session, "get_session_factory", _raise_on_use)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}


def test_health_response_carries_an_x_request_id_header(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers.get("x-request-id")


def test_health_echoes_a_caller_supplied_x_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "caller-supplied-id"})

    assert response.headers["x-request-id"] == "caller-supplied-id"


def test_health_log_line_carries_the_same_request_id_as_the_response_header(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        response = client.get("/health")

    request_id = response.headers["x-request-id"]
    matching = [
        record for record in caplog.records if getattr(record, "request_id", None) == request_id
    ]
    assert matching, "expected a log record carrying this request's X-Request-ID"
    assert matching[0].path == "/health"
