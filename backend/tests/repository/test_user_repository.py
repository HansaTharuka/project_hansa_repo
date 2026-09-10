"""`domain/auth/repository.py` tests — parameterized queries only (E1-S3 AC4;
ut-039, ut-040).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import (
    create_user,
    get_customer_by_user_id,
    get_user_by_email,
    get_user_by_id,
)


def _user_row_count(session: Session) -> int:
    return session.execute(text("SELECT COUNT(*) FROM user")).scalar_one()


def test_get_user_by_email_treats_sql_injection_style_input_as_literal_data(
    db_session: Session,
) -> None:
    seed = build_user(email="genuine.customer@wealthwise.test")
    create_user(
        db_session,
        email=seed.email,
        password_hash=seed.password_hash,
        role=seed.role,
        created_at=seed.created_at,
    )
    db_session.commit()
    baseline_count = _user_row_count(db_session)

    malicious_email = "attacker@test.com'; DROP TABLE user; --"
    result = get_user_by_email(db_session, malicious_email)

    assert result is None
    assert _user_row_count(db_session) == baseline_count


def test_create_user_round_trips_an_email_containing_sql_metacharacters(
    db_session: Session,
) -> None:
    seed = build_user(email="o'brien.customer@wealthwise.test")
    baseline_count = _user_row_count(db_session)

    created = create_user(
        db_session,
        email=seed.email,
        password_hash=seed.password_hash,
        role=seed.role,
        created_at=seed.created_at,
    )
    db_session.commit()

    fetched = get_user_by_id(db_session, created.id)

    assert fetched is not None
    assert fetched.email == "o'brien.customer@wealthwise.test"
    assert _user_row_count(db_session) == baseline_count + 1


def test_get_user_by_email_returns_none_when_no_row_matches(db_session: Session) -> None:
    assert get_user_by_email(db_session, "nobody.here@wealthwise.test") is None


def test_get_customer_by_user_id_returns_none_when_user_has_no_customer_profile(
    db_session: Session,
) -> None:
    seed = build_user(email="advisor.no-profile@wealthwise.test", role="advisor")
    user = create_user(
        db_session,
        email=seed.email,
        password_hash=seed.password_hash,
        role=seed.role,
        created_at=seed.created_at,
    )
    db_session.commit()

    assert get_customer_by_user_id(db_session, user.id) is None


def test_get_customer_by_user_id_returns_the_matching_customer(db_session: Session) -> None:
    user_seed = build_user(email="priya.customer@wealthwise.test")
    user = create_user(
        db_session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id, kyc_verified=False)
    db_session.add(
        Customer(
            user_id=customer_seed.user_id,
            kyc_verified=customer_seed.kyc_verified,
            created_at=customer_seed.created_at,
        )
    )
    db_session.commit()

    fetched = get_customer_by_user_id(db_session, user.id)

    assert fetched is not None
    assert fetched.user_id == user.id
    assert fetched.kyc_verified is False


def test_get_customer_by_user_id_defaults_the_factory_to_kyc_verified_true(
    db_session: Session,
) -> None:
    user_seed = build_user(email="kenji.customer@wealthwise.test")
    user = create_user(
        db_session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id)
    db_session.add(
        Customer(
            user_id=customer_seed.user_id,
            kyc_verified=customer_seed.kyc_verified,
            created_at=customer_seed.created_at,
        )
    )
    db_session.commit()

    fetched = get_customer_by_user_id(db_session, user.id)

    assert fetched is not None
    assert fetched.kyc_verified is True
