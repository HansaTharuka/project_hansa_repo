"""`domain/rebalancing/threshold_repository.py` tests (component-map.md E8-S1 row;
data-models.md §4.15; ut-088, ut-089, ut-090)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.domain.rebalancing.threshold_repository import (
    ThresholdOutOfRangeError,
    get_active_threshold,
    get_threshold_by_version,
    publish_threshold,
)


def test_repository_exposes_no_update_or_delete_function() -> None:
    import src.domain.rebalancing.threshold_repository as repository_module

    assert getattr(repository_module, "update_threshold", None) is None
    assert getattr(repository_module, "delete_threshold", None) is None


@pytest.mark.parametrize("invalid_bps", [0, 10001])
def test_publishing_a_threshold_outside_1_to_10000_is_rejected(
    db_session: Session, invalid_bps: int
) -> None:
    with pytest.raises(ThresholdOutOfRangeError):
        publish_threshold(
            db_session, threshold_bps=invalid_bps, published_at="2026-09-01T09:00:00Z"
        )

    count = db_session.execute(
        text("SELECT COUNT(*) FROM rebalancing_threshold")
    ).scalar_one()
    assert count == 0


def test_get_active_threshold_returns_exactly_one_row_at_any_point(
    db_session: Session,
) -> None:
    publish_threshold(db_session, threshold_bps=500, published_at="2026-09-01T09:00:00Z")
    db_session.commit()
    publish_threshold(db_session, threshold_bps=750, published_at="2026-09-02T09:00:00Z")
    db_session.commit()

    active = get_active_threshold(db_session)
    version_one = get_threshold_by_version(db_session, 1)

    assert active is not None
    assert active.version == 2
    assert active.threshold_bps == 750
    assert version_one is not None
    assert version_one.is_active is False
    assert version_one.threshold_bps == 500


def test_seed_produces_exactly_one_threshold_row_version_1_bps_500(
    seeded_session: Session,
) -> None:
    count = seeded_session.execute(
        text("SELECT COUNT(*) FROM rebalancing_threshold")
    ).scalar_one()
    assert count == 1
    row = seeded_session.execute(
        text("SELECT version, threshold_bps, is_active FROM rebalancing_threshold")
    ).one()
    assert row.version == 1
    assert row.threshold_bps == 500
    assert row.is_active == 1
