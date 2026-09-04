"""Holdings orchestration service.

`advance_day` (E6-S2) is the manual admin/dev trigger that advances the
simulated price feed by one day (BRD §5.1; no wall-clock scheduler, AC4). Per
system-design.md §5.3's fixed ordering — "NAV insert → holding revaluation →
drift → goal progress → rebalancing evaluation" — this module now implements
all five steps: E6-S2/E6-S3 built the first three; E7-S3 (this revision)
wires in goal-progress recompute per active goal; E8-S2 wires in rebalancing
evaluation per customer, both invoked automatically so no separate manual
call is ever required after `advance_day` (E7-S3 AC5, E8-S2).

`compute_customer_drift` (E6-S3) is the pure-computation wrapper: it reads a
customer's current holdings and delegates to `domain.holdings.drift` for the
fixed-point percentage math.

The customer-facing `GET /api/holdings` read view (E6-S4) lives in the
sibling `domain.holdings.views` module, split out once this file crossed the
300-line block threshold (CLAUDE.md) — it has no role in the `advance_day`
write path this module owns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core import clock
from src.domain.goals.repository import list_customer_ids_with_goals
from src.domain.goals.service import recompute_customer_goal_progress
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
from src.domain.rebalancing.service import evaluate_customer_rebalancing
from src.domain.recommendation.repository import get_active_template
from src.domain.risk_profile.repository import get_latest_assignment
from src.types.entities import AllocationSet, AssetClass, NavSnapshot
from src.types.errors import ConflictError, NotFoundError
from src.types.fixedpoint import quantize

MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class AdvanceDayResult:
    """The outcome of one `advance_day` call (api-contracts.md §12.1)."""

    price_date: str
    snapshots: tuple[NavSnapshot, ...]
    customers_redrifted: tuple[int, ...]
    holdings_revalued: int
    goal_snapshots_created: int
    rebalancing_recommendations_created: int


def advance_day(
    session: Session, *, actor_id: int | None = None, actor_role: str = "admin"
) -> AdvanceDayResult:
    """Advance the simulated price feed by exactly one day (AC1, AC4).

    See `_insert_snapshots_and_revalue` for the double-advance/`ConflictError`
    guarantee (AC2). `actor_id`/`actor_role` identify the caller for the
    rebalancing-evaluation step's audit entry (E8-S2 AC5); omitting
    `actor_id` (direct unit tests exercising only NAV/drift/goal-progress)
    skips that one step.
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
    snapshots, holdings_revalued = _insert_snapshots_and_revalue(
        session, asset_classes, latest_by_asset_class=latest_by_asset_class, next_date=next_date
    )

    customers_redrifted = tuple(list_customer_ids_with_holdings(session))
    for customer_id in customers_redrifted:
        recompute_customer_drift(session, customer_id)

    goal_snapshots_created = _recompute_all_goal_progress(session, price_date=next_date)
    rebalancing_recommendations_created = _evaluate_all_rebalancing(
        session, customer_ids=customers_redrifted, actor_id=actor_id, actor_role=actor_role
    )

    return AdvanceDayResult(
        price_date=next_date,
        snapshots=tuple(snapshots),
        customers_redrifted=customers_redrifted,
        holdings_revalued=holdings_revalued,
        goal_snapshots_created=goal_snapshots_created,
        rebalancing_recommendations_created=rebalancing_recommendations_created,
    )


def _insert_snapshots_and_revalue(
    session: Session,
    asset_classes: list[AssetClass],
    *,
    latest_by_asset_class: dict[int, NavSnapshot],
    next_date: str,
) -> tuple[list[NavSnapshot], int]:
    """Insert one `NavSnapshot` per asset class and revalue its `Holding` rows.

    A losing writer's `IntegrityError` on the `UNIQUE(asset_class_id,
    price_date)` index is translated to `ConflictError` (`DAY_ALREADY_ADVANCED`,
    AC2) — the caller never sees a partially-advanced day.
    """
    snapshots: list[NavSnapshot] = []
    holdings_revalued = 0
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
            holdings_revalued += _revalue_holdings(
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
    return snapshots, holdings_revalued


def _recompute_all_goal_progress(session: Session, *, price_date: str) -> int:
    """Snapshot every customer's goals for `price_date` (E7-S3 AC1, AC5) —
    every customer with at least one `Goal`, not only those with `Holding`
    rows, since a goal's progress is still meaningfully zero without one."""
    snapshot_at = _now_iso()
    total_created = 0
    for customer_id in list_customer_ids_with_goals(session):
        total_value = _sum_customer_holdings_value(session, customer_id)
        snapshots = recompute_customer_goal_progress(
            session,
            customer_id=customer_id,
            total_holdings_value=total_value,
            price_date=price_date,
            snapshot_at=snapshot_at,
        )
        total_created += len(snapshots)
    return total_created


def _evaluate_all_rebalancing(
    session: Session,
    *,
    customer_ids: tuple[int, ...],
    actor_id: int | None,
    actor_role: str,
) -> int:
    """Evaluate rebalancing for every customer with holdings (E8-S2), counting
    how many actually produced a new `RebalancingRecommendation`. A no-op when
    `actor_id` is absent (see `advance_day`'s docstring)."""
    if actor_id is None:
        return 0
    created = 0
    for customer_id in customer_ids:
        recommendation = evaluate_customer_rebalancing(
            session, customer_id=customer_id, actor_id=actor_id, actor_role=actor_role
        )
        if recommendation is not None:
            created += 1
    return created


def _sum_customer_holdings_value(session: Session, customer_id: int) -> Decimal:
    holdings = list_holdings_for_customer(session, customer_id)
    return sum((holding.current_value for holding in holdings), Decimal("0"))


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
) -> int:
    """Scale every `Holding` in `asset_class_id` by the NAV's price ratio
    (data-models.md §4.11: "revalued each advance-a-day"; system-design.md §5.3).
    Returns the count of `Holding` rows revalued, for `AdvanceDayResult.holdings_revalued`.
    """
    holdings = list_holdings_for_asset_class(session, asset_class_id)
    for holding in holdings:
        revalued = quantize(
            holding.current_value * new_nav_value / previous_nav_value, MONEY_QUANTUM
        )
        update_holding_value(
            session, holding_id=holding.id, current_value=revalued, as_of_date=as_of_date
        )
    return len(holdings)


def _require_latest_nav(session: Session, asset_class_id: int) -> NavSnapshot:
    latest = get_latest_nav(session, asset_class_id)
    if latest is None:
        raise NotFoundError(
            f"AssetClass {asset_class_id} has no NavSnapshot history to advance from.",
            code="NO_NAV_HISTORY",
        )
    return latest
