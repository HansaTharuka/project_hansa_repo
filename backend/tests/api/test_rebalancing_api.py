"""GET /api/rebalancing, POST /api/rebalancing/{id}/accept|dismiss (E8-S3
AC1-AC5; api-contracts.md §10.1-§10.3; ut-183..ut-187)."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

import src.db.session as db_session
from src.app.main import app
from src.core.security import hash_password
from src.db.models import Customer
from src.domain.audit.repository import count_audit_entries
from src.domain.auth.repository import create_user
from src.domain.rebalancing.repository import accept, insert_recommendation
from src.types.entities import ProposedAction, ProposedActions

KNOWN_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine
    with TestClient(app) as test_client:
        yield test_client


def _seed_customer_and_login(client: TestClient, session: Session, email: str) -> tuple[str, int]:
    user_seed = build_user(email=email, password_hash=hash_password(KNOWN_PASSWORD))
    user = create_user(
        session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id)
    customer = Customer(
        user_id=customer_seed.user_id,
        kyc_verified=customer_seed.kyc_verified,
        created_at=customer_seed.created_at,
    )
    session.add(customer)
    session.commit()
    response = client.post("/api/auth/login", json={"email": email, "password": KNOWN_PASSWORD})
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token, customer.id


def _sample_actions() -> ProposedActions:
    return ProposedActions(
        actions=[
            ProposedAction(
                asset_class_id=1, asset_class_code="EQ_DM", action="SELL",
                amount="3200.00", units="24.1600", drift_percent="8.20",
            )
        ],
        threshold_bps=500,
        threshold_version=1,
    )


def _insert_recommendation(session: Session, *, customer_id: int, recommendation_id: str) -> None:
    insert_recommendation(
        session,
        customer_id=customer_id,
        recommendation_id=recommendation_id,
        proposed_actions=_sample_actions(),
        generated_at="2026-09-04T08:00:00Z",
    )
    session.commit()


def test_get_rebalancing_with_no_status_param_returns_only_pending_recommendations(
    client: TestClient, db_session: Session
) -> None:
    token, customer_id = _seed_customer_and_login(
        client, db_session, "rebalapi.customer1@wealthwise.test"
    )
    _insert_recommendation(db_session, customer_id=customer_id, recommendation_id="rec-pending-1")
    _insert_recommendation(db_session, customer_id=customer_id, recommendation_id="rec-resolved-1")
    accept(db_session, recommendation_id="rec-resolved-1", resolved_at="2026-09-04T09:00:00Z")
    db_session.commit()

    response = client.get("/api/rebalancing", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["recommendation_id"] == "rec-pending-1"
    assert set(body[0].keys()) >= {"recommendation_id", "status", "proposed_actions"}


def test_accept_transitions_to_accepted_and_writes_one_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    token, customer_id = _seed_customer_and_login(
        client, db_session, "rebalapi.customer2@wealthwise.test"
    )
    _insert_recommendation(db_session, customer_id=customer_id, recommendation_id="rec-accept-1")
    before = count_audit_entries(db_session)

    response = client.post(
        "/api/rebalancing/rec-accept-1/accept", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "recommendation_id": "rec-accept-1",
        "status": "accepted",
        "resolved_at": body["resolved_at"],
    }
    assert body["resolved_at"] is not None
    after = count_audit_entries(db_session)
    assert after - before == 1


def test_dismiss_transitions_to_dismissed_and_writes_one_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    token, customer_id = _seed_customer_and_login(
        client, db_session, "rebalapi.customer3@wealthwise.test"
    )
    _insert_recommendation(db_session, customer_id=customer_id, recommendation_id="rec-dismiss-1")
    before = count_audit_entries(db_session)

    response = client.post(
        "/api/rebalancing/rec-dismiss-1/dismiss", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    after = count_audit_entries(db_session)
    assert after - before == 1


def test_accepting_an_already_resolved_recommendation_returns_409_and_leaves_resolved_at_unchanged(
    client: TestClient, db_session: Session
) -> None:
    token, customer_id = _seed_customer_and_login(
        client, db_session, "rebalapi.customer4@wealthwise.test"
    )
    _insert_recommendation(db_session, customer_id=customer_id, recommendation_id="rec-conflict-1")
    first = client.post(
        "/api/rebalancing/rec-conflict-1/accept", headers={"Authorization": f"Bearer {token}"}
    )
    assert first.status_code == 200
    first_resolved_at = first.json()["resolved_at"]

    second = client.post(
        "/api/rebalancing/rec-conflict-1/accept", headers={"Authorization": f"Bearer {token}"}
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_RESOLVED"

    from src.domain.rebalancing.repository import get_by_recommendation_id

    row = get_by_recommendation_id(db_session, "rec-conflict-1")
    assert row is not None
    assert row.resolved_at == first_resolved_at


def test_accepting_another_customers_recommendation_returns_404(
    client: TestClient, db_session: Session
) -> None:
    _, owner_id = _seed_customer_and_login(
        client, db_session, "rebalapi.owner1@wealthwise.test"
    )
    other_token, _ = _seed_customer_and_login(
        client, db_session, "rebalapi.other1@wealthwise.test"
    )
    _insert_recommendation(db_session, customer_id=owner_id, recommendation_id="rec-owned-1")

    response = client.post(
        "/api/rebalancing/rec-owned-1/accept", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECOMMENDATION_NOT_FOUND"


def test_unauthenticated_requests_return_401(client: TestClient, migrated_engine: Engine) -> None:
    del migrated_engine
    response = client.get("/api/rebalancing")

    assert response.status_code == 401
