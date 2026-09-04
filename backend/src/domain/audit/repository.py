"""AuditLogEntry persistence — insert-only (E3-S1 AC1, AC3; NFR-02).

Exposes exactly two operations: `insert_audit_entry` (write) and
`query_audit_entries` (read). No `update_*` / `delete_*` function exists anywhere
in this module — an audit trail that can be rewritten is not an audit trail.
Every query is built through SQLAlchemy ORM construction; no caller-supplied value
is ever concatenated into SQL text (NFR-08).

Both operations return the Pydantic mirror (`types.entities.AuditLogEntry`), not the
raw ORM row, so `details_json` comes back decoded as a `dict` without ever mutating
the ORM instance's mapped `str` column in place.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AuditLogEntry as AuditLogEntryRow
from src.types.entities import AuditDetailValue
from src.types.entities import AuditLogEntry as AuditLogEntryEntity


def insert_audit_entry(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    actor_id: int,
    actor_role: str,
    action: str,
    timestamp: str,
    details_json: dict[str, AuditDetailValue],
) -> AuditLogEntryEntity:
    """Insert one append-only audit row and flush so its `id` is available."""
    row = AuditLogEntryRow(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        timestamp=timestamp,
        details_json=json.dumps(details_json),
    )
    session.add(row)
    session.flush()
    return _to_entity(row)


def query_audit_entries(
    session: Session, *, entity_type: str, start: str, end: str
) -> list[AuditLogEntryEntity]:
    """Entries for `entity_type` within `[start, end]`, ordered by timestamp ascending."""
    statement = (
        select(AuditLogEntryRow)
        .where(AuditLogEntryRow.entity_type == entity_type)
        .where(AuditLogEntryRow.timestamp >= start)
        .where(AuditLogEntryRow.timestamp <= end)
        .order_by(AuditLogEntryRow.timestamp.asc())
    )
    rows = session.execute(statement).scalars().all()
    return [_to_entity(row) for row in rows]


def _to_entity(row: AuditLogEntryRow) -> AuditLogEntryEntity:
    """Decode `details_json` and build the closed, immutable Pydantic mirror."""
    return AuditLogEntryEntity(
        id=row.id,
        entity_type=row.entity_type,  # type: ignore[arg-type]
        entity_id=row.entity_id,
        actor_id=row.actor_id,
        actor_role=row.actor_role,  # type: ignore[arg-type]
        action=row.action,  # type: ignore[arg-type]
        timestamp=row.timestamp,
        details_json=json.loads(row.details_json),
    )
