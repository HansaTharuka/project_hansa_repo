"""AdvisorOverride persistence — append-only, audited (E9-S1 AC1-AC5; NFR-02).

No `update_*`/`delete_*` function exists for `AdvisorOverride` anywhere in this
module (AC2). `reason` is mandatory: blank or whitespace-only is rejected before
any row is persisted (AC4). `previous_band` must match the customer's most recent
`RiskBandAssignment.risk_band` — `ORDER BY assigned_at DESC, id DESC LIMIT 1`, the
same "current band" rule data-models.md §4.4 documents (AC5).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AdvisorOverride as AdvisorOverrideRow
from src.db.models import RiskBandAssignment
from src.types.entities import AdvisorOverride as AdvisorOverrideEntity


class BlankReasonError(ValueError):
    """Raised when `reason` is missing, empty, or whitespace-only."""

    def __init__(self) -> None:
        super().__init__("reason is mandatory and cannot be blank.")


class PreviousBandMismatchError(ValueError):
    """Raised when `previous_band` does not match the customer's latest assignment."""

    def __init__(self, expected: str | None, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"previous_band {actual!r} does not match the customer's latest "
            f"RiskBandAssignment.risk_band {expected!r}."
        )


def insert_override(
    session: Session,
    *,
    customer_id: int,
    advisor_id: int,
    previous_band: str,
    new_band: str,
    reason: str | None,
    note: str | None,
    created_at: str,
) -> AdvisorOverrideEntity:
    """Insert one append-only `AdvisorOverride` row."""
    if reason is None or reason.strip() == "":
        raise BlankReasonError

    current_band = _latest_risk_band(session, customer_id)
    if current_band != previous_band:
        raise PreviousBandMismatchError(current_band, previous_band)

    row = AdvisorOverrideRow(
        customer_id=customer_id,
        advisor_id=advisor_id,
        previous_band=previous_band,
        new_band=new_band,
        reason=reason,
        note=note,
        created_at=created_at,
    )
    session.add(row)
    session.flush()
    return _to_entity(row)


def get_overrides(session: Session, customer_id: int) -> list[AdvisorOverrideEntity]:
    """Full override history for `customer_id`, ordered by `created_at` descending."""
    statement = (
        select(AdvisorOverrideRow)
        .where(AdvisorOverrideRow.customer_id == customer_id)
        .order_by(AdvisorOverrideRow.created_at.desc())
    )
    rows = session.execute(statement).scalars().all()
    return [_to_entity(row) for row in rows]


def _latest_risk_band(session: Session, customer_id: int) -> str | None:
    statement = (
        select(RiskBandAssignment.risk_band)
        .where(RiskBandAssignment.customer_id == customer_id)
        .order_by(RiskBandAssignment.assigned_at.desc(), RiskBandAssignment.id.desc())
        .limit(1)
    )
    return session.execute(statement).scalar_one_or_none()


def _to_entity(row: AdvisorOverrideRow) -> AdvisorOverrideEntity:
    return AdvisorOverrideEntity(
        id=row.id,
        customer_id=row.customer_id,
        advisor_id=row.advisor_id,
        previous_band=row.previous_band,  # type: ignore[arg-type]
        new_band=row.new_band,  # type: ignore[arg-type]
        reason=row.reason,
        note=row.note,
        created_at=row.created_at,
    )
