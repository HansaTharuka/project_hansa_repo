"""Goal (mutable) / GoalProgressSnapshot (append-only) persistence (E7-S1).

`Goal` is one of only two genuinely mutable domain tables (data-models.md §4.7):
`update_goal` edits `target_amount`/`target_date`/`priority` in place without ever
touching `created_at`. `GoalProgressSnapshot` is append-only — no `update_*`/
`delete_*` function exists for it (AC2). `target_amount` and `current_value`
round-trip as `Decimal`, converted through `types.fixedpoint` at the repository
boundary only (AC4, NFR-01).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Goal as GoalRow
from src.db.models import GoalProgressSnapshot as GoalProgressSnapshotRow
from src.types.entities import Goal as GoalEntity
from src.types.entities import GoalProgressSnapshot as GoalProgressSnapshotEntity
from src.types.fixedpoint import (
    basis_points_to_decimal,
    decimal_to_basis_points,
    decimal_to_minor_units,
    minor_units_to_decimal,
)


def create_goal(
    session: Session,
    *,
    customer_id: int,
    target_amount: Decimal,
    target_date: str,
    priority: int,
    created_at: str,
) -> GoalEntity:
    """Insert one `Goal` row; `updated_at` starts equal to `created_at`."""
    row = GoalRow(
        customer_id=customer_id,
        target_amount=decimal_to_minor_units(target_amount),
        target_date=target_date,
        priority=priority,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(row)
    session.flush()
    return _goal_to_entity(row)


def update_goal(
    session: Session,
    *,
    goal_id: int,
    updated_at: str,
    target_amount: Decimal | None = None,
    target_date: str | None = None,
    priority: int | None = None,
) -> GoalEntity:
    """Edit mutable fields of an existing `Goal` row in place. `created_at` untouched."""
    row = session.execute(select(GoalRow).where(GoalRow.id == goal_id)).scalar_one()
    if target_amount is not None:
        row.target_amount = decimal_to_minor_units(target_amount)
    if target_date is not None:
        row.target_date = target_date
    if priority is not None:
        row.priority = priority
    row.updated_at = updated_at
    session.flush()
    return _goal_to_entity(row)


def get_goal(session: Session, goal_id: int) -> GoalEntity | None:
    """Look up a `Goal` by its primary key."""
    row = session.execute(select(GoalRow).where(GoalRow.id == goal_id)).scalar_one_or_none()
    return _goal_to_entity(row) if row is not None else None


def list_goals_for_customer(session: Session, customer_id: int) -> list[GoalEntity]:
    """All `Goal` rows owned by `customer_id`, ordered by id (insertion order)."""
    statement = select(GoalRow).where(GoalRow.customer_id == customer_id).order_by(GoalRow.id)
    rows = session.execute(statement).scalars().all()
    return [_goal_to_entity(row) for row in rows]


def list_customer_ids_with_goals(session: Session) -> list[int]:
    """Distinct `customer_id` values with at least one `Goal` row, ordered
    (E7-S3 AC1/AC5 — the advance-a-day flow recomputes every active goal, not
    only goals belonging to customers who also hold a `Holding` row)."""
    statement = select(GoalRow.customer_id).distinct().order_by(GoalRow.customer_id)
    return list(session.execute(statement).scalars().all())


def insert_progress_snapshot(
    session: Session,
    *,
    goal_id: int,
    current_value: Decimal,
    percent_complete: Decimal,
    snapshot_at: str,
    price_date: str,
) -> GoalProgressSnapshotEntity:
    """Insert one append-only `GoalProgressSnapshot` row."""
    row = GoalProgressSnapshotRow(
        goal_id=goal_id,
        current_value=decimal_to_minor_units(current_value),
        percent_complete=decimal_to_basis_points(percent_complete),
        snapshot_at=snapshot_at,
        price_date=price_date,
    )
    session.add(row)
    session.flush()
    return _progress_to_entity(row)


def get_latest_progress(session: Session, goal_id: int) -> GoalProgressSnapshotEntity | None:
    """The `GoalProgressSnapshot` with the most recent `snapshot_at` for `goal_id`."""
    statement = (
        select(GoalProgressSnapshotRow)
        .where(GoalProgressSnapshotRow.goal_id == goal_id)
        .order_by(GoalProgressSnapshotRow.snapshot_at.desc())
        .limit(1)
    )
    row = session.execute(statement).scalar_one_or_none()
    return _progress_to_entity(row) if row is not None else None


def _goal_to_entity(row: GoalRow) -> GoalEntity:
    return GoalEntity(
        id=row.id,
        customer_id=row.customer_id,
        target_amount=minor_units_to_decimal(row.target_amount),
        target_date=row.target_date,
        priority=row.priority,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _progress_to_entity(row: GoalProgressSnapshotRow) -> GoalProgressSnapshotEntity:
    return GoalProgressSnapshotEntity(
        id=row.id,
        goal_id=row.goal_id,
        current_value=minor_units_to_decimal(row.current_value),
        percent_complete=basis_points_to_decimal(row.percent_complete),
        snapshot_at=row.snapshot_at,
        price_date=row.price_date,
    )
