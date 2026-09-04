"""GET /api/audit (E3-S3 AC1-AC5; api-contracts.md §13.1; ut-126..ut-130)."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

import src.db.session as db_session
from src.app.main import app
from src.core.security import hash_password
from src.domain.audit.repository import insert_audit_entry
from src.domain.auth.repository import create_user

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


def _seed_audited_fixture(session: Session, *, actor_id: int) -> None:
    entity_types = [
        "RiskBandAssignment",
        "AllocationRecommendation",
        "RebalancingRecommendation",
        "AdvisorOverride",
        "ManualRecommendation",
        "RiskBandRule",
        "AllocationTemplate",
        "AssetClass",
        "RebalancingThreshold",
    ]
    for index, entity_type in enumerate(entity_types):
        insert_audit_entry(
            session,
            entity_type=entity_type,
            entity_id=str(index),
            actor_id=actor_id,
            actor_role="admin",
            action="CREATE_ASSET_CLASS",
            timestamp=f"2026-09-0{index + 1}T09:00:00Z",
            details_json={"seq": index},
        )
    session.commit()


def test_compliance_role_gets_a_paginated_page_of_matching_entries(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="audit.compliance1@wealthwise.test", role="compliance"
    )
    _seed_audited_fixture(db_session, actor_id=1)

    response = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"total", "limit", "offset", "entries"}
    assert body["total"] == 9
    assert len(body["entries"]) == 9


@pytest.mark.parametrize("role", ["customer", "advisor", "admin"])
def test_non_compliance_roles_are_rejected_with_403(
    client: TestClient, db_session: Session, role: str
) -> None:
    token = _seed_user_and_login(
        client, db_session, email=f"audit.{role}@wealthwise.test", role=role
    )

    response = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_write_verbs_return_405_not_404_or_403(
    client: TestClient, db_session: Session, method: str
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="audit.compliance2@wealthwise.test", role="compliance"
    )

    response = client.request(
        method, "/api/audit", headers={"Authorization": f"Bearer {token}"}, json={}
    )

    assert response.status_code == 405


def test_filtering_by_entity_type_returns_only_exact_matches(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="audit.compliance3@wealthwise.test", role="compliance"
    )
    _seed_audited_fixture(db_session, actor_id=1)

    response = client.get(
        "/api/audit?entity_type=RiskBandAssignment",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert all(entry["entity_type"] == "RiskBandAssignment" for entry in body["entries"])


def test_unauthenticated_request_returns_401(client: TestClient, migrated_engine: Engine) -> None:
    del migrated_engine
    response = client.get("/api/audit")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_MISSING"
