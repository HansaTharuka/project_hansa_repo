"""rebalancing

Creates `rebalancing_recommendation`, `rebalancing_threshold` (data-models.md §4.12,
§4.15). Provenance: E8-S1.

Revision ID: 0007_rebalancing
Revises: 0006_goals
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_rebalancing"
down_revision: str | None = "0006_goals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("pending", "accepted", "dismissed")


def upgrade() -> None:
    op.create_table(
        "rebalancing_recommendation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False
        ),
        sa.Column("recommendation_id", sa.Text(), nullable=False),
        sa.Column("proposed_actions_json", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("generated_at", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN (" + ",".join(f"'{value}'" for value in STATUSES) + ")",
            name="ck_rr_status",
        ),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_rr_recommendation_id",
        "rebalancing_recommendation",
        ["recommendation_id"],
        unique=True,
    )
    op.create_index(
        "ix_rr_customer_status",
        "rebalancing_recommendation",
        ["customer_id", "status"],
    )

    op.create_table(
        "rebalancing_threshold",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("threshold_bps", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "threshold_bps BETWEEN 1 AND 10000", name="ck_rt_threshold_bps_range"
        ),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_rt_version", "rebalancing_threshold", ["version"], unique=True)
    op.create_index(
        "ix_rt_active",
        "rebalancing_threshold",
        ["is_active"],
        sqlite_where=sa.text("is_active = 1"),
    )


def downgrade() -> None:
    op.drop_index("ix_rt_active", table_name="rebalancing_threshold")
    op.drop_index("ix_rt_version", table_name="rebalancing_threshold")
    op.drop_table("rebalancing_threshold")
    op.drop_index(
        "ix_rr_customer_status", table_name="rebalancing_recommendation"
    )
    op.drop_index(
        "ix_rr_recommendation_id", table_name="rebalancing_recommendation"
    )
    op.drop_table("rebalancing_recommendation")
