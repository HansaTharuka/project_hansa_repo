"""`db/engine.py` tests — pragma registration and Settings-driven construction."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from src.db.engine import create_sqlite_engine, get_engine

TEST_JWT_SECRET = "test-jwt-secret-for-engine-tests"  # pragma: allowlist secret


def test_create_sqlite_engine_sets_foreign_keys_pragma(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'engine-pragmas.db').as_posix()}"
    engine = create_sqlite_engine(database_url)
    try:
        with engine.connect() as connection:
            value = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        assert value == 1
    finally:
        engine.dispose()


def test_create_sqlite_engine_sets_wal_journal_mode(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'engine-pragmas.db').as_posix()}"
    engine = create_sqlite_engine(database_url)
    try:
        with engine.connect() as connection:
            value = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        assert str(value).lower() == "wal"
    finally:
        engine.dispose()


def test_create_sqlite_engine_sets_busy_timeout(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'engine-pragmas.db').as_posix()}"
    engine = create_sqlite_engine(database_url)
    try:
        with engine.connect() as connection:
            value = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
        assert value == 5000
    finally:
        engine.dispose()


def test_get_engine_builds_from_settings_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'get-engine.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    engine = get_engine()
    try:
        assert str(engine.url) == database_url
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    finally:
        engine.dispose()
