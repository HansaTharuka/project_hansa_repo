"""Risk-profile submission service (E4-S2) — wires `scoring.score_answers` to
persistence: records the customer's raw answers, computes the deterministic
risk band from the active `RiskBandRule`, inserts a new `RiskBandAssignment`,
and audits the assignment exactly once.

Ordering matters for AC2: `score_answers` runs — and can raise
`ValidationError` for an incomplete answer set — before either
`insert_answers` or `insert_assignment` is called, so an incomplete
submission persists nothing at all, not even the raw answers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.domain.audit.service import write_audit_entry
from src.domain.risk_profile.repository import (
    get_active_rule,
    get_latest_assignment,
    insert_answers,
    insert_assignment,
)
from src.domain.risk_profile.scoring import score_answers
from src.types.entities import RiskBandAssignment, RiskBandRule
from src.types.errors import NotFoundError


def submit_risk_profile(
    session: Session,
    *,
    customer_id: int,
    answers: dict[str, str],
    actor_id: int,
    actor_role: str,
) -> RiskBandAssignment:
    """Score `answers` against the active `RiskBandRule` and persist the
    resulting assignment (AC1, AC3).

    Raises `NotFoundError` (`NO_ACTIVE_RULE`) if no `RiskBandRule` has ever
    been published — there is nothing to score against.
    """
    rule = get_active_rule(session)
    if rule is None:
        raise NotFoundError("No active RiskBandRule has been published.", code="NO_ACTIVE_RULE")

    risk_band = score_answers(answers, rule)  # raises ValidationError first (AC2)

    submitted_at = _now_iso()
    insert_answers(
        session,
        customer_id=customer_id,
        answers=list(answers.items()),
        submitted_at=submitted_at,
    )
    assignment = insert_assignment(
        session,
        customer_id=customer_id,
        risk_band=risk_band,
        rule_version=rule.version,
        assigned_at=submitted_at,
    )
    write_audit_entry(
        session,
        entity_type="RiskBandAssignment",
        entity_id=str(assignment.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="ASSIGN_RISK_BAND",
        details={"customer_id": customer_id, "risk_band": risk_band, "rule_version": rule.version},
    )
    return assignment


def get_latest_risk_band_assignment(
    session: Session, customer_id: int
) -> RiskBandAssignment | None:
    """The caller's most recent `RiskBandAssignment`, or `None` if never
    assigned (E4-S3 AC4) — the service-layer read `app.routers.risk_profile`
    calls, so the router never imports `domain.risk_profile.repository`
    directly (system-design.md D3)."""
    return get_latest_assignment(session, customer_id)


def get_active_questionnaire(session: Session) -> RiskBandRule | None:
    """The currently active `RiskBandRule`, or `None` if never published — the
    service-layer read `app.routers.risk_profile`'s `GET /questionnaire`
    handler calls, so the router never imports `domain.risk_profile.repository`
    directly (system-design.md D3). Returned as-is, `points` included; the
    router strips `points` when building its customer-facing response."""
    return get_active_rule(session)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
