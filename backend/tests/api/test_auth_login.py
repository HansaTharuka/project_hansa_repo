"""POST /api/auth/login (E2-S2 AC1-AC5; api-contracts.md §5.1)."""

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

KNOWN_PLAINTEXT_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "_session_factory", None)


@pytest.fixture
def client(migrated_engine: Engine) -> Generator[TestClient, None, None]:
    del migrated_engine  # activates this test's own DATABASE_URL/JWT_SECRET env
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_user_session(db_session: Session) -> Session:
    create_user(
        db_session,
        email="login.customer@wealthwise.test",
        password_hash=hash_password(KNOWN_PLAINTEXT_PASSWORD),
        role="customer",
        created_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()
    return db_session


def test_login_with_valid_credentials_returns_200_with_token_and_role(
    client: TestClient, seeded_user_session: Session
) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "login.customer@wealthwise.test", "password": KNOWN_PLAINTEXT_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["role"] == "customer"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600


def test_login_with_wrong_password_returns_401_with_no_token(
    client: TestClient, seeded_user_session: Session
) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "login.customer@wealthwise.test", "password": "wrong-password"},
    )

    assert response.status_code == 401
    body = response.json()
    assert "access_token" not in body
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_with_unknown_email_returns_401(client: TestClient, migrated_engine: Engine) -> None:
    del migrated_engine
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@wealthwise.test", "password": "whatever-password"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "something"},
        {"email": "login.customer@wealthwise.test"},
        {"email": "", "password": "something"},
        {"email": "login.customer@wealthwise.test", "password": ""},
    ],
)
def test_login_with_a_malformed_body_returns_422(
    client: TestClient, migrated_engine: Engine, payload: dict[str, str]
) -> None:
    del migrated_engine
    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 422


def test_login_response_never_contains_password_hash_or_other_credential_material(
    client: TestClient, seeded_user_session: Session
) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "login.customer@wealthwise.test", "password": KNOWN_PLAINTEXT_PASSWORD},
    )

    body_text = response.text
    assert "password_hash" not in body_text
    assert KNOWN_PLAINTEXT_PASSWORD not in body_text


def test_a_protected_endpoint_rejects_a_request_missing_the_authorization_header(
    client: TestClient, migrated_engine: Engine
) -> None:
    """E2-S2 AC5, exercised against a real protected route: `POST
    /api/admin/advance-day` is not implemented until group E, so this uses
    `GET /api/auth/me` — the one other endpoint this router adds and the
    simplest route guarded by `require_role`."""
    del migrated_engine
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_MISSING"


def test_a_protected_endpoint_rejects_a_malformed_bearer_header(
    client: TestClient, migrated_engine: Engine
) -> None:
    del migrated_engine
    response = client.get("/api/auth/me", headers={"Authorization": "not-a-bearer-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_MISSING"


def test_get_me_with_a_valid_token_returns_the_caller_identity(
    client: TestClient, seeded_user_session: Session
) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": "login.customer@wealthwise.test", "password": KNOWN_PLAINTEXT_PASSWORD},
    )
    token = login_response.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "customer"
    assert body["email"] == "login.customer@wealthwise.test"


def test_get_me_returns_404_when_the_token_subject_no_longer_exists(
    client: TestClient, seeded_user_session: Session
) -> None:
    """A valid, correctly-signed token whose user row was since deleted (not a
    realistic flow in this app, since there is no delete-user endpoint, but a
    genuine edge case for a token that outlives the row it names)."""
    login_response = client.post(
        "/api/auth/login",
        json={"email": "login.customer@wealthwise.test", "password": KNOWN_PLAINTEXT_PASSWORD},
    )
    token = login_response.json()["access_token"]

    from sqlalchemy import text

    seeded_user_session.execute(text("DELETE FROM customer"))
    seeded_user_session.execute(text("DELETE FROM user"))
    seeded_user_session.commit()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_get_me_rejects_a_token_signed_with_a_different_secret(
    client: TestClient, migrated_engine: Engine
) -> None:
    import jwt as pyjwt

    del migrated_engine
    bogus_token = pyjwt.encode(
        {"sub": "1", "role": "customer", "iat": 0, "exp": 9_999_999_999},
        "a-completely-different-secret",
        algorithm="HS256",
    )

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bogus_token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"
