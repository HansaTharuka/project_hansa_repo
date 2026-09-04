"""The simulated price-feed clock (E6-S2 AC4; BRD §5.1).

No wall-clock scheduler, cron, or timer exists anywhere in this codebase — the
simulated day advances only when `domain.holdings.service.advance_day` is
explicitly invoked. This module holds no state of its own; it is a pure date
utility over the `YYYY-MM-DD` strings `NavSnapshot.price_date` already stores
(data-models.md §2), so it never needs a database session.
"""

from __future__ import annotations

from datetime import date, timedelta

DATE_FORMAT = "%Y-%m-%d"


def next_price_date(current: str) -> str:
    """The next sequential simulated date, exactly one day after `current`."""
    current_date = date.fromisoformat(current)
    return (current_date + timedelta(days=1)).strftime(DATE_FORMAT)
