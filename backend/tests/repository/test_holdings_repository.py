"""`domain/holdings/repository.py` tests (E6-S1 AC3-AC5; ut-070..ut-072; Holding
functions added by E6-S2/E6-S3, group D)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from tests.factories import build_customer, build_user

from src.db.models import Customer, NavSnapshot
from src.domain.auth.repository import create_user
from src.domain.holdings.repository import (
    get_holding,
    get_latest_nav,
    insert_asset_class,
    insert_holding,
    insert_nav_snapshot,
    list_customer_ids_with_holdings,
    list_holdings_for_asset_class,
    list_holdings_for_customer,
    update_holding_value,
)


def test_repository_exposes_no_update_function_for_nav_snapshot() -> None:
    import src.domain.holdings.repository as repository_module

    assert getattr(repository_module, "update_nav_snapshot", None) is None
    assert getattr(repository_module, "update_nav", None) is None


def test_a_new_price_on_a_later_date_is_a_new_row_not_a_rewrite(db_session: Session) -> None:
    asset_class = insert_asset_class(db_session, code="EQ_DM", name="Developed-Market Equity")
    db_session.commit()

    insert_nav_snapshot(
        db_session,
        asset_class_id=asset_class.id,
        price_date="2026-09-01",
        nav_value=Decimal("132.45"),
    )
    db_session.commit()
    insert_nav_snapshot(
        db_session,
        asset_class_id=asset_class.id,
        price_date="2026-09-02",
        nav_value=Decimal("133.10"),
    )
    db_session.commit()

    from sqlalchemy import text

    count = db_session.execute(
        text("SELECT COUNT(*) FROM nav_snapshot WHERE asset_class_id = :id"),
        {"id": asset_class.id},
    ).scalar_one()
    assert count == 2


def test_get_latest_nav_returns_the_row_with_the_maximum_price_date(
    db_session: Session,
) -> None:
    asset_class = insert_asset_class(db_session, code="FI_GOV", name="Government Fixed Income")
    db_session.commit()

    insert_nav_snapshot(
        db_session,
        asset_class_id=asset_class.id,
        price_date="2026-09-02",
        nav_value=Decimal("101.50"),
    )
    db_session.commit()
    insert_nav_snapshot(
        db_session,
        asset_class_id=asset_class.id,
        price_date="2026-08-31",
        nav_value=Decimal("100.90"),
    )
    db_session.commit()
    insert_nav_snapshot(
        db_session,
        asset_class_id=asset_class.id,
        price_date="2026-09-05",
        nav_value=Decimal("102.10"),
    )
    db_session.commit()

    latest = get_latest_nav(db_session, asset_class.id)

    assert latest is not None
    assert latest.price_date == "2026-09-05"
    assert latest.nav_value == Decimal("102.10")


def test_nav_value_is_stored_as_integer_minor_units_never_float() -> None:
    mapper = inspect(NavSnapshot)
    column = mapper.columns["nav_value"]
    assert column.type.python_type is int


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


def test_insert_holding_round_trips_and_is_readable_by_customer_and_asset_class(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "holdings.customer1@wealthwise.test")
    asset_class = insert_asset_class(db_session, code="EQ_DM", name="Developed-Market Equity")
    db_session.commit()

    holding = insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=asset_class.id,
        current_value=Decimal("5000.00"),
        as_of_date="2026-09-01",
    )
    db_session.commit()

    fetched = get_holding(db_session, customer_id=customer_id, asset_class_id=asset_class.id)
    assert fetched is not None
    assert fetched.id == holding.id
    assert fetched.current_value == Decimal("5000.00")
    assert fetched.as_of_date == "2026-09-01"


def test_update_holding_value_revalues_in_place_without_touching_ids(
    db_session: Session,
) -> None:
    customer_id = _seed_customer(db_session, "holdings.customer2@wealthwise.test")
    asset_class = insert_asset_class(db_session, code="FI_GOV", name="Government Fixed Income")
    db_session.commit()
    holding = insert_holding(
        db_session,
        customer_id=customer_id,
        asset_class_id=asset_class.id,
        current_value=Decimal("1000.00"),
        as_of_date="2026-09-01",
    )
    db_session.commit()

    updated = update_holding_value(
        db_session, holding_id=holding.id, current_value=Decimal("1010.00"), as_of_date="2026-09-02"
    )
    db_session.commit()

    assert updated.id == holding.id
    assert updated.customer_id == customer_id
    assert updated.asset_class_id == asset_class.id
    assert updated.current_value == Decimal("1010.00")
    assert updated.as_of_date == "2026-09-02"


def test_list_holdings_for_customer_returns_only_that_customers_rows(
    db_session: Session,
) -> None:
    customer_a = _seed_customer(db_session, "holdings.customerA@wealthwise.test")
    customer_b = _seed_customer(db_session, "holdings.customerB@wealthwise.test")
    asset_class = insert_asset_class(db_session, code="CASH", name="Cash and Equivalents")
    db_session.commit()
    insert_holding(
        db_session,
        customer_id=customer_a,
        asset_class_id=asset_class.id,
        current_value=Decimal("100.00"),
        as_of_date="2026-09-01",
    )
    insert_holding(
        db_session,
        customer_id=customer_b,
        asset_class_id=asset_class.id,
        current_value=Decimal("200.00"),
        as_of_date="2026-09-01",
    )
    db_session.commit()

    holdings_a = list_holdings_for_customer(db_session, customer_a)

    assert len(holdings_a) == 1
    assert holdings_a[0].customer_id == customer_a


def test_list_holdings_for_asset_class_spans_multiple_customers(db_session: Session) -> None:
    customer_a = _seed_customer(db_session, "holdings.customerC@wealthwise.test")
    customer_b = _seed_customer(db_session, "holdings.customerD@wealthwise.test")
    asset_class = insert_asset_class(db_session, code="RE", name="Real Estate")
    db_session.commit()
    insert_holding(
        db_session,
        customer_id=customer_a,
        asset_class_id=asset_class.id,
        current_value=Decimal("300.00"),
        as_of_date="2026-09-01",
    )
    insert_holding(
        db_session,
        customer_id=customer_b,
        asset_class_id=asset_class.id,
        current_value=Decimal("400.00"),
        as_of_date="2026-09-01",
    )
    db_session.commit()

    holdings = list_holdings_for_asset_class(db_session, asset_class.id)

    assert {holding.customer_id for holding in holdings} == {customer_a, customer_b}


def test_list_customer_ids_with_holdings_returns_distinct_ids_only(db_session: Session) -> None:
    customer_a = _seed_customer(db_session, "holdings.customerE@wealthwise.test")
    customer_b = _seed_customer(db_session, "holdings.customerF@wealthwise.test")
    ac1 = insert_asset_class(db_session, code="EQ_EM", name="Emerging-Market Equity")
    ac2 = insert_asset_class(db_session, code="FI_CORP", name="Corporate Fixed Income")
    db_session.commit()
    insert_holding(
        db_session,
        customer_id=customer_a,
        asset_class_id=ac1.id,
        current_value=Decimal("100.00"),
        as_of_date="2026-09-01",
    )
    insert_holding(
        db_session,
        customer_id=customer_a,
        asset_class_id=ac2.id,
        current_value=Decimal("50.00"),
        as_of_date="2026-09-01",
    )
    insert_holding(
        db_session,
        customer_id=customer_b,
        asset_class_id=ac1.id,
        current_value=Decimal("75.00"),
        as_of_date="2026-09-01",
    )
    db_session.commit()

    ids = list_customer_ids_with_holdings(db_session)

    assert ids == sorted({customer_a, customer_b})
