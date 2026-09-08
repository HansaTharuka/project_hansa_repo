"""GET /api/rebalancing, POST /api/rebalancing/{id}/accept|dismiss —
customer-role rebalancing recommendation list/accept/dismiss (E8-S3 AC1-AC5;
api-contracts.md §10.1-§10.3).

`customer_id` is always taken from the JWT. This router calls
`domain.rebalancing.service` only, never `domain.rebalancing.repository`
directly (system-design.md D3), and never raises `HTTPException` itself —
`AlreadyResolvedError`/ownership mismatches surface as typed domain errors the
registered handlers translate to 409/404.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.rebalancing.service import (
    list_customer_pending_recommendations,
    resolve_customer_recommendation,
)
from src.types.entities import ProposedAction, RebalancingRecommendation
from src.types.fixedpoint import (
    decimal_to_basis_points,
    decimal_to_minor_units,
    money_to_string,
    percent_to_string,
    units_to_string,
)

router = APIRouter(prefix="/api/rebalancing", tags=["rebalancing"])


class ProposedActionResponse(BaseModel):
    """One BUY/SELL leg (api-contracts.md §10.1)."""

    asset_class_id: int
    asset_class_code: str
    action: str
    amount: str
    units: str
    drift_percent: str


class RecommendationResponse(BaseModel):
    """One `RebalancingRecommendation` row (api-contracts.md §10.1)."""

    recommendation_id: str
    status: str
    generated_at: str
    resolved_at: str | None
    threshold_bps: int
    proposed_actions: list[ProposedActionResponse]


class ResolveResponse(BaseModel):
    """The accept/dismiss response (api-contracts.md §10.2, §10.3)."""

    recommendation_id: str
    status: str
    resolved_at: str | None


@router.get("", status_code=200)
def list_recommendations(
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> list[RecommendationResponse]:
    """The caller's pending recommendations, default (no `status` param) view (AC1)."""
    recommendations = list_customer_pending_recommendations(session, user.customer_id or 0)
    return [_to_response(recommendation) for recommendation in recommendations]


@router.post("/{recommendation_id}/accept", status_code=200)
def accept_recommendation(
    recommendation_id: str,
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> ResolveResponse:
    """Transition `recommendation_id` to `accepted` (AC2)."""
    recommendation = resolve_customer_recommendation(
        session,
        recommendation_id=recommendation_id,
        customer_id=user.customer_id or 0,
        resolution="accept",
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return _to_resolve_response(recommendation)


@router.post("/{recommendation_id}/dismiss", status_code=200)
def dismiss_recommendation(
    recommendation_id: str,
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> ResolveResponse:
    """Transition `recommendation_id` to `dismissed` (AC3)."""
    recommendation = resolve_customer_recommendation(
        session,
        recommendation_id=recommendation_id,
        customer_id=user.customer_id or 0,
        resolution="dismiss",
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return _to_resolve_response(recommendation)


def _to_response(recommendation: RebalancingRecommendation) -> RecommendationResponse:
    proposed = recommendation.proposed_actions_json
    return RecommendationResponse(
        recommendation_id=recommendation.recommendation_id,
        status=recommendation.status,
        generated_at=recommendation.generated_at,
        resolved_at=recommendation.resolved_at,
        threshold_bps=proposed.threshold_bps,
        proposed_actions=[_action_to_response(action) for action in proposed.actions],
    )


def _action_to_response(action: ProposedAction) -> ProposedActionResponse:
    return ProposedActionResponse(
        asset_class_id=action.asset_class_id,
        asset_class_code=action.asset_class_code,
        action=action.action,
        amount=money_to_string(decimal_to_minor_units(action.amount)),
        units=units_to_string(action.units),
        drift_percent=percent_to_string(decimal_to_basis_points(action.drift_percent)),
    )


def _to_resolve_response(recommendation: RebalancingRecommendation) -> ResolveResponse:
    return ResolveResponse(
        recommendation_id=recommendation.recommendation_id,
        status=recommendation.status,
        resolved_at=recommendation.resolved_at,
    )
