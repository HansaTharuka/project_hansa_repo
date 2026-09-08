"""`domain/rebalancing/engine.py` — propose_rebalancing_actions() (E8-S2 AC1,
AC2, AC6; ut-147, ut-152)."""

from __future__ import annotations

from decimal import Decimal

from src.domain.holdings.drift import AssetClassDrift, compute_drift
from src.domain.rebalancing.engine import AssetClassInfo, propose_rebalancing_actions
from src.types.enums import TradeAction

EQ_DM = AssetClassInfo(asset_class_id=1, code="EQ_DM", nav_value=Decimal("100.00"))
FI_GOV = AssetClassInfo(asset_class_id=2, code="FI_GOV", nav_value=Decimal("50.00"))
ASSET_CLASSES = {1: EQ_DM, 2: FI_GOV}


def test_a_drift_exceeding_threshold_produces_a_sell_action_moving_toward_target() -> None:
    drifts = compute_drift(
        holdings_by_asset_class={1: Decimal("7000.00"), 2: Decimal("3000.00")},
        target_bps_by_asset_class={1: 5000, 2: 5000},
    )

    actions = propose_rebalancing_actions(
        drifts=drifts,
        total_value=Decimal("10000.00"),
        threshold_bps=500,
        asset_classes_by_id=ASSET_CLASSES,
    )

    by_asset_class = {a.asset_class_id: a for a in actions}
    assert by_asset_class[1].action == TradeAction.SELL
    assert by_asset_class[1].amount == Decimal("2000.00")
    assert by_asset_class[2].action == TradeAction.BUY
    assert by_asset_class[2].amount == Decimal("2000.00")


def test_drift_within_threshold_on_every_asset_class_produces_no_actions() -> None:
    drifts = compute_drift(
        holdings_by_asset_class={1: Decimal("5100.00"), 2: Decimal("4900.00")},
        target_bps_by_asset_class={1: 5000, 2: 5000},
    )

    actions = propose_rebalancing_actions(
        drifts=drifts,
        total_value=Decimal("10000.00"),
        threshold_bps=500,
        asset_classes_by_id=ASSET_CLASSES,
    )

    assert actions == []


def test_units_are_computed_from_the_asset_class_nav_value() -> None:
    drifts = compute_drift(
        holdings_by_asset_class={1: Decimal("9000.00"), 2: Decimal("1000.00")},
        target_bps_by_asset_class={1: 5000, 2: 5000},
    )

    actions = propose_rebalancing_actions(
        drifts=drifts,
        total_value=Decimal("10000.00"),
        threshold_bps=500,
        asset_classes_by_id=ASSET_CLASSES,
    )

    sell_eq_dm = next(a for a in actions if a.asset_class_id == 1)
    assert sell_eq_dm.action == TradeAction.SELL
    assert sell_eq_dm.amount == Decimal("4000.00")
    assert sell_eq_dm.units == Decimal("40.0000")  # 4000.00 / 100.00 nav


def test_an_asset_class_already_exactly_at_target_value_produces_no_action() -> None:
    """An asset class whose drift crosses the threshold in percentage terms can
    still land at `amount == 0` once quantized back to money — `_propose_single_
    action` returns `None` for that asset class rather than a zero-value
    ProposedAction (engine.py line 68-69's documented no-op)."""
    drifts = [
        AssetClassDrift(
            asset_class_id=1,
            current_percent=Decimal("50.00"),
            target_percent=Decimal("50.00"),
            drift_percent=Decimal("50.00"),  # exceeds threshold in isolation
        )
    ]

    actions = propose_rebalancing_actions(
        drifts=drifts,
        total_value=Decimal("10000.00"),
        threshold_bps=0,
        asset_classes_by_id=ASSET_CLASSES,
    )

    assert actions == []


def test_no_float_appears_in_any_proposed_action_field() -> None:
    drifts = compute_drift(
        holdings_by_asset_class={1: Decimal("9000.00"), 2: Decimal("1000.00")},
        target_bps_by_asset_class={1: 5000, 2: 5000},
    )

    actions = propose_rebalancing_actions(
        drifts=drifts,
        total_value=Decimal("10000.00"),
        threshold_bps=500,
        asset_classes_by_id=ASSET_CLASSES,
    )

    for action in actions:
        assert isinstance(action.amount, Decimal)
        assert isinstance(action.units, Decimal)
        assert isinstance(action.drift_percent, Decimal)
        assert not isinstance(action.amount, float)
        assert not isinstance(action.units, float)
