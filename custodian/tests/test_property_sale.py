"""Card C14 annual sale aggregates. Every fixture and generated deal is invented."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_production_adapters import context
from custodian.tests.test_property_quarter import (
    USE_MAP,
    _blocked,
    _frame,
    _map,
    _parse,
    _resi,
)
from custodian.tests.test_property_sales_export import _export
from custodian.tests.test_property_sales_export import _parse as _parse_export
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.property.bulletin import Deal, sales_export_rows
from eii_custodian.publicdata.property.sale import sale_aggregates
from eii_custodian.publicdata.review.cache_fixture import write_cached

FIXTURES = (
    repository_root(Path(__file__)) / "custodian" / "tests" / "fixtures" / "property"
)
C14_ROW = {
    "district_key": "syn_north",
    "municipality_code": "syn_coast",
    "period": "2025",
    "property_type": "residential",
    "deal_count": 2,
    "median_price_per_m2": Decimal("15.00"),
}


def _rows(name: str) -> list[dict[str, object]]:
    loaded = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    return loaded


def _producer(tmp_path: Path, row, raw: list[dict[str, object]]):
    _frame(tmp_path)
    shutil.copy(USE_MAP, tmp_path / "property_use_map.csv")
    digest = write_cached(tmp_path, row, json.dumps(raw).encode())
    build = context(tmp_path, (row,))
    build.review = tmp_path
    build.selected = {row.key: digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    return build


def test_c14_worked_example_is_the_even_count_median(tmp_path: Path) -> None:
    parsed = _parse_export(_rows("c14_worked_example.json"), tmp_path)
    assert parsed.blocked == ()
    assert sale_aggregates(parsed.deals) == (C14_ROW,)


def test_layer_property_prices_over_producer_output(tmp_path: Path) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    build = _producer(tmp_path, row, _rows("c14_worked_example.json"))
    build.gis_property_singles()
    assert build.tables["pub_property_sale"] == [C14_ROW]
    assert build.table_sources["pub_property_sale"] == {row.key}
    assert build.source_tables[row.key] == ["pub_property_sale", "pub_property_quarter"]
    assert "SYN-TX-C14-A" not in repr(build.tables["pub_property_sale"])
    assert "SYN-PX-C14-A" not in repr(build.tables["pub_property_sale"])


def test_unmapped_arabic_label_keeps_use_map_refusal(tmp_path: Path) -> None:
    with pytest.raises(AdditionError, match=r"^unmapped_label$"):
        _parse_export([_export(nw_l_qr="SYN-UNMAPPED")], tmp_path)


@pytest.mark.parametrize("price", [0, -1], ids=["zero", "negative"])
def test_nonpositive_price_is_excluded_with_exact_count(
    tmp_path: Path, price: int
) -> None:
    parsed = _parse_export([_export(property_value=price)], tmp_path)
    assert parsed.deals == ()
    assert _blocked(parsed, "nonpositive_price") == 1
    assert sale_aggregates(parsed.deals) == ()


@pytest.mark.parametrize("area", [0, -1], ids=["zero", "negative"])
def test_nonpositive_area_is_excluded_with_exact_count(
    tmp_path: Path, area: int
) -> None:
    parsed = _parse_export([_export(area_square_meters=area)], tmp_path)
    assert parsed.deals == ()
    assert _blocked(parsed, "nonpositive_area") == 1
    assert sale_aggregates(parsed.deals) == ()


def test_unmatched_crosswalk_row_is_excluded_with_exact_count(tmp_path: Path) -> None:
    parsed = _parse_export([_export(district_name="SYN Unmapped")], tmp_path)
    assert parsed.deals == ()
    assert _blocked(parsed, "unmatched_district") == 1
    assert sale_aggregates(parsed.deals) == ()


def test_no_kept_rows_is_no_data_not_a_zero_valued_median() -> None:
    assert sale_aggregates(()) == ()


def test_zero_priced_cell_has_zero_count_and_null_median() -> None:
    deal = replace(
        _deal(0, 100, 10, 2025, "residential", "syn_north", "prop_sales"), price=None
    )
    (row,) = sale_aggregates([deal])
    assert row["deal_count"] == 0
    assert row["median_price_per_m2"] is None


def test_other_bulletin_never_enters_the_sale_table(tmp_path: Path) -> None:
    sale = _parse_export([_export()], tmp_path / "sale")
    resi = _parse([_resi()], tmp_path / "resi")
    rows = sale_aggregates(sale.deals + resi.deals)
    assert len(rows) == 1
    assert rows[0]["deal_count"] == 1
    assert rows[0]["median_price_per_m2"] == Decimal("1000.00")


def test_resi_only_producer_does_not_write_a_sale_table(tmp_path: Path) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_resi_units"),
        key="prop_resi_units",
    )
    build = _producer(tmp_path, row, [_resi()])
    build.gis_property_singles()
    assert "pub_property_quarter" in build.tables
    assert "pub_property_sale" not in build.tables


def test_producer_refuses_a_sale_identifier_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import eii_custodian.publicdata.property.sale as sale_module

    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    original = sale_module.sale_aggregates

    def leak(deals):
        rows = original(deals)
        return (dict(rows[0], property_type="SYN-TX-C14-A"), *rows[1:])

    monkeypatch.setattr(sale_module, "sale_aggregates", leak)
    build = _producer(tmp_path, row, _rows("c14_worked_example.json"))
    with pytest.raises(AdditionError, match=r"^identifier_leak$"):
        build.gis_property_singles()
    assert "pub_property_sale" not in build.tables


def _deal(
    index: int,
    value: int,
    area: int,
    year: int,
    use_key: str,
    district: str,
    source: str,
) -> Deal:
    municipality = "syn_coast" if district == "syn_north" else "syn_inland"
    return Deal(
        source_id=source,
        district_key=district,
        municipality_code=municipality,
        period=f"{year}-Q1",
        use_key=use_key,
        unit_type=None,
        land=True,
        basis="per_m2",
        price=Decimal(value) / Decimal(area),
        value=Decimal(value),
        area_m2=Decimal(area),
        area_ft2=None,
        transaction=f"SYN-TX-PBT-{index}",
    )


def _rounded_cents(value: Fraction) -> Decimal:
    scaled = value * 100
    whole, remainder = divmod(scaled.numerator, scaled.denominator)
    if remainder * 2 >= scaled.denominator:
        whole += 1
    return Decimal(whole) / Decimal(100)


def _oracle(
    cases: list[tuple[int, int, int, str, str, str]],
) -> list[dict[str, object]]:
    cells: dict[tuple[str, str, str, str], list[Fraction]] = {}
    for value, area, year, use_key, district, source in cases:
        if source != "prop_sales":
            continue
        municipality = "syn_coast" if district == "syn_north" else "syn_inland"
        cells.setdefault((district, municipality, str(year), use_key), []).append(
            Fraction(value, area)
        )
    rows = []
    for cell in sorted(cells):
        prices = sorted(cells[cell])
        count = len(prices)
        median = (
            prices[count // 2]
            if count % 2
            else (prices[count // 2 - 1] + prices[count // 2]) / 2
        )
        rows.append(
            {
                "district_key": cell[0],
                "municipality_code": cell[1],
                "period": cell[2],
                "property_type": cell[3],
                "deal_count": count,
                "median_price_per_m2": _rounded_cents(median),
            }
        )
    return rows


@example([])
@example([(200, 20, 2025, "residential", "syn_north", "prop_sales")])
@example(
    [
        (200, 20, 2025, "residential", "syn_north", "prop_sales"),
        (400, 20, 2025, "residential", "syn_north", "prop_sales"),
    ]
)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=100000),
            st.integers(min_value=1, max_value=1000),
            st.integers(min_value=2020, max_value=2025),
            st.sampled_from(["residential", "commercial"]),
            st.sampled_from(["syn_north", "syn_south"]),
            st.sampled_from(["prop_sales", "prop_resi_units"]),
        ),
        max_size=16,
    )
)
def test_exact_rational_oracle_over_valid_kept_deals(
    cases: list[tuple[int, int, int, str, str, str]],
) -> None:
    deals = tuple(_deal(index, *case) for index, case in enumerate(cases))
    assert list(sale_aggregates(deals)) == _oracle(cases)
    assert list(sale_aggregates(reversed(deals))) == _oracle(cases)


def test_group_keys_and_ties_stay_distinct_and_sorted() -> None:
    base = (100, 10, 2025, "residential", "syn_north", "prop_sales")
    cases = [
        base,
        base,
        (100, 10, 2024, "residential", "syn_north", "prop_sales"),
        (100, 10, 2025, "commercial", "syn_north", "prop_sales"),
        (100, 10, 2025, "residential", "syn_south", "prop_sales"),
    ]
    rows = sale_aggregates(_deal(index, *case) for index, case in enumerate(cases))
    assert [row["deal_count"] for row in rows] == [1, 1, 2, 1]
    assert [
        (row["district_key"], row["period"], row["property_type"]) for row in rows
    ] == [
        ("syn_north", "2024", "residential"),
        ("syn_north", "2025", "commercial"),
        ("syn_north", "2025", "residential"),
        ("syn_south", "2025", "residential"),
    ]
    assert all(row["median_price_per_m2"] == Decimal("10.00") for row in rows)


def test_bulletin_shape_adapter_is_used_by_the_producer(tmp_path: Path) -> None:
    raw = _rows("c14_worked_example.json")
    adapted = sales_export_rows(raw)
    assert all("usage" not in row for row in adapted)
    parsed = _parse(adapted, tmp_path, _map(), source_id="prop_sales")
    assert sale_aggregates(parsed.deals) == (C14_ROW,)
