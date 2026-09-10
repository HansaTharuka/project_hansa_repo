"""SQLite engine construction: WAL journal mode, `foreign_keys` pragma, busy timeout.

`PRAGMA foreign_keys = ON` is OFF by default on every new SQLite connection unless
set explicitly (data-models.md §1). Registering it on the driver-level `connect`
event — rather than once per `Engine` — is what makes it apply to every pooled
connection, including ones opened after the pool recycles (E1-S3 AC1, ut-034).
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

from src.core.config import Settings

BUSY_TIMEOUT_MS = 5000


def create_sqlite_engine(database_url: str) -> Engine:
    """Build an `Engine` with SQLite pragmas registered on every new connection."""
    engine = create_engine(database_url, future=True)
    _register_pragmas(engine)
    return engine


def _register_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(
        dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
    ) -> None:
        del connection_record  # unused — required by the SQLAlchemy event signature
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        cursor.close()


def get_engine() -> Engine:
    """Build the application's engine from `core.config.Settings.database_url`."""
    settings = Settings()
    return create_sqlite_engine(settings.database_url)
