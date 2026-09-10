"""Central audit-writer service (E3-S2) — the single reusable entry point every
domain service (risk profiling, recommendation, rebalancing, advisor override,
admin publish) calls to record an audit entry, so audit logging is consistent
and cannot be bypassed by a service writing its own ad hoc insert.

`write_audit_entry` does exactly one thing: validate `actor_role`, then delegate
to `domain.audit.repository.insert_audit_entry`, which always inserts a new row
(AC1, AC4). It never catches an exception from the repository — a failure here
must propagate to the caller rather than being silently swallowed, so a caller
can never commit a business action while losing its audit trail (AC5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.domain.audit.repository import count_audit_entries, insert_audit_entry, query_audit_entries
from src.types.entities import AuditDetailValue
from src.types.entities import AuditLogEntry as AuditLogEntryEntity
from src.types.enums import Role
from src.types.errors import ValidationError

ALLOWED_ACTOR_ROLES = frozenset(role.value for role in Role)


@dataclass(frozen=True)
class AuditPage:
    """One page of the audit trail (E3-S3 AC1; api-contracts.md §13.1)."""

    total: int
    limit: int
    offset: int
    entries: tuple[AuditLogEntryEntity, ...]


def write_audit_entry(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    actor_id: int,
    actor_role: str,
    action: str,
    details: dict[str, AuditDetailValue],
) -> AuditLogEntryEntity:
    """Insert exactly one audit row (AC1).

    Raises `ValidationError` (422) if `actor_role` is missing or not one of
    `{customer, advisor, admin, compliance}` (AC2) — before the repository is
    ever touched, so an invalid call never produces a partial row.
    """
    if not actor_role or actor_role not in ALLOWED_ACTOR_ROLES:
        raise ValidationError(
            f"actor_role must be one of {sorted(ALLOWED_ACTOR_ROLES)}, got {actor_role!r}.",
            code="INVALID_ACTOR_ROLE",
            details={"actor_role": actor_role},
        )
    return insert_audit_entry(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        timestamp=_now_iso(),
        details_json=details,
    )


def list_audit_entries(
    session: Session,
    *,
    actor_id: int | None = None,
    entity_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditPage:
    """One filterable, paginated page of the audit trail (E3-S3 AC1, AC4) —
    the read-side counterpart `app.routers.audit` calls so the router never
    imports `domain.audit.repository` directly."""
    entries = query_audit_entries(
        session,
        entity_type=entity_type,
        actor_id=actor_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
    total = count_audit_entries(
        session, entity_type=entity_type, actor_id=actor_id, start=start, end=end
    )
    return AuditPage(total=total, limit=limit, offset=offset, entries=tuple(entries))


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
