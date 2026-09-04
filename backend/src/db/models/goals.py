"""Goal / GoalProgressSnapshot tables (data-models.md §4.7, §4.8). Mirrors
`alembic/versions/0006_goals.py` exactly.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Goal(Base):
    """data-models.md §4.7 — mutable (AC-03); one of only two genuinely mutable tables."""

    __tablename__ = "goal"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="ck_goal_target_amount_positive"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_goal_priority_range"),
        Index("ix_goal_customer", "customer_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False)
    target_amount: Mapped[int] = mapped_column(nullable=False)
    target_date: Mapped[str] = mapped_column(nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class GoalProgressSnapshot(Base):
    """data-models.md §4.8 — append-only; `percent_complete` capped at 20000 bps."""

    __tablename__ = "goal_progress_snapshot"
    __table_args__ = (
        CheckConstraint("current_value >= 0", name="ck_gps_current_value_non_negative"),
        CheckConstraint(
            "percent_complete BETWEEN 0 AND 20000", name="ck_gps_percent_complete_range"
        ),
        Index("ix_gps_goal_pricedate", "goal_id", "price_date", unique=True),
        Index("ix_gps_goal_snapshot", "goal_id", "snapshot_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id"), nullable=False)
    current_value: Mapped[int] = mapped_column(nullable=False)
    percent_complete: Mapped[int] = mapped_column(nullable=False)
    snapshot_at: Mapped[str] = mapped_column(nullable=False)
    price_date: Mapped[str] = mapped_column(nullable=False)
