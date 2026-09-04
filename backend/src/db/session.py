"""Session factory and a per-unit-of-work context manager (folder-structure.md §2).

`get_session_factory()` builds the process-wide factory from `db/engine.py` lazily,
once. Callers that need an explicit transaction boundary — a seed run, a script —
use `session_scope`; request-scoped injection (`get_session` in `app/dependencies.py`)
is added by E2-S2 and builds directly on `get_session_factory()`.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.engine import get_engine

_session_factory: sessionmaker[Session] | None = None


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Construct a session factory bound to `engine`. Never auto-flushes mid-query."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory, building it from `get_engine()` once."""
    global _session_factory
    if _session_factory is None:
        _session_factory = build_session_factory(get_engine())
    return _session_factory


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Yield a session that commits on success and rolls back on any exception."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
