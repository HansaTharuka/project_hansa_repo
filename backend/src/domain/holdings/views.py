"""Customer-facing holdings-and-drift read view (E6-S4 AC1, AC5).

Split out of `domain.holdings.service` once that module crossed the
`check-file-length` warn threshold (CLAUDE.md's 300-line block rule,
component-map.md note 2's models-growth allowance applied the same way to
services) — `get_customer_holdings_view` is a pure read assembled from
`holdings.repository`, `holdings.drift` and the active template/threshold,
with no role in the `advance_day` write path itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from src.domain.holdings.drift import compute_drift, is_over_threshold
from src.domain.holdings.repository import list_asset_classes, list_holdings_for_customer
from src.domain.rebalancing.threshold_repository import get_active_threshold
from src.domain.recommendation.repository import get_active_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.fixedpoint import decimal_to_basis_points


@dataclass(frozen=True)
class HoldingLine:
    """One asset class's current value and drift, for `GET /api/holdings` (E6-S4 AC1)."""

    asset_class_id: int
    asset_class_code: str
    current_value: Decimal
    current_percent: Decimal
    target_percent: Decimal
    drift_percent: Decimal
    exceeds_threshold: bool


@dataclass(frozen=True)
class CustomerHoldingsView:
    """A customer's full holdings-and-drift snapshot (E6-S4 AC1, AC5)."""

    as_of_date: str | None
    total_value: Decimal
    threshold_bps: int
    holdings: tuple[HoldingLine, ...]


def get_customer_holdings_view(
    session: Session, customer_id: int, *, default_threshold_bps: int
) -> CustomerHoldingsView:
    """Build `customer_id`'s full holdings-and-drift view (E6-S4 AC1).

    A customer with zero `Holding` rows returns a populated-but-empty view —
    `as_of_date=None`, `total_value=0.00`, `holdings=()` — never an error
    (AC5). `default_threshold_bps` is used only if no `RebalancingThreshold`
    has ever been published yet.
    """
    holdings = list_holdings_for_customer(session, customer_id)
    threshold = get_active_threshold(session)
    threshold_bps = threshold.threshold_bps if threshold is not None else default_threshold_bps
    if not holdings:
        return CustomerHoldingsView(
            as_of_date=None, total_value=Decimal("0.00"), threshold_bps=threshold_bps, holdings=()
        )

    values_by_asset_class = {holding.asset_class_id: holding.current_value for holding in holdings}
    drifts = compute_drift(
        holdings_by_asset_class=values_by_asset_class,
        target_bps_by_asset_class=_target_bps_for_customer(session, customer_id),
    )
    codes_by_id = {asset_class.id: asset_class.code for asset_class in list_asset_classes(session)}
    lines = tuple(
        HoldingLine(
            asset_class_id=drift.asset_class_id,
            asset_class_code=codes_by_id.get(drift.asset_class_id, ""),
            current_value=values_by_asset_class[drift.asset_class_id],
            current_percent=drift.current_percent,
            target_percent=drift.target_percent,
            drift_percent=drift.drift_percent,
            exceeds_threshold=is_over_threshold(
                decimal_to_basis_points(drift.drift_percent), threshold_bps
            ),
        )
        for drift in drifts
    )
    return CustomerHoldingsView(
        as_of_date=max(holding.as_of_date for holding in holdings),
        total_value=sum(values_by_asset_class.values(), Decimal("0")),
        threshold_bps=threshold_bps,
        holdings=lines,
    )


def _target_bps_for_customer(session: Session, customer_id: int) -> dict[int, int]:
    """The customer's active recommended allocation, or `{}` if they have no
    risk-band assignment or no published template yet — every held asset
    class is then reported as 100% drift rather than raising."""
    assignment = get_latest_assignment(session, customer_id)
    if assignment is None:
        return {}
    template = get_active_template(session, assignment.risk_band)
    if template is None:
        return {}
    return {
        entry.asset_class_id: entry.percent_bps for entry in template.allocations_json.allocations
    }
