"""`domain/holdings/drift.py` — compute_drift() / is_over_threshold()
(E6-S3 AC1-AC5)."""

from __future__ import annotations

from decimal import Decimal

from src.domain.holdings.drift import compute_drift, is_over_threshold


def test_returns_current_target_and_drift_percent_per_asset_class() -> None:
    results = compute_drift(
        holdings_by_asset_class={1: Decimal("6000.00"), 2: Decimal("4000.00")},
        target_bps_by_asset_class={1: 5000, 2: 5000},
    )

    by_id = {r.asset_class_id: r for r in results}
    assert by_id[1].current_percent == Decimal("60.00")
    assert by_id[1].target_percent == Decimal("50.00")
    assert by_id[1].drift_percent == Decimal("10.00")
    assert by_id[2].current_percent == Decimal("40.00")
    assert by_id[2].target_percent == Decimal("50.00")
    assert by_id[2].drift_percent == Decimal("-10.00")


def test_no_float_appears_in_any_intermediate_or_final_drift_value() -> None:
    results = compute_drift(
        holdings_by_asset_class={1: Decimal("3333.33"), 2: Decimal("6666.67")},
        target_bps_by_asset_class={1: 3000, 2: 7000},
    )

    for result in results:
        assert isinstance(result.current_percent, Decimal)
        assert isinstance(result.target_percent, Decimal)
        assert isinstance(result.drift_percent, Decimal)
        assert not isinstance(result.current_percent, float)


def test_a_customer_with_zero_holdings_produces_an_empty_result_not_an_error() -> None:
    assert compute_drift(holdings_by_asset_class={}, target_bps_by_asset_class={1: 10000}) == []


def test_a_customer_whose_total_holding_value_is_zero_produces_an_empty_result() -> None:
    assert (
        compute_drift(
            holdings_by_asset_class={1: Decimal("0.00")}, target_bps_by_asset_class={1: 10000}
        )
        == []
    )


def test_drift_exactly_equal_to_the_threshold_does_not_trigger_exclusive_boundary() -> None:
    assert is_over_threshold(500, 500) is False
    assert is_over_threshold(-500, 500) is False


def test_drift_exceeding_the_threshold_by_one_basis_point_triggers() -> None:
    assert is_over_threshold(501, 500) is True
    assert is_over_threshold(-501, 500) is True


def test_drift_below_the_threshold_does_not_trigger() -> None:
    assert is_over_threshold(499, 500) is False


def test_sum_of_current_percent_equals_exactly_100_for_an_awkward_three_way_split() -> None:
    # 1/3 each rounds to 33.33 + 33.33 + 33.33 = 99.99 without remainder distribution.
    results = compute_drift(
        holdings_by_asset_class={
            1: Decimal("1000.00"),
            2: Decimal("1000.00"),
            3: Decimal("1000.01"),
        },
        target_bps_by_asset_class={1: 3333, 2: 3333, 3: 3334},
    )

    total = sum((r.current_percent for r in results), Decimal("0.00"))
    assert total == Decimal("100.00")


def test_a_held_asset_class_missing_from_the_target_allocation_is_treated_as_zero_target() -> None:
    results = compute_drift(
        holdings_by_asset_class={1: Decimal("1000.00")}, target_bps_by_asset_class={}
    )

    assert len(results) == 1
    assert results[0].target_percent == Decimal("0.00")
    assert results[0].drift_percent == Decimal("100.00")
