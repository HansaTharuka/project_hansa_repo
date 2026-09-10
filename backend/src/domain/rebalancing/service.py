"""Rebalancing evaluation service (E8-S2) — orchestrates one customer's
drift-vs-threshold check into a persisted `RebalancingRecommendation`.

Every early-return below is a documented no-op, not an error (AC2, AC3, AC4):
a `kyc_verified = false` customer, zero holdings, no risk-band assignment, no
active allocation template, and no active threshold each mean "nothing to
propose", so the function simply returns `None` rather than raising or
inserting an empty-actions row. A successful recommendation creation calls
the audit-writer exactly once (AC5).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from src.domain.audit.service import write_audit_entry
from src.domain.auth.repository import get_customer_by_id
from src.domain.holdings.drift import compute_drift
from src.domain.holdings.repository import (
    get_latest_nav,
    list_asset_classes,
    list_holdings_for_customer,
)
from src.domain.rebalancing.engine import AssetClassInfo, propose_rebalancing_actions
from src.domain.rebalancing.repository import (
    AlreadyResolvedError,
    accept,
    dismiss,
    get_by_recommendation_id,
    get_pending,
    insert_recommendation,
)
from src.domain.rebalancing.threshold_repository import get_active_threshold
from src.domain.recommendation.repository import get_active_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.entities import ProposedAction, ProposedActions
from src.types.entities import RebalancingRecommendation as RebalancingRecommendationEntity
from src.types.errors import ConflictError, NotFoundError


@dataclass(frozen=True)
class _EvaluationContext:
    """The three published rows a drift evaluation needs, all resolved
    successfully — bundled so `evaluate_customer_rebalancing` reads as one
    early-return per missing piece rather than three nested `if`s inline."""

    target_bps_by_asset_class: dict[int, int]
    threshold_bps: int
    threshold_version: int


def evaluate_customer_rebalancing(
    session: Session, *, customer_id: int, actor_id: int, actor_role: str
) -> RebalancingRecommendationEntity | None:
    """Evaluate `customer_id`'s current drift and, if it exceeds the active
    threshold on at least one asset class, create and audit one
    `RebalancingRecommendation` (AC1-AC5)."""
    customer = get_customer_by_id(session, customer_id)
    if customer is None or not customer.kyc_verified:
        return None
    holdings = list_holdings_for_customer(session, customer_id)
    if not holdings:
        return None
    context = _load_evaluation_context(session, customer_id)
    if context is None:
        return None

    values_by_asset_class = {holding.asset_class_id: holding.current_value for holding in holdings}
    drifts = compute_drift(
        holdings_by_asset_class=values_by_asset_class,
        target_bps_by_asset_class=context.target_bps_by_asset_class,
    )
    total_value = sum(values_by_asset_class.values(), Decimal("0"))
    asset_classes_by_id = _build_asset_class_lookup(session, values_by_asset_class.keys())

    actions = propose_rebalancing_actions(
        drifts=drifts,
        total_value=total_value,
        threshold_bps=context.threshold_bps,
        asset_classes_by_id=asset_classes_by_id,
    )
    if not actions:
        return None

    return _persist_recommendation(
        session,
        customer_id=customer_id,
        actions=actions,
        threshold_bps=context.threshold_bps,
        threshold_version=context.threshold_version,
        actor_id=actor_id,
        actor_role=actor_role,
    )


def _load_evaluation_context(session: Session, customer_id: int) -> _EvaluationContext | None:
    """Resolve the customer's active template and threshold, or `None` if
    either is missing — the customer has no risk-band assignment yet, no
    published template for their band, or no threshold has ever been
    published (each a documented no-op, AC2-AC4)."""
    assignment = get_latest_assignment(session, customer_id)
    if assignment is None:
        return None
    template = get_active_template(session, assignment.risk_band)
    if template is None:
        return None
    threshold = get_active_threshold(session)
    if threshold is None:
        return None
    target_bps_by_asset_class = {
        entry.asset_class_id: entry.percent_bps for entry in template.allocations_json.allocations
    }
    return _EvaluationContext(
        target_bps_by_asset_class=target_bps_by_asset_class,
        threshold_bps=threshold.threshold_bps,
        threshold_version=threshold.version,
    )


def _persist_recommendation(
    session: Session,
    *,
    customer_id: int,
    actions: list[ProposedAction],
    threshold_bps: int,
    threshold_version: int,
    actor_id: int,
    actor_role: str,
) -> RebalancingRecommendationEntity:
    proposed = ProposedActions(
        actions=actions, threshold_bps=threshold_bps, threshold_version=threshold_version
    )
    recommendation = insert_recommendation(
        session,
        customer_id=customer_id,
        recommendation_id=str(uuid4()),
        proposed_actions=proposed,
        generated_at=_now_iso(),
    )
    write_audit_entry(
        session,
        entity_type="RebalancingRecommendation",
        entity_id=recommendation.recommendation_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action="GENERATE_REBALANCING_RECOMMENDATION",
        details={"customer_id": customer_id, "recommendation_id": recommendation.recommendation_id},
    )
    return recommendation


def _build_asset_class_lookup(
    session: Session, asset_class_ids: Iterable[int]
) -> dict[int, AssetClassInfo]:
    wanted = set(asset_class_ids)
    lookup: dict[int, AssetClassInfo] = {}
    for asset_class in list_asset_classes(session):
        if asset_class.id not in wanted:
            continue
        nav = get_latest_nav(session, asset_class.id)
        nav_value = nav.nav_value if nav is not None else Decimal("0")
        lookup[asset_class.id] = AssetClassInfo(
            asset_class_id=asset_class.id, code=asset_class.code, nav_value=nav_value
        )
    return lookup


def list_customer_pending_recommendations(
    session: Session, customer_id: int
) -> list[RebalancingRecommendationEntity]:
    """The caller's `pending` recommendations only (E8-S3 AC1; api-contracts.md
    §10.1's default, no-`status`-param behaviour)."""
    return get_pending(session, customer_id)


def resolve_customer_recommendation(
    session: Session,
    *,
    recommendation_id: str,
    customer_id: int,
    resolution: str,
    actor_id: int,
    actor_role: str,
) -> RebalancingRecommendationEntity:
    """Transition one of `customer_id`'s recommendations to `accepted` or
    `dismissed`, auditing the event exactly once (E8-S3 AC2, AC3).

    Raises `NotFoundError` (`RECOMMENDATION_NOT_FOUND`) for an unknown id or
    one owned by a different customer — never `AuthorizationError`, so a
    non-owner cannot infer the id exists (AC5, system-design.md D12). Raises
    `ConflictError` (`ALREADY_RESOLVED`) for a second transition attempt on an
    already-resolved row, leaving `resolved_at` unchanged (AC4).
    """
    recommendation = get_by_recommendation_id(session, recommendation_id)
    if recommendation is None or recommendation.customer_id != customer_id:
        raise NotFoundError(
            f"RebalancingRecommendation {recommendation_id!r} does not exist.",
            code="RECOMMENDATION_NOT_FOUND",
        )

    resolved_at = _now_iso()
    try:
        if resolution == "accept":
            resolved = accept(
                session, recommendation_id=recommendation_id, resolved_at=resolved_at
            )
            action = "ACCEPT_REBALANCING_RECOMMENDATION"
        else:
            resolved = dismiss(
                session, recommendation_id=recommendation_id, resolved_at=resolved_at
            )
            action = "DISMISS_REBALANCING_RECOMMENDATION"
    except AlreadyResolvedError as exc:
        raise ConflictError(str(exc), code="ALREADY_RESOLVED") from exc

    write_audit_entry(
        session,
        entity_type="RebalancingRecommendation",
        entity_id=recommendation_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        details={"customer_id": customer_id, "recommendation_id": recommendation_id},
    )
    return resolved


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
