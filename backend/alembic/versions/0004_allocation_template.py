"""allocation template

Creates `allocation_template` (data-models.md §4.6). Provenance: E5-S1.
`allocations_json` references `asset_class_id` only inside the JSON document,
never via a database foreign key (data-models.md §3): renaming an asset class must
never rewrite a published, immutable template.

Revision ID: 0004_allocation_template
Revises: 0003_risk_profile
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_allocation_template"
down_revision: str | None = "0003_risk_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RISK_BANDS = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


def upgrade() -> None:
    op.create_table(
        "allocation_template",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("risk_band", sa.Text(), nullable=False),
        sa.Column("allocations_json", sa.Text(), nullable=False),
        sa.Column("published_at", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "risk_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_at_risk_band",
        ),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_at_band_version",
        "allocation_template",
        ["risk_band", "version"],
        unique=True,
    )
    op.create_index(
        "ix_at_band_active", "allocation_template", ["risk_band", "is_active"]
    )


def downgrade() -> None:
    op.drop_index("ix_at_band_active", table_name="allocation_template")
    op.drop_index("ix_at_band_version", table_name="allocation_template")
    op.drop_table("allocation_template")
