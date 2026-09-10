"""RebalancingRecommendation / RebalancingThreshold tables (data-models.md §4.12,
§4.15). Mirrors `alembic/versions/0007_rebalancing.py` exactly.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

STATUSES = ("pending", "accepted", "dismissed")


class RebalancingRecommendation(Base):
    """data-models.md §4.12 — append-only with one-shot status transition."""

    __tablename__ = "rebalancing_recommendation"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ",".join(f"'{value}'" for value in STATUSES) + ")",
            name="ck_rr_status",
        ),
        Index("ix_rr_recommendation_id", "recommendation_id", unique=True),
        Index("ix_rr_customer_status", "customer_id", "status"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False)
    recommendation_id: Mapped[str] = mapped_column(nullable=False)
    proposed_actions_json: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, server_default=text("'pending'"))
    generated_at: Mapped[str] = mapped_column(nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(nullable=True)


class RebalancingThreshold(Base):
    """data-models.md §4.15 — insert-only, versioned; `threshold_bps` never updated."""

    __tablename__ = "rebalancing_threshold"
    __table_args__ = (
        CheckConstraint(
            "threshold_bps BETWEEN 1 AND 10000", name="ck_rt_threshold_bps_range"
        ),
        Index("ix_rt_version", "version", unique=True),
        Index("ix_rt_active", "is_active", sqlite_where="is_active = 1"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(nullable=False)
    threshold_bps: Mapped[int] = mapped_column(nullable=False)
    published_at: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False)
