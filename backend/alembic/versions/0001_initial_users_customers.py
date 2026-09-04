"""initial users and customers

Creates `user` and `customer` (data-models.md §4.1, §4.2). Root of the migration
chain — `down_revision` is `None`.

Revision ID: 0001_initial_users_customers
Revises:
Create Date: 2026-09-04

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_users_customers"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "role IN ('customer','advisor','admin','compliance')", name="ck_user_role"
        ),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_role", "user", ["role"])

    op.create_table(
        "customer",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "kyc_verified", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_customer_user_id", "customer", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_customer_user_id", table_name="customer")
    op.drop_table("customer")
    op.drop_index("ix_user_role", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
