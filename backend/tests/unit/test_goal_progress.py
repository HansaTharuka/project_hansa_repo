"""`domain/goals/progress.py` (compute_percent_complete) and
`domain/goals/service.py` (recompute_customer_goal_progress) — E7-S3 AC1-AC4;
ut-142..ut-145."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.goals.progress import compute_percent_complete
from src.domain.goals.repository import list_goals_for_customer
from src.domain.goals.service import create_customer_goal, recompute_customer_goal_progress


def test_percent_complete_is_current_over_target_times_100(monkeypatch: object) -> None:
    assert compute_percent_complete(Decimal("62500.00"), Decimal("250000.00")) == Decimal("25.00")


def test_percent_complete_is_capped_at_200_percent_when_far_over_target() -> None:
    result = compute_percent_complete(Decimal("1000000.00"), Decimal("100000.00"))
    assert result == Decimal("200.00")


def test_percent_complete_at_exactly_the_target_is_100_percent() -> None:
    assert compute_percent_complete(Decimal("50000.00"), Decimal("50000.00")) == Decimal("100.00")


def test_zero_current_value_yields_zero_percent_without_raising() -> None:
    assert compute_percent_complete(Decimal("0.00"), Decimal("50000.00")) == Decimal("0.00")


def test_no_float_appears_in_the_computed_result() -> None:
    result = compute_percent_complete(Decimal("33333.33"), Decimal("100000.00"))
    assert isinstance(result, Decimal)
    assert not isinstance(result, float)


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


def test_recompute_creates_exactly_one_snapshot_per_active_goal(db_session: Session) -> None:
    customer_id = _seed_customer(db_session, "goalprogress.customer1@wealthwise.test")
    goal_one = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2030-01-01",
        priority=1,
    )
    goal_two = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("50000.00"),
        target_date="2031-01-01",
        priority=2,
    )
    db_session.commit()

    snapshots = recompute_customer_goal_progress(
        db_session,
        customer_id=customer_id,
        total_holdings_value=Decimal("25000.00"),
        price_date="2026-09-02",
        snapshot_at="2026-09-02T00:00:00Z",
    )
    db_session.commit()

    assert {s.goal_id for s in snapshots} == {goal_one.id, goal_two.id}
    assert len(snapshots) == 2


def test_recompute_twice_for_the_same_price_date_does_not_create_a_duplicate_snapshot(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "goalprogress.customer2@wealthwise.test")
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2030-01-01",
        priority=1,
    )
    db_session.commit()

    first = recompute_customer_goal_progress(
        db_session,
        customer_id=customer_id,
        total_holdings_value=Decimal("25000.00"),
        price_date="2026-09-02",
        snapshot_at="2026-09-02T00:00:00Z",
    )
    db_session.commit()
    second = recompute_customer_goal_progress(
        db_session,
        customer_id=customer_id,
        total_holdings_value=Decimal("30000.00"),
        price_date="2026-09-02",
        snapshot_at="2026-09-02T01:00:00Z",
    )
    db_session.commit()

    assert len(first) == 1
    assert len(second) == 0  # already snapshotted for this goal/price_date pair

    from sqlalchemy import text

    count = db_session.execute(
        text("SELECT COUNT(*) FROM goal_progress_snapshot WHERE goal_id = :goal_id"),
        {"goal_id": goal.id},
    ).scalar_one()
    assert count == 1


def test_recompute_with_a_customer_owning_no_goals_returns_an_empty_list(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "goalprogress.customer3@wealthwise.test")

    snapshots = recompute_customer_goal_progress(
        db_session,
        customer_id=customer_id,
        total_holdings_value=Decimal("1000.00"),
        price_date="2026-09-02",
        snapshot_at="2026-09-02T00:00:00Z",
    )

    assert snapshots == []


def test_a_goal_with_zero_current_holdings_value_gets_a_zero_percent_snapshot(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "goalprogress.customer4@wealthwise.test")
    create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("100000.00"),
        target_date="2030-01-01",
        priority=1,
    )
    db_session.commit()

    snapshots = recompute_customer_goal_progress(
        db_session,
        customer_id=customer_id,
        total_holdings_value=Decimal("0.00"),
        price_date="2026-09-02",
        snapshot_at="2026-09-02T00:00:00Z",
    )

    assert len(snapshots) == 1
    assert snapshots[0].percent_complete == Decimal("0.00")


def test_advance_day_creates_a_goal_progress_snapshot_with_no_separate_manual_call(
    db_session: Session,
) -> None:
    """E7-S3 AC5 / ut-146 — `advance_day` itself triggers the recompute."""
    from src.domain.holdings.csv_loader import load_seed_csvs
    from src.domain.holdings.repository import get_asset_class_by_code, insert_holding
    from src.domain.holdings.service import advance_day

    load_seed_csvs(db_session)
    db_session.commit()
    customer_id = _seed_customer(db_session, "goalprogress.advanceday@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    assert eq_dm is not None
    insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=eq_dm.id,
        current_value=Decimal("5000.00"),
        as_of_date="2026-09-01",
    )
    goal = create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("20000.00"),
        target_date="2030-01-01",
        priority=1,
    )
    db_session.commit()

    result = advance_day(db_session)
    db_session.commit()

    assert result.goal_snapshots_created == 1

    from sqlalchemy import text

    row = db_session.execute(
        text(
            "SELECT percent_complete, price_date FROM goal_progress_snapshot WHERE goal_id = :id"
        ),
        {"id": goal.id},
    ).one()
    assert row.price_date == result.price_date
    assert row.percent_complete == 2500  # 5000/20000 = 25.00% = 2500 bps


def test_list_goals_for_customer_reflects_created_goals_after_commit(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "goalprogress.customer5@wealthwise.test")
    create_customer_goal(
        db_session,
        customer_id=customer_id,
        target_amount=Decimal("10000.00"),
        target_date="2030-01-01",
        priority=1,
    )
    db_session.commit()

    assert len(list_goals_for_customer(db_session, customer_id)) == 1
