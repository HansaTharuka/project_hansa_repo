"""`domain/rebalancing/service.py` — evaluate_customer_rebalancing() (E8-S2
AC1-AC5; ut-147..ut-151)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer
from src.domain.auth.repository import create_user
from src.domain.holdings.csv_loader import load_seed_csvs
from src.domain.holdings.repository import get_asset_class_by_code, insert_holding
from src.domain.rebalancing.service import evaluate_customer_rebalancing
from src.domain.rebalancing.threshold_repository import publish_threshold
from src.domain.recommendation.repository import publish_template
from src.types.entities import AllocationEntry, AllocationSet

ACTOR = {"actor_id": 1, "actor_role": "advisor"}


def _seed_customer(session: Session, email: str, *, kyc_verified: bool = True) -> int:
    user_seed = build_user(email=email)
    user = create_user(
        session,
        email=user_seed.email,
        password_hash=user_seed.password_hash,
        role=user_seed.role,
        created_at=user_seed.created_at,
    )
    customer_seed = build_customer(user_id=user.id, kyc_verified=kyc_verified)
    customer = Customer(
        user_id=customer_seed.user_id,
        kyc_verified=customer_seed.kyc_verified,
        created_at=customer_seed.created_at,
    )
    session.add(customer)
    session.commit()
    return customer.id


def _assign_band(session: Session, *, customer_id: int, risk_band: str) -> None:
    from sqlalchemy import text

    session.execute(
        text(
            "INSERT INTO risk_band_assignment (customer_id, risk_band, rule_version, assigned_at) "
            "VALUES (:customer_id, :risk_band, 1, '2026-09-01T09:00:00Z')"
        ),
        {"customer_id": customer_id, "risk_band": risk_band},
    )
    session.commit()


def _setup_drifted_customer(session: Session, email: str, *, kyc_verified: bool = True) -> int:
    """A customer 90/10 EQ_DM/FI_GOV holdings vs. a 50/50 target — well past
    the seeded 5% threshold on both legs."""
    load_seed_csvs(session)
    customer_id = _seed_customer(session, email, kyc_verified=kyc_verified)
    eq_dm = get_asset_class_by_code(session, "EQ_DM")
    fi_gov = get_asset_class_by_code(session, "FI_GOV")
    assert eq_dm is not None and fi_gov is not None
    insert_holding(
        session, customer_id=customer_id, asset_class_id=eq_dm.id,
        current_value=Decimal("9000.00"), as_of_date="2026-09-01",
    )
    insert_holding(
        session, customer_id=customer_id, asset_class_id=fi_gov.id,
        current_value=Decimal("1000.00"), as_of_date="2026-09-01",
    )
    _assign_band(session, customer_id=customer_id, risk_band="MODERATE")
    publish_template(
        session, risk_band="MODERATE",
        allocations=AllocationSet(
            allocations=[
                AllocationEntry(asset_class_id=eq_dm.id, percent_bps=5000),
                AllocationEntry(asset_class_id=fi_gov.id, percent_bps=5000),
            ]
        ),
        published_at="2026-09-01T09:00:00Z",
    )
    publish_threshold(session, threshold_bps=500, published_at="2026-09-01T09:00:00Z")
    session.commit()
    return customer_id


def test_drift_exceeding_threshold_creates_one_recommendation_with_buy_sell_actions(
    db_session: Session,
) -> None:
    customer_id = _setup_drifted_customer(db_session, "rebal.customer1@wealthwise.test")

    recommendation = evaluate_customer_rebalancing(db_session, customer_id=customer_id, **ACTOR)

    assert recommendation is not None
    assert recommendation.customer_id == customer_id
    actions = recommendation.proposed_actions_json.actions
    assert len(actions) == 2
    assert {a.action.value for a in actions} == {"BUY", "SELL"}


def test_drift_within_threshold_produces_no_recommendation(db_session: Session) -> None:
    load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "rebal.customer2@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    fi_gov = get_asset_class_by_code(db_session, "FI_GOV")
    assert eq_dm is not None and fi_gov is not None
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=eq_dm.id,
        current_value=Decimal("5100.00"), as_of_date="2026-09-01",
    )
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=fi_gov.id,
        current_value=Decimal("4900.00"), as_of_date="2026-09-01",
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
    publish_threshold(db_session, threshold_bps=500, published_at="2026-09-01T09:00:00Z")
    db_session.commit()

    recommendation = evaluate_customer_rebalancing(db_session, customer_id=customer_id, **ACTOR)

    assert recommendation is None


def test_a_customer_with_zero_holdings_is_a_no_op_not_an_error(db_session: Session) -> None:
    load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "rebal.customer3@wealthwise.test")

    recommendation = evaluate_customer_rebalancing(db_session, customer_id=customer_id, **ACTOR)

    assert recommendation is None


def test_kyc_unverified_customer_produces_no_recommendation_even_with_drift(
    db_session: Session,
) -> None:
    customer_id = _setup_drifted_customer(
        db_session, "rebal.customer4@wealthwise.test", kyc_verified=False
    )

    recommendation = evaluate_customer_rebalancing(db_session, customer_id=customer_id, **ACTOR)

    assert recommendation is None


def test_a_successful_recommendation_invokes_the_audit_writer_exactly_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    customer_id = _setup_drifted_customer(db_session, "rebal.customer5@wealthwise.test")
    spy = MagicMock(wraps=lambda *args, **kwargs: None)
    monkeypatch.setattr("src.domain.rebalancing.service.write_audit_entry", spy)

    evaluate_customer_rebalancing(db_session, customer_id=customer_id, **ACTOR)

    spy.assert_called_once()
    assert spy.call_args.kwargs["entity_type"] == "RebalancingRecommendation"


def test_a_customer_with_no_risk_band_assignment_produces_no_recommendation(
    db_session: Session,
) -> None:
    load_seed_csvs(db_session)
    customer_id = _seed_customer(db_session, "rebal.customer6@wealthwise.test")
    eq_dm = get_asset_class_by_code(db_session, "EQ_DM")
    assert eq_dm is not None
    insert_holding(
        db_session, customer_id=customer_id, asset_class_id=eq_dm.id,
        current_value=Decimal("1000.00"), as_of_date="2026-09-01",
    )
    db_session.commit()

    recommendation = evaluate_customer_rebalancing(db_session, customer_id=customer_id, **ACTOR)

    assert recommendation is None


def test_advance_day_creates_a_rebalancing_recommendation_when_an_actor_is_supplied(
    db_session: Session,
) -> None:
    """E8-S2's wiring into `holdings.service.advance_day` — the admin API
    caller always supplies `actor_id`/`actor_role`, and the reported count
    reflects the recommendation created for the drifted customer."""
    from src.domain.holdings.service import advance_day

    customer_id = _setup_drifted_customer(db_session, "rebal.customer7@wealthwise.test")

    result = advance_day(db_session, actor_id=1, actor_role="admin")
    db_session.commit()

    assert customer_id in result.customers_redrifted
    assert result.rebalancing_recommendations_created == 1


def test_advance_day_skips_rebalancing_evaluation_when_no_actor_is_supplied(
    db_session: Session,
) -> None:
    from src.domain.holdings.service import advance_day

    _setup_drifted_customer(db_session, "rebal.customer8@wealthwise.test")

    result = advance_day(db_session)
    db_session.commit()

    assert result.rebalancing_recommendations_created == 0
