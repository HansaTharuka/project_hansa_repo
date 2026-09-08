"""POST/GET/PATCH /api/goals, GET /api/goals/{goal_id}/progress — customer-role
goal CRUD and progress history (E7-S4 AC1-AC5; api-contracts.md §9.1-§9.4).

`customer_id` is always taken from the JWT (`CurrentUser.customer_id`), never
from the request body or path — `GET /api/goals` can never widen its scope
(AC3, system-design.md D12). This router calls `domain.goals.service` only,
never `domain.goals.repository` directly (system-design.md D3).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.goals.service import (
    create_customer_goal,
    get_goal_progress,
    get_latest_percent_complete,
    list_customer_goals_with_progress,
    update_customer_goal,
)
from src.types.entities import Goal, GoalProgressSnapshot
from src.types.errors import ValidationError

router = APIRouter(prefix="/api/goals", tags=["goals"])

MONEY_SCALE = Decimal("0.01")


class GoalCreateRequest(BaseModel):
    """api-contracts.md §9.1 — `customer_id` is never part of the body."""

    target_amount: str = Field(min_length=1)
    target_date: str = Field(min_length=1)
    priority: int = Field(ge=1, le=5)


class GoalUpdateRequest(BaseModel):
    """api-contracts.md §9.3 — a partial update; at least one field required."""

    target_amount: str | None = None
    target_date: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class GoalResponse(BaseModel):
    """One goal, shaped identically across create/list/update (api-contracts.md §9.1)."""

    id: int
    customer_id: int
    target_amount: str
    target_date: str
    priority: int
    created_at: str
    updated_at: str
    percent_complete: str | None


class GoalProgressSnapshotResponse(BaseModel):
    """One `GoalProgressSnapshot` row (api-contracts.md §9.4)."""

    id: int
    current_value: str
    percent_complete: str
    snapshot_at: str
    price_date: str


class GoalProgressResponse(BaseModel):
    """The ordered snapshot history for one goal (api-contracts.md §9.4)."""

    goal_id: int
    target_amount: str
    snapshots: list[GoalProgressSnapshotResponse]


@router.post("", status_code=201)
def create_goal(
    body: GoalCreateRequest,
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> GoalResponse:
    """Create one `Goal` for the authenticated customer (AC1). A non-positive
    `target_amount` raises `ValidationError` before any row is written (AC2)."""
    goal = create_customer_goal(
        session,
        customer_id=user.customer_id or 0,
        target_amount=_parse_money(body.target_amount),
        target_date=body.target_date,
        priority=body.priority,
    )
    return _to_response(goal, percent_complete=None)


@router.get("", status_code=200)
def list_goals(
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> list[GoalResponse]:
    """Only the authenticated customer's own goals — there is no query
    parameter capable of widening the scope (AC3)."""
    pairs = list_customer_goals_with_progress(session, user.customer_id or 0)
    return [_to_response(goal, percent_complete=percent) for goal, percent in pairs]


@router.patch("/{goal_id}", status_code=200)
def update_goal(
    goal_id: int,
    body: GoalUpdateRequest,
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> GoalResponse:
    """Edit `target_amount`/`target_date`/`priority` in place (AC5), enforcing
    ownership — an unknown or another customer's `goal_id` raises `NotFoundError`."""
    if body.target_amount is None and body.target_date is None and body.priority is None:
        raise ValidationError("At least one field must be supplied.", code="VALIDATION_ERROR")
    goal = update_customer_goal(
        session,
        goal_id=goal_id,
        customer_id=user.customer_id or 0,
        target_amount=_parse_money(body.target_amount) if body.target_amount is not None else None,
        target_date=body.target_date,
        priority=body.priority,
    )
    percent_complete = get_latest_percent_complete(session, goal.id)
    return _to_response(goal, percent_complete=percent_complete)


@router.get("/{goal_id}/progress", status_code=200)
def get_progress(
    goal_id: int,
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> GoalProgressResponse:
    """The ordered snapshot history for one goal, oldest first (AC4)."""
    goal, snapshots = get_goal_progress(
        session, goal_id=goal_id, customer_id=user.customer_id or 0
    )
    return GoalProgressResponse(
        goal_id=goal.id,
        target_amount=str(goal.target_amount),
        snapshots=[_snapshot_to_response(snapshot) for snapshot in snapshots],
    )


def _parse_money(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(
            f"{value!r} is not a valid money amount.", code="VALIDATION_ERROR"
        ) from exc
    if parsed != parsed.quantize(MONEY_SCALE):
        raise ValidationError(
            f"{value!r} must have exactly 2 decimal places.", code="VALIDATION_ERROR"
        )
    return parsed


def _to_response(goal: Goal, *, percent_complete: Decimal | None) -> GoalResponse:
    return GoalResponse(
        id=goal.id,
        customer_id=goal.customer_id,
        target_amount=str(goal.target_amount),
        target_date=goal.target_date,
        priority=goal.priority,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
        percent_complete=str(percent_complete) if percent_complete is not None else None,
    )


def _snapshot_to_response(snapshot: GoalProgressSnapshot) -> GoalProgressSnapshotResponse:
    return GoalProgressSnapshotResponse(
        id=snapshot.id,
        current_value=str(snapshot.current_value),
        percent_complete=str(snapshot.percent_complete),
        snapshot_at=snapshot.snapshot_at,
        price_date=snapshot.price_date,
    )
