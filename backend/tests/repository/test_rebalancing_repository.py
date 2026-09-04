"""`domain/rebalancing/repository.py` tests (E8-S1 AC1-AC5; ut-078..ut-082)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.rebalancing.repository import (
    AlreadyResolvedError,
    accept,
    dismiss,
    get_pending,
    insert_recommendation,
)
from src.types.entities import ProposedAction, ProposedActions
from src.types.enums import TradeAction

PROPOSED_ACTIONS = ProposedActions(
    actions=[
        ProposedAction(
            asset_class_id=1,
            asset_class_code="EQ_DM",
            action=TradeAction.SELL,
            amount=Decimal("3200.00"),
            units=Decimal("24.1600"),
            drift_percent=Decimal("6.40"),
        )
    ],
    threshold_bps=500,
    threshold_version=1,
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


def test_insert_recommendation_persists_pending_with_null_resolved_at(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "rebal.customer1@wealthwise.test")

    recommendation = insert_recommendation(
        db_session,
        customer_id=customer_id,
        recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS,
        generated_at="2026-09-04T08:00:00Z",
    )
    db_session.commit()

    assert recommendation.status == "pending"
    assert recommendation.proposed_actions_json == PROPOSED_ACTIONS
    assert recommendation.generated_at == "2026-09-04T08:00:00Z"
    assert recommendation.resolved_at is None


def test_transitioning_to_accepted_sets_resolved_at_and_preserves_row(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "rebal.customer2@wealthwise.test")
    recommendation = insert_recommendation(
        db_session,
        customer_id=customer_id,
        recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS,
        generated_at="2026-09-04T08:00:00Z",
    )
    db_session.commit()

    resolved = accept(
        db_session,
        recommendation_id=recommendation.recommendation_id,
        resolved_at="2026-09-04T09:12:00Z",
    )
    db_session.commit()

    assert resolved.status == "accepted"
    assert resolved.resolved_at == "2026-09-04T09:12:00Z"
    assert resolved.id == recommendation.id
    assert resolved.customer_id == customer_id
    assert resolved.proposed_actions_json == PROPOSED_ACTIONS


def test_transitioning_to_dismissed_sets_resolved_at(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "rebal.customer3@wealthwise.test")
    recommendation = insert_recommendation(
        db_session,
        customer_id=customer_id,
        recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS,
        generated_at="2026-09-04T08:00:00Z",
    )
    db_session.commit()

    resolved = dismiss(
        db_session,
        recommendation_id=recommendation.recommendation_id,
        resolved_at="2026-09-04T09:12:00Z",
    )
    db_session.commit()

    assert resolved.status == "dismissed"
    assert resolved.resolved_at == "2026-09-04T09:12:00Z"


def test_repository_exposes_no_hard_delete_function() -> None:
    import src.domain.rebalancing.repository as repository_module

    for name in dir(repository_module):
        assert "delete" not in name.lower()


def test_second_transition_on_an_already_resolved_recommendation_is_rejected(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "rebal.customer4@wealthwise.test")
    recommendation = insert_recommendation(
        db_session,
        customer_id=customer_id,
        recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS,
        generated_at="2026-09-04T08:00:00Z",
    )
    db_session.commit()
    accept(
        db_session,
        recommendation_id=recommendation.recommendation_id,
        resolved_at="2026-09-04T09:12:00Z",
    )
    db_session.commit()

    with pytest.raises(AlreadyResolvedError):
        dismiss(
            db_session,
            recommendation_id=recommendation.recommendation_id,
            resolved_at="2026-09-04T10:00:00Z",
        )

    from src.domain.rebalancing.repository import get_by_recommendation_id

    unchanged = get_by_recommendation_id(db_session, recommendation.recommendation_id)
    assert unchanged is not None
    assert unchanged.status == "accepted"
    assert unchanged.resolved_at == "2026-09-04T09:12:00Z"


def test_get_pending_returns_only_pending_rows_for_that_customer(db_session: Session) -> None:
    customer_a = _seed_customer(db_session, "rebal.customerA@wealthwise.test")
    customer_b = _seed_customer(db_session, "rebal.customerB@wealthwise.test")

    pending_a = insert_recommendation(
        db_session, customer_id=customer_a, recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS, generated_at="2026-09-04T08:00:00Z",
    )
    db_session.commit()
    resolved_a = insert_recommendation(
        db_session, customer_id=customer_a, recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS, generated_at="2026-09-04T08:01:00Z",
    )
    db_session.commit()
    accept(
        db_session,
        recommendation_id=resolved_a.recommendation_id,
        resolved_at="2026-09-04T09:00:00Z",
    )
    db_session.commit()
    insert_recommendation(
        db_session, customer_id=customer_b, recommendation_id=str(uuid.uuid4()),
        proposed_actions=PROPOSED_ACTIONS, generated_at="2026-09-04T08:02:00Z",
    )
    db_session.commit()

    pending = get_pending(db_session, customer_a)

    assert [row.recommendation_id for row in pending] == [pending_a.recommendation_id]
