"""Goal management service (E7-S2) — create/edit logic for customer goals,
validating `target_amount`, `target_date` and `priority`, and enforcing
per-customer ownership.

All validation happens here, before `domain.goals.repository` is ever touched
— an invalid create/edit call never persists a partial or invalid row. Dates
are compared as `YYYY-MM-DD` strings (data-models.md §2), which sort and
compare correctly lexicographically without parsing into a `date` object.

`recompute_customer_goal_progress` (E7-S3) is the goal-progress half of the
advance-a-day flow: it snapshots every one of `customer_id`'s goals against
their shared portfolio value for one simulated `price_date`. Idempotency for
a repeated `price_date` relies on `GoalProgressSnapshot`'s
`UNIQUE(goal_id, price_date)` index, not a check-then-act read — each insert
runs inside its own `SAVEPOINT` (`session.begin_nested()`) so a duplicate's
`IntegrityError` rolls back only that one insert, leaving the rest of the
caller's in-flight transaction (e.g. `holdings.service.advance_day`'s NAV
inserts) untouched (AC4).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.goals.progress import compute_percent_complete
from src.domain.goals.repository import (
    create_goal,
    get_goal,
    get_latest_progress,
    insert_progress_snapshot,
    list_goals_for_customer,
    list_progress_snapshots,
    update_goal,
)
from src.types.entities import Goal, GoalProgressSnapshot
from src.types.errors import NotFoundError, ValidationError


def create_customer_goal(
    session: Session,
    *,
    customer_id: int,
    target_amount: Decimal,
    target_date: str,
    priority: int,
) -> Goal:
    """Create one `Goal` for `customer_id` (AC1, AC2, AC3).

    Rejects `target_amount <= 0` and a `target_date` in the past — both before
    any row is persisted.
    """
    _validate_target_amount(target_amount)
    _validate_target_date(target_date)

    return create_goal(
        session,
        customer_id=customer_id,
        target_amount=target_amount,
        target_date=target_date,
        priority=priority,
        created_at=_now_iso(),
    )


def update_customer_goal(
    session: Session,
    *,
    goal_id: int,
    customer_id: int,
    target_amount: Decimal | None = None,
    target_date: str | None = None,
    priority: int | None = None,
) -> Goal:
    """Edit an existing goal's mutable fields (AC4), enforcing ownership (AC5).

    `created_at` is never altered — only `repository.update_goal` touches
    `updated_at`.
    """
    goal = get_goal(session, goal_id)
    if goal is None:
        raise NotFoundError(f"Goal {goal_id} does not exist.", code="GOAL_NOT_FOUND")
    if goal.customer_id != customer_id:
        raise NotFoundError(
            f"Goal {goal_id} does not belong to customer {customer_id}.",
            code="GOAL_NOT_FOUND",
        )

    if target_amount is not None:
        _validate_target_amount(target_amount)
    if target_date is not None:
        _validate_target_date(target_date)

    return update_goal(
        session,
        goal_id=goal_id,
        updated_at=_now_iso(),
        target_amount=target_amount,
        target_date=target_date,
        priority=priority,
    )


def list_customer_goals_with_progress(
    session: Session, customer_id: int
) -> list[tuple[Goal, Decimal | None]]:
    """Every goal owned by `customer_id`, each paired with its latest
    `percent_complete` (or `None` if no snapshot exists yet), ordered
    `priority ASC, target_date ASC` (E7-S4 AC3, api-contracts.md §9.2).

    Scoping to `customer_id` happens once here — the API layer never accepts
    a `customer_id` from the request, only from the caller's JWT.
    """
    goals = list_goals_for_customer(session, customer_id)
    paired = [
        (goal, get_latest_percent_complete(session, goal.id))
        for goal in goals
    ]
    return sorted(paired, key=lambda pair: (pair[0].priority, pair[0].target_date))


def get_goal_progress(
    session: Session, *, goal_id: int, customer_id: int
) -> tuple[Goal, list[GoalProgressSnapshot]]:
    """A goal's full snapshot history, oldest first, enforcing ownership
    (E7-S4 AC4; api-contracts.md §9.4)."""
    goal = get_goal(session, goal_id)
    if goal is None or goal.customer_id != customer_id:
        raise NotFoundError(f"Goal {goal_id} does not exist.", code="GOAL_NOT_FOUND")
    return goal, list_progress_snapshots(session, goal_id)


def get_latest_percent_complete(session: Session, goal_id: int) -> Decimal | None:
    """The most recent `percent_complete` for `goal_id`, or `None` if the
    goal has never been snapshotted yet."""
    latest = get_latest_progress(session, goal_id)
    return latest.percent_complete if latest is not None else None


def recompute_customer_goal_progress(
    session: Session,
    *,
    customer_id: int,
    total_holdings_value: Decimal,
    price_date: str,
    snapshot_at: str,
) -> list[GoalProgressSnapshot]:
    """Snapshot `percent_complete` for every one of `customer_id`'s goals
    against `total_holdings_value` for `price_date` (AC1, AC2, AC3).

    A goal already snapshotted for `price_date` is silently skipped (AC4) —
    the `IntegrityError` from `GoalProgressSnapshot`'s unique index is caught
    per-goal via a nested `SAVEPOINT`, never by rolling back the whole call.
    """
    snapshots: list[GoalProgressSnapshot] = []
    for goal in list_goals_for_customer(session, customer_id):
        percent_complete = compute_percent_complete(total_holdings_value, goal.target_amount)
        try:
            with session.begin_nested():
                snapshot = insert_progress_snapshot(
                    session,
                    goal_id=goal.id,
                    current_value=total_holdings_value,
                    percent_complete=percent_complete,
                    snapshot_at=snapshot_at,
                    price_date=price_date,
                )
            snapshots.append(snapshot)
        except IntegrityError:
            continue
    return snapshots


def _validate_target_amount(target_amount: Decimal) -> None:
    if target_amount <= 0:
        raise ValidationError(
            "target_amount must be greater than zero.",
            code="VALIDATION_ERROR",
            details={"target_amount": str(target_amount)},
        )


def _validate_target_date(target_date: str) -> None:
    if target_date < _today_iso_date():
        raise ValidationError(
            "target_date cannot be in the past.",
            code="VALIDATION_ERROR",
            details={"target_date": target_date},
        )


def _today_iso_date() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
