"""GET /api/recommendation — customer-role allocation recommendation
(E5-S3 AC1-AC5; api-contracts.md §7.1).

`customer_id` is always taken from the JWT. `horizon` is resolved here from
an optional `goal_id` query parameter (or the customer's highest-priority
goal, falling back to `MEDIUM` with no goals at all) before delegating to
`domain.recommendation.service`, which this router calls exclusively — never
`domain.recommendation.repository` directly (system-design.md D3), and never
raises `HTTPException` itself.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.goals.service import get_goal_progress, list_customer_goals_with_progress
from src.domain.recommendation.horizon import MEDIUM, derive_horizon
from src.domain.recommendation.service import (
    AllocationLine,
    RecommendationResult,
    get_recommendation,
)
from src.types.fixedpoint import decimal_to_basis_points, percent_to_string
from src.types.responses import AllocationEntryResponse, RecommendationResponse

router = APIRouter(prefix="/api/recommendation", tags=["recommendation"])


@router.get("", status_code=200)
def get_recommendation_endpoint(
    goal_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session),
) -> RecommendationResponse:
    """The caller's current recommended allocation (AC1). Raises
    `NotFoundError` (`NO_RISK_BAND_ASSIGNMENT`) if the customer has never
    completed the risk questionnaire — never a default allocation (AC2).
    """
    customer_id = user.customer_id or 0
    horizon = _resolve_horizon(session, customer_id=customer_id, goal_id=goal_id)
    result = get_recommendation(
        session,
        customer_id=customer_id,
        horizon=horizon,
        actor_id=user.user_id,
        actor_role=user.role,
    )
    return _to_response(result)


def _resolve_horizon(session: Session, *, customer_id: int, goal_id: int | None) -> str:
    """A specific `goal_id`'s horizon, the highest-priority goal's horizon, or
    `MEDIUM` with no goals at all (api-contracts.md §7.1 Notes). A `goal_id`
    unknown to or not owned by this customer raises `NotFoundError`
    (`GOAL_NOT_FOUND`), matching `GET /api/goals/{goal_id}/progress`'s
    ownership rule.
    """
    today = _today_iso_date()
    if goal_id is not None:
        goal, _snapshots = get_goal_progress(session, goal_id=goal_id, customer_id=customer_id)
        return derive_horizon(target_date=goal.target_date, reference_date=today)

    goals = list_customer_goals_with_progress(session, customer_id)
    if not goals:
        return MEDIUM
    highest_priority_goal, _percent_complete = goals[0]
    return derive_horizon(target_date=highest_priority_goal.target_date, reference_date=today)


def _today_iso_date() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _to_response(result: RecommendationResult) -> RecommendationResponse:
    total_bps = sum(decimal_to_basis_points(line.percent) for line in result.allocations)
    return RecommendationResponse(
        risk_band=result.risk_band,
        rule_version=result.rule_version,
        template_version=result.template_version,
        horizon=result.horizon,
        allocations=[_line_to_response(line) for line in result.allocations],
        total_percent=percent_to_string(total_bps),
        generated_at=result.generated_at,
    )


def _line_to_response(line: AllocationLine) -> AllocationEntryResponse:
    return AllocationEntryResponse(
        asset_class_id=line.asset_class_id,
        asset_class_code=line.asset_class_code,
        asset_class_name=line.asset_class_name,
        percent=percent_to_string(decimal_to_basis_points(line.percent)),
    )
