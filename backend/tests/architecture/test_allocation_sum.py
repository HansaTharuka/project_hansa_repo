"""AC-02 / NFR-08 — every AllocationTemplate row sums to exactly 10000 bps.

New in this group, owned solely by E5-S1 (component-map.md). Asserts both that
every seeded/insertable row sums to exactly 10000 (no tolerance) and that the
repository's insert path itself rejects a non-10000 sum rather than silently
normalizing it.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.domain.recommendation.repository import (
    TemplateSumInvalidError,
    publish_template,
)
from src.types.entities import AllocationEntry, AllocationSet

ALLOCATION_TOTAL_BPS = 10000


def test_every_seeded_allocation_template_row_sums_to_exactly_10000_bps(
    seeded_session: Session,
) -> None:
    from sqlalchemy import text

    rows = seeded_session.execute(
        text("SELECT allocations_json FROM allocation_template")
    ).all()
    assert rows, "no AllocationTemplate rows were seeded"

    for (allocations_json,) in rows:
        parsed = AllocationSet.model_validate_json(allocations_json)
        total_bps = sum(entry.percent_bps for entry in parsed.allocations)
        assert total_bps == ALLOCATION_TOTAL_BPS


@pytest.mark.parametrize("skew", [-100, 100])
def test_insert_path_rejects_any_non_10000_sum_no_tolerance(
    db_session: Session, skew: int
) -> None:
    allocations = AllocationSet(
        allocations=[
            AllocationEntry(asset_class_id=1, percent_bps=6000 + skew),
            AllocationEntry(asset_class_id=2, percent_bps=4000),
        ]
    )
    with pytest.raises(TemplateSumInvalidError):
        publish_template(
            db_session,
            risk_band="MODERATE",
            allocations=allocations,
            published_at="2026-09-01T09:00:00Z",
        )
