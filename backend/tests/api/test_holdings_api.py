"""GET /api/holdings (E6-S4 AC1, AC5; api-contracts.md §8.1; ut-137, ut-141)."""

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
from src.domain.holdings.csv_loader import load_seed_csvs
from src.domain.holdings.repository import get_asset_class_by_code, insert_holding

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
    return token


def test_holdings_for_a_customer_with_seeded_holdings_returns_drift_per_asset_class(
    client: TestClient, db_session: Session
) -> None:
    load_seed_csvs(db_session)
    db_session.commit()
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    fi_gov = get_asset_class_by_code(db_session, "FI_GOV")
    assert eq_dm is not None and fi_gov is not None
    token = _seed_customer_and_login(client, db_session, "holdings.customer1@wealthwise.test")

    from sqlalchemy import select

    from src.db.models import User

    user_id = db_session.execute(
        select(User.id).where(User.email == "holdings.customer1@wealthwise.test")
    ).scalar_one()
    customer_id = db_session.execute(
        select(Customer.id).where(Customer.user_id == user_id)
    ).scalar_one()
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=eq_dm.id,
        current_value=Decimal("6000.00"), as_of_date="2026-09-01",
    )
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=fi_gov.id,
        current_value=Decimal("4000.00"), as_of_date="2026-09-01",
    )
    db_session.commit()

    response = client.get("/api/holdings", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "as_of_date", "total_value", "threshold_bps", "threshold_percent", "holdings",
    }
    assert body["total_value"] == "10000.00"
    assert len(body["holdings"]) == 2
    for line in body["holdings"]:
        assert set(line.keys()) == {
            "asset_class_id", "asset_class_code", "current_value",
            "current_percent", "target_percent", "drift_percent", "exceeds_threshold",
        }


def test_holdings_for_a_customer_with_zero_holdings_returns_200_with_empty_list(
    client: TestClient, db_session: Session
) -> None:
    load_seed_csvs(db_session)
    db_session.commit()
    token = _seed_customer_and_login(client, db_session, "holdings.customer2@wealthwise.test")

    response = client.get("/api/holdings", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["as_of_date"] is None
    assert body["total_value"] == "0.00"
    assert body["holdings"] == []


def test_unauthenticated_request_returns_401(client: TestClient, migrated_engine: Engine) -> None:
    del migrated_engine
    response = client.get("/api/holdings")

    assert response.status_code == 401
