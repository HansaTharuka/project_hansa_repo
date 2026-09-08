"""POST/GET/PATCH /api/goals, GET /api/goals/{id}/progress (E7-S4 AC1-AC5;
api-contracts.md §9.1-§9.4; ut-178..ut-182)."""

from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

import src.db.session as db_session
from src.app.main import app
from src.core.security import hash_password
from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.goals.repository import insert_progress_snapshot, list_goals_for_customer

KNOWN_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine
    with TestClient(app) as test_client:
        yield test_client


def _seed_customer_and_login(client: TestClient, session: Session, email: str) -> str:
    user_seed = build_user(email=email, password_hash=hash_password(KNOWN_PASSWORD))
    user = create_user(
        session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id)
    session.add(
        Customer(
            user_id=customer_seed.user_id,
            kyc_verified=customer_seed.kyc_verified,
            created_at=customer_seed.created_at,
        )
    )
    session.commit()
    response = client.post("/api/auth/login", json={"email": email, "password": KNOWN_PASSWORD})
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token


def test_valid_goal_creation_returns_201_with_the_created_goals_id(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_customer_and_login(client, db_session, "goalsapi.customer1@wealthwise.test")

    response = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": "250000.00", "target_date": "2032-06-30", "priority": 1},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {
        "id", "customer_id", "target_amount", "target_date",
        "priority", "created_at", "updated_at", "percent_complete",
    }
    assert body["id"] is not None
    assert body["target_amount"] == "250000.00"
    assert body["percent_complete"] is None


@pytest.mark.parametrize("target_amount", ["0.00", "-100.00"])
def test_non_positive_target_amount_returns_422_and_creates_no_row(
    client: TestClient, db_session: Session, target_amount: str
) -> None:
    token = _seed_customer_and_login(
        client, db_session, f"goalsapi.customer.invalid{target_amount}@wealthwise.test"
    )

    response = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": target_amount, "target_date": "2032-06-30", "priority": 1},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_goals_is_scoped_to_the_authenticated_customer_only(
    client: TestClient, db_session: Session
) -> None:
    token_a = _seed_customer_and_login(client, db_session, "goalsapi.customer.a@wealthwise.test")
    token_b = _seed_customer_and_login(client, db_session, "goalsapi.customer.b@wealthwise.test")
    client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"target_amount": "100000.00", "target_date": "2031-01-01", "priority": 2},
    )
    client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"target_amount": "500000.00", "target_date": "2033-01-01", "priority": 1},
    )

    response = client.get("/api/goals", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["target_amount"] == "100000.00"


def test_goal_progress_returns_snapshots_ordered_oldest_first(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_customer_and_login(client, db_session, "goalsapi.customer2@wealthwise.test")
    create = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": "200000.00", "target_date": "2032-01-01", "priority": 1},
    )
    goal_id = create.json()["id"]
    goals = list_goals_for_customer(db_session, create.json()["customer_id"])
    assert goals[0].id == goal_id
    insert_progress_snapshot(
        db_session, goal_id=goal_id, current_value=Decimal("62500.00"),
        percent_complete=Decimal("31.25"),
        snapshot_at="2026-09-04T10:30:00Z", price_date="2026-09-04",
    )
    insert_progress_snapshot(
        db_session, goal_id=goal_id, current_value=Decimal("50000.00"),
        percent_complete=Decimal("25.00"),
        snapshot_at="2026-09-03T10:30:00Z", price_date="2026-09-03",
    )
    db_session.commit()

    response = client.get(
        f"/api/goals/{goal_id}/progress", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["goal_id"] == goal_id
    assert [s["price_date"] for s in body["snapshots"]] == ["2026-09-03", "2026-09-04"]


def test_goal_progress_for_a_goal_with_no_snapshots_returns_an_empty_list(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_customer_and_login(client, db_session, "goalsapi.customer3@wealthwise.test")
    create = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": "200000.00", "target_date": "2032-01-01", "priority": 1},
    )
    goal_id = create.json()["id"]

    response = client.get(
        f"/api/goals/{goal_id}/progress", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["snapshots"] == []


def test_patch_updating_priority_returns_200_and_persists(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_customer_and_login(client, db_session, "goalsapi.customer4@wealthwise.test")
    create = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": "200000.00", "target_date": "2032-01-01", "priority": 1},
    )
    goal_id = create.json()["id"]

    patch_response = client.patch(
        f"/api/goals/{goal_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"priority": 3},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["priority"] == 3

    follow_up = client.get("/api/goals", headers={"Authorization": f"Bearer {token}"})
    matching = [goal for goal in follow_up.json() if goal["id"] == goal_id]
    assert matching[0]["priority"] == 3
    assert matching[0]["created_at"] == create.json()["created_at"]


def test_goal_progress_for_an_unknown_or_another_customers_goal_returns_404(
    client: TestClient, db_session: Session
) -> None:
    owner_token = _seed_customer_and_login(
        client, db_session, "goalsapi.owner1@wealthwise.test"
    )
    other_token = _seed_customer_and_login(
        client, db_session, "goalsapi.other1@wealthwise.test"
    )
    create = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"target_amount": "200000.00", "target_date": "2032-01-01", "priority": 1},
    )
    goal_id = create.json()["id"]

    response = client.get(
        f"/api/goals/{goal_id}/progress", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GOAL_NOT_FOUND"


def test_patch_with_an_empty_body_returns_422(client: TestClient, db_session: Session) -> None:
    token = _seed_customer_and_login(client, db_session, "goalsapi.customer5@wealthwise.test")
    create = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": "200000.00", "target_date": "2032-01-01", "priority": 1},
    )
    goal_id = create.json()["id"]

    response = client.patch(
        f"/api/goals/{goal_id}", headers={"Authorization": f"Bearer {token}"}, json={}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("target_amount", ["not-a-number", "100.001"])
def test_patch_with_a_malformed_target_amount_returns_422(
    client: TestClient, db_session: Session, target_amount: str
) -> None:
    token = _seed_customer_and_login(
        client, db_session, f"goalsapi.customer6.{target_amount}@wealthwise.test"
    )
    create = client.post(
        "/api/goals",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": "200000.00", "target_date": "2032-01-01", "priority": 1},
    )
    goal_id = create.json()["id"]

    response = client.patch(
        f"/api/goals/{goal_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_amount": target_amount},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unauthenticated_requests_return_401(client: TestClient, migrated_engine: Engine) -> None:
    del migrated_engine
    response = client.get("/api/goals")

    assert response.status_code == 401
