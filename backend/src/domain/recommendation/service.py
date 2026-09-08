"""Allocation recommendation service (E5-S2) — combines a customer's current
risk band with their goal horizon to select and return the active
`AllocationTemplate`, recording an audit entry.

Template selection is keyed on `risk_band` alone (`recommendation.repository`'s
`get_active_template`) — there is exactly one active template per band at any
time, so the same `(risk_band, horizon)` pair always resolves to the same
template version (AC4); `horizon` is carried through to the result for
display/audit purposes only, never used to branch template selection. Every
allocation percentage is converted to `Decimal` through `types.fixedpoint` at
this module's boundary — no `float` literal, `float()` call, or `-> float`
annotation appears anywhere here (AC5, NFR-01).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.domain.audit.service import write_audit_entry
from src.domain.recommendation.repository import get_active_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.errors import NotFoundError
from src.types.fixedpoint import basis_points_to_decimal


@dataclass(frozen=True)
class AllocationLine:
    """One asset class's recommended weight, in transportable `Decimal` form."""

    asset_class_id: int
    percent: Decimal


@dataclass(frozen=True)
class RecommendationResult:
    """A customer's recommended allocation for this request (api-contracts.md §7.1)."""

    risk_band: str
    template_version: int
    horizon: str
    allocations: tuple[AllocationLine, ...]
    generated_at: str


def get_recommendation(
    session: Session,
    *,
    customer_id: int,
    horizon: str,
    actor_id: int,
    actor_role: str,
) -> RecommendationResult:
    """Select `customer_id`'s active allocation template for their current
    risk band (AC1), auditing the event exactly once (AC3).

    Raises `NotFoundError` (`NO_RISK_BAND_ASSIGNMENT`) if the customer has
    never been assigned a band — no default/fallback allocation is ever
    returned (AC2). Raises `NotFoundError` (`NO_ACTIVE_TEMPLATE`) if no
    template has been published for that band.
    """
    assignment = get_latest_assignment(session, customer_id)
    if assignment is None:
        raise NotFoundError(
            f"Customer {customer_id} has no RiskBandAssignment.",
            code="NO_RISK_BAND_ASSIGNMENT",
        )
    template = get_active_template(session, assignment.risk_band)
    if template is None:
        raise NotFoundError(
            f"No active AllocationTemplate for risk band {assignment.risk_band!r}.",
            code="NO_ACTIVE_TEMPLATE",
        )

    allocations = tuple(
        AllocationLine(
            asset_class_id=entry.asset_class_id,
            percent=basis_points_to_decimal(entry.percent_bps),
        )
        for entry in template.allocations_json.allocations
    )
    write_audit_entry(
        session,
        entity_type="AllocationRecommendation",
        entity_id=str(template.id),
        actor_id=actor_id,
        actor_role=actor_role,
        action="GENERATE_ALLOCATION_RECOMMENDATION",
        details={
            "customer_id": customer_id,
            "risk_band": assignment.risk_band,
            "template_version": template.version,
        },
    )
    return RecommendationResult(
        risk_band=assignment.risk_band,
        template_version=template.version,
        horizon=horizon,
        allocations=allocations,
        generated_at=_now_iso(),
    )


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
