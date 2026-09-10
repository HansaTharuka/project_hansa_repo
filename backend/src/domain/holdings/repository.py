"""AssetClass / NavSnapshot / Holding persistence (E6-S1; Holding functions added
by E6-S2/E6-S3, group D, since `advance_day`'s orchestration and the drift
calculation both need to read and revalue a customer's current positions and no
public function existed for that yet).

`NavSnapshot` is append-only — no `update_*` function exists for it (AC3). A new
price for the same asset class on a later `price_date` is always a new inserted
row. `nav_value` round-trips as `Decimal`, converted through
`types.fixedpoint` at the repository boundary only; the underlying column stores
integer minor units, never a Python `float` (AC5, NFR-01).

`Holding` is mutable (data-models.md §4.11: "revalued each advance-a-day") —
`update_holding_value` is the one function that edits it in place, changing only
`current_value`/`as_of_date`; it never touches `customer_id`/`asset_class_id`.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AssetClass as AssetClassRow
from src.db.models import Holding as HoldingRow
from src.db.models import NavSnapshot as NavSnapshotRow
from src.types.entities import AssetClass as AssetClassEntity
from src.types.entities import Holding as HoldingEntity
from src.types.entities import NavSnapshot as NavSnapshotEntity
from src.types.fixedpoint import decimal_to_minor_units, minor_units_to_decimal


def insert_asset_class(session: Session, *, code: str, name: str) -> AssetClassEntity:
    """Insert one `AssetClass` row. `code` is unique — a duplicate raises IntegrityError."""
    row = AssetClassRow(code=code, name=name)
    session.add(row)
    session.flush()
    return _asset_class_to_entity(row)


def get_asset_class_by_code(session: Session, code: str) -> AssetClassEntity | None:
    """Look up an `AssetClass` by its unique `code`."""
    statement = select(AssetClassRow).where(AssetClassRow.code == code)
    row = session.execute(statement).scalar_one_or_none()
    return _asset_class_to_entity(row) if row is not None else None


def list_asset_classes(session: Session) -> list[AssetClassEntity]:
    """All `AssetClass` rows, ordered by id (insertion order)."""
    statement = select(AssetClassRow).order_by(AssetClassRow.id.asc())
    rows = session.execute(statement).scalars().all()
    return [_asset_class_to_entity(row) for row in rows]


def insert_nav_snapshot(
    session: Session, *, asset_class_id: int, price_date: str, nav_value: Decimal
) -> NavSnapshotEntity:
    """Insert one append-only `NavSnapshot` row."""
    row = NavSnapshotRow(
        asset_class_id=asset_class_id,
        price_date=price_date,
        nav_value=decimal_to_minor_units(nav_value),
    )
    session.add(row)
    session.flush()
    return _nav_snapshot_to_entity(row)


def get_nav_by_asset_class_and_date(
    session: Session, *, asset_class_id: int, price_date: str
) -> NavSnapshotEntity | None:
    """Look up the `NavSnapshot` for one asset class on one exact `price_date`."""
    statement = select(NavSnapshotRow).where(
        NavSnapshotRow.asset_class_id == asset_class_id,
        NavSnapshotRow.price_date == price_date,
    )
    row = session.execute(statement).scalar_one_or_none()
    return _nav_snapshot_to_entity(row) if row is not None else None


def get_latest_nav(session: Session, asset_class_id: int) -> NavSnapshotEntity | None:
    """The `NavSnapshot` with the most recent `price_date` for `asset_class_id`."""
    statement = (
        select(NavSnapshotRow)
        .where(NavSnapshotRow.asset_class_id == asset_class_id)
        .order_by(NavSnapshotRow.price_date.desc())
        .limit(1)
    )
    row = session.execute(statement).scalar_one_or_none()
    return _nav_snapshot_to_entity(row) if row is not None else None


def insert_holding(
    session: Session,
    *,
    customer_id: int,
    asset_class_id: int,
    current_value: Decimal,
    as_of_date: str,
) -> HoldingEntity:
    """Insert one `Holding` row for `customer_id`/`asset_class_id`."""
    row = HoldingRow(
        customer_id=customer_id,
        asset_class_id=asset_class_id,
        current_value=decimal_to_minor_units(current_value),
        as_of_date=as_of_date,
    )
    session.add(row)
    session.flush()
    return _holding_to_entity(row)


def update_holding_value(
    session: Session, *, holding_id: int, current_value: Decimal, as_of_date: str
) -> HoldingEntity:
    """Revalue an existing `Holding` row in place (the advance-a-day flow)."""
    row = session.execute(select(HoldingRow).where(HoldingRow.id == holding_id)).scalar_one()
    row.current_value = decimal_to_minor_units(current_value)
    row.as_of_date = as_of_date
    session.flush()
    return _holding_to_entity(row)


def get_holding(session: Session, *, customer_id: int, asset_class_id: int) -> HoldingEntity | None:
    """Look up the one `Holding` row for a customer/asset-class pair, if any."""
    statement = select(HoldingRow).where(
        HoldingRow.customer_id == customer_id, HoldingRow.asset_class_id == asset_class_id
    )
    row = session.execute(statement).scalar_one_or_none()
    return _holding_to_entity(row) if row is not None else None


def list_holdings_for_customer(session: Session, customer_id: int) -> list[HoldingEntity]:
    """All `Holding` rows for `customer_id`, ordered by id (insertion order)."""
    statement = (
        select(HoldingRow).where(HoldingRow.customer_id == customer_id).order_by(HoldingRow.id)
    )
    rows = session.execute(statement).scalars().all()
    return [_holding_to_entity(row) for row in rows]


def list_holdings_for_asset_class(session: Session, asset_class_id: int) -> list[HoldingEntity]:
    """Every customer's `Holding` row in one asset class — used to revalue them
    all after a `NavSnapshot` price change (the advance-a-day flow)."""
    statement = (
        select(HoldingRow)
        .where(HoldingRow.asset_class_id == asset_class_id)
        .order_by(HoldingRow.id)
    )
    rows = session.execute(statement).scalars().all()
    return [_holding_to_entity(row) for row in rows]


def list_customer_ids_with_holdings(session: Session) -> list[int]:
    """Distinct `customer_id` values with at least one `Holding` row, ordered."""
    statement = select(HoldingRow.customer_id).distinct().order_by(HoldingRow.customer_id)
    return list(session.execute(statement).scalars().all())


def _asset_class_to_entity(row: AssetClassRow) -> AssetClassEntity:
    return AssetClassEntity(id=row.id, code=row.code, name=row.name)


def _nav_snapshot_to_entity(row: NavSnapshotRow) -> NavSnapshotEntity:
    return NavSnapshotEntity(
        id=row.id,
        asset_class_id=row.asset_class_id,
        price_date=row.price_date,
        nav_value=minor_units_to_decimal(row.nav_value),
    )


def _holding_to_entity(row: HoldingRow) -> HoldingEntity:
    return HoldingEntity(
        id=row.id,
        customer_id=row.customer_id,
        asset_class_id=row.asset_class_id,
        current_value=minor_units_to_decimal(row.current_value),
        as_of_date=row.as_of_date,
    )
