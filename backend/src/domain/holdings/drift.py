"""Holdings drift calculation (E6-S3) — pure fixed-point computation of a
customer's current vs. target per-asset-class allocation, given their holdings
and their active recommended allocation (E6-S3 AC1).

Every value here is an integer basis point or a `Decimal` derived from one via
`types.fixedpoint`; no `float` appears anywhere in this module or in any
intermediate value (AC2). `current_percent` is allocated with a largest-remainder
method so the reported percentages always sum to exactly 100 when a customer
holds at least one asset class (AC5) — not merely "within tolerance".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from src.types.fixedpoint import basis_points_to_decimal

TOTAL_BASIS_POINTS = 10000


@dataclass(frozen=True)
class AssetClassDrift:
    """One asset class's current vs. target allocation for a customer."""

    asset_class_id: int
    current_percent: Decimal
    target_percent: Decimal
    drift_percent: Decimal


def compute_drift(
    *,
    holdings_by_asset_class: dict[int, Decimal],
    target_bps_by_asset_class: dict[int, int],
) -> list[AssetClassDrift]:
    """Current vs. target percentage per held asset class (AC1).

    A customer with zero holdings returns an empty list — not an error and not
    a divide-by-zero exception (AC3). `target_bps_by_asset_class` entries with
    no corresponding holding are ignored; a held asset class absent from the
    target allocation is treated as a 0% target (its entire current position is
    drift).
    """
    if not holdings_by_asset_class:
        return []
    total_value = sum(holdings_by_asset_class.values(), Decimal(0))
    if total_value <= 0:
        return []

    current_bps = _allocate_bps_exact(holdings_by_asset_class, total_value)

    results: list[AssetClassDrift] = []
    for asset_class_id in holdings_by_asset_class:
        current = current_bps[asset_class_id]
        target = target_bps_by_asset_class.get(asset_class_id, 0)
        results.append(
            AssetClassDrift(
                asset_class_id=asset_class_id,
                current_percent=basis_points_to_decimal(current),
                target_percent=basis_points_to_decimal(target),
                drift_percent=basis_points_to_decimal(current - target),
            )
        )
    return results


def is_over_threshold(drift_percent_bps: int, threshold_bps: int) -> bool:
    """The threshold is exclusive (E6-S3 AC4, system-design.md §6.1): drift must
    strictly exceed the threshold to trigger rebalancing — exactly equal does
    not trigger. Both arguments are integers, so the comparison is exact."""
    return abs(drift_percent_bps) > threshold_bps


def _allocate_bps_exact(values: dict[int, Decimal], total: Decimal) -> dict[int, int]:
    """Largest-remainder allocation of `values` as basis points of `total`.

    Guarantees `sum(result.values()) == 10000` exactly whenever `total > 0` —
    per-item rounding alone can drift the sum away from 10000 by a few basis
    points; the largest fractional remainder(s) absorb that difference so the
    total is always exact (AC5).
    """
    raw = {
        asset_class_id: (value / total) * Decimal(TOTAL_BASIS_POINTS)
        for asset_class_id, value in values.items()
    }
    floors = {
        asset_class_id: int(ratio.to_integral_value(rounding=ROUND_FLOOR))
        for asset_class_id, ratio in raw.items()
    }
    remainder = TOTAL_BASIS_POINTS - sum(floors.values())

    by_fractional_part_desc = sorted(
        raw, key=lambda asset_class_id: raw[asset_class_id] - floors[asset_class_id], reverse=True
    )
    result = dict(floors)
    for asset_class_id in by_fractional_part_desc[:remainder]:
        result[asset_class_id] += 1
    return result
