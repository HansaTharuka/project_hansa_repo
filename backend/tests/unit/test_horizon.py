"""`domain/recommendation/horizon.py` — derive_horizon() (E5-S2 AC4; ut-171).

Boundary semantics per api-contracts.md §7.1 Notes: horizon buckets are
derived deterministically from `target_date` minus a reference date —
`SHORT` < 3 years, `MEDIUM` 3-7 years (inclusive both ends), `LONG` > 7 years.
"""

from __future__ import annotations

import pytest

from src.domain.recommendation.horizon import LONG, MEDIUM, SHORT, derive_horizon


@pytest.mark.parametrize(
    ("reference_date", "target_date", "expected"),
    [
        ("2026-09-07", "2027-09-07", SHORT),  # exactly 1 year away
        ("2026-09-07", "2029-09-06", SHORT),  # one day short of 3 years
        ("2026-09-07", "2029-09-07", MEDIUM),  # exactly 3 years away
        ("2026-09-07", "2033-09-07", MEDIUM),  # exactly 7 years away
        ("2026-09-07", "2034-09-06", MEDIUM),  # one day short of 8 years
        ("2026-09-07", "2034-09-07", LONG),  # exactly 8 years away
        ("2026-09-07", "2040-01-01", LONG),  # far in the future
    ],
)
def test_derive_horizon_buckets_target_date_against_reference_date(
    reference_date: str, target_date: str, expected: str
) -> None:
    assert derive_horizon(target_date=target_date, reference_date=reference_date) == expected


def test_derive_horizon_is_deterministic_across_repeated_calls() -> None:
    first = derive_horizon(target_date="2033-09-07", reference_date="2026-09-07")
    second = derive_horizon(target_date="2033-09-07", reference_date="2026-09-07")

    assert first == second == MEDIUM


def test_derive_horizon_rejects_a_target_date_in_the_past_of_reference_date() -> None:
    with pytest.raises(ValueError, match="target_date"):
        derive_horizon(target_date="2020-01-01", reference_date="2026-09-07")
