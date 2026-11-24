"""Card C14 annual sale aggregates. Every fixture and generated deal is invented."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_property_quarter import (
    USE_MAP,
    _blocked,
    _frame,
    _map,
    _parse,
    _resi,
    _rows,
)
from custodian.tests.test_property_sales_export import _export
from custodian.tests.test_property_sales_export import _parse as _parse_export
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_reports import draw_tables
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.property.bulletin import Deal, sales_export_rows
from eii_custodian.publicdata.property.price_as_of import as_of_from_receipt
from eii_custodian.publicdata.property.sale import sale_aggregates
from eii_custodian.publicdata.review.cache_fixture import write_cached

C14_ROW = {
    "district_key": "syn_north",
    "municipality_code": "syn_coast",
    "period": "2025",
    "property_type": "residential",
    "deal_count": 2,
    "median_price_per_m2": Decimal("15.00"),
}


def _producer(tmp_path: Path, row, raw: list[dict[str, object]], *, additional=()):
    _frame(tmp_path)
    shutil.copy(USE_MAP, tmp_path / "property_use_map.csv")
    digest = write_cached(tmp_path, row, json.dumps(raw).encode())
    entries = [row]
    selected = {row.key: digest.stem}
    for extra_row, extra_raw, retrieved_utc in additional:
        entries.append(extra_row)
        extra_digest = write_cached(
            tmp_path,
            extra_row,
            json.dumps(extra_raw).encode(),
            retrieved_utc=retrieved_utc,
        )
        selected[extra_row.key] = extra_digest.stem
    build = context(tmp_path, tuple(entries))
    build.review = tmp_path
    build.selected = selected
    build.frame_result = FrameResult(
        {
            "grid_cell": [],
            "district": [
                {"district_key": "syn_north", "municipality_code": "syn_coast"},
                {"district_key": "syn_inland", "municipality_code": "syn_inland"},
                {"district_key": "syn_one", "municipality_code": "syn_coast"},
            ],
        },
        [],
        {},
    )
    return build


def test_c14_worked_example_is_the_even_count_median(tmp_path: Path) -> None:
    parsed = _parse_export(_rows("c14_worked_example.json"), tmp_path)
    assert parsed.blocked == ()
    assert sale_aggregates(parsed.deals) == (C14_ROW,)


def test_december_january_boundary_stays_in_separate_years(tmp_path: Path) -> None:
    parsed = _parse_export(
        [
            _export(registration_date="2024-12-31"),
            _export(
                registration_date="2025-01-01",
                encrypted_transaction_number="SYN-TX-JANUARY",
                encrypted_parcel_number="SYN-PX-JANUARY",
            ),
        ],
        tmp_path,
    )
    assert parsed.blocked == ()
    rows = sale_aggregates(parsed.deals)
    assert [
        (row["period"], row["deal_count"], row["median_price_per_m2"]) for row in rows
    ] == [
        ("2024", 1, Decimal("1000.00")),
        ("2025", 1, Decimal("1000.00")),
    ]


def test_layer_property_prices_over_producer_output(tmp_path: Path) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    build = _producer(tmp_path, row, _rows("c14_worked_example.json"))
    build.gis_property_singles()
    expected_row = dict(C14_ROW, as_of=as_of_from_receipt(build.receipts[row.key]))
    assert build.tables["pub_property_sale"] == [expected_row]
    assert build.table_sources["pub_property_sale"] == {row.key}
    assert build.source_tables[row.key] == ["pub_property_sale", "pub_property_quarter"]
    assert "SYN-TX-C14-A" not in repr(build.tables["pub_property_sale"])
    assert "SYN-PX-C14-A" not in repr(build.tables["pub_property_sale"])

    figures = draw_tables(build)["pub_property_sale"]()
    by_field = {figure.figure_id.rsplit(":", 1)[-1]: figure for figure in figures}
    assert set(by_field) == {"deal_count", "median_price_per_m2"}
    assert by_field["median_price_per_m2"].value == "15.00"
    assert by_field["median_price_per_m2"].kind == "money"
    assert by_field["deal_count"].value == "2"
    assert by_field["deal_count"].kind == "count"
    receipt = build.receipts[row.key]
    for figure in figures:
        assert figure.source_id == str(receipt["source_id"])
        assert figure.url == str(receipt["fetch_url"])
        assert f"snapshot={receipt['sha256']}" in figure.filter
        assert f'"sha256": "{receipt["sha256"]}"' in figure.filter


def test_even_count_with_tied_central_prices_through_stored_reader(
    tmp_path: Path,
) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    raw = [
        _export(
            encrypted_transaction_number=f"SYN-TX-TIE-{index}",
            encrypted_parcel_number=f"SYN-PX-TIE-{index}",
            property_value=value,
            area_square_meters=area,
        )
        for index, (value, area) in enumerate(
            ((50, 10), (100, 10), (200, 20), (400, 20))
        )
    ]
    build = _producer(tmp_path, row, raw)
    build.gis_property_singles()
    expected_row = dict(
        C14_ROW,
        deal_count=4,
        median_price_per_m2=Decimal("10.00"),
        as_of=as_of_from_receipt(build.receipts[row.key]),
    )
    assert build.tables["pub_property_sale"] == [expected_row]
    figures = draw_tables(build)["pub_property_sale"]()
    by_field = {figure.figure_id.rsplit(":", 1)[-1]: figure for figure in figures}
    assert by_field["median_price_per_m2"].value == "10.00"
    assert by_field["median_price_per_m2"].kind == "money"
    assert by_field["deal_count"].value == "4"
    assert by_field["deal_count"].kind == "count"


def test_stored_reader_refuses_an_unreviewed_sale_numeric_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import eii_custodian.publicdata.property.sale as sale_module

    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    original = sale_module.sale_aggregates

    def add_unknown_numeric(deals, **kwargs):
        rows = original(deals, **kwargs)
        return (dict(rows[0], unreviewed_numeric=1), *rows[1:])

    monkeypatch.setattr(sale_module, "sale_aggregates", add_unknown_numeric)
    build = _producer(tmp_path, row, _rows("c14_worked_example.json"))
    build.gis_property_singles()
    with pytest.raises(AssemblyError, match=r"^assembly_draw_field_unknown$"):
        draw_tables(build)["pub_property_sale"]()


@pytest.mark.parametrize("foreign", [False, True], ids=["missing", "foreign"])
def test_producer_refuses_invalid_sale_as_of(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: bool
) -> None:
    import eii_custodian.publicdata.property.sale as sale_module

    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    original = sale_module.sale_aggregates
    foreign_as_of = "2026-11-19"

    def break_as_of(deals, **kwargs):
        rows = [dict(item) for item in original(deals, **kwargs)]
        if foreign:
            rows[0]["as_of"] = foreign_as_of
        else:
            rows[0].pop("as_of", None)
        return tuple(rows)

    additional = ()
    if foreign:
        resi_row = replace(
            next(e for e in load_registry() if e.source_id == "prop_resi_units"),
            key="prop_resi_units",
        )
        additional = (
            (
                resi_row,
                [_resi(registration_date="2025-07-02")],
                foreign_as_of + "T00:00:00Z",
            ),
        )
    raw = _rows("c14_worked_example.json")
    if foreign:
        control = _producer(tmp_path / "control", row, raw, additional=additional)
        control.gis_property_singles()
        assert "pub_property_sale" in control.tables
    monkeypatch.setattr(sale_module, "sale_aggregates", break_as_of)
    build = _producer(tmp_path / "plant", row, raw, additional=additional)
    with pytest.raises(AdditionError, match=r"^price_as_of_missing$"):
        build.gis_property_singles()
    assert "pub_property_sale" not in build.tables
    assert "pub_property_sale" not in build.table_sources


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


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("property_value", 0, "nonpositive_price"),
        ("area_square_meters", -1, "nonpositive_area"),
    ],
    ids=["zero_price", "negative_area"],
)
def test_invalid_deal_among_valid_deals_is_excluded_with_exact_count(
    tmp_path: Path, field: str, value: int, reason: str
) -> None:
    parsed = _parse_export(
        [
            _export(),
            _export(
                encrypted_transaction_number="SYN-TX-INVALID",
                encrypted_parcel_number="SYN-PX-INVALID",
                **{field: value},
            ),
        ],
        tmp_path,
    )
    assert len(parsed.deals) == 1
    assert _blocked(parsed, reason) == 1
    (row,) = sale_aggregates(parsed.deals)
    assert row["deal_count"] == 1
    assert row["median_price_per_m2"] == Decimal("1000.00")


def test_producer_checks_every_crosswalk_key_against_the_frame(tmp_path: Path) -> None:
    from eii_custodian.publicdata.frame.checks import FrameError

    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    build = _producer(tmp_path, row, _rows("c14_worked_example.json"))
    path = tmp_path / "district_crosswalk.csv"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "SYN Unused,syn_coast,ZZZ999999999,two_language_exact\n",
        encoding="utf-8",
    )
    with pytest.raises(FrameError, match=r"^district_crosswalk: outside_frame$"):
        build.gis_property_singles()


def test_unmatched_crosswalk_row_is_excluded_with_exact_count(tmp_path: Path) -> None:
    parsed = _parse_export(
        [_export(district_name="SYN Unmapped", sm_lmntq="SYN Unmapped AR")], tmp_path
    )
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

    def leak(deals, **kwargs):
        rows = original(deals, **kwargs)
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
