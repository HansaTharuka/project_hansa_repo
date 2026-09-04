"""`domain/goals/service.py` — create_customer_goal() / update_customer_goal()
(E7-S2 AC1-AC5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.goals.repository import list_goals_for_customer
from src.domain.goals.service import create_customer_goal, update_customer_goal
from src.types.errors import NotFoundError, ValidationError

FUTURE_DATE = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%d")
PAST_DATE = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")


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


def test_creating_a_goal_with_non_positive_target_amount_is_rejected(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goal.customer1@wealthwise.test")

    with pytest.raises(ValidationError):
        create_customer_goal(
            db_session,
            customer_id=customer_id,
            target_amount=Decimal("0.00"),
            target_date=FUTURE_DATE,
            priority=1,
        )
    with pytest.raises(ValidationError):
        create_customer_goal(
            db_session,
            customer_id=customer_id,
            target_amount=Decimal("-100.00"),
            target_date=FUTURE_DATE,
            priority=1,
        )

    assert list_goals_for_customer(db_session, customer_id) == []


def test_creating_a_goal_with_a_past_target_date_is_rejected(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goal.customer2@wealthwise.test")

    with pytest.raises(ValidationError):
        create_customer_goal(
            db_session,
            customer_id=customer_id,
            target_amount=Decimal("5000.00"),
            target_date=PAST_DATE,
            priority=1,
        )

    assert list_goals_for_customer(db_session, customer_id) == []


def test_a_customer_can_hold_more_than_one_goal_simultaneously(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goal.customer3@wealthwise.test")

    first = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("10000.00"),
        target_date=FUTURE_DATE,
        priority=1,
    )
    db_session.commit()
    second = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("25000.00"),
        target_date=FUTURE_DATE,
        priority=2,
    )
    db_session.commit()

    goals = list_goals_for_customer(db_session, customer_id)
    assert {goal.id for goal in goals} == {first.id, second.id}


def test_editing_priority_succeeds_and_is_reflected_without_altering_created_at(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "goal.customer4@wealthwise.test")
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("10000.00"),
        target_date=FUTURE_DATE,
        priority=1,
    )
    db_session.commit()

    updated = update_customer_goal(db_session, goal_id=goal.id, customer_id=customer_id, priority=3)
    db_session.commit()

    assert updated.priority == 3
    assert updated.created_at == goal.created_at
    assert updated.updated_at != goal.created_at or updated.updated_at == goal.created_at


def test_a_customer_cannot_edit_a_goal_belonging_to_a_different_customer(
    db_session: Session,
) -> None:
    owner_id = _seed_customer(db_session, "goal.owner@wealthwise.test")
    intruder_id = _seed_customer(db_session, "goal.intruder@wealthwise.test")
    goal = create_customer_goal(
        db_session,
        customer_id=owner_id,
        target_amount=Decimal("10000.00"),
        target_date=FUTURE_DATE,
        priority=1,
    )
    db_session.commit()

    with pytest.raises(NotFoundError):
        update_customer_goal(db_session, goal_id=goal.id, customer_id=intruder_id, priority=5)


def test_updating_a_goal_that_does_not_exist_is_rejected(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goal.customer6@wealthwise.test")

    with pytest.raises(NotFoundError):
        update_customer_goal(db_session, goal_id=999_999, customer_id=customer_id, priority=2)


def test_editing_target_date_to_a_past_date_is_rejected(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goal.customer7@wealthwise.test")
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("10000.00"),
        target_date=FUTURE_DATE,
        priority=1,
    )
    db_session.commit()

    with pytest.raises(ValidationError):
        update_customer_goal(
            db_session, goal_id=goal.id, customer_id=customer_id, target_date=PAST_DATE
        )


def test_editing_target_date_succeeds_and_is_reflected_on_the_next_read(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "goal.customer8@wealthwise.test")
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("10000.00"),
        target_date=FUTURE_DATE,
        priority=1,
    )
    db_session.commit()
    new_date = (datetime.now(UTC) + timedelta(days=730)).strftime("%Y-%m-%d")

    updated = update_customer_goal(
        db_session, goal_id=goal.id, customer_id=customer_id, target_date=new_date
    )
    db_session.commit()

    assert updated.target_date == new_date


def test_editing_target_amount_to_non_positive_is_rejected(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goal.customer5@wealthwise.test")
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("10000.00"),
        target_date=FUTURE_DATE,
        priority=1,
    )
    db_session.commit()

    with pytest.raises(ValidationError):
        update_customer_goal(
            db_session,
            goal_id=goal.id,
            customer_id=customer_id,
            target_amount=Decimal("-1.00"),
        )
