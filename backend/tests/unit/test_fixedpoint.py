"""ut-006 — E1-S1 AC2: fixed-point round-trips per data-models.md §2.

Minor units, basis points and unit quantities convert to Decimal and to their
2- or 4-decimal string transport form and back, with ROUND_HALF_UP applied once
and no float at any point.
"""

from decimal import Decimal

import pytest

from src.types import fixedpoint


class TestMoneyRoundTrip:
    """Money: INTEGER minor units (scale 2) <-> Decimal <-> 2-decimal string."""

    def test_minor_units_become_a_two_decimal_decimal(self) -> None:
        assert fixedpoint.minor_units_to_decimal(2_500_000) == Decimal("25000.00")

    def test_minor_units_decimal_keeps_the_two_decimal_exponent(self) -> None:
        # Arrange / Act
        amount = fixedpoint.minor_units_to_decimal(2_500_000)
        # Assert — Decimal("25000") would compare equal but serialise as "25000"
        assert amount.as_tuple().exponent == -2

    def test_minor_units_render_as_a_two_decimal_string(self) -> None:
        assert fixedpoint.money_to_string(2_500_000) == "25000.00"

    def test_two_decimal_string_parses_back_to_minor_units(self) -> None:
        assert fixedpoint.string_to_minor_units("25000.00") == 2_500_000

    def test_money_round_trips_through_string_unchanged(self) -> None:
        assert fixedpoint.string_to_minor_units(fixedpoint.money_to_string(4_820_000)) == 4_820_000

    def test_decimal_converts_to_minor_units(self) -> None:
        assert fixedpoint.decimal_to_minor_units(Decimal("132.45")) == 13_245

    def test_sub_cent_decimal_rounds_half_up_to_minor_units(self) -> None:
        assert fixedpoint.decimal_to_minor_units(Decimal("0.005")) == 1

    def test_negative_sub_cent_decimal_rounds_half_away_from_zero(self) -> None:
        assert fixedpoint.decimal_to_minor_units(Decimal("-0.005")) == -1

    def test_zero_money_renders_with_both_decimals(self) -> None:
        assert fixedpoint.money_to_string(0) == "0.00"


class TestBasisPointRoundTrip:
    """Percentage / drift: INTEGER basis points <-> Decimal <-> 2-decimal string."""

    @pytest.mark.parametrize(
        ("basis_points", "rendered"),
        [(6000, "60.00"), (10000, "100.00"), (-725, "-7.25"), (0, "0.00"), (500, "5.00")],
    )
    def test_basis_points_render_as_a_two_decimal_percent_string(
        self, basis_points: int, rendered: str
    ) -> None:
        assert fixedpoint.percent_to_string(basis_points) == rendered

    @pytest.mark.parametrize(
        ("basis_points", "rendered"),
        [(6000, "60.00"), (10000, "100.00"), (-725, "-7.25"), (0, "0.00"), (500, "5.00")],
    )
    def test_percent_string_parses_back_to_basis_points(
        self, basis_points: int, rendered: str
    ) -> None:
        assert fixedpoint.string_to_basis_points(rendered) == basis_points

    def test_basis_points_become_a_two_decimal_decimal(self) -> None:
        assert fixedpoint.basis_points_to_decimal(6000) == Decimal("60.00")

    def test_negative_drift_is_preserved_as_a_signed_decimal(self) -> None:
        assert fixedpoint.basis_points_to_decimal(-725) == Decimal("-7.25")

    def test_decimal_percent_converts_to_basis_points(self) -> None:
        assert fixedpoint.decimal_to_basis_points(Decimal("40.00")) == 4000

    def test_fractional_basis_point_rounds_half_up(self) -> None:
        assert fixedpoint.decimal_to_basis_points(Decimal("7.245")) == 725


class TestUnitsRoundTrip:
    """Units inside proposed_actions_json: Decimal quantized to 4 decimals."""

    def test_units_quantize_to_four_decimals(self) -> None:
        assert fixedpoint.quantize_units(Decimal("12.3456")) == Decimal("12.3456")

    def test_units_render_as_a_four_decimal_string(self) -> None:
        assert fixedpoint.units_to_string(Decimal("12.3456")) == "12.3456"

    def test_whole_units_render_with_four_decimals(self) -> None:
        assert fixedpoint.units_to_string(Decimal("32")) == "32.0000"

    def test_units_string_parses_back_to_a_quantized_decimal(self) -> None:
        assert fixedpoint.string_to_units("24.1600") == Decimal("24.1600")

    def test_excess_precision_rounds_half_up_to_four_decimals(self) -> None:
        assert fixedpoint.units_to_string(Decimal("12.34565")) == "12.3457"


class TestRoundingIsAppliedOnce:
    """data-models.md §2 rule 3 — ROUND_HALF_UP, applied once, never mid-calculation."""

    def test_quantize_uses_round_half_up(self) -> None:
        assert fixedpoint.quantize(Decimal("2.345"), fixedpoint.MONEY_QUANTUM) == Decimal("2.35")

    def test_repeated_quantization_is_idempotent(self) -> None:
        # Arrange
        once = fixedpoint.quantize(Decimal("2.345"), fixedpoint.MONEY_QUANTUM)
        # Act
        twice = fixedpoint.quantize(once, fixedpoint.MONEY_QUANTUM)
        # Assert — a second rounding pass must not move the value again
        assert twice == once

    def test_conversions_never_produce_a_float(self) -> None:
        values: list[object] = [
            fixedpoint.minor_units_to_decimal(2_500_000),
            fixedpoint.basis_points_to_decimal(-725),
            fixedpoint.quantize_units(Decimal("12.3456")),
        ]
        assert all(isinstance(value, Decimal) for value in values)
