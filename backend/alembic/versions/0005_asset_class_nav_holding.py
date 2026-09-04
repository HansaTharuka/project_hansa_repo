"""asset class, nav snapshot, holding

Creates `asset_class`, `nav_snapshot`, `holding` (data-models.md §4.9, §4.10, §4.11).
Provenance: E6-S1. This story's own `seed.py` inserts baseline `asset_class` rows
directly (component-map.md note 4) using this migration's schema.

Revision ID: 0005_asset_class_nav_holding
Revises: 0004_allocation_template
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_asset_class_nav_holding"
down_revision: str | None = "0004_allocation_template"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_class",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_ac_code", "asset_class", ["code"], unique=True)

    op.create_table(
        "nav_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "asset_class_id",
            sa.Integer(),
            sa.ForeignKey("asset_class.id"),
            nullable=False,
        ),
        sa.Column("price_date", sa.Text(), nullable=False),
        sa.Column("nav_value", sa.Integer(), nullable=False),
        sa.CheckConstraint("nav_value > 0", name="ck_nav_value_positive"),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_nav_ac_date", "nav_snapshot", ["asset_class_id", "price_date"], unique=True
    )
    op.execute(
        "CREATE INDEX ix_nav_ac_date_desc ON nav_snapshot "
        "(asset_class_id, price_date DESC)"
    )

    op.create_table(
        "holding",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False
        ),
        sa.Column(
            "asset_class_id",
            sa.Integer(),
            sa.ForeignKey("asset_class.id"),
            nullable=False,
        ),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Text(), nullable=False),
        sa.CheckConstraint("current_value >= 0", name="ck_holding_value_non_negative"),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_holding_customer_ac",
        "holding",
        ["customer_id", "asset_class_id"],
        unique=True,
    )
    op.create_index("ix_holding_customer", "holding", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_holding_customer", table_name="holding")
    op.drop_index("ix_holding_customer_ac", table_name="holding")
    op.drop_table("holding")
    op.execute("DROP INDEX IF EXISTS ix_nav_ac_date_desc")
    op.drop_index("ix_nav_ac_date", table_name="nav_snapshot")
    op.drop_table("nav_snapshot")
    op.drop_index("ix_ac_code", table_name="asset_class")
    op.drop_table("asset_class")
