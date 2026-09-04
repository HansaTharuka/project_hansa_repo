"""AssetClass / NavSnapshot / Holding tables (data-models.md §4.9, §4.10, §4.11).
Mirrors `alembic/versions/0005_asset_class_nav_holding.py` exactly.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AssetClass(Base):
    """data-models.md §4.9 — master data, mutable (E10-S1 AC4)."""

    __tablename__ = "asset_class"
    __table_args__ = (
        Index("ix_ac_code", "code", unique=True),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)


class NavSnapshot(Base):
    """data-models.md §4.10 — append-only price per asset class per simulated date."""

    __tablename__ = "nav_snapshot"
    __table_args__ = (
        CheckConstraint("nav_value > 0", name="ck_nav_value_positive"),
        Index("ix_nav_ac_date", "asset_class_id", "price_date", unique=True),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_class_id: Mapped[int] = mapped_column(ForeignKey("asset_class.id"), nullable=False)
    price_date: Mapped[str] = mapped_column(nullable=False)
    nav_value: Mapped[int] = mapped_column(nullable=False)


class Holding(Base):
    """data-models.md §4.11 — a current position, revalued on each advance-a-day."""

    __tablename__ = "holding"
    __table_args__ = (
        CheckConstraint("current_value >= 0", name="ck_holding_value_non_negative"),
        Index("ix_holding_customer_ac", "customer_id", "asset_class_id", unique=True),
        Index("ix_holding_customer", "customer_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False)
    asset_class_id: Mapped[int] = mapped_column(ForeignKey("asset_class.id"), nullable=False)
    current_value: Mapped[int] = mapped_column(nullable=False)
    as_of_date: Mapped[str] = mapped_column(nullable=False)
