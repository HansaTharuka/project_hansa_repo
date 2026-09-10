"""`domain/auth/service.py` — authenticate() (E2-S1 AC1, AC2, AC3, AC5;
ut-049, ut-050, ut-051, ut-053).
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.security import decode_access_token, hash_password
from src.db.models import Customer
from src.domain.auth.repository import create_user, get_user_by_email
from src.domain.auth.service import authenticate
from src.types.errors import AuthenticationError

KNOWN_PLAINTEXT_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret
TEST_JWT_SECRET = "test-jwt-secret-not-real"  # pragma: allowlist secret


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url="sqlite:///:memory:",
        jwt_secret=TEST_JWT_SECRET,
        jwt_access_token_expiry_minutes=60,
    )


def _seed_user(session: Session, *, email: str, role: str) -> int:
    user = create_user(
        session,
        email=email,
        password_hash=hash_password(KNOWN_PLAINTEXT_PASSWORD),
        role=role,
        created_at="2026-09-01T09:00:00Z",
    )
    session.commit()
    return user.id


def test_authenticate_with_correct_credentials_returns_a_jwt_with_sub_and_role(
    db_session: Session,
) -> None:
    user_id = _seed_user(db_session, email="advisor@wealthwise.test", role="advisor")

    result = authenticate(
        db_session,
        email="advisor@wealthwise.test",
        password=KNOWN_PLAINTEXT_PASSWORD,
        settings=_settings(),
    )

    assert result.user_id == user_id
    assert result.role == "advisor"
    decoded = decode_access_token(result.token, secret=TEST_JWT_SECRET)
    assert decoded["sub"] == str(user_id)
    assert decoded["role"] == "advisor"


def test_authenticate_for_a_customer_includes_customer_id_claim(db_session: Session) -> None:
    user_id = _seed_user(db_session, email="customer.claim@wealthwise.test", role="customer")
    customer = Customer(user_id=user_id, kyc_verified=True, created_at="2026-09-01T09:00:00Z")
    db_session.add(customer)
    db_session.commit()

    result = authenticate(
        db_session,
        email="customer.claim@wealthwise.test",
        password=KNOWN_PLAINTEXT_PASSWORD,
        settings=_settings(),
    )

    decoded = decode_access_token(result.token, secret=TEST_JWT_SECRET)
    assert decoded["customer_id"] == customer.id


def test_authenticate_for_a_non_customer_role_has_no_customer_id_claim(
    db_session: Session,
) -> None:
    _seed_user(db_session, email="advisor.claim@wealthwise.test", role="advisor")

    result = authenticate(
        db_session,
        email="advisor.claim@wealthwise.test",
        password=KNOWN_PLAINTEXT_PASSWORD,
        settings=_settings(),
    )

    decoded = decode_access_token(result.token, secret=TEST_JWT_SECRET)
    assert "customer_id" not in decoded


def test_authenticate_matches_email_case_insensitively(db_session: Session) -> None:
    _seed_user(db_session, email="mixedcase@wealthwise.test", role="advisor")

    result = authenticate(
        db_session,
        email="MixedCase@WealthWise.Test",
        password=KNOWN_PLAINTEXT_PASSWORD,
        settings=_settings(),
    )

    assert result.role == "advisor"


def test_authenticate_wrong_password_and_unknown_email_raise_the_identical_error(
    db_session: Session,
) -> None:
    _seed_user(db_session, email="customer@wealthwise.test", role="customer")

    with pytest.raises(AuthenticationError) as wrong_password_excinfo:
        authenticate(
            db_session,
            email="customer@wealthwise.test",
            password="wrong-password",
            settings=_settings(),
        )

    with pytest.raises(AuthenticationError) as unknown_email_excinfo:
        authenticate(
            db_session,
            email="nobody@wealthwise.test",
            password=KNOWN_PLAINTEXT_PASSWORD,
            settings=_settings(),
        )

    assert type(wrong_password_excinfo.value) is type(unknown_email_excinfo.value)
    assert str(wrong_password_excinfo.value) == str(unknown_email_excinfo.value)
    assert wrong_password_excinfo.value.code == unknown_email_excinfo.value.code


def test_authenticate_unknown_email_creates_no_row(db_session: Session) -> None:
    with pytest.raises(AuthenticationError):
        authenticate(
            db_session, email="ghost@wealthwise.test", password="whatever", settings=_settings()
        )

    assert get_user_by_email(db_session, "ghost@wealthwise.test") is None


def test_service_exposes_no_register_or_create_account_function() -> None:
    import src.domain.auth.service as service_module

    assert getattr(service_module, "register", None) is None
    assert getattr(service_module, "create_account", None) is None
    assert not any(name.startswith("register") for name in dir(service_module))


def test_authenticate_never_logs_the_plaintext_password_on_success_or_failure(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    _seed_user(db_session, email="watched@wealthwise.test", role="customer")

    with caplog.at_level(logging.DEBUG):
        authenticate(
            db_session,
            email="watched@wealthwise.test",
            password=KNOWN_PLAINTEXT_PASSWORD,
            settings=_settings(),
        )
        with pytest.raises(AuthenticationError):
            authenticate(
                db_session,
                email="watched@wealthwise.test",
                password="totally-wrong",
                settings=_settings(),
            )
        with pytest.raises(AuthenticationError):
            authenticate(
                db_session,
                email="ghost2@wealthwise.test",
                password=KNOWN_PLAINTEXT_PASSWORD,
                settings=_settings(),
            )

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert KNOWN_PLAINTEXT_PASSWORD not in log_text
    assert "totally-wrong" not in log_text
