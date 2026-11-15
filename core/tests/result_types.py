"""Runtime narrowing for heterogeneous card results in tests."""

from decimal import Decimal

from eii_core.calc.facts import CalculationFact


def fact_value(value: object) -> Decimal | str:
    assert isinstance(value, CalculationFact)
    return value.value
