"""W12 arithmetic; component rows use the published survey figures."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest
from method_rows import measure
from result_types import fact_value

from eii_core.calc.facts import WithdrawnProduction
from eii_core.calc.sector_economics import (
    CLOSED_OUTPUTS,
    Component,
    output_keys,
    sector_norms,
    share_range,
)

FIXTURE = Path(__file__).parent / "fixtures/methods/public_methods.json"


def inputs(year: str = "2022"):
    fixture = json.loads(FIXTURE.read_text())["published"]["C4"]
    row = fixture["years"][year]
    common = {"period": year, "geography": "national", "kind": "national"}
    return (
        {
            "employees": measure(
                row["employees"].replace(",", ""), unit="count", **common
            ),
            "productivity": measure(
                row["productivity"].replace(",", ""), unit="qar", **common
            ),
            "compensation_thousand": measure(
                row["compensation_thousand"].replace(",", ""),
                unit="qar_thousand",
                **common,
            ),
            "surplus_thousand": measure(
                row["surplus_thousand"].replace(",", ""), unit="qar_thousand", **common
            ),
            "goods_percent": measure(row["goods_percent"], unit="percent", **common),
            "services_percent": measure(
                row["services_percent"], unit="percent", **common
            ),
        },
        row,
        common,
    )


def component(
    key: str, group: str, value: str, total: str, year: str = "2022"
) -> Component:
    common = {
        "period": year,
        "geography": "national",
        "kind": "national",
        "unit": "qar_thousand",
    }
    return Component(
        key,
        group,
        measure(value.replace(",", ""), **common),
        measure(total.replace(",", ""), **common),
        group,
    )


def test_w12_published_shares():
    values, _, _ = inputs()
    result = sector_norms(**values)
    assert fact_value(result["compensation_percent"]) == D("20.6")
    assert fact_value(result["surplus_percent"]) == D("19.7")
    assert fact_value(result["goods_percent"]) == D("40.6")
    assert fact_value(result["services_percent"]) == D("16.5")
    assert output_keys(result) == frozenset(CLOSED_OUTPUTS)
    assert set(result) == {
        "compensation_percent",
        "surplus_percent",
        "goods_percent",
        "services_percent",
        "compensation_percent_unrounded",
        "surplus_percent_unrounded",
    }


def test_withdrawn_production_refused():
    """Refusal is by name, not by the numerical derivation supplied."""
    values, _, _ = inputs()
    with pytest.raises(
        WithdrawnProduction, match="withdrawn production derivation: production"
    ):
        sector_norms(**values, production=D(1))


def test_output_per_establishment_is_the_same_named_refusal():
    values, _, _ = inputs()
    with pytest.raises(WithdrawnProduction, match="output_per_establishment"):
        sector_norms(**values, output_per_establishment=D(1))


def test_published_2022_components_and_card_ranges():
    """Card C4 printed 2022 shares and the ranges document 07 prints (MTH-25)."""
    food = {}
    rent = {}
    compensation = {}
    surplus = {}
    beverages = {}
    for year in ("2018", "2019", "2020", "2021", "2022"):
        values, row, _ = inputs(year)
        result = sector_norms(
            **values,
            components=(
                component("food", "goods", row["food"], row["goods_total"], year),
                component(
                    "beverages", "goods", row["beverages"], row["goods_total"], year
                ),
                component(
                    "building_rent",
                    "services",
                    row["rent"],
                    row["services_total"],
                    year,
                ),
            ),
        )
        food[year] = fact_value(result["food"])
        beverages[year] = fact_value(result["beverages"])
        rent[year] = fact_value(result["building_rent"])
        compensation[year] = fact_value(result["compensation_percent"])
        surplus[year] = fact_value(result["surplus_percent"])
    assert food["2022"] == D("29.3")
    assert beverages["2022"] == D("5.6")
    assert rent["2022"] == D("11.6")
    assert compensation["2022"] == D("20.6")
    assert surplus["2022"] == D("19.7")
    assert share_range(tuple(food.values())) == (D("28.0"), D("29.3"))
    assert share_range(tuple(rent.values())) == (D("11.6"), D("15.1"))
    assert share_range(tuple(compensation.values())) == (D("20.6"), D("25.2"))
    assert share_range(tuple(surplus.values())) == (D("6.9"), D("19.7"))


def test_invented_component_and_mismatched_group():
    values, _, _ = inputs()
    made = component("invented_food", "goods", "25", "100")
    assert sector_norms(**values, components=(made,))["invented_food"].value == D(
        "10.2"
    )
    with pytest.raises(ValueError, match="group"):
        sector_norms(**values, components=(component("bad", "other", "1", "2"),))


@pytest.mark.parametrize(
    "field,value",
    [
        ("employees", "0"),
        ("productivity", "0"),
        ("compensation_thousand", "NaN"),
        ("goods_percent", "101"),
    ],
)
def test_invalid_norm_input(field, value):
    values, _, common = inputs()
    unit = values[field].unit
    with pytest.raises(ValueError):
        values[field] = measure(value, unit=unit, **common)
        sector_norms(**values)


def test_component_bounds_negative_full_share_and_key_collision():
    values, _, _ = inputs()
    with pytest.raises(ValueError, match="outside"):
        sector_norms(**values, components=(component("invented", "goods", "3", "2"),))
    negative = inputs()[0]
    negative["surplus_thousand"] = measure(
        -1, unit="qar_thousand", period="2022", geography="national", kind="national"
    )
    with pytest.raises(ValueError, match="negative"):
        sector_norms(**negative)
    full = inputs()[0]
    full["goods_percent"] = measure(
        100, unit="percent", period="2022", geography="national", kind="national"
    )
    assert fact_value(sector_norms(**full)["goods_percent"]) == D(100)
    with pytest.raises(ValueError, match="key"):
        sector_norms(
            **values, components=(component("goods_percent", "goods", "1", "2"),)
        )
    with pytest.raises(ValueError, match="key"):
        sector_norms(
            **values, components=(component("production_value", "goods", "1", "2"),)
        )


def test_component_total_group_must_match():
    values, _, _ = inputs()
    bad = component("invented", "goods", "1", "2")
    bad = Component(bad.key, bad.group, bad.value, bad.group_total, "services")
    with pytest.raises(ValueError, match="group"):
        sector_norms(**values, components=(bad,))


def test_service_component_and_reserved_output_names():
    values, _, _ = inputs()
    assert fact_value(
        sector_norms(
            **values, components=(component("invented_rent", "services", "25", "100"),)
        )["invented_rent"]
    ) == D("4.1")
    for name in ("production", "output_per_establishment", "output_value"):
        with pytest.raises(ValueError, match="key"):
            sector_norms(**values, components=(component(name, "goods", "1", "2"),))
