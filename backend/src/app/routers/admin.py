"""POST /api/admin/advance-day — admin-role-only manual price-feed trigger
(E6-S4 AC2-AC4; api-contracts.md §12.1). E10-S3 (group F) extends this same
router with rule/template/threshold publish and asset-class CRUD routes
(component-map.md note 3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, require_role
from src.domain.holdings.service import advance_day

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdvanceDayResponse(BaseModel):
    """The shared response shape E6-S4/E7-S3/E8-S2 all contribute a count to."""

    price_date: str
    nav_snapshots_created: int
    holdings_revalued: int
    goal_snapshots_created: int
    rebalancing_recommendations_created: int


@router.post("/advance-day", status_code=200)
def post_advance_day(
    user: CurrentUser = Depends(require_role("admin")),
    session: Session = Depends(get_session),
) -> AdvanceDayResponse:
    """Advance the simulated price feed by exactly one day (AC2, AC3).

    A second immediate call for the same simulated day raises `ConflictError`
    (`DAY_ALREADY_ADVANCED`), mapped to 409 by the already-registered generic
    handler (AC4) — this router never constructs a status code itself.
    """
    result = advance_day(session, actor_id=user.user_id, actor_role=user.role)
    return AdvanceDayResponse(
        price_date=result.price_date,
        nav_snapshots_created=len(result.snapshots),
        holdings_revalued=result.holdings_revalued,
        goal_snapshots_created=result.goal_snapshots_created,
        rebalancing_recommendations_created=result.rebalancing_recommendations_created,
    )
