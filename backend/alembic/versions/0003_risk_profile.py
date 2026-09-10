"""risk profile

Creates `risk_band_rule`, `risk_profile_answer`, `risk_band_assignment`
(data-models.md §4.3, §4.4, §4.5). Provenance: E4-S1.

`risk_band_assignment.rule_version` is a documented soft reference to
`risk_band_rule.version` — deliberately no foreign key (data-models.md §4.4, ut-032):
a referencing row can be written before the referenced rule exists, which is exactly
what this story's own seed step does (rule_version = 1, seeded before any
`RiskBandRule` row — E4-S1 seeds that later).

Revision ID: 0003_risk_profile
Revises: 0002_audit_log
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_risk_profile"
down_revision: str | None = "0002_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RISK_BANDS = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


def upgrade() -> None:
    op.create_table(
        "risk_band_rule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("questionnaire_json", sa.Text(), nullable=False),
        sa.Column("scoring_rules_json", sa.Text(), nullable=False),
        sa.Column("published_at", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_rbr_version", "risk_band_rule", ["version"], unique=True)
    op.create_index(
        "ix_rbr_active",
        "risk_band_rule",
        ["is_active"],
        sqlite_where=sa.text("is_active = 1"),
    )

    op.create_table(
        "risk_profile_answer",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False
        ),
        sa.Column("question_id", sa.Text(), nullable=False),
        sa.Column("answer_value", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_rpa_customer_submitted",
        "risk_profile_answer",
        ["customer_id", "submitted_at"],
    )

    op.create_table(
        "risk_band_assignment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "customer_id", sa.Integer(), sa.ForeignKey("customer.id"), nullable=False
        ),
        sa.Column("risk_band", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "risk_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_rba_risk_band",
        ),
        sqlite_autoincrement=True,
    )
    op.execute(
        "CREATE INDEX ix_rba_customer_assigned ON risk_band_assignment "
        "(customer_id, assigned_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rba_customer_assigned")
    op.drop_table("risk_band_assignment")
    op.drop_index("ix_rpa_customer_submitted", table_name="risk_profile_answer")
    op.drop_table("risk_profile_answer")
    op.drop_index("ix_rbr_active", table_name="risk_band_rule")
    op.drop_index("ix_rbr_version", table_name="risk_band_rule")
    op.drop_table("risk_band_rule")
