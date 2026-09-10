"""User / Customer reads, and a User create for round-trip testing (E1-S3 AC4).

Every query here is built through SQLAlchemy ORM construction: no string-formatted
SQL text is assembled anywhere in this module. A caller-supplied value (e.g. an
email containing SQL metacharacters) is always bound as literal query data, never
concatenated into the statement. bcrypt verification and JWT issuance are
service-layer concerns added by E2-S1, not here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Customer, User


def get_user_by_email(session: Session, email: str) -> User | None:
    """Look up a user by exact email match. Returns `None` if no row matches."""
    statement = select(User).where(User.email == email)
    return session.execute(statement).scalar_one_or_none()


def get_user_by_id(session: Session, user_id: int) -> User | None:
    """Look up a user by primary key. Returns `None` if no row matches."""
    statement = select(User).where(User.id == user_id)
    return session.execute(statement).scalar_one_or_none()


def get_customer_by_user_id(session: Session, user_id: int) -> Customer | None:
    """Look up the customer profile for a given user id, if one exists."""
    statement = select(Customer).where(Customer.user_id == user_id)
    return session.execute(statement).scalar_one_or_none()


def get_customer_by_id(session: Session, customer_id: int) -> Customer | None:
    """Look up a customer profile by its own primary key (e.g. the
    `kyc_verified` gate `domain.rebalancing.service` checks, E8-S2 AC4)."""
    statement = select(Customer).where(Customer.id == customer_id)
    return session.execute(statement).scalar_one_or_none()


def list_customers(session: Session) -> list[Customer]:
    """Every `Customer` row, ordered by id — the advisor customer list's
    source set (E9-S3 AC1)."""
    statement = select(Customer).order_by(Customer.id.asc())
    return list(session.execute(statement).scalars().all())


def create_user(
    session: Session, *, email: str, password_hash: str, role: str, created_at: str
) -> User:
    """Insert a new `User` row and flush so its generated `id` is available."""
    user = User(email=email, password_hash=password_hash, role=role, created_at=created_at)
    session.add(user)
    session.flush()
    return user
