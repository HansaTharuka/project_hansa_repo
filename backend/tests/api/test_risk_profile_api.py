"""POST /api/risk-profile/submit, GET /api/risk-profile/latest (E4-S3 AC1-AC5;
api-contracts.md §6.2, §6.3; ut-163..ut-167)."""

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
from src.domain.risk_profile.repository import publish_rule
from src.types.entities import BandRange, Question, Questionnaire, QuestionOption, ScoringRules

KNOWN_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret

QUESTIONNAIRE = Questionnaire(
    questions=[
        Question(
            question_id=f"Q{i}",
            text=f"Question {i}?",
            options=[
                QuestionOption(value="low", label="Low", points=1),
                QuestionOption(value="high", label="High", points=5),
            ],
        )
        for i in range(1, 7)
    ]
)
SCORING_RULES = ScoringRules(
    bands=[
        BandRange(risk_band="CONSERVATIVE", min_points=6, max_points=13),
        BandRange(risk_band="MODERATE", min_points=14, max_points=22),
        BandRange(risk_band="AGGRESSIVE", min_points=23, max_points=30),
    ]
)
ALL_LOW_ANSWERS = [{"question_id": f"Q{i}", "answer_value": "low"} for i in range(1, 7)]


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine
    with TestClient(app) as test_client:
        yield test_client


def _publish_rule(session: Session) -> None:
    publish_rule(
        session,
        questionnaire=QUESTIONNAIRE,
        scoring_rules=SCORING_RULES,
        published_at="2026-09-01T09:00:00Z",
    )
    session.commit()


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


def _seed_customer_and_login(client: TestClient, session: Session, email: str) -> str:
    from tests.factories import build_customer, build_user

    from src.db.models import Customer

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


def test_a_complete_valid_answer_set_returns_201_with_the_assigned_risk_band(
    client: TestClient, db_session: Session
) -> None:
    _publish_rule(db_session)
    token = _seed_customer_and_login(client, db_session, "riskapi.customer1@wealthwise.test")

    response = client.post(
        "/api/risk-profile/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"answers": ALL_LOW_ANSWERS},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"assignment_id", "risk_band", "rule_version", "assigned_at"}
    assert body["risk_band"] == "CONSERVATIVE"
    assert body["rule_version"] == 1


def test_an_incomplete_answer_set_returns_422_and_writes_nothing(
    client: TestClient, db_session: Session
) -> None:
    _publish_rule(db_session)
    token = _seed_customer_and_login(client, db_session, "riskapi.customer2@wealthwise.test")

    response = client.post(
        "/api/risk-profile/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"answers": ALL_LOW_ANSWERS[:5]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INCOMPLETE_QUESTIONNAIRE"

    latest = client.get("/api/risk-profile/latest", headers={"Authorization": f"Bearer {token}"})
    assert latest.status_code == 404


def test_a_duplicate_question_id_in_the_answer_set_returns_422(
    client: TestClient, db_session: Session
) -> None:
    _publish_rule(db_session)
    token = _seed_customer_and_login(client, db_session, "riskapi.customer2b@wealthwise.test")
    duplicated = [*ALL_LOW_ANSWERS, {"question_id": "Q1", "answer_value": "high"}]

    response = client.post(
        "/api/risk-profile/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"answers": duplicated},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INCOMPLETE_QUESTIONNAIRE"


@pytest.mark.parametrize("role", ["advisor", "admin"])
def test_non_customer_roles_are_rejected_with_403(
    client: TestClient, db_session: Session, role: str
) -> None:
    _publish_rule(db_session)
    token = _seed_user_and_login(
        client, db_session, email=f"riskapi.{role}@wealthwise.test", role=role
    )

    response = client.post(
        "/api/risk-profile/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"answers": ALL_LOW_ANSWERS},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


def test_latest_returns_the_most_recent_assignment_or_404_when_none_exists(
    client: TestClient, db_session: Session
) -> None:
    _publish_rule(db_session)
    token = _seed_customer_and_login(client, db_session, "riskapi.customer3@wealthwise.test")

    before = client.get("/api/risk-profile/latest", headers={"Authorization": f"Bearer {token}"})
    assert before.status_code == 404
    assert before.json()["error"]["code"] == "NO_RISK_BAND_ASSIGNMENT"

    submit = client.post(
        "/api/risk-profile/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"answers": ALL_LOW_ANSWERS},
    )
    assert submit.status_code == 201

    after = client.get("/api/risk-profile/latest", headers={"Authorization": f"Bearer {token}"})
    assert after.status_code == 200
    body = after.json()
    assert set(body.keys()) == {
        "assignment_id", "customer_id", "risk_band", "rule_version", "assigned_at",
    }
    assert body["risk_band"] == "CONSERVATIVE"


def test_unauthenticated_requests_return_401(client: TestClient, db_session: Session) -> None:
    _publish_rule(db_session)

    submit = client.post("/api/risk-profile/submit", json={"answers": ALL_LOW_ANSWERS})
    latest = client.get("/api/risk-profile/latest")

    assert submit.status_code == 401
    assert latest.status_code == 401
