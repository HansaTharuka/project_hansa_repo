"""SQLAlchemy 2.x declarative models (data-models.md §4).

This story maps only `User` and `Customer` — the two tables `domain/auth/repository.py`
reads and writes. The full 15-table schema already exists after `alembic upgrade head`
(the migration chain is authored in full by this story — component-map.md note 1);
`backend/src/db/seed.py` writes its `AssetClass` and `RiskBandAssignment` rows through
parameterized `text()` statements rather than an ORM class, because those tables'
`Mapped`/`mapped_column` classes are added by the repository stories that own them
(E6-S1, E4-S1 — component-map.md note 2: "modified by every repository story").
"""

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
