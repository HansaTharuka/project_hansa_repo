"""GET /api/advisor/customers, GET /api/advisor/customers/{id}, POST .../override,
POST .../manual-recommendation (E9-S3 AC1-AC5; api-contracts.md §11.1-§11.4;
ut-218..ut-222)."""

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
from src.domain.audit.repository import count_audit_entries
from src.domain.auth.repository import create_user
from src.domain.goals.service import create_customer_goal
from src.domain.holdings.repository import insert_asset_class, insert_holding
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


def _publish_template(
    session: Session, *, risk_band: str, equity_id: int, fixed_income_id: int
) -> None:
    publish_template(
        session,
        risk_band=risk_band,
        allocations=AllocationSet(
            allocations=[
                AllocationEntry(asset_class_id=equity_id, percent_bps=6000),
                AllocationEntry(asset_class_id=fixed_income_id, percent_bps=4000),
            ]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    session.commit()


def _assign_band(session: Session, *, customer_id: int, risk_band: str) -> None:
    insert_assignment(
        session,
        customer_id=customer_id,
        risk_band=risk_band,
        rule_version=1,
        assigned_at="2026-09-01T09:00:00Z",
    )
    session.commit()


ADVISOR_ENDPOINTS: list[tuple[str, str, dict[str, str] | None]] = [
    ("GET", "/api/advisor/customers", None),
    ("GET", "/api/advisor/customers/{customer_id}", None),
    (
        "POST",
        "/api/advisor/customers/{customer_id}/override",
        {"new_band": "CONSERVATIVE", "reason": "Client reported imminent liquidity need."},
    ),
    (
        "POST",
        "/api/advisor/customers/{customer_id}/manual-recommendation",
        {"note": "Role-scoping probe note."},
    ),
]


def test_list_customers_with_advisor_token_returns_200_with_every_expected_field(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_template(
        db_session, risk_band="MODERATE", equity_id=equity_id, fixed_income_id=fixed_income_id
    )
    _token_a, customer_a_id = _seed_customer_and_login(
        client, db_session, "advapi.customer1@wealthwise.test"
    )
    _assign_band(db_session, customer_id=customer_a_id, risk_band="MODERATE")
    insert_holding(
        db_session, customer_id=customer_a_id, asset_class_id=equity_id,
        current_value=Decimal("60000.00"), as_of_date="2026-09-04",
    )
    db_session.commit()
    create_customer_goal(
        db_session, customer_id=customer_a_id, target_amount=Decimal("100000.00"),
        target_date="2032-01-01", priority=1,
    )
    db_session.commit()
    _token_b, _customer_b_id = _seed_customer_and_login(
        client, db_session, "advapi.customer2@wealthwise.test"
    )
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor1@wealthwise.test", role="advisor"
    )

    response = client.get(
        "/api/advisor/customers", headers={"Authorization": f"Bearer {advisor_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    for entry in body:
        assert set(entry.keys()) == {
            "customer_id", "email", "risk_band", "kyc_verified", "total_value", "goal_count",
        }
    by_id = {entry["customer_id"]: entry for entry in body}
    assert by_id[customer_a_id]["risk_band"] == "MODERATE"
    assert by_id[customer_a_id]["total_value"] == "60000.00"
    assert by_id[customer_a_id]["goal_count"] == 1
    assert by_id[_customer_b_id]["risk_band"] is None
    assert by_id[_customer_b_id]["goal_count"] == 0


def test_drill_in_returns_holdings_goals_and_allocation_in_one_call(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_template(
        db_session, risk_band="MODERATE", equity_id=equity_id, fixed_income_id=fixed_income_id
    )
    _token, customer_id = _seed_customer_and_login(
        client, db_session, "advapi.customer3@wealthwise.test"
    )
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=equity_id,
        current_value=Decimal("60000.00"), as_of_date="2026-09-04",
    )
    db_session.commit()
    create_customer_goal(
        db_session, customer_id=customer_id, target_amount=Decimal("100000.00"),
        target_date="2032-01-01", priority=1,
    )
    db_session.commit()
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor2@wealthwise.test", role="advisor"
    )

    response = client.get(
        f"/api/advisor/customers/{customer_id}",
        headers={"Authorization": f"Bearer {advisor_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "customer_id", "email", "kyc_verified", "risk_band", "rule_version",
        "holdings", "goals", "allocation", "override_history",
    }
    assert body["risk_band"] == "MODERATE"
    assert len(body["holdings"]["holdings"]) == 1
    assert len(body["goals"]) == 1
    assert body["allocation"] is not None
    assert body["allocation"]["total_percent"] == "100.00"
    assert body["override_history"] == []


def test_drill_in_for_a_customer_with_no_assignment_returns_a_null_allocation(
    client: TestClient, db_session: Session
) -> None:
    _token, customer_id = _seed_customer_and_login(
        client, db_session, "advapi.customer4@wealthwise.test"
    )
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor3@wealthwise.test", role="advisor"
    )

    response = client.get(
        f"/api/advisor/customers/{customer_id}",
        headers={"Authorization": f"Bearer {advisor_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["risk_band"] is None
    assert body["allocation"] is None


def test_drill_in_for_an_unknown_customer_returns_404_customer_not_found(
    client: TestClient, db_session: Session
) -> None:
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor4@wealthwise.test", role="advisor"
    )

    response = client.get(
        "/api/advisor/customers/999999", headers={"Authorization": f"Bearer {advisor_token}"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CUSTOMER_NOT_FOUND"


def test_override_with_a_valid_reason_returns_201_and_the_recommendation_reflects_it_immediately(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_template(
        db_session, risk_band="MODERATE", equity_id=equity_id, fixed_income_id=fixed_income_id
    )
    _publish_template(
        db_session, risk_band="CONSERVATIVE", equity_id=equity_id, fixed_income_id=fixed_income_id
    )
    customer_token, customer_id = _seed_customer_and_login(
        client, db_session, "advapi.customer5@wealthwise.test"
    )
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor5@wealthwise.test", role="advisor"
    )

    response = client.post(
        f"/api/advisor/customers/{customer_id}/override",
        headers={"Authorization": f"Bearer {advisor_token}"},
        json={"new_band": "CONSERVATIVE", "reason": "Client reported imminent liquidity need."},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {
        "override_id", "customer_id", "previous_band", "new_band", "reason",
        "note", "created_at", "assignment_id", "risk_band",
    }
    assert body["previous_band"] == "MODERATE"
    assert body["new_band"] == "CONSERVATIVE"
    assert body["risk_band"] == "CONSERVATIVE"
    assert body["note"] is None

    follow_up = client.get(
        "/api/recommendation", headers={"Authorization": f"Bearer {customer_token}"}
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["risk_band"] == "CONSERVATIVE"

    drill_in = client.get(
        f"/api/advisor/customers/{customer_id}",
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert drill_in.status_code == 200
    override_history = drill_in.json()["override_history"]
    assert len(override_history) == 1
    assert override_history[0]["previous_band"] == "MODERATE"
    assert override_history[0]["new_band"] == "CONSERVATIVE"
    assert override_history[0]["reason"] == "Client reported imminent liquidity need."


def test_override_missing_reason_returns_422_and_writes_no_rows(
    client: TestClient, db_session: Session
) -> None:
    equity_id, fixed_income_id = _seed_asset_classes(db_session)
    _publish_template(
        db_session, risk_band="MODERATE", equity_id=equity_id, fixed_income_id=fixed_income_id
    )
    _token, customer_id = _seed_customer_and_login(
        client, db_session, "advapi.customer6@wealthwise.test"
    )
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor6@wealthwise.test", role="advisor"
    )

    response = client.post(
        f"/api/advisor/customers/{customer_id}/override",
        headers={"Authorization": f"Bearer {advisor_token}"},
        json={"new_band": "CONSERVATIVE"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REASON_REQUIRED"

    follow_up = client.get(
        f"/api/advisor/customers/{customer_id}",
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["risk_band"] == "MODERATE"
    assert follow_up.json()["override_history"] == []


def test_manual_recommendation_returns_201_and_writes_exactly_one_audit_log_entry(
    client: TestClient, db_session: Session
) -> None:
    _token, customer_id = _seed_customer_and_login(
        client, db_session, "advapi.customer7@wealthwise.test"
    )
    advisor_token = _seed_user_and_login(
        client, db_session, email="advapi.advisor7@wealthwise.test", role="advisor"
    )
    note = "Recommended increasing cash weighting ahead of the client's Q4 liquidity need."

    response = client.post(
        f"/api/advisor/customers/{customer_id}/manual-recommendation",
        headers={"Authorization": f"Bearer {advisor_token}"},
        json={"note": note},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {
        "audit_entry_id", "customer_id", "advisor_id", "note", "created_at",
    }
    assert body["customer_id"] == customer_id
    assert body["note"] == note
    assert count_audit_entries(db_session, entity_type="ManualRecommendation") == 1

    compliance_token = _seed_user_and_login(
        client, db_session, email="advapi.compliance1@wealthwise.test", role="compliance"
    )
    audit_response = client.get(
        "/api/audit?entity_type=ManualRecommendation",
        headers={"Authorization": f"Bearer {compliance_token}"},
    )
    assert audit_response.status_code == 200
    entries = audit_response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["details_json"]["note"] == note


@pytest.mark.parametrize("role", ["customer", "compliance"])
@pytest.mark.parametrize("method,path_template,body", ADVISOR_ENDPOINTS)
def test_every_advisor_endpoint_rejects_customer_and_compliance_roles(
    client: TestClient,
    db_session: Session,
    method: str,
    path_template: str,
    body: dict[str, str] | None,
    role: str,
) -> None:
    method_slug = method.lower()
    _target_token, target_customer_id = _seed_customer_and_login(
        client, db_session, f"advapi.target.{method_slug}.{role}@wealthwise.test"
    )
    actor_token = _seed_user_and_login(
        client, db_session, email=f"advapi.actor.{method_slug}.{role}@wealthwise.test", role=role
    )
    path = path_template.format(customer_id=target_customer_id)

    if method == "GET":
        response = client.get(path, headers={"Authorization": f"Bearer {actor_token}"})
    else:
        response = client.post(
            path, headers={"Authorization": f"Bearer {actor_token}"}, json=body
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"
