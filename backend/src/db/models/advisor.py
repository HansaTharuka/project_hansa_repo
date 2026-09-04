"""AdvisorOverride table (data-models.md §4.13) — append-only, audited (NFR-02).
Mirrors `alembic/versions/0008_advisor_override.py` exactly.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

RISK_BANDS = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


class AdvisorOverride(Base):
    """data-models.md §4.13 — append-only; `reason` mandatory, `note` optional."""

    __tablename__ = "advisor_override"
    __table_args__ = (
        CheckConstraint(
            "previous_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_ao_previous_band",
        ),
        CheckConstraint(
            "new_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_ao_new_band",
        ),
        CheckConstraint("length(trim(reason)) >= 1", name="ck_ao_reason_not_blank"),
        Index("ix_ao_customer_created", "customer_id", "created_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    previous_band: Mapped[str] = mapped_column(nullable=False)
    new_band: Mapped[str] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
