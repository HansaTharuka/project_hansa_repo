"""advisor override

Creates `advisor_override` (data-models.md §4.13) — the head of the migration chain.
Provenance: E9-S1.

Revision ID: 0008_advisor_override
Revises: 0007_rebalancing
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_advisor_override"
down_revision: str | None = "0007_rebalancing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RISK_BANDS = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


def upgrade() -> None:
    op.create_table(
        "advisor_override",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False
        ),
        sa.Column("advisor_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("previous_band", sa.Text(), nullable=False),
        sa.Column("new_band", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "previous_band IN ("
            + ",".join(f"'{value}'" for value in RISK_BANDS)
            + ")",
            name="ck_ao_previous_band",
        ),
        sa.CheckConstraint(
            "new_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_ao_new_band",
        ),
        sa.CheckConstraint("length(trim(reason)) >= 1", name="ck_ao_reason_not_blank"),
        sqlite_autoincrement=True,
    )
    op.execute(
        "CREATE INDEX ix_ao_customer_created ON advisor_override "
        "(customer_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ao_customer_created")
    op.drop_table("advisor_override")
