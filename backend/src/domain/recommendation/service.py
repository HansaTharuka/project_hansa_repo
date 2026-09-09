"""Allocation recommendation service (E5-S2, extended by E5-S3) — combines a
customer's current risk band with their goal horizon to select and return the
active `AllocationTemplate`, recording an audit entry.

Template selection is keyed on `risk_band` alone (`recommendation.repository`'s
`get_active_template`) — there is exactly one active template per band at any
time, so the same `(risk_band, horizon)` pair always resolves to the same
template version (AC4); `horizon` is carried through to the result for
display/audit purposes only, never used to branch template selection. Every
allocation percentage is converted to `Decimal` through `types.fixedpoint` at
this module's boundary — no `float` literal, `float()` call, or `-> float`
annotation appears anywhere here (AC5, NFR-01).

`get_recommendation_or_none` (E9-S3) shares `_select_assignment_and_template`/
`_build_allocation_lines` with `get_recommendation` but never writes an audit
entry — the advisor drill-in view (api-contracts.md §11.2) reads a customer's
allocation without that customer having requested a recommendation, so no
`AllocationRecommendation` event should be recorded for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.domain.audit.service import write_audit_entry
from src.domain.holdings.repository import list_asset_classes
from src.domain.recommendation.repository import get_active_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.entities import AllocationTemplate, RiskBandAssignment
from src.types.errors import NotFoundError
from src.types.fixedpoint import basis_points_to_decimal


@dataclass(frozen=True)
class AllocationLine:
    """One asset class's recommended weight, in transportable `Decimal` form."""

    asset_class_id: int
    asset_class_code: str
    asset_class_name: str
    percent: Decimal


@dataclass(frozen=True)
class RecommendationResult:
    """A customer's recommended allocation for this request (api-contracts.md §7.1)."""

    risk_band: str
    rule_version: int
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
    assignment, template = _select_assignment_and_template(session, customer_id)
    allocations = _build_allocation_lines(session, template)
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
        rule_version=assignment.rule_version,
        template_version=template.version,
        horizon=horizon,
        allocations=allocations,
        generated_at=_now_iso(),
    )


def get_recommendation_or_none(
    session: Session, *, customer_id: int, horizon: str
) -> RecommendationResult | None:
    """The same selection `get_recommendation` performs, but returns `None`
    instead of raising when the customer has no `RiskBandAssignment` or no
    active template for their band — and never writes an audit entry. Used
    by the advisor drill-in view (E9-S3 AC2; api-contracts.md §11.2).
    """
    try:
        assignment, template = _select_assignment_and_template(session, customer_id)
    except NotFoundError:
        return None
    allocations = _build_allocation_lines(session, template)
    return RecommendationResult(
        risk_band=assignment.risk_band,
        rule_version=assignment.rule_version,
        template_version=template.version,
        horizon=horizon,
        allocations=allocations,
        generated_at=_now_iso(),
    )


def _select_assignment_and_template(
    session: Session, customer_id: int
) -> tuple[RiskBandAssignment, AllocationTemplate]:
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
    return assignment, template


def _build_allocation_lines(
    session: Session, template: AllocationTemplate
) -> tuple[AllocationLine, ...]:
    asset_classes = {asset_class.id: asset_class for asset_class in list_asset_classes(session)}
    lines = []
    for entry in template.allocations_json.allocations:
        asset_class = asset_classes.get(entry.asset_class_id)
        lines.append(
            AllocationLine(
                asset_class_id=entry.asset_class_id,
                asset_class_code=asset_class.code if asset_class is not None else "",
                asset_class_name=asset_class.name if asset_class is not None else "",
                percent=basis_points_to_decimal(entry.percent_bps),
            )
        )
    return tuple(lines)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
