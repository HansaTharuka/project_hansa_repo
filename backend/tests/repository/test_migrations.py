"""Migration-chain structural tests (E1-S3 AC1, AC3, AC5; ut-031..034, ut-037, ut-041, ut-044).

Runs `alembic upgrade head` against a fresh, per-test SQLite file (via the
`migrated_engine` fixture) and introspects the result with SQLAlchemy's `Inspector`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "user",
    "customer",
    "audit_log_entry",
    "risk_band_rule",
    "risk_profile_answer",
    "risk_band_assignment",
    "allocation_template",
    "asset_class",
    "nav_snapshot",
    "holding",
    "goal",
    "goal_progress_snapshot",
    "rebalancing_recommendation",
    "rebalancing_threshold",
    "advisor_override",
}

# table -> {column: (referred_table, referred_column)}
EXPECTED_FOREIGN_KEYS: dict[str, dict[str, tuple[str, str]]] = {
    "customer": {"user_id": ("user", "id")},
    "risk_profile_answer": {"customer_id": ("customer", "id")},
    "risk_band_assignment": {"customer_id": ("customer", "id")},
    "goal": {"customer_id": ("customer", "id")},
    "goal_progress_snapshot": {"goal_id": ("goal", "id")},
    "nav_snapshot": {"asset_class_id": ("asset_class", "id")},
    "holding": {
        "customer_id": ("customer", "id"),
        "asset_class_id": ("asset_class", "id"),
    },
    "rebalancing_recommendation": {"customer_id": ("customer", "id")},
    "advisor_override": {
        "customer_id": ("customer", "id"),
        "advisor_id": ("user", "id"),
    },
    "audit_log_entry": {"actor_id": ("user", "id")},
}


def _foreign_key_map(engine: Engine, table: str) -> dict[str, tuple[str, str]]:
    inspector = inspect(engine)
    result: dict[str, tuple[str, str]] = {}
    for fk in inspector.get_foreign_keys(table):
        column = fk["constrained_columns"][0]
        referred_column = fk["referred_columns"][0]
        result[column] = (fk["referred_table"], referred_column)
    return result


def test_upgrade_head_creates_exactly_the_fifteen_entity_tables(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table_names = set(inspector.get_table_names())
    assert table_names == EXPECTED_TABLES | {"alembic_version"}


@pytest.mark.parametrize("table", sorted(EXPECTED_FOREIGN_KEYS))
def test_foreign_keys_target_the_correct_parent(table: str, migrated_engine: Engine) -> None:
    assert _foreign_key_map(migrated_engine, table) == EXPECTED_FOREIGN_KEYS[table]


def test_allocation_template_has_no_foreign_key(migrated_engine: Engine) -> None:
    # allocations_json references asset classes only inside the JSON document
    # (data-models.md §3) — renaming an asset class must never rewrite a
    # published template (E10-S1 AC4).
    assert _foreign_key_map(migrated_engine, "allocation_template") == {}


def test_risk_band_assignment_rule_version_has_no_foreign_key(migrated_engine: Engine) -> None:
    # rule_version is a soft reference to risk_band_rule.version (data-models.md §4.4):
    # only customer_id is a real foreign key on this table.
    assert set(_foreign_key_map(migrated_engine, "risk_band_assignment")) == {"customer_id"}


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_primary_key_is_exactly_id(table: str, migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    pk = inspector.get_pk_constraint(table)
    assert pk["constrained_columns"] == ["id"]


def test_autoincrementing_id_yields_distinct_increasing_ids(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        first = connection.execute(
            text("INSERT INTO asset_class (code, name) VALUES ('EQ_DM', 'Developed Markets')")
        ).lastrowid
        second = connection.execute(
            text("INSERT INTO asset_class (code, name) VALUES ('EQ_EM', 'Emerging Markets')")
        ).lastrowid
    assert isinstance(first, int)
    assert isinstance(second, int)
    assert second > first


def test_foreign_keys_pragma_is_enforced_on_every_connection(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user (email, password_hash, role, created_at) "
                "VALUES ('fk.pragma.check@wealthwise.test', 'x', 'customer', "
                "'2026-09-01T09:00:00Z')"
            )
        )
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO customer (user_id, kyc_verified, created_at) "
                    "VALUES (999999, 1, '2026-09-01T09:00:00Z')"
                )
            )


def test_customer_kyc_verified_defaults_to_true(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user (email, password_hash, role, created_at) "
                "VALUES ('kyc.default.check@wealthwise.test', 'x', 'customer', "
                "'2026-09-01T09:00:00Z')"
            )
        )
        user_id = connection.execute(
            text("SELECT id FROM user WHERE email = 'kyc.default.check@wealthwise.test'")
        ).scalar_one()
        connection.execute(
            text("INSERT INTO customer (user_id, created_at) VALUES (:user_id, :created_at)"),
            {"user_id": user_id, "created_at": "2026-09-01T09:00:00Z"},
        )
    with migrated_engine.begin() as connection:
        kyc_verified = connection.execute(
            text("SELECT kyc_verified FROM customer WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).scalar_one()
    assert bool(kyc_verified) is True


def test_upgrading_an_already_migrated_database_is_idempotent(
    migrated_engine: Engine, database_url: str
) -> None:
    inspector_before = inspect(migrated_engine)
    tables_before = set(inspector_before.get_table_names())
    with migrated_engine.begin() as connection:
        version_before = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    from alembic import command

    command.upgrade(alembic_config(database_url), "head")

    inspector_after = inspect(migrated_engine)
    tables_after = set(inspector_after.get_table_names())
    with migrated_engine.begin() as connection:
        rows_after = connection.execute(text("SELECT version_num FROM alembic_version")).all()

    assert tables_after == tables_before
    assert len(rows_after) == 1
    assert rows_after[0][0] == version_before


def test_env_py_targets_database_url_from_settings(
    migrated_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # migrated_engine already migrated the FIRST database (from the `database_url`
    # fixture). Point DATABASE_URL at a SECOND, distinct file and upgrade that one.
    from alembic import command

    second_db_path = tmp_path / "second-wealthwise-test.db"
    second_database_url = f"sqlite:///{second_db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", second_database_url)

    command.upgrade(alembic_config(second_database_url), "head")

    from sqlalchemy import create_engine

    second_engine = create_engine(second_database_url, future=True)
    try:
        second_tables = set(inspect(second_engine).get_table_names())
    finally:
        second_engine.dispose()
    assert second_tables == EXPECTED_TABLES | {"alembic_version"}

    # the FIRST database is untouched by the second upgrade.
    first_tables = set(inspect(migrated_engine).get_table_names())
    assert first_tables == EXPECTED_TABLES | {"alembic_version"}
