"""`domain/holdings/views.py` — get_customer_holdings_view() (E6-S4 AC1, AC5)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.holdings.csv_loader import load_seed_csvs
from src.domain.holdings.repository import get_asset_class_by_code, insert_holding
from src.domain.holdings.views import get_customer_holdings_view
from src.domain.recommendation.repository import publish_template
from src.types.entities import AllocationEntry, AllocationSet

DEFAULT_THRESHOLD_BPS = 500


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


def _assign_band(session: Session, *, customer_id: int, risk_band: str) -> None:
    session.execute(
        text(
            "INSERT INTO risk_band_assignment (customer_id, risk_band, rule_version, assigned_at) "
            "VALUES (:customer_id, :risk_band, 1, '2026-09-01T09:00:00Z')"
        ),
        {"customer_id": customer_id, "risk_band": risk_band},
    )
    session.commit()


def test_a_customer_with_a_risk_band_but_no_published_template_reports_full_drift(
    db_session: Session,
) -> None:
    """A risk-band assignment with no active `AllocationTemplate` for that band
    is treated the same as no assignment at all — `_target_bps_for_customer`
    returns `{}`, so the held asset class reports 100% drift rather than
    raising (views.py's own docstring, E6-S4 AC5)."""
    load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "holdings.notemplate@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    assert eq_dm is not None
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=eq_dm.id,
        current_value=Decimal("1000.00"), as_of_date="2026-09-01",
    )
    # Assigned to a band no AllocationTemplate has ever been published for.
    _assign_band(db_session, customer_id=customer_id, risk_band="AGGRESSIVE")
    db_session.commit()

    view = get_customer_holdings_view(
        db_session, customer_id, default_threshold_bps=DEFAULT_THRESHOLD_BPS
    )

    assert len(view.holdings) == 1
    line = view.holdings[0]
    assert line.target_percent == Decimal("0.00")
    assert line.current_value == Decimal("1000.00")
    assert line.exceeds_threshold is True


def test_a_customer_with_a_risk_band_and_a_published_template_reports_the_template_s_target(
    db_session: Session,
) -> None:
    """The success path of `_target_bps_for_customer`: an assignment and an
    active `AllocationTemplate` for that band resolve to the template's real
    target percentages rather than the `{}` fallback."""
    load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "holdings.withtemplate@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    fi_gov = get_asset_class_by_code(db_session, "FI_GOV")
    assert eq_dm is not None and fi_gov is not None
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=eq_dm.id,
        current_value=Decimal("6000.00"), as_of_date="2026-09-01",
    )
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=fi_gov.id,
        current_value=Decimal("4000.00"), as_of_date="2026-09-01",
    )
    _assign_band(db_session, customer_id=customer_id, risk_band="MODERATE")
    publish_template(
        db_session, risk_band="MODERATE",
        allocations=AllocationSet(
            allocations=[
                AllocationEntry(asset_class_id=eq_dm.id, percent_bps=5000),
                AllocationEntry(asset_class_id=fi_gov.id, percent_bps=5000),
            ]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    db_session.commit()

    view = get_customer_holdings_view(
        db_session, customer_id, default_threshold_bps=DEFAULT_THRESHOLD_BPS
    )

    by_asset_class = {line.asset_class_id: line for line in view.holdings}
    assert by_asset_class[eq_dm.id].target_percent == Decimal("50.00")
    assert by_asset_class[fi_gov.id].target_percent == Decimal("50.00")
