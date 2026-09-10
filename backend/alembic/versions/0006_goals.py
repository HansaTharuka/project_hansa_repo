"""goals

Creates `goal`, `goal_progress_snapshot` (data-models.md §4.7, §4.8). Provenance: E7-S1.

Revision ID: 0006_goals
Revises: 0005_asset_class_nav_holding
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_goals"
down_revision: str | None = "0005_asset_class_nav_holding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goal",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False
        ),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint("target_amount > 0", name="ck_goal_target_amount_positive"),
        sa.CheckConstraint(
            "priority BETWEEN 1 AND 5", name="ck_goal_priority_range"
        ),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_goal_customer", "goal", ["customer_id"])

    op.create_table(
        "goal_progress_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("goal.id"), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.Column("percent_complete", sa.Integer(), nullable=False),
        sa.Column("snapshot_at", sa.Text(), nullable=False),
        sa.Column("price_date", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "current_value >= 0", name="ck_gps_current_value_non_negative"
        ),
        sa.CheckConstraint(
            "percent_complete BETWEEN 0 AND 20000", name="ck_gps_percent_complete_range"
        ),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_gps_goal_pricedate",
        "goal_progress_snapshot",
        ["goal_id", "price_date"],
        unique=True,
    )
    op.execute(
        "CREATE INDEX ix_gps_goal_snapshot ON goal_progress_snapshot "
        "(goal_id, snapshot_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_gps_goal_snapshot")
    op.drop_index("ix_gps_goal_pricedate", table_name="goal_progress_snapshot")
    op.drop_table("goal_progress_snapshot")
    op.drop_index("ix_goal_customer", table_name="goal")
    op.drop_table("goal")
