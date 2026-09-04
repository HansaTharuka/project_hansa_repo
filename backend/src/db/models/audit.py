"""AuditLogEntry table (data-models.md §4.14) — append-only, insert-only (NFR-02).

The three indexes (`timestamp`, `entity_type, timestamp`, `actor_id, timestamp`)
mirror `alembic/versions/0002_audit_log.py` exactly — the migration already created
this table; this class only maps it.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

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


class AuditLogEntry(Base):
    """data-models.md §4.14 — insert-only; `details_json` carries ids/enums only."""

    __tablename__ = "audit_log_entry"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN (" + ",".join(f"'{value}'" for value in ENTITY_TYPES) + ")",
            name="ck_ale_entity_type",
        ),
        CheckConstraint(
            "actor_role IN (" + ",".join(f"'{value}'" for value in ROLES) + ")",
            name="ck_ale_actor_role",
        ),
        Index("ix_ale_timestamp", "timestamp"),
        Index("ix_ale_entity_type_ts", "entity_type", "timestamp"),
        Index("ix_ale_actor_ts", "actor_id", "timestamp"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[str] = mapped_column(nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    actor_role: Mapped[str] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(nullable=False)
    timestamp: Mapped[str] = mapped_column(nullable=False)
    details_json: Mapped[str] = mapped_column(nullable=False)
