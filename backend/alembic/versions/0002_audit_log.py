"""audit log entry

Creates `audit_log_entry` (data-models.md §4.14). Provenance: E3-S1 — the full
migration chain is authored here per component-map.md note 1.

Revision ID: 0002_audit_log
Revises: 0001_initial_users_customers
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_audit_log"
down_revision: str | None = "0001_initial_users_customers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTITY_TYPES = (
    "RiskBandAssignment",
    "AllocationRecommendation",
    "RebalancingRecommendation",
    "AdvisorOverride",
    "ManualRecommendation",
    "RiskBandRule",
    "AllocationTemplate",
    "AssetClass",
    "RebalancingThreshold",
)
ROLES = ("customer", "advisor", "admin", "compliance")


def upgrade() -> None:
    op.create_table(
        "audit_log_entry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN (" + ",".join(f"'{value}'" for value in ENTITY_TYPES) + ")",
            name="ck_ale_entity_type",
        ),
        sa.CheckConstraint(
            "actor_role IN (" + ",".join(f"'{value}'" for value in ROLES) + ")",
            name="ck_ale_actor_role",
        ),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_ale_timestamp", "audit_log_entry", ["timestamp"])
    op.create_index(
        "ix_ale_entity_type_ts", "audit_log_entry", ["entity_type", "timestamp"]
    )
    op.create_index("ix_ale_actor_ts", "audit_log_entry", ["actor_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_ale_actor_ts", table_name="audit_log_entry")
    op.drop_index("ix_ale_entity_type_ts", table_name="audit_log_entry")
    op.drop_index("ix_ale_timestamp", table_name="audit_log_entry")
    op.drop_table("audit_log_entry")
