"""Rebalancing engine (E8-S2) — pure BUY/SELL proposal computation.

Given each held asset class's current-vs-target drift (already computed by
`domain.holdings.drift.compute_drift`) and the portfolio's total value, this
module proposes the BUY/SELL amount and unit count that would move the
customer's allocation exactly to target for every asset class whose absolute
drift exceeds the active threshold (AC1). Every value is `Decimal`/`int`
derived through `types.fixedpoint`; no `float` appears anywhere in this
module or in any intermediate value (AC6).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.holdings.drift import AssetClassDrift, is_over_threshold
from src.types.entities import ProposedAction
from src.types.enums import TradeAction
from src.types.fixedpoint import decimal_to_basis_points, quantize, quantize_units

MONEY_QUANTUM = Decimal("0.01")
BASIS_POINTS_TOTAL = Decimal(10000)


@dataclass(frozen=True)
class AssetClassInfo:
    """The lookup an asset class needs to turn a bps drift into a unit count."""

    asset_class_id: int
    code: str
    nav_value: Decimal


def propose_rebalancing_actions(
    *,
    drifts: list[AssetClassDrift],
    total_value: Decimal,
    threshold_bps: int,
    asset_classes_by_id: dict[int, AssetClassInfo],
) -> list[ProposedAction]:
    """One `ProposedAction` per asset class whose drift exceeds `threshold_bps`
    (AC1, AC2) — an asset class within threshold contributes nothing, so a
    fully-within-threshold portfolio returns an empty list, not a no-op row."""
    actions: list[ProposedAction] = []
    for drift in drifts:
        if not is_over_threshold(decimal_to_basis_points(drift.drift_percent), threshold_bps):
            continue
        asset_class_info = asset_classes_by_id[drift.asset_class_id]
        action = _propose_single_action(
            drift, total_value=total_value, asset_class_info=asset_class_info
        )
        if action is not None:
            actions.append(action)
    return actions


def _propose_single_action(
    drift: AssetClassDrift, *, total_value: Decimal, asset_class_info: AssetClassInfo
) -> ProposedAction | None:
    target_bps = decimal_to_basis_points(drift.target_percent)
    current_bps = decimal_to_basis_points(drift.current_percent)
    target_value = quantize(total_value * Decimal(target_bps) / BASIS_POINTS_TOTAL, MONEY_QUANTUM)
    current_value = quantize(
        total_value * Decimal(current_bps) / BASIS_POINTS_TOTAL, MONEY_QUANTUM
    )
    amount = quantize(target_value - current_value, MONEY_QUANTUM)
    if amount == 0:
        return None

    trade_action = TradeAction.BUY if amount > 0 else TradeAction.SELL
    units = (
        quantize_units(abs(amount) / asset_class_info.nav_value)
        if asset_class_info.nav_value > 0
        else Decimal("0.0000")
    )
    return ProposedAction(
        asset_class_id=drift.asset_class_id,
        asset_class_code=asset_class_info.code,
        action=trade_action,
        amount=abs(amount),
        units=units,
        drift_percent=drift.drift_percent,
    )
