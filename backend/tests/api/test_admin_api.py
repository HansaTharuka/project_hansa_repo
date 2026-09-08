"""POST /api/admin/risk-band-rules, POST/GET /api/admin/allocation-templates,
POST /api/admin/asset-classes (E10-S3 AC1-AC5; api-contracts.md §12.3-§12.7;
ut-193..ut-197)."""

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

KNOWN_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret

VALID_QUESTIONNAIRE = {
    "questions": [
        {
            "question_id": f"Q{i}",
            "text": f"Question {i}?",
            "options": [
                {"value": "low", "label": "Low", "points": 1},
                {"value": "high", "label": "High", "points": 5},
            ],
        }
        for i in range(1, 7)
    ]
}
VALID_SCORING_RULES = {
    "bands": [
        {"risk_band": "CONSERVATIVE", "min_points": 6, "max_points": 13},
        {"risk_band": "MODERATE", "min_points": 14, "max_points": 22},
        {"risk_band": "AGGRESSIVE", "min_points": 23, "max_points": 30},
    ]
}


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
        session, email=email, password_hash=hash_password(KNOWN_PASSWORD), role=role,
        created_at="2026-09-01T09:00:00Z",
    )
    session.commit()
    response = client.post("/api/auth/login", json={"email": email, "password": KNOWN_PASSWORD})
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token


def _allocation_body(*, risk_band: str, asset_class_id: int, percent: str) -> dict[str, object]:
    return {
        "risk_band": risk_band,
        "allocations": [{"asset_class_id": asset_class_id, "percent": percent}],
    }


def _seed_asset_class(session: Session, *, code: str, name: str) -> int:
    from src.domain.holdings.repository import insert_asset_class

    asset_class = insert_asset_class(session, code=code, name=name)
    session.commit()
    return asset_class.id


def test_publishing_a_valid_questionnaire_returns_201_with_the_next_version(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="adminapi.admin1@wealthwise.test", role="admin"
    )

    response = client.post(
        "/api/admin/risk-band-rules",
        headers={"Authorization": f"Bearer {token}"},
        json={"questionnaire_json": VALID_QUESTIONNAIRE, "scoring_rules_json": VALID_SCORING_RULES},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"id", "version", "published_at", "is_active"}
    assert body["version"] == 1
    assert body["is_active"] is True


def test_publishing_a_template_summing_to_100_returns_201(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="adminapi.admin2@wealthwise.test", role="admin"
    )
    asset_class_id = _seed_asset_class(db_session, code="EQ_DM", name="Developed-Market Equity")
    body = _allocation_body(risk_band="MODERATE", asset_class_id=asset_class_id, percent="100.00")

    response = client.post(
        "/api/admin/allocation-templates",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["total_percent"] == "100.00"
    assert body["risk_band"] == "MODERATE"


@pytest.mark.parametrize(
    ("percent", "expected_sum_bps"), [("99.00", 9900), ("101.00", 10100)]
)
def test_publishing_a_template_not_summing_to_100_returns_422_and_writes_nothing(
    client: TestClient, db_session: Session, percent: str, expected_sum_bps: int
) -> None:
    token = _seed_user_and_login(
        client, db_session, email=f"adminapi.admin3.{percent}@wealthwise.test", role="admin"
    )
    asset_class_id = _seed_asset_class(
        db_session, code=f"EQ_DM_{percent}", name="Developed-Market Equity"
    )

    response = client.post(
        "/api/admin/allocation-templates",
        headers={"Authorization": f"Bearer {token}"},
        json=_allocation_body(risk_band="MODERATE", asset_class_id=asset_class_id, percent=percent),
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "TEMPLATE_SUM_INVALID"
    assert error["details"]["sum_bps"] == expected_sum_bps


def test_creating_a_new_asset_class_returns_201_with_the_created_row(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="adminapi.admin3b@wealthwise.test", role="admin"
    )

    response = client.post(
        "/api/admin/asset-classes",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "EQ_EM", "name": "Emerging-Market Equity"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "EQ_EM"
    assert body["name"] == "Emerging-Market Equity"
    assert body["id"] is not None


@pytest.mark.parametrize(
    "percent",
    ["not-a-number", "100.001"],
)
def test_publishing_a_template_with_a_malformed_percent_returns_422(
    client: TestClient, db_session: Session, percent: str
) -> None:
    token = _seed_user_and_login(
        client, db_session, email=f"adminapi.admin3c.{percent}@wealthwise.test", role="admin"
    )
    asset_class_id = _seed_asset_class(
        db_session, code=f"EQ_DMX_{percent[:3]}", name="Developed-Market Equity"
    )
    body = _allocation_body(risk_band="MODERATE", asset_class_id=asset_class_id, percent=percent)

    response = client.post(
        "/api/admin/allocation-templates",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_creating_an_asset_class_with_a_duplicate_code_returns_409(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="adminapi.admin4@wealthwise.test", role="admin"
    )
    _seed_asset_class(db_session, code="EQ_DM", name="Developed-Market Equity")

    response = client.post(
        "/api/admin/asset-classes",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "EQ_DM", "name": "Duplicate of an existing code"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_ASSET_CLASS_CODE"


@pytest.mark.parametrize("role", ["customer", "advisor", "compliance"])
@pytest.mark.parametrize(
    "path,body",
    [
        (
            "/api/admin/risk-band-rules",
            {"questionnaire_json": VALID_QUESTIONNAIRE, "scoring_rules_json": VALID_SCORING_RULES},
        ),
        ("/api/admin/allocation-templates", {"risk_band": "MODERATE", "allocations": []}),
        ("/api/admin/asset-classes", {"code": "EQ_EM", "name": "Emerging-Market Equity"}),
    ],
)
def test_non_admin_roles_are_rejected_with_403(
    client: TestClient, db_session: Session, role: str, path: str, body: dict[str, object]
) -> None:
    email = f"adminapi.{role}.{path.split('/')[-1]}@wealthwise.test"
    token = _seed_user_and_login(client, db_session, email=email, role=role)

    response = client.post(path, headers={"Authorization": f"Bearer {token}"}, json=body)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


def test_get_allocation_templates_filtered_by_risk_band_returns_all_versions_ordered_by_version(
    client: TestClient, db_session: Session
) -> None:
    token = _seed_user_and_login(
        client, db_session, email="adminapi.admin5@wealthwise.test", role="admin"
    )
    conservative_id = _seed_asset_class(db_session, code="FI_GOV", name="Government Fixed Income")
    moderate_id = _seed_asset_class(db_session, code="EQ_DM2", name="Developed-Market Equity")

    conservative_body = _allocation_body(
        risk_band="CONSERVATIVE", asset_class_id=conservative_id, percent="100.00"
    )
    moderate_body = _allocation_body(
        risk_band="MODERATE", asset_class_id=moderate_id, percent="100.00"
    )
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/admin/allocation-templates", headers=headers, json=conservative_body)
    client.post("/api/admin/allocation-templates", headers=headers, json=conservative_body)
    client.post("/api/admin/allocation-templates", headers=headers, json=moderate_body)

    response = client.get(
        "/api/admin/allocation-templates?risk_band=CONSERVATIVE",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [row["risk_band"] for row in body] == ["CONSERVATIVE", "CONSERVATIVE"]
    assert [row["version"] for row in body] == [1, 2]
