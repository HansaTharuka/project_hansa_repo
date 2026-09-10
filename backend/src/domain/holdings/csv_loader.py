"""Idempotent seed-CSV loader for `AssetClass` and the initial `NavSnapshot` row
per asset class (E6-S1 AC1, AC2).

Re-running against an already-seeded database inserts nothing new: `AssetClass`
lookup is by its unique `code`, `NavSnapshot` lookup is by
`(asset_class_id, price_date)` — both already enforced as unique indexes by
`alembic/versions/0005_asset_class_nav_holding.py`.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from src.domain.holdings.repository import (
    get_asset_class_by_code,
    get_nav_by_asset_class_and_date,
    insert_asset_class,
    insert_nav_snapshot,
)

DEFAULT_ASSET_CLASSES_CSV = Path(__file__).resolve().parents[3] / "seed" / "asset_classes.csv"
DEFAULT_NAV_INITIAL_CSV = Path(__file__).resolve().parents[3] / "seed" / "nav_initial.csv"


def load_seed_csvs(
    session: Session,
    *,
    asset_classes_csv: Path = DEFAULT_ASSET_CLASSES_CSV,
    nav_initial_csv: Path = DEFAULT_NAV_INITIAL_CSV,
) -> None:
    """Load `asset_classes_csv` then `nav_initial_csv`, idempotently."""
    _load_asset_classes(session, asset_classes_csv)
    _load_initial_nav(session, nav_initial_csv)


def _load_asset_classes(session: Session, path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            code = row["code"]
            if get_asset_class_by_code(session, code) is not None:
                continue
            insert_asset_class(session, code=code, name=row["name"])


def _load_initial_nav(session: Session, path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            asset_class = get_asset_class_by_code(session, row["code"])
            if asset_class is None:
                continue
            price_date = row["price_date"]
            if (
                get_nav_by_asset_class_and_date(
                    session, asset_class_id=asset_class.id, price_date=price_date
                )
                is not None
            ):
                continue
            insert_nav_snapshot(
                session,
                asset_class_id=asset_class.id,
                price_date=price_date,
                nav_value=Decimal(row["nav_value"]),
            )
