"""`domain/holdings/service.py` — advance_day() / compute_customer_drift() /
recompute_customer_drift() (E6-S2 AC1-AC5; E6-S3 AC1)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.holdings.csv_loader import load_seed_csvs
from src.domain.holdings.repository import (
    get_asset_class_by_code,
    get_latest_nav,
    insert_asset_class,
    insert_holding,
)
from src.domain.holdings.service import (
    advance_day,
    compute_customer_drift,
    recompute_customer_drift,
)
from src.domain.recommendation.repository import publish_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.entities import AllocationEntry, AllocationSet
from src.types.errors import ConflictError


def _load_seed_csvs(session: Session) -> None:
    load_seed_csvs(session)
    session.commit()


def _seed_customer(session: Session, email: str) -> int:
    user_seed = build_user(email=email)
    user = create_user(
        session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id)
    customer = Customer(
        user_id=customer_seed.user_id,
        kyc_verified=customer_seed.kyc_verified,
        created_at=customer_seed.created_at,
    )
    session.add(customer)
    session.commit()
    return customer.id


def test_advancing_once_inserts_exactly_one_new_nav_snapshot_per_asset_class(
    db_session: Session,
) -> None:
    _load_seed_csvs(db_session)

    result = advance_day(db_session)
    db_session.commit()

    assert result.price_date == "2026-09-02"
    assert len(result.snapshots) == 6  # one per seeded asset class
    assert {snapshot.price_date for snapshot in result.snapshots} == {"2026-09-02"}


def _make_integrity_error() -> IntegrityError:
    """A stand-in for the `IntegrityError` SQLite raises on the losing writer
    of a real `UNIQUE(asset_class_id, price_date)` race — see the two tests
    below for why this is simulated rather than triggered via true concurrency.
    """
    return IntegrityError(
        "INSERT INTO nav_snapshot ...",
        {},
        Exception("UNIQUE constraint failed: nav_snapshot.asset_class_id, nav_snapshot.price_date"),
    )


def test_advancing_a_second_time_on_the_same_simulated_day_is_rejected(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E6-S2 AC2 / system-design.md §9.5: the double-advance guarantee is a
    DB-level `UNIQUE(asset_class_id, price_date)` constraint, not a
    check-then-act read — `advance_day` always computes `max(price_date) + 1
    day`, so a genuine collision only happens when two callers race on a
    stale "latest NAV" read (api-contracts.md §12.1). That race can't be
    reproduced deterministically by calling `advance_day` twice in sequence
    on one session (the second call would simply see the first's committed
    row and legitimately target the next day after it), so this test
    simulates the losing writer directly: `insert_nav_snapshot` raises the
    `IntegrityError` SQLite would raise, and `advance_day` must translate it
    into `ConflictError` rather than let it propagate raw or partially advance.
    """
    _load_seed_csvs(db_session)
    monkeypatch.setattr(
        "src.domain.holdings.service.insert_nav_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(_make_integrity_error()),
    )

    with pytest.raises(ConflictError) as excinfo:
        advance_day(db_session)

    assert excinfo.value.code == "DAY_ALREADY_ADVANCED"


def test_advancing_does_not_insert_duplicate_nav_snapshot_rows_after_a_rejected_retry(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failed advance (simulated as in the test above) must not leave a
    partial write behind: `advance_day` rolls back on `IntegrityError`, so
    only the original seed row remains — never a stray row from the aborted
    attempt.
    """
    _load_seed_csvs(db_session)
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    assert eq_dm is not None
    monkeypatch.setattr(
        "src.domain.holdings.service.insert_nav_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(_make_integrity_error()),
    )

    with pytest.raises(ConflictError):
        advance_day(db_session)
    db_session.rollback()

    from sqlalchemy import text

    count = db_session.execute(
        text("SELECT COUNT(*) FROM nav_snapshot WHERE asset_class_id = :id"),
        {"id": eq_dm.id},
    ).scalar_one()
    assert count == 1  # only the seed row; the mocked failing insert never committed


def test_after_advancing_get_latest_nav_returns_the_newly_inserted_snapshot(
    db_session: Session,
) -> None:
    _load_seed_csvs(db_session)
    asset_class = get_asset_class_by_code(db_session, "CASH")
    assert asset_class is not None

    advance_day(db_session)
    db_session.commit()

    latest = get_latest_nav(db_session, asset_class.id)
    assert latest is not None
    assert latest.price_date == "2026-09-02"


def test_advance_day_recomputes_drift_for_every_customer_with_holdings(
    db_session: Session,
) -> None:
    _load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "advance.customer1@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    fi_gov = get_asset_class_by_code(db_session, "FI_GOV")
    assert eq_dm is not None and fi_gov is not None
    insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=eq_dm.id,
        current_value=Decimal("6000.00"),
        as_of_date="2026-09-01",
    )
    insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=fi_gov.id,
        current_value=Decimal("4000.00"),
        as_of_date="2026-09-01",
    )
    from sqlalchemy import text

    db_session.execute(
        text(
            "INSERT INTO risk_band_assignment (customer_id, risk_band, rule_version, assigned_at) "
            "VALUES (:customer_id, 'MODERATE', 1, '2026-09-01T09:00:00Z')"
        ),
        {"customer_id": customer_id},
    )
    publish_template(
        db_session,
        risk_band="MODERATE",
        allocations=AllocationSet(
            allocations=[
                AllocationEntry(asset_class_id=eq_dm.id, percent_bps=5000),
                AllocationEntry(asset_class_id=fi_gov.id, percent_bps=5000),
            ]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    result = advance_day(db_session)
    db_session.commit()

    assert customer_id in result.customers_redrifted
    drift = recompute_customer_drift(db_session, customer_id)
    assert {d.asset_class_id for d in drift} == {eq_dm.id, fi_gov.id}


def test_recompute_customer_drift_is_empty_for_a_customer_with_no_risk_band_assignment(
    db_session: Session,
) -> None:
    _load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "advance.customer2@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    assert eq_dm is not None
    insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=eq_dm.id,
        current_value=Decimal("1000.00"),
        as_of_date="2026-09-01",
    )
    db_session.commit()
    assert get_latest_assignment(db_session, customer_id) is None

    assert recompute_customer_drift(db_session, customer_id) == []


def test_compute_customer_drift_returns_empty_list_for_a_customer_with_no_holdings(
    db_session: Session,
) -> None:
    _load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "advance.customer3@wealthwise.test")

    drift = compute_customer_drift(
        db_session,
        customer_id=customer_id,
        allocations=AllocationSet(allocations=[]),
    )

    assert drift == []


def test_advancing_with_no_asset_classes_seeded_raises_not_found(db_session: Session) -> None:
    """`advance_day` on a database with no `AssetClass` rows at all has
    nothing to advance from and must not attempt any insert."""
    from src.types.errors import NotFoundError

    with pytest.raises(NotFoundError) as excinfo:
        advance_day(db_session)

    assert excinfo.value.code == "NO_ASSET_CLASSES"


def test_advancing_an_asset_class_with_no_nav_history_raises_not_found(
    db_session: Session,
) -> None:
    """An `AssetClass` inserted directly (bypassing the seed CSV loader) has no
    `NavSnapshot` row to advance from — `advance_day` cannot compute a "next"
    date without one."""
    from src.types.errors import NotFoundError

    insert_asset_class(db_session, code="NEW_AC", name="Freshly Added Asset Class")
    db_session.commit()

    with pytest.raises(NotFoundError) as excinfo:
        advance_day(db_session)

    assert excinfo.value.code == "NO_NAV_HISTORY"


def test_recompute_customer_drift_is_empty_when_the_assigned_band_has_no_active_template(
    db_session: Session,
) -> None:
    """A customer with a risk-band assignment but no *published* allocation
    template for that band has nothing to compare their holdings against."""
    _load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "advance.customer4@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    assert eq_dm is not None
    insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=eq_dm.id,
        current_value=Decimal("1000.00"),
        as_of_date="2026-09-01",
    )
    from sqlalchemy import text

    db_session.execute(
        text(
            "INSERT INTO risk_band_assignment (customer_id, risk_band, rule_version, assigned_at) "
            "VALUES (:customer_id, 'AGGRESSIVE', 1, '2026-09-01T09:00:00Z')"
        ),
        {"customer_id": customer_id},
    )
    db_session.commit()

    assert recompute_customer_drift(db_session, customer_id) == []
