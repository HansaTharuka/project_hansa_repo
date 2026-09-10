"""User / Customer tables (data-models.md §4.1, §4.2)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class User(Base):
    """data-models.md §4.1."""

    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(
            "role IN ('customer','advisor','admin','compliance')", name="ck_user_role"
        ),
        Index("ix_user_email", "email", unique=True),
        Index("ix_user_role", "role"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)


class Customer(Base):
    """data-models.md §4.2."""

    __tablename__ = "customer"
    __table_args__ = (
        Index("ix_customer_user_id", "user_id", unique=True),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    kyc_verified: Mapped[bool] = mapped_column(nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(nullable=False)
