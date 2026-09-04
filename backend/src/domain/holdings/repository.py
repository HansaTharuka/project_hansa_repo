"""AssetClass / NavSnapshot persistence (E6-S1).

`NavSnapshot` is append-only — no `update_*` function exists for it (AC3). A new
price for the same asset class on a later `price_date` is always a new inserted
row. `nav_value` round-trips as `Decimal`, converted through
`types.fixedpoint` at the repository boundary only; the underlying column stores
integer minor units, never a Python `float` (AC5, NFR-01).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AssetClass as AssetClassRow
from src.db.models import NavSnapshot as NavSnapshotRow
from src.types.entities import AssetClass as AssetClassEntity
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


def _asset_class_to_entity(row: AssetClassRow) -> AssetClassEntity:
    return AssetClassEntity(id=row.id, code=row.code, name=row.name)


def _nav_snapshot_to_entity(row: NavSnapshotRow) -> NavSnapshotEntity:
    return NavSnapshotEntity(
        id=row.id,
        asset_class_id=row.asset_class_id,
        price_date=row.price_date,
        nav_value=minor_units_to_decimal(row.nav_value),
    )
