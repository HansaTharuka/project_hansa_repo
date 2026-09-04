"""Goal management service (E7-S2) — create/edit logic for customer goals,
validating `target_amount`, `target_date` and `priority`, and enforcing
per-customer ownership.

All validation happens here, before `domain.goals.repository` is ever touched
— an invalid create/edit call never persists a partial or invalid row. Dates
are compared as `YYYY-MM-DD` strings (data-models.md §2), which sort and
compare correctly lexicographically without parsing into a `date` object.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.domain.goals.repository import create_goal, get_goal, update_goal
from src.types.entities import Goal
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
