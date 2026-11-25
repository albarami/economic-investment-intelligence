"""Card C41 quarterly aggregates over kept bulletin deals. Fixtures are invented."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.additions.property_venues import IDENTIFIER_FIELDS
from eii_custodian.publicdata.fetch.report import coverage_count_line
from eii_custodian.publicdata.property import use_map as use_map_module
from eii_custodian.publicdata.property.bulletin import (
    BulletinDeals,
    parse_bulletin,
    quarter_of,
    refuse_release_identifiers,
)
from eii_custodian.publicdata.property.quarter import (
    SQ_M_PER_SQ_FT,
    expected_as_of,
    forecast_window,
    held_series_window,
    quarter_aggregates,
    square_feet,
)
from eii_custodian.publicdata.property.sale import sale_aggregates
from eii_custodian.publicdata.property.use_map import UseMapping, load_use_map

FIXTURES = (
    repository_root(Path(__file__)) / "custodian" / "tests" / "fixtures" / "property"
)
USE_MAP = FIXTURES / "use_map.csv"
_QUARTER_AS_OF = "2026-11-17"


def _as_of_map(*source_ids: str) -> dict[str, str]:
    return dict.fromkeys(source_ids, _QUARTER_AS_OF)


def _rows(name: str) -> list[dict[str, object]]:
    loaded = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, list)
    return loaded


def _frame(folder: Path) -> dict[str, object]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "SYN Coast,syn_coast\n"
        "SYN Coast AR,syn_coast\n"
        "SYN Inland,syn_inland\n"
        "SYN Inland AR,syn_inland\n",
        encoding="utf-8",
    )
    (folder / "district_crosswalk.csv").write_text(
        "name,municipality_code,district_keys,basis\n"
        "SYN North,syn_coast,syn_north,two_language_exact\n"
        "SYN North AR,syn_coast,syn_north,two_language_exact\n"
        "SYN North,syn_inland,syn_inland,two_language_exact\n"
        "SYN North AR,syn_inland,syn_inland,two_language_exact\n"
        "SYN One,syn_coast,syn_one,one_language_exact\n",
        encoding="utf-8",
    )
    return {"frame": folder}


def _map() -> object:
    return load_use_map(USE_MAP)


def _parse(
    rows: list[dict[str, object]],
    folder: Path,
    use_map: object = None,
    source_id: str = "prop_resi_units",
) -> BulletinDeals:
    return parse_bulletin(
        rows,
        source_id,
        use_map if use_map is not None else _map(),
        _frame(folder),
    )


def _resi(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "registration_date": "2025-10-02",
        "encrypted_transaction_number": "SYN-TX-1",
        "encrypted_parcel_number": "SYN-PX-1",
        "sm_lbldy": "SYN Coast AR",
        "municipality_name": "SYN Coast",
        "sm_lmntq": "SYN North AR",
        "district_name": "SYN North",
        "nw_l_qr": "SYN-UNIT",
        "property_type": "SYN-EN-UNIT",
        "area_square_meters": 80,
        "price_per_square_meter": 10,
        "property_value": 800,
    }
    row.update(overrides)
    return row


def _sale(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "registration_date": "2025-10-02",
        "encrypted_transaction_number": "SYN-TX-9",
        "encrypted_parcel_number": "SYN-PX-9",
        "sm_lbldy": "SYN Coast AR",
        "municipality_name": "SYN Coast",
        "sm_lmntq": "SYN North AR",
        "district_name": "SYN North",
        "nw_l_qr": "SYN-LAND-1",
        "property_type": "SYN-EN-LAND",
        "property_usage": "SYN-USE-RESI",
        "area_square_meters": None,
        "area_square_feet": 2000,
        "property_value": 1000000,
    }
    row.update(overrides)
    return row


def _all_row(rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    return next(row for row in rows if row["unit_type"] == "all")


def _unit_row(rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    return next(row for row in rows if row["unit_type"] == "residential_unit")


def _blocked(parsed: BulletinDeals, reason: str) -> int:
    return sum(item.count for item in parsed.blocked if item.reason == reason)


@pytest.mark.parametrize("absent", [False, True])
def test_absent_usage_matches_the_closed_no_usage_cell(
    tmp_path: Path, absent: bool
) -> None:
    from custodian.tests.test_property_use_map import _write

    mappings = load_use_map(
        _write(
            tmp_path / "no-usage.csv",
            [
                f"prop_sales,SYN-LAND-1,{use_map_module.NO_USAGE},unspecified,land,SYN reviewer,2026-11-24"
            ],
        )
    )
    row = _sale(property_usage=None)
    if absent:
        del row["property_usage"]
    parsed = _parse([row], tmp_path / "frame", mappings, "prop_sales")
    assert len(parsed.deals) == 1
    assert parsed.deals[0].use_key == "unspecified"


@pytest.mark.parametrize("consumer", ["deal", "quarter", "as_of", "sale"])
def test_built_sale_enters_use_only(tmp_path: Path, consumer: str) -> None:
    mapping = UseMapping(
        "prop_sales",
        "SYN-BUILT",
        "*",
        "residential",
        "built",
        "SYN reviewer",
        "2026-11-24",
    )
    parsed = _parse([_sale(nw_l_qr="SYN-BUILT")], tmp_path, (mapping,), "prop_sales")
    if consumer == "deal":
        assert len(parsed.deals) == 1
        assert not parsed.deals[0].land
        assert parsed.deals[0].unit_type is None
    elif consumer == "quarter":
        rows = quarter_aggregates(
            parsed.deals, as_of_by_source=_as_of_map("prop_sales")
        )
        assert len(rows) == 1
        row = _all_row(rows)
        assert row["deal_count"] == 1
        assert row["median_price_per_ft2"] == Decimal("500.00")
        assert row["land_deal_count"] == 0
        assert row["land_median_price_per_ft2"] is None
    elif consumer == "as_of":
        expected = expected_as_of(parsed.deals, _as_of_map("prop_sales"))
        assert expected == {
            ("syn_north", "syn_coast", "2025-Q4", "residential", "all"): _QUARTER_AS_OF
        }
    else:
        rows = sale_aggregates(parsed.deals)
        assert len(rows) == 1
        assert rows[0]["deal_count"] == 1
        assert rows[0]["property_type"] == "residential"


def test_worked_example_reproduces_the_card_fixture(tmp_path: Path) -> None:
    """MTH-116: median 550, deal count 2 and deal value 2,500,000."""
    parsed = _parse(_rows("worked_example.json"), tmp_path, source_id="prop_sales")
    assert len(parsed.deals) == 2
    assert _blocked(parsed, "repeated_deal_price_disagreement") == 0
    rows = quarter_aggregates(parsed.deals, as_of_by_source=_as_of_map("prop_sales"))
    row = _all_row(rows)
    assert row["median_price_per_ft2"] == Decimal("550.00")
    assert row["deal_count"] == 2
    assert row["deal_value"] == Decimal("2500000.00")
    assert row["land_deal_count"] == 2
    assert row["land_median_price_per_ft2"] == Decimal("550.00")
    assert row["district_key"] == "syn_north"
    assert row["municipality_code"] == "syn_coast"
    assert row["period"] == "2025-Q4"
    assert row["use_key"] == "residential"
    assert row["unit_type"] == "all"
    assert row["median_price"] is None
    assert row["price_basis"] is None
    assert all(item["unit_type"] == "all" for item in rows)


def test_square_feet_uses_the_exact_factor() -> None:
    """MTH-116: a floor area of 100 square metres is 1,076.39 square feet."""
    assert SQ_M_PER_SQ_FT == Decimal("0.09290304")
    assert square_feet(Decimal(100)) == Decimal("1076.39")


def test_a_deal_in_square_metres_converts_by_the_exact_factor(
    tmp_path: Path,
) -> None:
    deals = _parse(
        [_sale(area_square_feet=None, area_square_meters=100, property_value=100000)],
        tmp_path,
        source_id="prop_sales",
    )
    row = _all_row(
        quarter_aggregates(deals.deals, as_of_by_source=_as_of_map("prop_sales"))
    )
    assert row["median_price_per_ft2"] == Decimal("92.90")


def test_even_count_median_is_the_mean_of_the_two_central_values(
    tmp_path: Path,
) -> None:
    rows = [
        _sale(
            encrypted_transaction_number=f"SYN-TX-{index}",
            area_square_feet=100,
            property_value=price * 100,
        )
        for index, price in enumerate((100, 200, 300, 400))
    ]
    row = _all_row(
        quarter_aggregates(
            _parse(rows, tmp_path, source_id="prop_sales").deals,
            as_of_by_source=_as_of_map("prop_sales"),
        )
    )
    assert row["median_price_per_ft2"] == Decimal("250.00")
    assert row["deal_count"] == 4


def test_only_per_m2_resi_deals_enter_the_ft2_median(tmp_path: Path) -> None:
    """A per-unit deal counts and pays but gives no square-foot price."""
    from dataclasses import replace

    parsed = _parse([_resi()], tmp_path)
    per_m2 = parsed.deals[0]
    per_unit = replace(
        per_m2,
        unit_type=None,
        land=True,
        basis="per_unit",
        price=Decimal(900),
        value=Decimal(900),
        area_m2=None,
        area_ft2=None,
        transaction="SYN-TX-LAND",
    )
    row = _all_row(
        quarter_aggregates(
            [per_m2, per_unit], as_of_by_source=_as_of_map("prop_resi_units")
        )
    )
    assert row["deal_count"] == 2
    assert row["deal_value"] == Decimal("1700.00")
    assert row["median_price_per_ft2"] == Decimal("0.93")
    assert row["land_deal_count"] == 1
    assert row["land_median_price_per_ft2"] is None


def test_agreeing_repeats_are_one_deal_and_value_is_not_doubled(
    tmp_path: Path,
) -> None:
    """A repeated transaction number counts once; a count of two would double it."""
    parsed = _parse(
        [
            _resi(),
            _resi(encrypted_parcel_number="SYN-PX-2"),
        ],
        tmp_path,
    )
    assert len(parsed.deals) == 1
    rows = quarter_aggregates(
        parsed.deals, as_of_by_source=_as_of_map("prop_resi_units")
    )
    assert _all_row(rows)["deal_count"] == 1
    assert _all_row(rows)["deal_value"] == Decimal("800.00")
    assert _unit_row(rows)["deal_count"] == 1


def test_disagreeing_repeats_block_the_deal_with_a_named_reason(
    tmp_path: Path,
) -> None:
    parsed = _parse(
        [
            _resi(price_per_square_meter=10, property_value=800),
            _resi(
                encrypted_parcel_number="SYN-PX-2",
                price_per_square_meter=20,
                property_value=1600,
            ),
            _resi(encrypted_transaction_number="SYN-TX-2"),
        ],
        tmp_path,
    )
    assert len(parsed.deals) == 1
    assert _blocked(parsed, "repeated_deal_price_disagreement") == 1
    rows = quarter_aggregates(
        parsed.deals, as_of_by_source=_as_of_map("prop_resi_units")
    )
    assert _all_row(rows)["deal_count"] == 1
    assert _all_row(rows)["deal_value"] == Decimal("800.00")


def test_unmapped_label_and_unmapped_usage_fail_the_build(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as label:
        _parse(_rows("planted_unmapped_label.json"), tmp_path / "label")
    assert label.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as usage:
        _parse(
            [_sale(property_usage="SYN-USE-UNMAPPED")],
            tmp_path / "usage",
            source_id="prop_sales",
        )
    assert usage.value.name == "unmapped_usage"


def test_the_arabic_label_wins_where_english_disagrees(tmp_path: Path) -> None:
    """The English property_type is never read: a contradicting value still parses."""
    parsed = _parse(_rows("planted_english_disagree.json"), tmp_path)
    assert len(parsed.deals) == 1
    deal = parsed.deals[0]
    assert deal.use_key == "residential"
    assert deal.unit_type == "residential_unit"
    assert deal.basis == "per_m2"


def test_identifiers_never_reach_the_release_rows(tmp_path: Path) -> None:
    """DR1: identifier fields build inside, none is present in a release row."""
    resi = _parse([_resi()], tmp_path)
    sale = _parse([_sale()], tmp_path, source_id="prop_sales")
    identifiers = resi.identifiers | sale.identifiers
    rows = quarter_aggregates(
        resi.deals + sale.deals,
        as_of_by_source=_as_of_map("prop_sales", "prop_resi_units"),
    )
    text = repr(rows)
    for name in IDENTIFIER_FIELDS:
        assert name not in text
    for identifier in identifiers:
        assert identifier not in text
    for row in rows:
        assert not set(row) & set(IDENTIFIER_FIELDS)


def test_a_planted_identifier_column_or_value_in_a_release_row_fails(
    tmp_path: Path,
) -> None:
    parsed = _parse([_resi()], tmp_path)
    rows = quarter_aggregates(
        parsed.deals, as_of_by_source=_as_of_map("prop_resi_units")
    )
    refuse_release_identifiers(rows, parsed.identifiers)
    planted_column = [dict(rows[0], encrypted_parcel_number="SYN-PX-Z")]
    with pytest.raises(AdditionError) as column:
        refuse_release_identifiers(planted_column, parsed.identifiers)
    assert column.value.name == "identifier_leak"
    leaked = next(iter(parsed.identifiers))
    planted_value = [dict(rows[0], use_key=leaked)]
    with pytest.raises(AdditionError) as value:
        refuse_release_identifiers(planted_value, parsed.identifiers)
    assert value.value.name == "identifier_leak"


def test_a_district_outside_the_reviewed_crosswalk_fails(tmp_path: Path) -> None:
    """An unmatched district is a blocked row with a named reason, never kept."""
    parsed = _parse(
        [_resi(district_name="SYN Unmapped", sm_lmntq="SYN Unmapped AR")],
        tmp_path,
    )
    assert parsed.deals == ()
    assert _blocked(parsed, "unmatched_district") == 1


def test_a_null_district_name_is_counted_unmatched_not_refused(tmp_path: Path) -> None:
    """R1: a live row with no district name is a blocked row, never a refusal."""
    parsed = _parse([_resi(district_name=None, sm_lmntq=None)], tmp_path)
    assert parsed.deals == ()
    assert _blocked(parsed, "unmatched_district") == 1


def test_a_non_text_district_name_still_refuses(tmp_path: Path) -> None:
    with pytest.raises(AdditionError, match="measure_unparsed"):
        _parse([_resi(district_name=7)], tmp_path)


def test_two_matching_languages_must_name_the_same_district(tmp_path: Path) -> None:
    _frame(tmp_path)
    path = tmp_path / "district_crosswalk.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "SYN North AR,syn_coast,syn_north,two_language_exact",
            "SYN North AR,syn_coast,syn_inland,two_language_exact",
        ),
        encoding="utf-8",
    )
    parsed = parse_bulletin([_resi()], "prop_resi_units", _map(), {"frame": tmp_path})
    assert parsed.deals == ()
    assert _blocked(parsed, "district_disagreement") == 1


def test_the_old_unqualified_crosswalk_header_is_refused(tmp_path: Path) -> None:
    from eii_custodian.publicdata.frame.checks import FrameError

    _frame(tmp_path)
    (tmp_path / "district_crosswalk.csv").write_text(
        "name,district_keys\nSYN North,syn_north\n", encoding="utf-8"
    )
    with pytest.raises(FrameError, match=r"^district_alias: CSV header$"):
        parse_bulletin([_resi()], "prop_resi_units", _map(), {"frame": tmp_path})


def test_an_unmapped_municipality_fails(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as municipality:
        _parse([_resi(municipality_name="SYN Unmapped Muni")], tmp_path)
    assert municipality.value.name == "unmapped_municipality"


def test_a_shared_district_name_uses_each_municipality(tmp_path: Path) -> None:
    """The same source name maps to each municipality's own frame key."""
    rows = [
        _resi(),
        _resi(
            encrypted_transaction_number="SYN-TX-2",
            municipality_name="SYN Inland",
            sm_lbldy="SYN Inland AR",
        ),
    ]
    parsed = _parse(rows, tmp_path)
    assert {deal.district_key for deal in parsed.deals} == {"syn_north", "syn_inland"}
    assert _blocked(parsed, "ambiguous_district") == 0


def test_one_exact_language_is_enough(tmp_path: Path) -> None:
    parsed = _parse([_resi(district_name="SYN One", sm_lmntq="SYN One AR")], tmp_path)
    assert [deal.district_key for deal in parsed.deals] == ["syn_one"]
    assert _blocked(parsed, "unmatched_district") == 0


def test_a_no_break_space_matches_the_reviewed_name(tmp_path: Path) -> None:
    parsed = _parse([_resi(district_name="SYN\u00a0North")], tmp_path)
    assert [deal.district_key for deal in parsed.deals] == ["syn_north"]


def test_a_usage_field_that_is_not_text_fails(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as caught:
        _parse([_sale(property_usage=9)], tmp_path, source_id="prop_sales")
    assert caught.value.name == "measure_unparsed"


def test_nonpositive_measures_are_blocked_not_kept(tmp_path: Path) -> None:
    resi = _parse(
        [
            _resi(price_per_square_meter=0),
            _resi(encrypted_transaction_number="SYN-TX-2", property_value=0),
        ],
        tmp_path,
    )
    sale = _parse(
        [_sale(area_square_feet=0, area_square_meters=None)],
        tmp_path,
        source_id="prop_sales",
    )
    assert not resi.deals and not sale.deals
    assert _blocked(resi, "nonpositive_price") == 2
    assert _blocked(sale, "nonpositive_area") == 1
    assert (
        quarter_aggregates(
            resi.deals + sale.deals,
            as_of_by_source=_as_of_map("prop_sales", "prop_resi_units"),
        )
        == ()
    )


def test_a_unit_row_refuses_mixed_price_bases(tmp_path: Path) -> None:
    parsed = _parse(_rows("planted_mixed_basis.json"), tmp_path)
    assert len(parsed.deals) == 2
    with pytest.raises(AdditionError) as caught:
        quarter_aggregates(parsed.deals, as_of_by_source=_as_of_map("prop_resi_units"))
    assert caught.value.name == "mixed_price_basis"


def test_unit_type_rows_carry_their_basis_median_and_count(
    tmp_path: Path,
) -> None:
    rows = [
        _resi(encrypted_transaction_number="SYN-TX-A", price_per_square_meter=10),
        _resi(
            encrypted_transaction_number="SYN-TX-B",
            price_per_square_meter=20,
            property_value=1600,
        ),
    ]
    parsed = _parse(rows, tmp_path)
    all_row = _all_row(
        quarter_aggregates(parsed.deals, as_of_by_source=_as_of_map("prop_resi_units"))
    )
    assert all_row["deal_count"] == 2
    assert all_row["deal_value"] == Decimal("2400.00")
    unit = _unit_row(
        quarter_aggregates(parsed.deals, as_of_by_source=_as_of_map("prop_resi_units"))
    )
    assert unit["median_price"] == Decimal("15.00")
    assert unit["price_basis"] == "per_m2"
    assert unit["deal_count"] == 2
    assert unit["deal_value"] == Decimal("2400.00")
    assert unit["median_price_per_ft2"] is None
    assert unit["land_deal_count"] is None
    assert unit["land_median_price_per_ft2"] is None


def test_a_shared_row_carries_no_source_id(tmp_path: Path) -> None:
    """DR2: the two bulletins' deals share one row keyed as section 7.3 states."""
    resi = _parse([_resi()], tmp_path)
    sale = _parse(
        [_sale(nw_l_qr="SYN-UNIT-1", area_square_feet=100, property_value=200)],
        tmp_path,
        source_id="prop_sales",
    )
    rows = quarter_aggregates(
        resi.deals + sale.deals,
        as_of_by_source=_as_of_map("prop_sales", "prop_resi_units"),
    )
    all_row = _all_row(rows)
    assert set(all_row) == {
        "district_key",
        "municipality_code",
        "period",
        "use_key",
        "unit_type",
        "deal_count",
        "deal_value",
        "median_price_per_ft2",
        "land_deal_count",
        "land_median_price_per_ft2",
        "median_price",
        "price_basis",
        "as_of",
    }
    assert all_row["deal_count"] == 2
    assert all_row["deal_value"] == Decimal("1000.00")
    assert "source_id" not in all_row
    unit = _unit_row(rows)
    assert unit["deal_count"] == 2
    assert unit["price_basis"] == "per_m2"


def test_period_is_the_calendar_quarter_of_the_registration_date() -> None:
    assert quarter_of("2025-08-24") == "2025-Q3"
    assert quarter_of("2025-12-31") == "2025-Q4"
    assert quarter_of("2020-07-05") == "2020-Q3"
    assert quarter_of("2020-01-01") == "2020-Q1"
    with pytest.raises(AdditionError):
        quarter_of("not-a-date")


def test_an_unknown_source_field_is_refused(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as caught:
        _parse([_resi(invented_field="x")], tmp_path)
    assert caught.value.name == "unknown_source_field"


def test_a_row_stream_that_is_not_a_list_of_maps_fails(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as rows:
        parse_bulletin("not-a-list", "prop_resi_units", _map(), _frame(tmp_path))
    assert rows.value.name == "bulletin_rows"
    with pytest.raises(AdditionError) as row:
        parse_bulletin(
            ["not-a-map"], "prop_resi_units", _map(), _frame(tmp_path / "row")
        )
    assert row.value.name == "bulletin_row"


def test_a_malformed_measure_or_label_is_refused(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as price:
        _parse([_resi(price_per_square_meter="ten")], tmp_path / "price")
    assert price.value.name == "measure_unparsed"
    with pytest.raises(AdditionError) as label:
        _parse([_resi(nw_l_qr=None)], tmp_path / "label")
    assert label.value.name == "measure_unparsed"


def test_no_kept_deal_writes_no_row(tmp_path: Path) -> None:
    parsed = _parse([_resi(price_per_square_meter=0, property_value=0)], tmp_path)
    assert (
        quarter_aggregates(parsed.deals, as_of_by_source=_as_of_map("prop_resi_units"))
        == ()
    )
    assert quarter_aggregates((), as_of_by_source=_as_of_map("prop_resi_units")) == ()


def test_forecast_window_counts_the_trailing_contiguous_quarters() -> None:
    """C30: a quarter with no kept deal has no value; quarters before it are not used."""
    assert forecast_window({"2020-Q3", "2020-Q4", "2021-Q1"}) == (
        "2020-Q3",
        "2021-Q1",
        3,
    )
    assert forecast_window({"2020-Q1", "2020-Q3", "2020-Q4", "2021-Q1"}) == (
        "2020-Q3",
        "2021-Q1",
        3,
    )
    assert forecast_window({"2025-Q4"}) == ("2025-Q4", "2025-Q4", 1)
    assert forecast_window(set()) is None
    assert forecast_window({"2020-Q4", "2021-Q1"}) == ("2020-Q4", "2021-Q1", 2)
    for malformed in ({"2020-10", "invented"}, {"2020-Q9"}, {"2020-Q0"}):
        with pytest.raises(AdditionError) as caught:
            forecast_window(malformed)
        assert caught.value.name == "quarter_period"


def test_a_second_quarter_is_a_second_row(tmp_path: Path) -> None:
    rows = [
        _resi(registration_date="2025-08-24"),
        _resi(
            registration_date="2025-11-20",
            encrypted_transaction_number="SYN-TX-2",
        ),
    ]
    parsed = _parse(rows, tmp_path)
    periods = {
        row["period"]
        for row in quarter_aggregates(
            parsed.deals, as_of_by_source=_as_of_map("prop_resi_units")
        )
        if row["unit_type"] == "all"
    }
    assert periods == {"2025-Q3", "2025-Q4"}
    assert forecast_window(periods) == ("2025-Q3", "2025-Q4", 2)


def test_blocked_deals_go_on_the_build_report(tmp_path: Path) -> None:
    """J28: an out-of-crosswalk district is a blocked row the report counts."""
    parsed = _parse(
        [_resi(district_name="SYN Unmapped", sm_lmntq="SYN Unmapped AR")],
        tmp_path,
    )
    assert parsed.deals == ()
    assert _blocked(parsed, "unmatched_district") == 1
    lines = [
        coverage_count_line("prop_resi_units", entry.reason, entry.count)
        for entry in parsed.blocked
    ]
    assert lines == ["COVERAGE prop_resi_units unmatched_district 1"]


def test_a_held_entry_whose_count_differs_from_the_kept_quarters_refuses() -> None:
    """J27: a held entry holds only the count the kept quarters give."""
    assert held_series_window("2025-Q3/2025-Q4", 2, {"2025-Q3", "2025-Q4"}) == (
        "2025-Q3",
        "2025-Q4",
        2,
    )
    with pytest.raises(AdditionError) as caught:
        held_series_window("2025-Q3/2025-Q4", 22, {"2025-Q3", "2025-Q4"})
    assert caught.value.name == "held_window_mismatch"
    with pytest.raises(AdditionError) as empty:
        held_series_window("2020-Q3/2025-Q4", 22, set())
    assert empty.value.name == "held_window_mismatch"
