"""`domain/recommendation/repository.py` tests (E5-S1 AC1-AC5; ut-063..ut-067)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.domain.recommendation.repository import (
    TemplateSumInvalidError,
    get_active_template,
    get_template_by_version,
    publish_template,
)
from src.types.entities import AllocationEntry, AllocationSet

VALID_ALLOCATIONS = AllocationSet(
    allocations=[
        AllocationEntry(asset_class_id=1, percent_bps=4000),
        AllocationEntry(asset_class_id=2, percent_bps=3500),
        AllocationEntry(asset_class_id=3, percent_bps=2500),
    ]
)


def _row_count(session: Session) -> int:
    return session.execute(text("SELECT COUNT(*) FROM allocation_template")).scalar_one()


def test_insert_rejects_allocations_that_do_not_sum_to_exactly_10000_bps(
    db_session: Session,
) -> None:
    under = AllocationSet(
        allocations=[
            AllocationEntry(asset_class_id=1, percent_bps=4000),
            AllocationEntry(asset_class_id=2, percent_bps=3500),
            AllocationEntry(asset_class_id=3, percent_bps=2400),
        ]
    )
    over = AllocationSet(
        allocations=[
            AllocationEntry(asset_class_id=1, percent_bps=4000),
            AllocationEntry(asset_class_id=2, percent_bps=3500),
            AllocationEntry(asset_class_id=3, percent_bps=2600),
        ]
    )
    baseline = _row_count(db_session)

    with pytest.raises(TemplateSumInvalidError):
        publish_template(
            db_session,
            risk_band="MODERATE",
            allocations=under,
            published_at="2026-09-01T09:00:00Z",
        )
    with pytest.raises(TemplateSumInvalidError):
        publish_template(
            db_session,
            risk_band="MODERATE",
            allocations=over,
            published_at="2026-09-01T09:00:00Z",
        )
    assert _row_count(db_session) == baseline

    template = publish_template(
        db_session,
        risk_band="MODERATE",
        allocations=VALID_ALLOCATIONS,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()
    assert template.version == 1


def test_repository_exposes_no_update_function() -> None:
    import src.domain.recommendation.repository as repository_module

    assert getattr(repository_module, "update_template", None) is None
    assert getattr(repository_module, "update_allocation_template", None) is None


def test_get_active_template_returns_exactly_one_row_per_band(db_session: Session) -> None:
    publish_template(
        db_session,
        risk_band="MODERATE",
        allocations=VALID_ALLOCATIONS,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()
    publish_template(
        db_session,
        risk_band="MODERATE",
        allocations=VALID_ALLOCATIONS,
        published_at="2026-09-02T09:00:00Z",
    )
    db_session.commit()
    publish_template(
        db_session,
        risk_band="CONSERVATIVE",
        allocations=VALID_ALLOCATIONS,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    moderate = get_active_template(db_session, "MODERATE")
    conservative = get_active_template(db_session, "CONSERVATIVE")

    assert moderate is not None
    assert moderate.version == 2
    assert conservative is not None
    assert conservative.version == 1
    assert conservative.risk_band == "CONSERVATIVE"


def test_superseded_versions_remain_individually_queryable(db_session: Session) -> None:
    publish_template(
        db_session,
        risk_band="AGGRESSIVE",
        allocations=VALID_ALLOCATIONS,
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()
    publish_template(
        db_session,
        risk_band="AGGRESSIVE",
        allocations=VALID_ALLOCATIONS,
        published_at="2026-09-02T09:00:00Z",
    )
    db_session.commit()

    version_one = get_template_by_version(db_session, risk_band="AGGRESSIVE", version=1)
    version_two = get_template_by_version(db_session, risk_band="AGGRESSIVE", version=2)

    assert version_one is not None
    assert version_one.is_active is False
    assert version_two is not None
    assert version_two.is_active is True
    assert version_one.version != version_two.version


def test_seeding_produces_two_versions_per_band_six_rows_total(
    seeded_session: Session,
) -> None:
    total = _row_count(seeded_session)
    assert total == 6
    for band in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE"):
        active_count = seeded_session.execute(
            text(
                "SELECT COUNT(*) FROM allocation_template "
                "WHERE risk_band = :band AND is_active = 1"
            ),
            {"band": band},
        ).scalar_one()
        assert active_count == 1
        version_count = seeded_session.execute(
            text("SELECT COUNT(*) FROM allocation_template WHERE risk_band = :band"),
            {"band": band},
        ).scalar_one()
        assert version_count == 2
