"""`domain/advisor/repository.py` tests (E9-S1 AC1-AC5; ut-083..ut-087)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer, RiskBandAssignment
from src.domain.advisor.repository import (
    BlankReasonError,
    PreviousBandMismatchError,
    get_overrides,
    insert_override,
)
from src.domain.auth.repository import create_user


def _seed_customer_with_band(session: Session, *, email: str, risk_band: str) -> tuple[int, int]:
    user_seed = build_user(email=email)
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
    session.flush()
    session.add(
        RiskBandAssignment(
            customer_id=customer.id,
            risk_band=risk_band,
            rule_version=1,
            assigned_at="2026-09-01T09:00:00Z",
        )
    )
    session.commit()
    return customer.id, user.id


def _seed_advisor(session: Session) -> int:
    seed = build_user(email="advisor.override@wealthwise.test", role="advisor")
    user = create_user(
        session,
        email=seed.email,
        password_hash=seed.password_hash,
        role=seed.role,
        created_at=seed.created_at,
    )
    session.commit()
    return user.id


def test_insert_override_round_trips_every_column_including_omitted_note(
    db_session: Session,
) -> None:
    customer_id, _ = _seed_customer_with_band(
        db_session, email="override.customer1@wealthwise.test", risk_band="MODERATE"
    )
    advisor_id = _seed_advisor(db_session)

    override = insert_override(
        db_session,
        customer_id=customer_id,
        advisor_id=advisor_id,
        previous_band="MODERATE",
        new_band="CONSERVATIVE",
        reason="Client reported imminent liquidity need",
        note=None,
        created_at="2026-09-03T14:05:00Z",
    )
    db_session.commit()

    assert override.customer_id == customer_id
    assert override.advisor_id == advisor_id
    assert override.previous_band == "MODERATE"
    assert override.new_band == "CONSERVATIVE"
    assert override.reason == "Client reported imminent liquidity need"
    assert override.note is None
    assert override.created_at == "2026-09-03T14:05:00Z"


def test_repository_exposes_no_update_or_delete_function() -> None:
    import src.domain.advisor.repository as repository_module

    assert getattr(repository_module, "update_override", None) is None
    assert getattr(repository_module, "delete_override", None) is None


def test_get_overrides_returns_history_ordered_by_created_at_descending(
    db_session: Session,
) -> None:
    customer_id, _ = _seed_customer_with_band(
        db_session, email="override.customer2@wealthwise.test", risk_band="AGGRESSIVE"
    )
    advisor_id = _seed_advisor(db_session)

    insert_override(
        db_session, customer_id=customer_id, advisor_id=advisor_id,
        previous_band="AGGRESSIVE", new_band="MODERATE", reason="First override",
        note=None, created_at="2026-09-02T09:00:00Z",
    )
    db_session.commit()
    from src.domain.risk_profile.repository import insert_answers  # noqa: F401
    db_session.add(
        RiskBandAssignment(
            customer_id=customer_id, risk_band="MODERATE", rule_version=1,
            assigned_at="2026-09-02T09:00:01Z",
        )
    )
    db_session.commit()
    insert_override(
        db_session, customer_id=customer_id, advisor_id=advisor_id,
        previous_band="MODERATE", new_band="CONSERVATIVE", reason="Second override",
        note=None, created_at="2026-09-04T09:00:00Z",
    )
    db_session.commit()
    db_session.add(
        RiskBandAssignment(
            customer_id=customer_id, risk_band="CONSERVATIVE", rule_version=1,
            assigned_at="2026-09-04T09:00:01Z",
        )
    )
    db_session.commit()
    insert_override(
        db_session, customer_id=customer_id, advisor_id=advisor_id,
        previous_band="CONSERVATIVE", new_band="MODERATE", reason="Third override",
        note=None, created_at="2026-09-03T09:00:00Z",
    )
    db_session.commit()

    history = get_overrides(db_session, customer_id)

    assert [entry.reason for entry in history] == [
        "Second override",
        "Third override",
        "First override",
    ]


@pytest.mark.parametrize("reason", ["", None, "   "])
def test_inserting_with_an_empty_or_blank_reason_is_rejected(
    db_session: Session, reason: str | None
) -> None:
    customer_id, _ = _seed_customer_with_band(
        db_session, email="override.customer3@wealthwise.test", risk_band="MODERATE"
    )
    advisor_id = _seed_advisor(db_session)

    with pytest.raises(BlankReasonError):
        insert_override(
            db_session, customer_id=customer_id, advisor_id=advisor_id,
            previous_band="MODERATE", new_band="CONSERVATIVE", reason=reason,
            note=None, created_at="2026-09-03T14:05:00Z",
        )


def test_previous_band_must_match_the_customers_latest_risk_band_assignment(
    db_session: Session,
) -> None:
    customer_id, _ = _seed_customer_with_band(
        db_session, email="override.customer4@wealthwise.test", risk_band="MODERATE"
    )
    advisor_id = _seed_advisor(db_session)

    with pytest.raises(PreviousBandMismatchError):
        insert_override(
            db_session, customer_id=customer_id, advisor_id=advisor_id,
            previous_band="CONSERVATIVE", new_band="AGGRESSIVE",
            reason="Mismatched previous band", note=None,
            created_at="2026-09-03T14:05:00Z",
        )

    override = insert_override(
        db_session, customer_id=customer_id, advisor_id=advisor_id,
        previous_band="MODERATE", new_band="AGGRESSIVE",
        reason="Matches latest assignment", note=None,
        created_at="2026-09-03T14:06:00Z",
    )
    db_session.commit()
    assert override.previous_band == "MODERATE"
