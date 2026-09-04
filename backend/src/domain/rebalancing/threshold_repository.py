"""RebalancingThreshold persistence — insert-only, versioned (E8-S1, data-models.md
§4.15).

The same immutable-versioned-publish pattern as `RiskBandRule` (E4-S1) and
`AllocationTemplate` (E5-S1): `publish_threshold` computes the next version,
deactivates the current one, and inserts the new version as active. `threshold_bps`
is never updated in place — no `update_threshold` function exists.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.config import MAX_THRESHOLD_BPS, MIN_THRESHOLD_BPS
from src.db.models import RebalancingThreshold as RebalancingThresholdRow
from src.types.entities import RebalancingThreshold as RebalancingThresholdEntity


class ThresholdOutOfRangeError(ValueError):
    """Raised when `threshold_bps` falls outside `[1, 10000]`."""

    def __init__(self, threshold_bps: int) -> None:
        self.threshold_bps = threshold_bps
        super().__init__(
            f"threshold_bps must be between {MIN_THRESHOLD_BPS} and "
            f"{MAX_THRESHOLD_BPS}, got {threshold_bps}."
        )


def publish_threshold(
    session: Session, *, threshold_bps: int, published_at: str
) -> RebalancingThresholdEntity:
    """Insert the next `RebalancingThreshold` version and deactivate the current one."""
    if not (MIN_THRESHOLD_BPS <= threshold_bps <= MAX_THRESHOLD_BPS):
        raise ThresholdOutOfRangeError(threshold_bps)

    next_version = _next_version(session)
    _deactivate_current(session)

    row = RebalancingThresholdRow(
        version=next_version,
        threshold_bps=threshold_bps,
        published_at=published_at,
        is_active=True,
    )
    session.add(row)
    session.flush()
    return _to_entity(row)


def get_active_threshold(session: Session) -> RebalancingThresholdEntity | None:
    """The exactly-one row with `is_active = True`, or `None` if never published."""
    statement = select(RebalancingThresholdRow).where(
        RebalancingThresholdRow.is_active.is_(True)
    )
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def get_threshold_by_version(session: Session, version: int) -> RebalancingThresholdEntity | None:
    """A specific, possibly-superseded threshold version — still fully queryable."""
    statement = select(RebalancingThresholdRow).where(
        RebalancingThresholdRow.version == version
    )
    row = session.execute(statement).scalar_one_or_none()
    return _to_entity(row) if row is not None else None


def _next_version(session: Session) -> int:
    current_max = session.execute(select(func.max(RebalancingThresholdRow.version))).scalar_one()
    return 1 if current_max is None else current_max + 1


def _deactivate_current(session: Session) -> None:
    statement = select(RebalancingThresholdRow).where(
        RebalancingThresholdRow.is_active.is_(True)
    )
    active_row = session.execute(statement).scalar_one_or_none()
    if active_row is not None:
        active_row.is_active = False


def _to_entity(row: RebalancingThresholdRow) -> RebalancingThresholdEntity:
    return RebalancingThresholdEntity(
        id=row.id,
        version=row.version,
        threshold_bps=row.threshold_bps,
        published_at=row.published_at,
        is_active=row.is_active,
    )
