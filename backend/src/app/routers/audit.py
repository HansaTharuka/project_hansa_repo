"""GET /api/audit — compliance-role-only, filterable, paginated audit trail
(E3-S3 AC1-AC5; api-contracts.md §13.1).

Only `GET` is ever registered on this router — no write verb exists anywhere
in this module, so FastAPI itself answers POST/PUT/PATCH/DELETE with its own
405 (AC3), never a hand-rolled one. `require_role("compliance")` is the sole
authorisation check (AC2, AC5); this router calls `domain.audit.service`
only, never `domain.audit.repository` directly (system-design.md D3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.audit.service import list_audit_entries
from src.types.entities import AuditDetailValue

router = APIRouter(prefix="/api/audit", tags=["audit"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class AuditEntryResponse(BaseModel):
    """One `AuditLogEntry` row (api-contracts.md §13.1)."""

    id: int
    entity_type: str
    entity_id: str
    actor_id: int
    actor_role: str
    action: str
    timestamp: str
    details_json: dict[str, AuditDetailValue]


class AuditPageResponse(BaseModel):
    """The paginated envelope every `GET /api/audit` response uses."""

    total: int
    limit: int
    offset: int
    entries: list[AuditEntryResponse]


@router.get("", status_code=200)
def get_audit_entries(
    actor_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_role("compliance")),
    session: Session = Depends(get_session),
) -> AuditPageResponse:
    """Compliance-only paginated read of the audit trail (AC1, AC4)."""
    del user
    page = list_audit_entries(
        session,
        actor_id=actor_id,
        entity_type=entity_type,
        start=from_,
        end=to,
        limit=limit,
        offset=offset,
    )
    return AuditPageResponse(
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        entries=[
            AuditEntryResponse(
                id=entry.id,
                entity_type=entry.entity_type.value,
                entity_id=entry.entity_id,
                actor_id=entry.actor_id,
                actor_role=entry.actor_role.value,
                action=entry.action.value,
                timestamp=entry.timestamp,
                details_json=entry.details_json,
            )
            for entry in page.entries
        ],
    )
