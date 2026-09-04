"""Holdings orchestration service.

`advance_day` (E6-S2) is the manual admin/dev trigger that advances the
simulated price feed by one day (BRD §5.1; no wall-clock scheduler, AC4). Per
system-design.md §5.3's fixed ordering — "NAV insert → holding revaluation →
drift → goal progress → rebalancing evaluation" — this module implements the
first three steps, which are this group's scope (E6-S2, E6-S3); goal-progress
recompute (E7-S3) and rebalancing evaluation (E8-S2) are wired into the same
flow by their own group-E stories, not here.

`compute_customer_drift` (E6-S3) is the pure-computation wrapper: it reads a
customer's current holdings and delegates to `domain.holdings.drift` for the
fixed-point percentage math.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core import clock
from src.domain.holdings.drift import AssetClassDrift, compute_drift
from src.domain.holdings.repository import (
    get_latest_nav,
    insert_nav_snapshot,
    list_asset_classes,
    list_customer_ids_with_holdings,
    list_holdings_for_asset_class,
    list_holdings_for_customer,
    update_holding_value,
)
from src.domain.recommendation.repository import get_active_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.entities import AllocationSet, NavSnapshot
from src.types.errors import ConflictError, NotFoundError
from src.types.fixedpoint import quantize

MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class AdvanceDayResult:
    """The outcome of one `advance_day` call."""

    price_date: str
    snapshots: tuple[NavSnapshot, ...]
    customers_redrifted: tuple[int, ...]


def advance_day(session: Session) -> AdvanceDayResult:
    """Advance the simulated price feed by exactly one day (AC1, AC4).

    Inserts one new `NavSnapshot` per `AssetClass` for the next sequential
    `price_date`, revalues every affected `Holding`, then recomputes drift for
    every customer with holdings (AC5). Per system-design.md §9.5, the
    double-advance edge case is a **DB-level guarantee** (the
    `UNIQUE(asset_class_id, price_date)` index on `nav_snapshot`) rather than a
    check-then-act read: two callers that both compute the same `next_date`
    from a stale "latest NAV" read race to insert, and the loser's
    `IntegrityError` is translated here into `ConflictError`
    (`DAY_ALREADY_ADVANCED`, AC2, api-contracts.md §12.1) instead of leaving a
    partially-advanced day.
    """
    asset_classes = list_asset_classes(session)
    if not asset_classes:
        raise NotFoundError(
            "No AssetClass rows exist; nothing to advance.", code="NO_ASSET_CLASSES"
        )

    latest_by_asset_class = {
        asset_class.id: _require_latest_nav(session, asset_class.id)
        for asset_class in asset_classes
    }
    next_date = clock.next_price_date(max(nav.price_date for nav in latest_by_asset_class.values()))

    snapshots: list[NavSnapshot] = []
    try:
        for asset_class in asset_classes:
            previous_nav = latest_by_asset_class[asset_class.id]
            new_snapshot = insert_nav_snapshot(
                session,
                asset_class_id=asset_class.id,
                price_date=next_date,
                nav_value=previous_nav.nav_value,  # stub feed: carried forward unchanged
            )
            snapshots.append(new_snapshot)
            _revalue_holdings(
                session,
                asset_class_id=asset_class.id,
                previous_nav_value=previous_nav.nav_value,
                new_nav_value=new_snapshot.nav_value,
                as_of_date=next_date,
            )
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            "The simulated day has already been advanced.", code="DAY_ALREADY_ADVANCED"
        ) from exc

    customers_redrifted = tuple(list_customer_ids_with_holdings(session))
    for customer_id in customers_redrifted:
        recompute_customer_drift(session, customer_id)

    return AdvanceDayResult(
        price_date=next_date, snapshots=tuple(snapshots), customers_redrifted=customers_redrifted
    )


def compute_customer_drift(
    session: Session, *, customer_id: int, allocations: AllocationSet
) -> list[AssetClassDrift]:
    """Current vs. target per-asset-class drift for `customer_id` (E6-S3 AC1-AC5),
    given their holdings and their active recommended allocation `allocations`.
    """
    holdings = list_holdings_for_customer(session, customer_id)
    if not holdings:
        return []
    values_by_asset_class = {holding.asset_class_id: holding.current_value for holding in holdings}
    target_bps = {entry.asset_class_id: entry.percent_bps for entry in allocations.allocations}
    return compute_drift(
        holdings_by_asset_class=values_by_asset_class, target_bps_by_asset_class=target_bps
    )


def recompute_customer_drift(session: Session, customer_id: int) -> list[AssetClassDrift]:
    """Look up `customer_id`'s risk band and active template, then compute drift.

    Used by `advance_day` (AC5) to redrift every customer with holdings without
    a separate manual step. A customer with no risk-band assignment yet, or
    whose band has no published active template, produces no drift (there is
    nothing to compare against) rather than raising.
    """
    assignment = get_latest_assignment(session, customer_id)
    if assignment is None:
        return []
    template = get_active_template(session, assignment.risk_band)
    if template is None:
        return []
    return compute_customer_drift(
        session, customer_id=customer_id, allocations=template.allocations_json
    )


def _revalue_holdings(
    session: Session,
    *,
    asset_class_id: int,
    previous_nav_value: Decimal,
    new_nav_value: Decimal,
    as_of_date: str,
) -> None:
    """Scale every `Holding` in `asset_class_id` by the NAV's price ratio
    (data-models.md §4.11: "revalued each advance-a-day"; system-design.md §5.3).
    """
    holdings = list_holdings_for_asset_class(session, asset_class_id)
    for holding in holdings:
        revalued = quantize(
            holding.current_value * new_nav_value / previous_nav_value, MONEY_QUANTUM
        )
        update_holding_value(
            session, holding_id=holding.id, current_value=revalued, as_of_date=as_of_date
        )


def _require_latest_nav(session: Session, asset_class_id: int) -> NavSnapshot:
    latest = get_latest_nav(session, asset_class_id)
    if latest is None:
        raise NotFoundError(
            f"AssetClass {asset_class_id} has no NavSnapshot history to advance from.",
            code="NO_NAV_HISTORY",
        )
    return latest
