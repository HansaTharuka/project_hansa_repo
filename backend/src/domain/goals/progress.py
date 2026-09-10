"""Goal progress computation (E7-S3) — pure fixed-point mapping from a
customer's current portfolio value to a goal's `percent_complete`.

`current_value * 10000 / target_amount` is computed and rounded to a whole
basis point (`ROUND_HALF_UP`) before ever being converted back to the 2-dp
`Decimal` percent the API transports, and the result is capped at 20000 bps
(200.00%, AC2) — a `current_value` far exceeding `target_amount` never
produces an unbounded percentage. `current_value <= 0` short-circuits to
`Decimal("0.00")` without ever dividing (AC3). Every value here is `Decimal`
or `int`; no `float` appears anywhere in this module (AC2, NFR-01).
"""

from __future__ import annotations

from decimal import Decimal

from src.types.fixedpoint import WHOLE_QUANTUM, basis_points_to_decimal, quantize

BASIS_POINTS_PER_UNIT = Decimal(10000)
MAX_PERCENT_COMPLETE_BPS = 20000
ZERO_PERCENT = Decimal("0.00")


def compute_percent_complete(current_value: Decimal, target_amount: Decimal) -> Decimal:
    """`current_value` and `target_amount` are money `Decimal` values;
    `target_amount > 0` is guaranteed by `Goal`'s own CHECK constraint, so the
    divisor is never zero here (AC3)."""
    if current_value <= 0:
        return ZERO_PERCENT

    raw_bps = current_value * BASIS_POINTS_PER_UNIT / target_amount
    rounded_bps = int(quantize(raw_bps, WHOLE_QUANTUM))
    capped_bps = min(rounded_bps, MAX_PERCENT_COMPLETE_BPS)
    return basis_points_to_decimal(capped_bps)
