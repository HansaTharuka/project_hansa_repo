"""`domain/goals/repository.py` tests (E7-S1 AC1-AC5; ut-073..ut-077)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer, Goal
from src.domain.auth.repository import create_user
from src.domain.goals.repository import (
    create_goal,
    get_latest_progress,
    insert_progress_snapshot,
    update_goal,
)


def _seed_customer(session: Session, email: str = "goal.customer@wealthwise.test") -> int:
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


def test_creating_three_goals_for_the_same_customer_succeeds_independently(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session)

    goal_a = create_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("250000.00"),
        target_date="2032-06-30",
        priority=1,
        created_at="2026-09-01T09:30:00Z",
    )
    db_session.commit()
    goal_b = create_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("50000.00"),
        target_date="2028-01-15",
        priority=2,
        created_at="2026-09-01T09:31:00Z",
    )
    db_session.commit()
    goal_c = create_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("15000.00"),
        target_date="2027-03-01",
        priority=3,
        created_at="2026-09-01T09:32:00Z",
    )
    db_session.commit()

    assert goal_a.target_amount == Decimal("250000.00")
    assert goal_b.target_amount == Decimal("50000.00")
    assert goal_c.target_amount == Decimal("15000.00")
    assert {goal_a.id, goal_b.id, goal_c.id} == {goal_a.id, goal_b.id, goal_c.id}
    assert len({goal_a.id, goal_b.id, goal_c.id}) == 3


def test_repository_exposes_no_update_or_delete_function_for_progress_snapshot() -> None:
    import src.domain.goals.repository as repository_module

    assert getattr(repository_module, "update_progress_snapshot", None) is None
    assert getattr(repository_module, "delete_progress_snapshot", None) is None


def test_recomputed_snapshot_for_a_new_price_date_is_a_new_row(db_session: Session) -> None:
    customer_id = _seed_customer(db_session)
    goal = create_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2030-01-01",
        priority=1,
        created_at="2026-09-01T09:30:00Z",
    )
    db_session.commit()

    insert_progress_snapshot(
        db_session,
        goal_id=goal.id,
        current_value=Decimal("25000.00"),
        percent_complete=Decimal("25.00"),
        snapshot_at="2026-09-01T10:00:00Z",
        price_date="2026-09-01",
    )
    db_session.commit()
    insert_progress_snapshot(
        db_session,
        goal_id=goal.id,
        current_value=Decimal("26000.00"),
        percent_complete=Decimal("26.00"),
        snapshot_at="2026-09-02T10:00:00Z",
        price_date="2026-09-02",
    )
    db_session.commit()

    from sqlalchemy import text

    count = db_session.execute(
        text("SELECT COUNT(*) FROM goal_progress_snapshot WHERE goal_id = :id"),
        {"id": goal.id},
    ).scalar_one()
    assert count == 2


def test_get_latest_progress_returns_the_row_with_the_maximum_snapshot_at(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session)
    goal = create_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2030-01-01",
        priority=1,
        created_at="2026-09-01T09:30:00Z",
    )
    db_session.commit()

    insert_progress_snapshot(
        db_session, goal_id=goal.id, current_value=Decimal("20000.00"),
        percent_complete=Decimal("20.00"), snapshot_at="2026-09-02T10:00:00Z",
        price_date="2026-09-02",
    )
    db_session.commit()
    insert_progress_snapshot(
        db_session, goal_id=goal.id, current_value=Decimal("18000.00"),
        percent_complete=Decimal("18.00"), snapshot_at="2026-08-31T10:00:00Z",
        price_date="2026-08-31",
    )
    db_session.commit()
    insert_progress_snapshot(
        db_session, goal_id=goal.id, current_value=Decimal("22000.00"),
        percent_complete=Decimal("22.00"), snapshot_at="2026-09-05T10:00:00Z",
        price_date="2026-09-05",
    )
    db_session.commit()

    latest = get_latest_progress(db_session, goal.id)

    assert latest is not None
    assert latest.snapshot_at == "2026-09-05T10:00:00Z"
    assert latest.current_value == Decimal("22000.00")


def test_goal_target_amount_column_is_integer_never_float() -> None:
    mapper = inspect(Goal)
    column = mapper.columns["target_amount"]
    assert column.type.python_type is int


def test_update_goal_changes_mutable_fields_in_place_without_altering_created_at(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session)
    goal = create_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2030-01-01",
        priority=3,
        created_at="2026-09-01T09:30:00Z",
    )
    db_session.commit()

    updated = update_goal(
        db_session,
        goal_id=goal.id,
        target_amount=Decimal("120000.00"),
        priority=1,
        updated_at="2026-09-03T10:20:00Z",
    )
    db_session.commit()

    from sqlalchemy import text

    row_count = db_session.execute(text("SELECT COUNT(*) FROM goal")).scalar_one()
    assert row_count == 1
    assert updated.target_amount == Decimal("120000.00")
    assert updated.priority == 1
    assert updated.created_at == "2026-09-01T09:30:00Z"
    assert updated.updated_at == "2026-09-03T10:20:00Z"
