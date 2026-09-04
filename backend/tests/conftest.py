"""Shared fixtures — a freshly migrated, per-test-function SQLite database (E1-S3).

`migrated_engine` sets `DATABASE_URL`/`JWT_SECRET` and runs `alembic upgrade head`
against a `tmp_path` SQLite file before any test body executes, so every repository
test starts from a clean, fully-migrated schema and no test shares state with
another (ut-043). `alembic_config` is exported (not just used internally) so tests
that need a second, independently-migrated database — e.g. ut-044 — can build one.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.engine import create_sqlite_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = BACKEND_ROOT / "alembic"

TEST_JWT_SECRET = "test-jwt-secret-not-used-outside-pytest"  # pragma: allowlist secret


def alembic_config(database_url: str) -> Config:
    """Build an Alembic `Config` targeting `database_url` for programmatic use."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'wealthwise-test.db').as_posix()}"


@pytest.fixture
def migrated_engine(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> Generator[Engine, None, None]:
    """A `db/engine.py`-built engine, migrated to `head`, torn down after the test."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    command.upgrade(alembic_config(database_url), "head")
    engine = create_sqlite_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_session(db_session: Session) -> Session:
    """A session whose database has already run `seed.seed_database` once."""
    from src.db.seed import seed_database

    seed_database(db_session)
    return db_session
