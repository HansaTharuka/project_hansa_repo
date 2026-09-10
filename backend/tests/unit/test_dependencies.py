"""`app/dependencies.py` — require_role() (E2-S2 AC5; system-design.md §9.2).

Exercises the dependency directly against a throwaway FastAPI app (not the
real `src.app.main.app`) so a role-mismatch (403) and a genuinely expired
token (401) can be tested without waiting on any other router.
"""

from __future__ import annotations

from collections.abc import Generator

import jwt as pyjwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.app.dependencies import CurrentUser, require_role
from src.app.error_handlers import register_error_handlers
from src.core.security import create_access_token

TEST_SECRET = "dependencies-test-secret-not-real"  # pragma: allowlist secret


@pytest.fixture
def guarded_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/admin-only")
    def _admin_only(user: CurrentUser = Depends(require_role("admin"))) -> dict[str, str]:
        return {"role": user.role}

    with TestClient(app) as client:
        yield client


def _token(role: str) -> str:
    return create_access_token("1", role, expiry_minutes=60, secret=TEST_SECRET)


def test_a_role_outside_the_allowed_set_is_rejected_with_403(guarded_client: TestClient) -> None:
    response = guarded_client.get(
        "/admin-only", headers={"Authorization": f"Bearer {_token('customer')}"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


def test_the_allowed_role_is_accepted(guarded_client: TestClient) -> None:
    response = guarded_client.get(
        "/admin-only", headers={"Authorization": f"Bearer {_token('admin')}"}
    )

    assert response.status_code == 200
    assert response.json() == {"role": "admin"}


def test_an_expired_token_is_rejected_with_401_token_expired(
    guarded_client: TestClient,
) -> None:
    expired = pyjwt.encode(
        {"sub": "1", "role": "admin", "iat": 0, "exp": 1},
        TEST_SECRET,
        algorithm="HS256",
    )

    response = guarded_client.get("/admin-only", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_a_bearer_header_with_no_token_after_the_prefix_is_rejected_as_token_missing(
    guarded_client: TestClient,
) -> None:
    response = guarded_client.get("/admin-only", headers={"Authorization": "Bearer "})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_MISSING"
