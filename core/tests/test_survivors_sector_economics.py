"""Literal C4 boundary check for the redundant Decimal context survivor."""

from decimal import Decimal, Inexact, Rounded, localcontext
from fractions import Fraction

from method_rows import measure

from eii_core.calc.sector_economics import Component, sector_norms


def test_sector_fraction_shares_ignore_caller_precision_and_traps():
    """Compensation .00375*1000/3=1.25%; component 37.65/3=12.55%."""
    with localcontext(prec=1) as context:
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        result = sector_norms(
            employees=measure(3),
            productivity=measure(100, "qar"),
            compensation_thousand=measure(".00375", "qar_thousand"),
            surplus_thousand=measure(".00375", "qar_thousand"),
            goods_percent=measure("37.65", "percent"),
            services_percent=measure(0, "percent"),
            components=[
                Component(
                    "invented",
                    "goods",
                    measure(1, "qar_thousand"),
                    measure(3, "qar_thousand"),
                    "goods",
                )
            ],
        )
    assert result["compensation_percent_unrounded"] == Fraction(5, 4)
    assert result["compensation_percent"].value == Decimal("1.3")
    assert result["surplus_percent"].value == Decimal("1.3")
    assert result["invented"].value == Decimal("12.6")
