"""AllocationTemplate table (data-models.md §4.6). Mirrors
`alembic/versions/0004_allocation_template.py` exactly.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

RISK_BANDS = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


class AllocationTemplate(Base):
    """data-models.md §4.6 — insert-only, immutable once published (AC-02, AC-10)."""

    __tablename__ = "allocation_template"
    __table_args__ = (
        CheckConstraint(
            "risk_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_at_risk_band",
        ),
        Index("ix_at_band_version", "risk_band", "version", unique=True),
        Index("ix_at_band_active", "risk_band", "is_active"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(nullable=False)
    risk_band: Mapped[str] = mapped_column(nullable=False)
    allocations_json: Mapped[str] = mapped_column(nullable=False)
    published_at: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False)
