"""Card C41 quarterly aggregates over kept bulletin deals. Fixtures are invented."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.additions.property_venues import IDENTIFIER_FIELDS
from eii_custodian.publicdata.property.bulletin import (
    BulletinDeals,
    parse_bulletin,
    quarter_of,
    refuse_release_identifiers,
)
from eii_custodian.publicdata.property.quarter import (
    SQ_M_PER_SQ_FT,
    forecast_window,
    quarter_aggregates,
    square_feet,
)
from eii_custodian.publicdata.property.use_map import load_use_map

FIXTURES = (
    repository_root(Path(__file__)) / "custodian" / "tests" / "fixtures" / "property"
)
USE_MAP = FIXTURES / "use_map.csv"


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
        "name,district_keys\nSYN North,syn_north\nSYN North AR,syn_north\n",
        encoding="utf-8",
    )
    return {"frame": folder}


def _map() -> object:
    return load_use_map(USE_MAP)


def _parse(
    rows: list[dict[str, object]], folder: Path, use_map: object = None
) -> BulletinDeals:
    return parse_bulletin(
        rows, use_map if use_map is not None else _map(), _frame(folder)
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


def test_worked_example_reproduces_the_card_fixture(tmp_path: Path) -> None:
    """MTH-116: median 550, deal count 2 and deal value 2,500,000."""
    parsed = _parse(_rows("worked_example.json"), tmp_path)
    assert len(parsed.deals) == 2
    assert _blocked(parsed, "repeated_deal_price_disagreement") == 0
    rows = quarter_aggregates(parsed.deals)
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
    )
    row = _all_row(quarter_aggregates(deals.deals))
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
    row = _all_row(quarter_aggregates(_parse(rows, tmp_path).deals))
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
    row = _all_row(quarter_aggregates([per_m2, per_unit]))
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
    rows = quarter_aggregates(parsed.deals)
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
    rows = quarter_aggregates(parsed.deals)
    assert _all_row(rows)["deal_count"] == 1
    assert _all_row(rows)["deal_value"] == Decimal("800.00")


def test_unmapped_label_and_unmapped_usage_fail_the_build(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as label:
        _parse(_rows("planted_unmapped_label.json"), tmp_path / "label")
    assert label.value.name == "unmapped_label"
    with pytest.raises(AdditionError) as usage:
        _parse([_sale(property_usage="SYN-USE-UNMAPPED")], tmp_path / "usage")
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
    parsed = _parse([_resi(), _sale()], tmp_path)
    rows = quarter_aggregates(parsed.deals)
    text = repr(rows)
    for name in IDENTIFIER_FIELDS:
        assert name not in text
    for identifier in parsed.identifiers:
        assert identifier not in text
    for row in rows:
        assert not set(row) & set(IDENTIFIER_FIELDS)


def test_a_planted_identifier_column_or_value_in_a_release_row_fails(
    tmp_path: Path,
) -> None:
    parsed = _parse([_resi()], tmp_path)
    rows = quarter_aggregates(parsed.deals)
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


def test_an_unmapped_municipality_fails(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as municipality:
        _parse([_resi(municipality_name="SYN Unmapped Muni")], tmp_path)
    assert municipality.value.name == "unmapped_municipality"


def test_an_ambiguous_district_is_blocked_not_kept(tmp_path: Path) -> None:
    """A district name read under two municipalities enters no aggregate."""
    rows = [
        _resi(),
        _resi(
            encrypted_transaction_number="SYN-TX-2",
            municipality_name="SYN Inland",
            sm_lbldy="SYN Inland AR",
        ),
    ]
    parsed = _parse(rows, tmp_path)
    assert parsed.deals == ()
    assert _blocked(parsed, "ambiguous_district") == 2


def test_a_usage_field_that_is_not_text_fails(tmp_path: Path) -> None:
    with pytest.raises(AdditionError) as caught:
        _parse([_sale(property_usage=9)], tmp_path)
    assert caught.value.name == "measure_unparsed"


def test_nonpositive_measures_are_blocked_not_kept(tmp_path: Path) -> None:
    parsed = _parse(
        [
            _resi(price_per_square_meter=0),
            _resi(encrypted_transaction_number="SYN-TX-2", property_value=0),
            _sale(area_square_feet=0, area_square_meters=None),
        ],
        tmp_path,
    )
    assert not parsed.deals
    assert _blocked(parsed, "nonpositive_price") == 2
    assert _blocked(parsed, "nonpositive_area") == 1
    assert quarter_aggregates(parsed.deals) == ()


def test_a_unit_row_refuses_mixed_price_bases(tmp_path: Path) -> None:
    parsed = _parse(_rows("planted_mixed_basis.json"), tmp_path)
    assert len(parsed.deals) == 2
    with pytest.raises(AdditionError) as caught:
        quarter_aggregates(parsed.deals)
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
    all_row = _all_row(quarter_aggregates(parsed.deals))
    assert all_row["deal_count"] == 2
    assert all_row["deal_value"] == Decimal("2400.00")
    unit = _unit_row(quarter_aggregates(parsed.deals))
    assert unit["median_price"] == Decimal("15.00")
    assert unit["price_basis"] == "per_m2"
    assert unit["deal_count"] == 2
    assert unit["deal_value"] == Decimal("2400.00")
    assert unit["median_price_per_ft2"] is None
    assert unit["land_deal_count"] is None
    assert unit["land_median_price_per_ft2"] is None


def test_a_shared_row_carries_no_source_id(tmp_path: Path) -> None:
    """DR2: the two bulletins' deals share one row keyed as section 7.3 states."""
    parsed = _parse(
        [
            _resi(),
            _sale(nw_l_qr="SYN-UNIT-1", area_square_feet=100, property_value=200),
        ],
        tmp_path,
    )
    rows = quarter_aggregates(parsed.deals)
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
        parse_bulletin("not-a-list", _map(), _frame(tmp_path))
    assert rows.value.name == "bulletin_rows"
    with pytest.raises(AdditionError) as row:
        parse_bulletin(["not-a-map"], _map(), _frame(tmp_path / "row"))
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
    assert quarter_aggregates(parsed.deals) == ()
    assert quarter_aggregates(()) == ()


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
        for row in quarter_aggregates(parsed.deals)
        if row["unit_type"] == "all"
    }
    assert periods == {"2025-Q3", "2025-Q4"}
    assert forecast_window(periods) == ("2025-Q3", "2025-Q4", 2)
