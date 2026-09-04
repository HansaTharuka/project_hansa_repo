"""AllocationTemplate persistence — insert-only, versioned per risk band (E5-S1).

`publish_template` rejects, before touching the session, any `allocations` whose
`percent_bps` values do not sum to exactly 10000 (AC-02, NFR-08) — no partial row
is ever persisted. No `update_template` function exists; a correction is always a
new version (E5-S1 AC2).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.models import AllocationTemplate as AllocationTemplateRow
from src.types.entities import AllocationSet
from src.types.entities import AllocationTemplate as AllocationTemplateEntity

ALLOCATION_TOTAL_BPS = 10000


class TemplateSumInvalidError(ValueError):
    """Raised when `allocations.percent_bps` values do not sum to exactly 10000."""

    def __init__(self, actual_sum_bps: int) -> None:
        self.actual_sum_bps = actual_sum_bps
        super().__init__(
            f"Allocation percentages must sum to exactly {ALLOCATION_TOTAL_BPS} bps, "
            f"got {actual_sum_bps}."
        )


def publish_template(
    session: Session,
    *,
    risk_band: str,
    allocations: AllocationSet,
    published_at: str,
) -> AllocationTemplateEntity:
    """Insert the next `AllocationTemplate` version for `risk_band`."""
    total_bps = sum(entry.percent_bps for entry in allocations.allocations)
    if total_bps != ALLOCATION_TOTAL_BPS:
        raise TemplateSumInvalidError(total_bps)

    next_version = _next_version(session, risk_band)
    _deactivate_current(session, risk_band)

    row = AllocationTemplateRow(
        version=next_version,
        risk_band=risk_band,
        allocations_json=allocations.model_dump_json(),
        published_at=published_at,
        is_active=True,
    )
    session.add(row)
    session.flush()
    return _to_entity(row)


def get_active_template(session: Session, risk_band: str) -> AllocationTemplateEntity | None:
    """The exactly-one active template for `risk_band`, or `None` if never published."""
    statement = select(AllocationTemplateRow).where(
        AllocationTemplateRow.risk_band == risk_band,
        AllocationTemplateRow.is_active.is_(True),
    )
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def get_template_by_version(
    session: Session, *, risk_band: str, version: int
) -> AllocationTemplateEntity | None:
    """A specific, possibly-superseded template version — still fully queryable."""
    statement = select(AllocationTemplateRow).where(
        AllocationTemplateRow.risk_band == risk_band,
        AllocationTemplateRow.version == version,
    )
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def _next_version(session: Session, risk_band: str) -> int:
    statement = select(func.max(AllocationTemplateRow.version)).where(
        AllocationTemplateRow.risk_band == risk_band
    )
    current_max = session.execute(statement).scalar_one()
    return 1 if current_max is None else current_max + 1


def _deactivate_current(session: Session, risk_band: str) -> None:
    statement = select(AllocationTemplateRow).where(
        AllocationTemplateRow.risk_band == risk_band,
        AllocationTemplateRow.is_active.is_(True),
    )
    active_row = session.execute(statement).scalar_one_or_none()
    if active_row is not None:
        active_row.is_active = False


def _to_entity(row: AllocationTemplateRow) -> AllocationTemplateEntity:
    return AllocationTemplateEntity(
        id=row.id,
        version=row.version,
        risk_band=row.risk_band,  # type: ignore[arg-type]
        allocations_json=AllocationSet.model_validate_json(row.allocations_json),
        published_at=row.published_at,
        is_active=row.is_active,
    )
