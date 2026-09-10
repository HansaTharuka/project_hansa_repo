"""`domain/recommendation/service.py` — get_recommendation() (E5-S2 AC1-AC5;
ut-168..ut-172)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.recommendation.repository import publish_template
from src.domain.recommendation.service import RecommendationResult, get_recommendation
from src.domain.risk_profile.repository import insert_assignment
from src.types.entities import AllocationEntry, AllocationSet
from src.types.errors import NotFoundError

CONSERVATIVE_ALLOCATIONS = AllocationSet(
    allocations=[
        AllocationEntry(asset_class_id=1, percent_bps=7000),
        AllocationEntry(asset_class_id=2, percent_bps=3000),
    ]
)


def _seed_customer(session: Session, email: str) -> int:
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
    session.commit()
    return customer.id


def _publish_conservative_template(session: Session) -> None:
    publish_template(
        session,
        risk_band="CONSERVATIVE",
        allocations=CONSERVATIVE_ALLOCATIONS,
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


def _get_recommendation(
    session: Session, *, customer_id: int, horizon: str
) -> RecommendationResult:
    return get_recommendation(
        session,
        customer_id=customer_id,
        horizon=horizon,
        actor_id=customer_id,
        actor_role="customer",
    )


def test_get_recommendation_for_a_conservative_customer_returns_the_active_template_summing_to_100(
    db_session: Session,
) -> None:
    _publish_conservative_template(db_session)
    customer_id = _seed_customer(db_session, "recommendation.customer1@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="CONSERVATIVE")

    result = _get_recommendation(db_session, customer_id=customer_id, horizon="MEDIUM")

    assert result.risk_band == "CONSERVATIVE"
    assert sum(line.percent for line in result.allocations) == Decimal("100.00")


def test_a_customer_with_an_assignment_but_no_published_template_raises_no_active_template(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "recommendation.customer1b@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="AGGRESSIVE")

    with pytest.raises(NotFoundError) as excinfo:
        _get_recommendation(db_session, customer_id=customer_id, horizon="MEDIUM")

    assert excinfo.value.code == "NO_ACTIVE_TEMPLATE"


def test_a_customer_with_no_risk_band_assignment_raises_not_found(db_session: Session) -> None:
    _publish_conservative_template(db_session)
    customer_id = _seed_customer(db_session, "recommendation.customer2@wealthwise.test")

    with pytest.raises(NotFoundError) as excinfo:
        _get_recommendation(db_session, customer_id=customer_id, horizon="MEDIUM")

    assert excinfo.value.code == "NO_RISK_BAND_ASSIGNMENT"


def test_a_successful_call_invokes_the_audit_writer_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _publish_conservative_template(db_session)
    customer_id = _seed_customer(db_session, "recommendation.customer3@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="CONSERVATIVE")
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.recommendation.service.write_audit_entry", spy)

    _get_recommendation(db_session, customer_id=customer_id, horizon="MEDIUM")

    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "AllocationRecommendation"


def test_calling_twice_with_the_identical_band_and_horizon_selects_the_identical_template_version(
    db_session: Session,
) -> None:
    _publish_conservative_template(db_session)
    customer_id = _seed_customer(db_session, "recommendation.customer4@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="CONSERVATIVE")

    first = _get_recommendation(db_session, customer_id=customer_id, horizon="LONG")
    second = _get_recommendation(db_session, customer_id=customer_id, horizon="LONG")

    assert first.template_version == second.template_version


def test_every_allocation_percent_is_decimal_never_float(db_session: Session) -> None:
    _publish_conservative_template(db_session)
    customer_id = _seed_customer(db_session, "recommendation.customer5@wealthwise.test")
    _assign_band(db_session, customer_id=customer_id, risk_band="CONSERVATIVE")

    result = _get_recommendation(db_session, customer_id=customer_id, horizon="MEDIUM")

    total = Decimal("0")
    for line in result.allocations:
        assert isinstance(line.percent, Decimal)
        assert not isinstance(line.percent, float)
        total += line.percent
    assert total == Decimal("100.00")
