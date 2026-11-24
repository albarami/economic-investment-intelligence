"""C4 component mapping at its real entry point, not the downstream scenario."""

from decimal import Decimal

import pytest
from product.tests.sector_fixture import norm_rows, release_store, with_lineage

from eii_core import calc
from eii_product.tools.sector_facts import sector_facts


def run_norms(data):
    with release_store(with_lineage(data)) as store:
        return sector_facts(
            store,
            dict(
                activity="SYN-restaurant", topic="unit_economics", geography="national"
            ),
        )


def test_unit_economics_reproduces_all_card_c4_component_norms():
    result = run_norms(norm_rows())
    values = {(f.period, f.label_en): f.value for f in result["facts"]}
    assert {
        label: value for (year, label), value in values.items() if year == "2022"
    } == {
        "Food share": Decimal("29.3"),
        "Beverages share": Decimal("5.6"),
        "Building rent share": Decimal("11.6"),
        "Compensation share": Decimal("20.6"),
        "Surplus share": Decimal("19.7"),
        "Goods share": Decimal("40.6"),
        "Services share": Decimal("16.5"),
    }
    assert {year for year, _ in values} == {"2018", "2019", "2020", "2021", "2022"}
    for label, bounds in (
        ("Food share", ("28.0", "29.3")),
        ("Building rent share", ("11.6", "15.1")),
        ("Compensation share", ("20.6", "25.2")),
        ("Surplus share", ("6.9", "19.7")),
    ):
        selected = [value for (_, key), value in values.items() if key == label]
        assert (min(selected), max(selected)) == tuple(map(Decimal, bounds))


def test_component_inputs_use_own_group_year_and_fixed_read_totals(monkeypatch):
    seen = []
    original = calc.sector_norms

    def spy(**kwargs):
        components = kwargs["components"]
        assert {c.key for c in components} == {"food", "beverages", "building_rent"}
        for c in components:
            assert c.group == c.total_group
            assert c.value.period == c.group_total.period == kwargs["employees"].period
            assert c.group_total.unit == c.value.unit == "qar_thousand"
        seen.append(components)
        return original(**kwargs)

    monkeypatch.setattr(calc, "sector_norms", spy)
    run_norms(norm_rows())
    assert len(seen) == 5
    latest = {c.key: c for c in seen[-1]}
    assert latest["food"].group_total.value == Decimal(2573362)
    assert latest["building_rent"].group_total.value == Decimal(1045667)


@pytest.mark.parametrize("plant", ["unit", "missing_total", "missing_component"])
def test_invalid_component_does_not_acquire_a_share(plant):
    data = norm_rows()
    rows = data["pub_sector_accounts"]
    if plant == "unit":
        next(
            r
            for r in rows
            if r["period"] == "2022"
            and r["indicator"] == "intermediate_goods:Food%20Stuff"
        )["unit"] = "QAR"
    elif plant == "missing_total":
        for row in rows:
            if (
                row["indicator"].startswith("intermediate_goods:")
                and row["period"] == "2022"
            ):
                row["value"] = None
    else:
        data["pub_sector_accounts"] = [
            r
            for r in rows
            if not (
                r["period"] == "2022"
                and r["indicator"] == "intermediate_goods:Food%20Stuff"
            )
        ]
    result = run_norms(data)
    assert not any(
        f.period == "2022" and f.label_en == "Food share" for f in result["facts"]
    )
    assert any(
        f.period == "2021" and f.label_en == "Food share" for f in result["facts"]
    )
