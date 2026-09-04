"""`domain/holdings/csv_loader.py` tests (E6-S1 AC1, AC2; ut-068, ut-069)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.domain.holdings.csv_loader import load_seed_csvs

SEED_ROOT = Path(__file__).resolve().parents[2] / "seed"
ASSET_CLASSES_CSV = SEED_ROOT / "asset_classes.csv"
NAV_INITIAL_CSV = SEED_ROOT / "nav_initial.csv"


def test_loading_an_empty_database_inserts_asset_classes_and_one_nav_row_each(
    db_session: Session,
) -> None:
    load_seed_csvs(
        db_session, asset_classes_csv=ASSET_CLASSES_CSV, nav_initial_csv=NAV_INITIAL_CSV
    )
    db_session.commit()

    asset_class_count = db_session.execute(
        text("SELECT COUNT(*) FROM asset_class")
    ).scalar_one()
    nav_count = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()

    assert 5 <= asset_class_count <= 6
    assert nav_count == asset_class_count


def test_running_the_loader_twice_creates_no_duplicate_rows(db_session: Session) -> None:
    load_seed_csvs(
        db_session, asset_classes_csv=ASSET_CLASSES_CSV, nav_initial_csv=NAV_INITIAL_CSV
    )
    db_session.commit()
    before_asset_classes = db_session.execute(
        text("SELECT COUNT(*) FROM asset_class")
    ).scalar_one()
    before_nav = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()

    load_seed_csvs(
        db_session, asset_classes_csv=ASSET_CLASSES_CSV, nav_initial_csv=NAV_INITIAL_CSV
    )
    db_session.commit()

    after_asset_classes = db_session.execute(
        text("SELECT COUNT(*) FROM asset_class")
    ).scalar_one()
    after_nav = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()

    assert after_asset_classes == before_asset_classes
    assert after_nav == before_nav
