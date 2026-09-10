"""`db/session.py` tests — factory construction, unit-of-work commit/rollback."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import text

import src.db.session as session_module
from src.db.engine import create_sqlite_engine
from src.db.session import build_session_factory, get_session_factory, session_scope

TEST_JWT_SECRET = "test-jwt-secret-for-session-tests"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _reset_session_factory_singleton() -> Generator[None, None, None]:
    """`get_session_factory` memoizes a module-level global; isolate tests from it."""
    session_module._session_factory = None
    yield
    session_module._session_factory = None


def test_build_session_factory_binds_to_the_given_engine(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'factory.db').as_posix()}")
    try:
        factory = build_session_factory(engine)
        session = factory()
        try:
            assert session.get_bind() is engine
        finally:
            session.close()
    finally:
        engine.dispose()


def test_get_session_factory_builds_from_settings_and_memoizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'singleton.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)

    first = get_session_factory()
    second = get_session_factory()

    assert first is second


def test_session_scope_commits_on_success(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'scope-commit.db').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT)"))
        factory = build_session_factory(engine)

        with session_scope(factory) as session:
            session.execute(text("INSERT INTO probe (value) VALUES ('committed')"))

        with engine.connect() as connection:
            row = connection.execute(text("SELECT value FROM probe")).scalar_one()
        assert row == "committed"
    finally:
        engine.dispose()


def test_session_scope_rolls_back_on_exception(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'scope-rollback.db').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT)"))
        factory = build_session_factory(engine)

        with pytest.raises(ValueError, match="boom"):
            with session_scope(factory) as session:
                session.execute(text("INSERT INTO probe (value) VALUES ('rolled-back')"))
                raise ValueError("boom")

        with engine.connect() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM probe")).scalar_one()
        assert count == 0
    finally:
        engine.dispose()
