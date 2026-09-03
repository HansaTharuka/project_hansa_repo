"""The single money / percent conversion module (NFR-01, data-models.md §2).

Stored integers (minor units, basis points) convert here — and only here — to the
`Decimal` values the domain computes with and the fixed-scale strings the API
transports. Rounding is ROUND_HALF_UP and is applied exactly once per conversion,
never mid-calculation. No float appears in this module or in any intermediate value.
"""

from decimal import ROUND_HALF_UP, Decimal

MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")
UNITS_QUANTUM = Decimal("0.0001")
WHOLE_QUANTUM = Decimal(1)

MINOR_UNITS_PER_MAJOR = Decimal(100)
BASIS_POINTS_PER_PERCENT = Decimal(100)


def quantize(value: Decimal, quantum: Decimal) -> Decimal:
    """Round `value` to `quantum`'s scale, half away from zero."""
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def minor_units_to_decimal(minor_units: int) -> Decimal:
    """2_500_000 -> Decimal('25000.00')."""
    return quantize(Decimal(minor_units) / MINOR_UNITS_PER_MAJOR, MONEY_QUANTUM)


def decimal_to_minor_units(amount: Decimal) -> int:
    """Decimal('25000.00') -> 2_500_000."""
    return int(quantize(amount * MINOR_UNITS_PER_MAJOR, WHOLE_QUANTUM))


def money_to_string(minor_units: int) -> str:
    """2_500_000 -> '25000.00' — the JSON transport form for money."""
    return str(minor_units_to_decimal(minor_units))


def string_to_minor_units(value: str) -> int:
    """'25000.00' -> 2_500_000."""
    return decimal_to_minor_units(Decimal(value))


def basis_points_to_decimal(basis_points: int) -> Decimal:
    """6000 -> Decimal('60.00'); -725 -> Decimal('-7.25')."""
    return quantize(Decimal(basis_points) / BASIS_POINTS_PER_PERCENT, PERCENT_QUANTUM)


def decimal_to_basis_points(percent: Decimal) -> int:
    """Decimal('60.00') -> 6000."""
    return int(quantize(percent * BASIS_POINTS_PER_PERCENT, WHOLE_QUANTUM))


def percent_to_string(basis_points: int) -> str:
    """6000 -> '60.00' — the JSON transport form for percentages and drift."""
    return str(basis_points_to_decimal(basis_points))


def string_to_basis_points(value: str) -> int:
    """'60.00' -> 6000."""
    return decimal_to_basis_points(Decimal(value))


def quantize_units(units: Decimal) -> Decimal:
    """Quantities inside proposed_actions_json carry scale 4."""
    return quantize(units, UNITS_QUANTUM)


def units_to_string(units: Decimal) -> str:
    """Decimal('12.3456') -> '12.3456'."""
    return str(quantize_units(units))


def string_to_units(value: str) -> Decimal:
    """'24.1600' -> Decimal('24.1600')."""
    return quantize_units(Decimal(value))
