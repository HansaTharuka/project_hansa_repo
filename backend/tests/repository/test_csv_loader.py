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
    load_seed_csvs(db_session, asset_classes_csv=ASSET_CLASSES_CSV, nav_initial_csv=NAV_INITIAL_CSV)
    db_session.commit()

    asset_class_count = db_session.execute(text("SELECT COUNT(*) FROM asset_class")).scalar_one()
    nav_count = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()

    assert 5 <= asset_class_count <= 6
    assert nav_count == asset_class_count


def test_a_nav_row_for_an_unknown_asset_class_code_is_skipped_not_an_error(
    db_session: Session, tmp_path: Path
) -> None:
    """`nav_initial.csv` rows referencing a `code` absent from `asset_classes.csv`
    (e.g. load order, or a stale seed row) are silently skipped rather than
    raising — no `AssetClass` exists yet to attach the `NavSnapshot` to."""
    asset_classes_csv = tmp_path / "asset_classes.csv"
    asset_classes_csv.write_text("code,name\nEQ_DM,Developed-Market Equity\n", encoding="utf-8")
    nav_initial_csv = tmp_path / "nav_initial.csv"
    nav_initial_csv.write_text(
        "code,price_date,nav_value\nEQ_DM,2026-09-01,100.00\nUNKNOWN_CODE,2026-09-01,50.00\n",
        encoding="utf-8",
    )

    load_seed_csvs(db_session, asset_classes_csv=asset_classes_csv, nav_initial_csv=nav_initial_csv)
    db_session.commit()

    asset_class_count = db_session.execute(text("SELECT COUNT(*) FROM asset_class")).scalar_one()
    nav_count = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()
    assert asset_class_count == 1
    assert nav_count == 1


def test_running_the_loader_twice_creates_no_duplicate_rows(db_session: Session) -> None:
    load_seed_csvs(db_session, asset_classes_csv=ASSET_CLASSES_CSV, nav_initial_csv=NAV_INITIAL_CSV)
    db_session.commit()
    before_asset_classes = db_session.execute(text("SELECT COUNT(*) FROM asset_class")).scalar_one()
    before_nav = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()

    load_seed_csvs(db_session, asset_classes_csv=ASSET_CLASSES_CSV, nav_initial_csv=NAV_INITIAL_CSV)
    db_session.commit()

    after_asset_classes = db_session.execute(text("SELECT COUNT(*) FROM asset_class")).scalar_one()
    after_nav = db_session.execute(text("SELECT COUNT(*) FROM nav_snapshot")).scalar_one()

    assert after_asset_classes == before_asset_classes
    assert after_nav == before_nav
