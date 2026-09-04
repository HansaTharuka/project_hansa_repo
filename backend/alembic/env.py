"""Alembic runtime wiring — resolves the target database from `core.config.Settings`.

Never a hardcoded path and never independent of the application's own config: the
migration tool and the running application always read `database_url` from the same
`Settings` object, sourced from the `DATABASE_URL` environment variable (folder-structure.md
§2, E1-S3 AC1, ut-044). `_env_file=None` keeps a developer's local `backend/.env` from
leaking into a monkeypatched-`DATABASE_URL` test run (testing SKILL.md).
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.core.config import Settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrations are authored by hand across every table (data-models.md §6), not
# generated from `Base.metadata` — `db/models.py` currently maps only the tables
# its own repository stories own (component-map.md note 2). Autogenerate is
# therefore not used and no comparison target is registered here.
target_metadata = None


def _database_url() -> str:
    return Settings(_env_file=None).database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection opened from `Settings.database_url`."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        _run_migrations_with_connection(connection)


def _run_migrations_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
