"""`domain/holdings/repository.py` tests (E6-S1 AC3-AC5; ut-070..ut-072)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from src.db.models import NavSnapshot
from src.domain.holdings.repository import (
    get_latest_nav,
    insert_asset_class,
    insert_nav_snapshot,
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
        db_session, asset_class_id=asset_class.id, price_date="2026-09-02",
        nav_value=Decimal("101.50"),
    )
    db_session.commit()
    insert_nav_snapshot(
        db_session, asset_class_id=asset_class.id, price_date="2026-08-31",
        nav_value=Decimal("100.90"),
    )
    db_session.commit()
    insert_nav_snapshot(
        db_session, asset_class_id=asset_class.id, price_date="2026-09-05",
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
