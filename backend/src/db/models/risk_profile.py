"""RiskBandRule / RiskProfileAnswer / RiskBandAssignment tables (data-models.md
§4.5, §4.3, §4.4). Mirrors `alembic/versions/0003_risk_profile.py` exactly.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

RISK_BANDS = ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")


class RiskBandRule(Base):
    """data-models.md §4.5 — insert-only, immutable once published (AC-10)."""

    __tablename__ = "risk_band_rule"
    __table_args__ = (
        Index("ix_rbr_version", "version", unique=True),
        Index("ix_rbr_active", "is_active", sqlite_where="is_active = 1"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(nullable=False)
    questionnaire_json: Mapped[str] = mapped_column(nullable=False)
    scoring_rules_json: Mapped[str] = mapped_column(nullable=False)
    published_at: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False)


class RiskProfileAnswer(Base):
    """data-models.md §4.3 — append-only (NFR-02)."""

    __tablename__ = "risk_profile_answer"
    __table_args__ = (
        Index("ix_rpa_customer_submitted", "customer_id", "submitted_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(nullable=False)
    answer_value: Mapped[str] = mapped_column(nullable=False)
    submitted_at: Mapped[str] = mapped_column(nullable=False)


class RiskBandAssignment(Base):
    """data-models.md §4.4 — append-only; `rule_version` pins the rule used."""

    __tablename__ = "risk_band_assignment"
    __table_args__ = (
        CheckConstraint(
            "risk_band IN (" + ",".join(f"'{value}'" for value in RISK_BANDS) + ")",
            name="ck_rba_risk_band",
        ),
        Index("ix_rba_customer_assigned", "customer_id", "assigned_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False)
    risk_band: Mapped[str] = mapped_column(nullable=False)
    rule_version: Mapped[int] = mapped_column(nullable=False)
    assigned_at: Mapped[str] = mapped_column(nullable=False)
