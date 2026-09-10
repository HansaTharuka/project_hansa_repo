"""Goal-horizon bucket derivation (E5-S2 AC4; api-contracts.md §7.1 Notes).

Pure, integer-only date arithmetic: `date.fromisoformat` produces `date`
objects, and the year difference is computed by simple integer subtraction
with a month/day anniversary adjustment — no `float` literal, `float()` call,
or floating-point division appears anywhere in this module (NFR-01,
`tests/architecture/test_no_float_in_domain.py`). Calling `derive_horizon`
twice with identical inputs always returns the identical bucket: there is no
randomness, no wall-clock read, and no mutable module-level state (AC4).
"""

from __future__ import annotations

from datetime import date

SHORT = "SHORT"
MEDIUM = "MEDIUM"
LONG = "LONG"

_SHORT_MAX_YEARS_EXCLUSIVE = 3
_MEDIUM_MAX_YEARS_INCLUSIVE = 7


def derive_horizon(*, target_date: str, reference_date: str) -> str:
    """Bucket `target_date` relative to `reference_date` into SHORT/MEDIUM/LONG.

    `SHORT` for less than 3 years away, `MEDIUM` for 3 to 7 years inclusive,
    `LONG` for more than 7 years. Raises `ValueError` if `target_date` is
    earlier than `reference_date` — a goal cannot have a horizon in the past.
    """
    years = _whole_years_between(reference_date, target_date)
    if years < 0:
        raise ValueError(
            f"target_date {target_date!r} cannot be earlier than reference_date "
            f"{reference_date!r}."
        )
    if years < _SHORT_MAX_YEARS_EXCLUSIVE:
        return SHORT
    if years <= _MEDIUM_MAX_YEARS_INCLUSIVE:
        return MEDIUM
    return LONG


def _whole_years_between(reference_date: str, target_date: str) -> int:
    """The number of whole anniversaries of `reference_date` that have
    elapsed by `target_date`, as a plain integer (never a float)."""
    reference = date.fromisoformat(reference_date)
    target = date.fromisoformat(target_date)
    years = target.year - reference.year
    if (target.month, target.day) < (reference.month, reference.day):
        years -= 1
    return years
