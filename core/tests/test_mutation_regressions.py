"""Independent invented boundary fixtures for the mutation campaign."""

from dataclasses import replace
from decimal import ROUND_DOWN, localcontext
from decimal import Decimal as D
from fractions import Fraction

import pytest
from method_rows import measure
from test_sector_economics import component

from eii_core.calc import sector_economics as se


def invented_norms():
    common = {"period": "2022", "geography": "national", "kind": "national"}
    return {
        "employees": measure(10, **common),
        "productivity": measure(1000, unit="qar", **common),
        "compensation_thousand": measure(1, unit="qar_thousand", **common),
        "surplus_thousand": measure(2, unit="qar_thousand", **common),
        "goods_percent": measure("40.65", unit="percent", **common),
        "services_percent": measure("10.25", unit="percent", **common),
    }


def test_sector_literals_metadata_and_boundaries():
    result = se.sector_norms(
        **invented_norms(),
        components=(
            component("invented_zero", "goods", "0", "10"),
            component("invented_full", "services", "10", "10"),
        ),
    )
    for key, expected in {
        "compensation_percent": "10.0",
        "surplus_percent": "20.0",
        "goods_percent": "40.7",
        "services_percent": "10.3",
        "invented_zero": "0.0",
        "invented_full": "10.3",
    }.items():
        fact = result[key]
        assert str(fact.value) == expected
        assert fact.metric_key == key
        assert fact.release_id == "published"
        assert fact.period == "2022"
        assert fact.geography == "national"
    assert result["compensation_percent_unrounded"] == D(10)
    assert result["surplus_percent_unrounded"] == D(20)
    values = invented_norms()
    values["goods_percent"] = replace(values["goods_percent"], value=D(0))
    assert se.sector_norms(**values)["goods_percent"].value == D("0.0")


@pytest.mark.parametrize(
    "field,changes,reason",
    [
        ("employees", {"unit": "qar"}, "unit mismatch"),
        ("employees", {"value": D("1.5")}, "unit mismatch"),
        ("productivity", {"unit": "count"}, "unit mismatch"),
        ("productivity", {"period": "2021"}, "period mismatch"),
        (
            "productivity",
            {"geography": "zone:invented", "geography_kind": "public"},
            "geography mismatch",
        ),
        ("surplus_thousand", {"value": D(-1)}, "negative survey value"),
        ("goods_percent", {"value": D(101)}, "invalid percentage"),
    ],
)
def test_sector_exact_refusals(field, changes, reason):
    values = invented_norms()
    values[field] = replace(values[field], **changes)
    with pytest.raises(ValueError) as error:
        se.sector_norms(**values)
    assert str(error.value) == reason


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"group": "invented_unknown"}, "unknown component group"),
        ({"key": "production"}, "invalid component key"),
        (
            {
                "value": measure(
                    11,
                    unit="qar_thousand",
                    period="2022",
                    geography="national",
                    kind="national",
                )
            },
            "component outside group total",
        ),
        (
            {
                "value": measure(
                    1,
                    unit="qar_thousand",
                    period="2021",
                    geography="national",
                    kind="national",
                )
            },
            "period mismatch",
        ),
        (
            {"value": measure(1, unit="qar_thousand", period="2022")},
            "geography mismatch",
        ),
    ],
)
def test_sector_component_exact_refusals(changes, reason):
    made = replace(component("invented", "goods", "1", "10"), **changes)
    with pytest.raises(ValueError) as error:
        se.sector_norms(**invented_norms(), components=(made,))
    assert str(error.value) == reason


def test_sector_other_exact_refusals():
    with pytest.raises(ValueError) as error:
        se.share_range(())
    assert str(error.value) == "missing share"
    with pytest.raises(ValueError) as error:
        se.sector_norms(**invented_norms(), output_per_establishment=D(1))
    assert (
        str(error.value) == "withdrawn production derivation: output_per_establishment"
    )


def test_sector_precision_is_independent_of_callers_context():
    values = invented_norms()
    values["employees"] = replace(values["employees"], value=D(3))
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        result = se.sector_norms(**values)
    # 100/3, hand long division at the declared fifty significant digits.
    assert str(result["compensation_percent_unrounded"]) == "100/3"


def test_sector_case_sensitive_component_name():
    result = se.sector_norms(
        **invented_norms(), components=(component("PRODUCTION", "goods", "0", "10"),)
    )
    assert result["PRODUCTION"].value == D("0.0")


def test_sector_half_up_at_working_precision():
    values = invented_norms()
    values["compensation_thousand"] = replace(
        values["compensation_thousand"], value=D("1." + "0" * 49 + "5")
    )
    result = se.sector_norms(**values)
    assert result["compensation_percent_unrounded"] == Fraction(
        D("10." + "0" * 48 + "5")
    )


def test_share_range_preserves_first_equal_representation():
    low, high = se.share_range((D("1.0"), D("1.00")))
    assert str(low) == "1.0"
    assert str(high) == "1.0"
