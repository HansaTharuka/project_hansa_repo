"""GET /api/recommendation (E5-S3 AC1-AC5; api-contracts.md §7.1; ut-203..ut-207)."""

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
from src.domain.goals.service import create_customer_goal
from src.domain.holdings.repository import insert_asset_class
from src.domain.recommendation.repository import publish_template
from src.domain.risk_profile.repository import insert_assignment
from src.types.entities import AllocationEntry, AllocationSet

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


def _seed_asset_classes(session: Session) -> tuple[int, int]:
    equity = insert_asset_class(session, code="EQ_DM", name="Developed-Market Equity")
    fixed_income = insert_asset_class(session, code="FI_GOV", name="Government Fixed Income")
    session.commit()
    return equity.id, fixed_income.id


def _publish_moderate_template(session: Session, *, equity_id: int, fixed_income_id: int) -> None:
    publish_template(
        session,
        risk_band="MODERATE",
        allocations=AllocationSet(
            allocations=[
                AllocationEntry(asset_class_id=equity_id, percent_bps=6000),
                AllocationEntry(asset_class_id=fixed_income_id, percent_bps=4000),
            ]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    session.commit()


def _assign_moderate_band(session: Session, *, customer_id: int) -> None:
    insert_assignment(
        session,
        customer_id=customer_id,
        risk_band="MODERATE",
        rule_version=1,
        assigned_at="2026-09-01T09:00:00Z",
    )
    session.commit()


def test_customer_with_an_assignment_gets_200_with_allocations_summing_to_100(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer1@wealthwise.test"
    )
    _assign_moderate_band(db_session, customer_id=customer_id)

    response = client.get("/api/recommendation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "risk_band", "rule_version", "template_version", "horizon",
        "allocations", "total_percent", "generated_at",
    }
    assert body["risk_band"] == "MODERATE"
    assert body["total_percent"] == "100.00"
    total = sum(Decimal(entry["percent"]) for entry in body["allocations"])
    assert total == Decimal("100.00")
    codes = {entry["asset_class_code"] for entry in body["allocations"]}
    assert codes == {"EQ_DM", "FI_GOV"}


def test_customer_with_no_assignment_returns_404_no_risk_band_assignment(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, _customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer2@wealthwise.test"
    )

    response = client.get("/api/recommendation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_RISK_BAND_ASSIGNMENT"


@pytest.mark.parametrize("role", ["advisor", "admin"])
def test_advisor_and_admin_tokens_return_403(
    client: TestClient, db_session: Session, role: str
) -> None:
    token = _seed_user_and_login(
        client, db_session, email=f"recapi.{role}@wealthwise.test", role=role
    )

    response = client.get("/api/recommendation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


def test_response_includes_template_version_matching_the_active_template(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer3@wealthwise.test"
    )
    _assign_moderate_band(db_session, customer_id=customer_id)

    response = client.get("/api/recommendation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["template_version"] == 1


def test_unauthenticated_request_returns_401(client: TestClient, migrated_engine: Engine) -> None:
    del migrated_engine
    response = client.get("/api/recommendation")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_MISSING"


def test_a_customer_with_no_goals_gets_the_default_medium_horizon(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer4@wealthwise.test"
    )
    _assign_moderate_band(db_session, customer_id=customer_id)

    response = client.get("/api/recommendation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["horizon"] == "MEDIUM"


def test_with_no_goal_id_param_the_highest_priority_goals_horizon_is_used(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer4b@wealthwise.test"
    )
    _assign_moderate_band(db_session, customer_id=customer_id)
    create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2027-06-01",
        priority=1,
    )
    create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("500000.00"),
        target_date="2040-01-01",
        priority=2,
    )
    db_session.commit()

    response = client.get("/api/recommendation", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["horizon"] == "SHORT"


def test_a_goal_id_query_param_selects_that_goals_horizon(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer5@wealthwise.test"
    )
    _assign_moderate_band(db_session, customer_id=customer_id)
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("500000.00"),
        target_date="2040-01-01",
        priority=1,
    )
    db_session.commit()

    response = client.get(
        f"/api/recommendation?goal_id={goal.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["horizon"] == "LONG"


def test_an_unknown_goal_id_returns_404_goal_not_found(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_moderate_template(db_session, equity_id=equity_id, fixed_income_id=fixed_income_id)
    token, customer_id = _seed_customer_and_login(
        client, db_session, "recapi.customer6@wealthwise.test"
    )
    _assign_moderate_band(db_session, customer_id=customer_id)

    response = client.get(
        "/api/recommendation?goal_id=999999", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "GOAL_NOT_FOUND"
