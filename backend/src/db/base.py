"""SQLAlchemy declarative base shared by every ORM model (data-models.md §1).

Column conventions enforced by every model that subclasses `Base`: `id INTEGER
PRIMARY KEY AUTOINCREMENT`; timestamps and dates are `TEXT` (ISO-8601 UTC / YYYY-MM-DD);
booleans are `INTEGER` 0/1; money and percentages are `INTEGER` (minor units / basis
points, never `float`, NFR-01).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Every table in `backend/src/db/models.py` subclasses this."""
