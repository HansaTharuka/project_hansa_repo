"""Advisor override and manual-recommendation service (E9-S2, extended by
E9-S3) — AC-09's fully audited advisor workflows plus the two read-composition
views the advisor API needs.

`override_risk_band` verifies the customer exists before anything else (AC5),
rejects a blank `reason` before either row is written (AC2 — `reason`
validation happens here, ahead of `domain.advisor.repository.insert_override`'s
own check, so the error carries the api-contracts.md §11.3 `REASON_REQUIRED`
code rather than a bare `ValueError`), then inserts one `AdvisorOverride` row
and one new `RiskBandAssignment` row reflecting `new_band` in the same
transaction, auditing the event exactly once (AC1, AC3). `log_manual_recommendation`
writes no new table — it is an `AuditLogEntry` with `entity_type =
"ManualRecommendation"` (system-design.md §6.4) — but still validates `note`
before writing anything (AC4).

`list_customers` and `get_customer_detail` (E9-S3 AC1, AC2) are pure reads
composed from already-tested sibling services/repositories (`auth`, `holdings`,
`goals`, `recommendation`, this module's own `advisor.repository`) — no new
persistence or validation rule is introduced here, only assembly, so this
router-facing composition lives alongside the write-path functions rather
than duplicating any of their logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.domain.advisor.repository import get_overrides, insert_override
from src.domain.audit.service import write_audit_entry
from src.domain.auth.repository import get_customer_by_id, get_user_by_id
from src.domain.auth.repository import list_customers as list_customer_rows
from src.domain.goals.repository import list_goals_for_customer
from src.domain.goals.service import list_customer_goals_with_progress
from src.domain.holdings.repository import list_holdings_for_customer
from src.domain.holdings.views import CustomerHoldingsView, get_customer_holdings_view
from src.domain.recommendation.service import RecommendationResult, get_recommendation_or_none
from src.domain.risk_profile.repository import get_latest_assignment, insert_assignment
from src.types.entities import AdvisorOverride, Goal
from src.types.errors import ConflictError, NotFoundError, ValidationError

MIN_NOTE_LENGTH = 1
MAX_NOTE_LENGTH = 2000
MONEY_QUANTUM = Decimal("0.01")
DEFAULT_HORIZON = "MEDIUM"


@dataclass(frozen=True)
class OverrideResult:
    """The combined override + new-assignment outcome (api-contracts.md §11.3)."""

    override_id: int
    customer_id: int
    previous_band: str
    new_band: str
    reason: str
    note: str | None
    created_at: str
    assignment_id: int
    risk_band: str


@dataclass(frozen=True)
class ManualRecommendationResult:
    """The audit-only outcome of logging a manual recommendation (api-contracts.md §11.4)."""

    audit_entry_id: int
    customer_id: int
    advisor_id: int
    note: str
    created_at: str


@dataclass(frozen=True)
class CustomerSummary:
    """One row of the advisor customer list (E9-S3 AC1; api-contracts.md §11.1)."""

    customer_id: int
    email: str
    risk_band: str | None
    kyc_verified: bool
    total_value: Decimal
    goal_count: int


@dataclass(frozen=True)
class CustomerDetail:
    """The advisor drill-in payload — holdings, goals, allocation and override
    history assembled in one call (E9-S3 AC2; api-contracts.md §11.2)."""

    customer_id: int
    email: str
    kyc_verified: bool
    risk_band: str | None
    rule_version: int | None
    holdings: CustomerHoldingsView
    goals: list[tuple[Goal, Decimal | None]]
    allocation: RecommendationResult | None
    override_history: list[AdvisorOverride]


def override_risk_band(
    session: Session,
    *,
    customer_id: int,
    advisor_id: int,
    new_band: str,
    reason: str | None,
    note: str | None,
    actor_id: int,
    actor_role: str,
) -> OverrideResult:
    """Record an advisor's override of `customer_id`'s risk band (AC1-AC3, AC5).

    Raises `NotFoundError` (`CUSTOMER_NOT_FOUND`) for an unknown customer
    before any row is written (AC5). Raises `ValidationError`
    (`REASON_REQUIRED`) for a missing/blank `reason`, also before any row is
    written (AC2).
    """
    customer = get_customer_by_id(session, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} does not exist.", code="CUSTOMER_NOT_FOUND")
    if reason is None or reason.strip() == "":
        raise ValidationError("reason is mandatory and cannot be blank.", code="REASON_REQUIRED")

    previous_assignment = get_latest_assignment(session, customer_id)
    if previous_assignment is None:
        raise ConflictError(
            f"Customer {customer_id} has no prior RiskBandAssignment to override.",
            code="NO_PRIOR_ASSIGNMENT",
        )
    previous_band = previous_assignment.risk_band

    created_at = _now_iso()
    # `reason` is already validated non-blank above, so `insert_override`'s own
    # `BlankReasonError` guard (defence-in-depth against a future caller that
    # skips this service) is structurally unreachable through this function.
    override = insert_override(
        session,
        customer_id=customer_id,
        advisor_id=advisor_id,
        previous_band=previous_band,
        new_band=new_band,
        reason=reason,
        note=note,
        created_at=created_at,
    )

    assignment = insert_assignment(
        session,
        customer_id=customer_id,
        risk_band=new_band,
        rule_version=previous_assignment.rule_version,
        assigned_at=created_at,
    )
    write_audit_entry(
        session,
        entity_type="AdvisorOverride",
        entity_id=str(override.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="OVERRIDE_RISK_BAND",
        details={
            "customer_id": customer_id,
            "previous_band": previous_band,
            "new_band": new_band,
            "assignment_id": assignment.id,
        },
    )
    return OverrideResult(
        override_id=override.id,
        customer_id=override.customer_id,
        previous_band=override.previous_band,
        new_band=override.new_band,
        reason=override.reason,
        note=override.note,
        created_at=override.created_at,
        assignment_id=assignment.id,
        risk_band=assignment.risk_band,
    )


def log_manual_recommendation(
    session: Session,
    *,
    customer_id: int,
    advisor_id: int,
    note: str | None,
    actor_id: int,
    actor_role: str,
) -> ManualRecommendationResult:
    """Record an advisor's free-text manual recommendation as an
    `AuditLogEntry` only — no new table (AC4, system-design.md §6.4).

    Raises `ValidationError` (`NOTE_REQUIRED`) for a missing, blank, or
    over-length `note`.
    """
    trimmed = (note or "").strip()
    if not trimmed or len(trimmed) > MAX_NOTE_LENGTH:
        raise ValidationError(
            f"note must be {MIN_NOTE_LENGTH}-{MAX_NOTE_LENGTH} characters after trimming.",
            code="NOTE_REQUIRED",
        )

    entry = write_audit_entry(
        session,
        entity_type="ManualRecommendation",
        entity_id=str(customer_id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="LOG_MANUAL_RECOMMENDATION",
        details={"note": trimmed},
    )
    return ManualRecommendationResult(
        audit_entry_id=entry.id,
        customer_id=customer_id,
        advisor_id=advisor_id,
        note=trimmed,
        created_at=entry.timestamp,
    )


def list_customers(session: Session) -> list[CustomerSummary]:
    """Every customer, each paired with their current risk band (`None` if
    never assigned), KYC status, total holdings value, and goal count (E9-S3
    AC1).
    """
    summaries: list[CustomerSummary] = []
    for customer in list_customer_rows(session):
        user = get_user_by_id(session, customer.user_id)
        assignment = get_latest_assignment(session, customer.id)
        holdings = list_holdings_for_customer(session, customer.id)
        goals = list_goals_for_customer(session, customer.id)
        total_value = sum((holding.current_value for holding in holdings), Decimal("0")).quantize(
            MONEY_QUANTUM
        )
        summaries.append(
            CustomerSummary(
                customer_id=customer.id,
                email=user.email if user is not None else "",
                risk_band=assignment.risk_band if assignment is not None else None,
                kyc_verified=customer.kyc_verified,
                total_value=total_value,
                goal_count=len(goals),
            )
        )
    return summaries


def get_customer_detail(
    session: Session, customer_id: int, *, default_threshold_bps: int
) -> CustomerDetail:
    """The full drill-in payload for one customer in a single call (E9-S3
    AC2): holdings, goals, current allocation and override history.

    Raises `NotFoundError` (`CUSTOMER_NOT_FOUND`) for an unknown customer.
    `allocation` is `None` only when the customer has no `RiskBandAssignment`
    (or, degenerately, no active template for their band) — computed via
    `recommendation.service.get_recommendation_or_none`, which writes no
    `AllocationRecommendation` audit entry, because the customer did not
    request a recommendation (api-contracts.md §11.2 Notes).
    """
    customer = get_customer_by_id(session, customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} does not exist.", code="CUSTOMER_NOT_FOUND")

    user = get_user_by_id(session, customer.user_id)
    assignment = get_latest_assignment(session, customer_id)
    holdings_view = get_customer_holdings_view(
        session, customer_id, default_threshold_bps=default_threshold_bps
    )
    goals = list_customer_goals_with_progress(session, customer_id)
    allocation = get_recommendation_or_none(
        session, customer_id=customer_id, horizon=DEFAULT_HORIZON
    )
    override_history = get_overrides(session, customer_id)

    return CustomerDetail(
        customer_id=customer.id,
        email=user.email if user is not None else "",
        kyc_verified=customer.kyc_verified,
        risk_band=assignment.risk_band if assignment is not None else None,
        rule_version=assignment.rule_version if assignment is not None else None,
        holdings=holdings_view,
        goals=goals,
        allocation=allocation,
        override_history=override_history,
    )


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
