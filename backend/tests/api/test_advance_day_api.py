"""POST /api/admin/advance-day (E6-S4 AC2-AC4; api-contracts.md §12.1;
ut-138..ut-140)."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import src.db.session as db_session
from src.app.main import app
from src.core.security import hash_password
from src.domain.auth.repository import create_user
from src.domain.holdings.csv_loader import load_seed_csvs

KNOWN_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine
    with TestClient(app) as test_client:
        yield test_client


def _seed_user_and_login(client: TestClient, session: Session, *, email: str, role: str) -> str:
    create_user(
        session,
        email=email,
        password_hash=hash_password(KNOWN_PASSWORD),
        role=role,
        created_at="2026-09-01T09:00:00Z",
    )
    session.commit()
    response = client.post("/api/auth/login", json={"email": email, "password": KNOWN_PASSWORD})
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token


def test_admin_token_advances_the_day_and_returns_the_shared_response_shape(
    client: TestClient, db_session: Session
) -> None:
    load_seed_csvs(db_session)
    db_session.commit()
    token = _seed_user_and_login(
        client, db_session, email="advanceday.admin1@wealthwise.test", role="admin"
    )

    response = client.post(
        "/api/admin/advance-day", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "price_date", "nav_snapshots_created", "holdings_revalued",
        "goal_snapshots_created", "rebalancing_recommendations_created",
    }
    assert body["price_date"] == "2026-09-02"


@pytest.mark.parametrize("role", ["customer", "advisor"])
def test_non_admin_roles_are_rejected_with_403(
    client: TestClient, db_session: Session, role: str
) -> None:
    load_seed_csvs(db_session)
    db_session.commit()
    token = _seed_user_and_login(
        client, db_session, email=f"advanceday.{role}@wealthwise.test", role=role
    )

    response = client.post(
        "/api/admin/advance-day", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


def test_a_second_immediate_call_for_the_same_day_returns_409_with_no_duplicate_rows(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    load_seed_csvs(db_session)
    db_session.commit()
    token = _seed_user_and_login(
        client, db_session, email="advanceday.admin2@wealthwise.test", role="admin"
    )

    first = client.post("/api/admin/advance-day", headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 200

    from sqlalchemy.exc import IntegrityError

    def _raise_integrity_error(*args: object, **kwargs: object) -> None:
        raise IntegrityError(
            "INSERT INTO nav_snapshot ...", {}, Exception("UNIQUE constraint failed")
        )

    monkeypatch.setattr(
        "src.domain.holdings.service.insert_nav_snapshot", _raise_integrity_error
    )

    second = client.post("/api/admin/advance-day", headers={"Authorization": f"Bearer {token}"})

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DAY_ALREADY_ADVANCED"

    from sqlalchemy import text

    count = db_session.execute(
        text("SELECT COUNT(*) FROM nav_snapshot WHERE price_date = '2026-09-02'")
    ).scalar_one()
    assert count == 6  # one per seeded asset class from the first, successful call only
