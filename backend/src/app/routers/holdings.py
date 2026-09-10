"""GET /api/holdings — customer-role, current holdings and per-asset-class
drift (E6-S4 AC1, AC5; api-contracts.md §8.1).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.app.dependencies import CurrentUser, get_session, get_settings, require_role
from src.core.config import Settings
from src.domain.holdings.views import HoldingLine, get_customer_holdings_view
from src.types.fixedpoint import (
    decimal_to_basis_points,
    decimal_to_minor_units,
    money_to_string,
    percent_to_string,
)

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


class HoldingResponse(BaseModel):
    """One asset class's current value and drift (matches `drift.py`'s computation)."""

    asset_class_id: int
    asset_class_code: str
    current_value: str
    current_percent: str
    target_percent: str
    drift_percent: str
    exceeds_threshold: bool


class HoldingsResponse(BaseModel):
    """The full customer holdings-and-drift view (api-contracts.md §8.1)."""

    as_of_date: str | None
    total_value: str
    threshold_bps: int
    threshold_percent: str
    holdings: list[HoldingResponse]


@router.get("", status_code=200)
def get_holdings(
    user: CurrentUser = Depends(require_role("customer")),
    session: Session = Depends(get_session, scope="function"),
    settings: Settings = Depends(get_settings),
) -> HoldingsResponse:
    """A customer with zero `Holding` rows gets 200 with an empty list, never
    a 404 or 500 (AC5)."""
    default_threshold_bps = settings.default_drift_threshold_percent * 100
    view = get_customer_holdings_view(
        session, user.customer_id or 0, default_threshold_bps=default_threshold_bps
    )
    return HoldingsResponse(
        as_of_date=view.as_of_date,
        total_value=money_to_string(decimal_to_minor_units(view.total_value)),
        threshold_bps=view.threshold_bps,
        threshold_percent=percent_to_string(view.threshold_bps),
        holdings=[_to_holding_response(line) for line in view.holdings],
    )


def _to_holding_response(line: HoldingLine) -> HoldingResponse:
    return HoldingResponse(
        asset_class_id=line.asset_class_id,
        asset_class_code=line.asset_class_code,
        current_value=money_to_string(decimal_to_minor_units(line.current_value)),
        current_percent=percent_to_string(decimal_to_basis_points(line.current_percent)),
        target_percent=percent_to_string(decimal_to_basis_points(line.target_percent)),
        drift_percent=percent_to_string(decimal_to_basis_points(line.drift_percent)),
        exceeds_threshold=line.exceeds_threshold,
    )
