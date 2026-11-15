"""Municipal permit, population, hotel and census parsers. Fixtures are invented."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from eii_custodian.publicdata.additions.common import AdditionError, require_lineage
from eii_custodian.publicdata.additions.municipal import PARSERS
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.frame.checks import FrameError

REVIEW = Path(__file__).resolve().parents[1] / "publicdata" / "review"
RECEIPT = {"retrieved_utc": "2026-03-04T05:06:07Z", "sha256": "ab" * 32}
METHOD_PERMITS = "eii_custodian.publicdata.additions.municipal.parse_permits@1"
METHOD_POPULATION = "eii_custodian.publicdata.additions.municipal.parse_population@1"
METHOD_HOTELS = "eii_custodian.publicdata.additions.municipal.parse_hotels@1"
METHOD_CENSUS = "eii_custodian.publicdata.additions.municipal.parse_census@1"
PERMIT_ANNUAL = (
    "total-building-permits-issued-by-municipality-and-type-of-building-type-of-permit"
)
PERMIT_CERT = "total-building-completion-certificates-issued-by-municipality-and-type-of-building-type-of"
PERMIT_MONTH = (
    "building-permits-issued-by-type-of-permit-and-month-al-daayen-municipality"
)
PERMIT_MONTH_FLOAT = (
    "building-permits-issued-by-type-of-permit-and-month-al-wakrah-municipality"
)
POPULATION = "population-by-municipality-and-age-groups"
HOTELS = "hotels-and-hotel-apartments-by-municipality"
CENSUS = (
    "distribution-of-business-establishments-and-employees-by-municipalities-"
    "according-to-census-2015"
)
FAMILIES = ("permits_muni", "pop_muni_age", "hotels_muni", "est_census_2015_muni")
LINEAGE = (
    "source_key",
    "period",
    "retrieved_utc",
    "method",
    "licence_id",
    "sha256",
)


def _map() -> dict[str, object]:
    loaded = yaml.safe_load(
        (REVIEW / "additions_municipal.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(loaded, dict)
    return loaded


def _entry(slug: str) -> Entry:
    return next(entry for entry in load_registry() if entry.slug == slug)


def _frame(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "SYN Coast,syn_coast\n"
        "SYN Coast AR,syn_coast\n"
        "SYN Inland,syn_inland\n"
        "SYN Inland AR,syn_inland\n",
        encoding="utf-8",
    )
    return folder


def _run(
    source: str,
    slug: str,
    rows: list[dict[str, object]],
    folder: Path,
    field_map: dict[str, object] | None = None,
    receipt: dict[str, object] | None = None,
) -> object:
    return PARSERS[source](
        _entry(slug),
        rows,
        RECEIPT if receipt is None else receipt,
        _map() if field_map is None else field_map,
        {"frame": _frame(folder), "review": REVIEW},
    )


def _coverage(parsed: object, reason: str) -> int:
    return sum(item.count for item in parsed.coverage if item.reason == reason)  # type: ignore[attr-defined]


def _lineage(source_key: str, period: str, method: str) -> dict[str, object]:
    return {
        "source_key": source_key,
        "publisher": "National Planning Council",
        "licence_id": "CC-BY-4.0",
        "licence_basis": "dataset",
        "retrieved_utc": "2026-03-04T05:06:07Z",
        "sha256": "ab" * 32,
        "period": period,
        "method": method,
    }


def _permit(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2022",
        "building_type": "RESIDENTIAL BUILDINGS",
        "nw_lmbn": "مباني سكنية",
        "permit_type": "VILLA",
        "nw_lrkhs": "فيلا",
        "municipality": "SYN Coast",
        "lbldy": "SYN Coast AR",
        "count": 4,
    }
    row.update(overrides)
    return row


def _certificate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2021",
        "building_type": "ADDITIONS",
        "nw_lmbn": "الاضافات",
        "certificate_type": "VILLA",
        "nw_lshhd": "فيلا",
        "municipality": "SYN Inland",
        "lbldy": "SYN Inland AR",
        "count": 2,
    }
    row.update(overrides)
    return row


def _month(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2018",
        "month": "JANUARY",
        "lshhr": "SYN-MONTH",
        "type_of_permit": "New Building",
        "nw_lrkhs": "مباني جديدة",
        "number": 6,
    }
    row.update(overrides)
    return row


def _named_month(field_map: dict[str, object], slug: str) -> dict[str, object]:
    copied = json.loads(json.dumps(field_map))
    copied["geography"][f"permits_muni/{slug}"]["published_names"] = [
        "SYN Coast",
        "SYN Coast AR",
    ]
    return copied


def test_review_declares_each_slug_on_its_municipality() -> None:
    """Each slug's geography is the municipality, with no code written in the review."""
    loaded = _map()
    geography = loaded["geography"]
    assert isinstance(geography, dict)
    keys = [entry.key for entry in load_registry() if entry.source_id in FAMILIES]
    assert len(keys) == 13
    for key in keys:
        item = geography[key]
        assert item["grain"] == "municipality"
        assert "municipality_code" not in item
    text = (REVIEW / "additions_municipal.yaml").read_text(encoding="utf-8")
    assert "municipality_code:" not in text


def test_annual_permit_table_keeps_the_count_and_its_lineage(tmp_path: Path) -> None:
    """One invented annual permit row is the whole table, with its source chain."""
    entry = _entry(PERMIT_ANNUAL)
    parsed = _run("permits_muni", PERMIT_ANNUAL, [_permit()], tmp_path)
    assert parsed.table == "pub_building_permits"  # type: ignore[attr-defined]
    assert parsed.rows == (  # type: ignore[attr-defined]
        {
            "municipality_code": "syn_coast",
            "document_type": "building_permit",
            "permit_type": "VILLA",
            "building_type": "RESIDENTIAL BUILDINGS",
            "document_count": 4,
            **_lineage(entry.key, "2022", METHOD_PERMITS),
        },
    )
    assert parsed.period_first == "2022"  # type: ignore[attr-defined]
    assert parsed.period_last == "2022"  # type: ignore[attr-defined]
    assert _coverage(parsed, "missing_measure") == 0
    assert all(item.count > 0 for item in parsed.coverage)  # type: ignore[attr-defined]
    question = parsed.questions[0]  # type: ignore[attr-defined]
    assert "published key" in question.contract
    assert "3 classes" in question.inventory
    assert "classification" in question.change


def test_certificate_count_is_not_read_as_a_permit_number(tmp_path: Path) -> None:
    """The certificate slug keeps certificate_type and the count field's own number."""
    entry = _entry(PERMIT_CERT)
    parsed = _run("permits_muni", PERMIT_CERT, [_certificate()], tmp_path)
    assert parsed.rows == (  # type: ignore[attr-defined]
        {
            "municipality_code": "syn_inland",
            "document_type": "completion_certificate",
            "permit_type": "VILLA",
            "building_type": "ADDITIONS",
            "document_count": 2,
            **_lineage(entry.key, "2021", METHOD_PERMITS),
        },
    )


def test_monthly_permit_uses_the_lookup_and_building_type_all(tmp_path: Path) -> None:
    """A declared spelling is looked up. The month stays a month and the count is not summed."""
    entry = _entry(PERMIT_MONTH)
    parsed = _run(
        "permits_muni",
        PERMIT_MONTH,
        [_month(number=3), _month(year="2019", month="MARCH", number=7)],
        tmp_path,
        _named_month(_map(), PERMIT_MONTH),
    )
    assert [row["document_count"] for row in parsed.rows] == [3, 7]  # type: ignore[attr-defined]
    assert {row["period"] for row in parsed.rows} == {"2018-01", "2019-03"}  # type: ignore[attr-defined]
    assert {row["building_type"] for row in parsed.rows} == {"all"}  # type: ignore[attr-defined]
    assert {row["permit_type"] for row in parsed.rows} == {"New Building"}  # type: ignore[attr-defined]
    assert {row["municipality_code"] for row in parsed.rows} == {"syn_coast"}  # type: ignore[attr-defined]
    assert parsed.period_first == "2018-01"  # type: ignore[attr-defined]
    assert parsed.period_last == "2019-03"  # type: ignore[attr-defined]
    assert entry.period_first == "2016-01"
    assert parsed.rows[0]["method"] == METHOD_PERMITS  # type: ignore[attr-defined]


def test_monthly_float_count_stays_integral_and_zero_stays_zero(tmp_path: Path) -> None:
    """A float that is a whole number is that count. Zero is a count, not a missing row."""
    parsed = _run(
        "permits_muni",
        PERMIT_MONTH_FLOAT,
        [_month(number=4.0), _month(year="2019", month="MARCH", number=0)],
        tmp_path,
        _named_month(_map(), PERMIT_MONTH_FLOAT),
    )
    assert [row["document_count"] for row in parsed.rows] == [4, 0]  # type: ignore[attr-defined]


def test_monthly_without_a_declared_spelling_writes_no_row(tmp_path: Path) -> None:
    """No municipality field and no declared spelling: the row is left out, not guessed."""
    parsed = _run(
        "permits_muni", PERMIT_MONTH, [_month(), _month(year="2019")], tmp_path
    )
    assert parsed.rows == ()  # type: ignore[attr-defined]
    assert _coverage(parsed, "municipality_absent") == 2
    question = parsed.questions[-1]  # type: ignore[attr-defined]
    assert "no municipality field" in question.inventory
    assert "existing lookup" in question.change


def test_monthly_and_annual_views_are_not_added(tmp_path: Path) -> None:
    """The monthly numbers and the annual count stay the figures their own fields state."""
    annual = _run(
        "permits_muni", PERMIT_ANNUAL, [_permit(count=10)], tmp_path / "annual"
    )
    monthly = _run(
        "permits_muni",
        PERMIT_MONTH,
        [_month(number=3), _month(year="2019", month="MARCH", number=7)],
        tmp_path / "monthly",
        _named_month(_map(), PERMIT_MONTH),
    )
    assert annual.rows[0]["document_count"] == 10  # type: ignore[attr-defined]
    assert [row["document_count"] for row in monthly.rows] == [3, 7]  # type: ignore[attr-defined]


def test_unmapped_spelling_stops_with_the_lookup_count(tmp_path: Path) -> None:
    """The lookup's message carries the count of spellings and not the spelling."""
    with pytest.raises(FrameError) as caught:
        _run(
            "permits_muni",
            PERMIT_ANNUAL,
            [_permit(municipality="SYN Nowhere", lbldy="SYN Nowhere AR")],
            tmp_path,
        )
    message = str(caught.value)
    assert "1 unmapped spellings" in message
    assert "SYN Nowhere" not in message


def test_bilingual_municipality_disagreement_stops_with_the_lookup(
    tmp_path: Path,
) -> None:
    """Two spellings that resolve to different keys stop on the lookup's own disagreement."""
    with pytest.raises(FrameError) as caught:
        _run(
            "hotels_muni",
            HOTELS,
            [
                {
                    "year": "2023",
                    "municipality": "SYN Coast",
                    "lbldy": "SYN Inland AR",
                    "facility_type": "Hotels",
                    "nw_lmnsh": "الفنادق",
                    "number": 1,
                }
            ],
            tmp_path,
        )
    message = str(caught.value)
    assert message == "hotels_muni: municipality name disagreement"
    assert "SYN Coast" not in message


def test_permit_category_outside_the_list_stops(tmp_path: Path) -> None:
    """A permit type the review does not list stops the build."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_ANNUAL,
            [_permit(permit_type="SYN OTHER")],
            tmp_path,
        )
    assert caught.value.name == "category_unlisted"


def test_monthly_category_pair_disagreement_stops(tmp_path: Path) -> None:
    """English and Arabic permit classes that are not the reviewed pair stop the build."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_MONTH,
            [_month(nw_lrkhs="تحويط")],
            tmp_path,
            _named_month(_map(), PERMIT_MONTH),
        )
    assert caught.value.name == "category_disagreement"


def test_missing_count_is_left_out_and_a_dash_stops(tmp_path: Path) -> None:
    """A null count writes no row and is not stored as zero. Any other text stops."""
    parsed = _run(
        "permits_muni",
        PERMIT_ANNUAL,
        [_permit(count=None), _permit(year="2023", count=5)],
        tmp_path / "null",
    )
    assert [row["document_count"] for row in parsed.rows] == [5]  # type: ignore[attr-defined]
    assert _coverage(parsed, "missing_measure") == 1
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_ANNUAL,
            [_permit(count="-")],
            tmp_path / "dash",
        )
    assert caught.value.name == "measure_unparsed"


def test_negative_and_fractional_counts_stop(tmp_path: Path) -> None:
    """A negative count and a fractional count are not stored."""
    with pytest.raises(AdditionError) as caught:
        _run("permits_muni", PERMIT_ANNUAL, [_permit(count=-1)], tmp_path / "neg")
    assert caught.value.name == "measure_negative"
    with pytest.raises(AdditionError) as caught_fraction:
        _run(
            "permits_muni",
            PERMIT_MONTH_FLOAT,
            [_month(number=1.5)],
            tmp_path / "fraction",
            _named_month(_map(), PERMIT_MONTH_FLOAT),
        )
    assert caught_fraction.value.name == "measure_not_integral"


def test_a_period_outside_the_closed_forms_stops(tmp_path: Path) -> None:
    """A month name and a year outside the closed forms stop the build."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_MONTH,
            [_month(month="Smarch")],
            tmp_path / "month",
            _named_month(_map(), PERMIT_MONTH),
        )
    assert caught.value.name == "period_form"
    with pytest.raises(AdditionError) as caught_year:
        _run(
            "pop_muni_age",
            POPULATION,
            [
                {
                    "years": "20",
                    "age_groups": "0",
                    "lbldy": "SYN Coast AR",
                    "municipality": "SYN Coast",
                    "count": 1,
                }
            ],
            tmp_path / "year",
        )
    assert caught_year.value.name == "period_form"


def test_the_modified_date_is_not_the_period(tmp_path: Path) -> None:
    """The observed year is the period. The file's modified date is not."""
    parsed = _run(
        "hotels_muni",
        HOTELS,
        [
            {
                "year": "2024",
                "municipality": "SYN Coast",
                "lbldy": "SYN Coast AR",
                "facility_type": "Hotels",
                "nw_lmnsh": "الفنادق",
                "number": 2,
            }
        ],
        tmp_path,
        receipt={**RECEIPT, "source_modified": "1999-01-01"},
    )
    assert parsed.rows[0]["period"] == "2024"  # type: ignore[attr-defined]
    assert parsed.period_first == "2024"  # type: ignore[attr-defined]
    assert "1999" not in parsed.rows[0]["period"]  # type: ignore[attr-defined]


def test_population_table_and_its_lineage(tmp_path: Path) -> None:
    """One age cell is residents on that municipality, with the contract unit."""
    entry = _entry(POPULATION)
    parsed = _run(
        "pop_muni_age",
        POPULATION,
        [
            {
                "years": "2020",
                "age_groups": "5 - 9",
                "lbldy": "SYN Coast AR",
                "municipality": "SYN Coast",
                "count": 12.0,
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_population_age"  # type: ignore[attr-defined]
    assert parsed.rows == (  # type: ignore[attr-defined]
        {
            "municipality_code": "syn_coast",
            "age_group": "5 - 9",
            "indicator": "residents",
            "value": Decimal("12.0000"),
            "unit": "persons",
            **_lineage(entry.key, "2020", METHOD_POPULATION),
        },
    )


def test_population_cells_are_not_summed_across_age_or_municipality(
    tmp_path: Path,
) -> None:
    """Two cells stay two cells. No national total is added."""
    parsed = _run(
        "pop_muni_age",
        POPULATION,
        [
            {
                "years": "2020",
                "age_groups": "0",
                "lbldy": "SYN Coast AR",
                "municipality": "SYN Coast",
                "count": 4,
            },
            {
                "years": "2020",
                "age_groups": "1 - 4",
                "lbldy": "SYN Inland AR",
                "municipality": "SYN Inland",
                "count": 6,
            },
        ],
        tmp_path,
    )
    assert len(parsed.rows) == 2  # type: ignore[attr-defined]
    assert sorted(row["value"] for row in parsed.rows) == [  # type: ignore[attr-defined]
        Decimal("4.0000"),
        Decimal("6.0000"),
    ]
    assert {row["municipality_code"] for row in parsed.rows} == {  # type: ignore[attr-defined]
        "syn_coast",
        "syn_inland",
    }


def test_unknown_age_group_stops(tmp_path: Path) -> None:
    """An age label outside the reviewed list stops the build."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "pop_muni_age",
            POPULATION,
            [
                {
                    "years": "2020",
                    "age_groups": "5-9",
                    "lbldy": "SYN Coast AR",
                    "municipality": "SYN Coast",
                    "count": 1,
                }
            ],
            tmp_path,
        )
    assert caught.value.name == "age_group"


def test_hotel_table_counts_facilities(tmp_path: Path) -> None:
    """The number field is a facility count. The row has no guest or room figure."""
    entry = _entry(HOTELS)
    parsed = _run(
        "hotels_muni",
        HOTELS,
        [
            {
                "year": "2022",
                "municipality": "SYN Coast",
                "lbldy": "SYN Coast AR",
                "facility_type": "Hotel Apartments",
                "nw_lmnsh": "الشقق الفندقية",
                "number": 3,
            }
        ],
        tmp_path,
    )
    assert parsed.table == "pub_hotels_municipality"  # type: ignore[attr-defined]
    assert parsed.rows == (  # type: ignore[attr-defined]
        {
            "municipality_code": "syn_coast",
            "facility_type": "Hotel Apartments",
            "facility_count": 3,
            **_lineage(entry.key, "2022", METHOD_HOTELS),
        },
    )
    assert "guests" not in parsed.rows[0]  # type: ignore[attr-defined]
    assert "rooms" not in parsed.rows[0]  # type: ignore[attr-defined]


def test_a_guest_field_and_an_unknown_facility_type_stop(tmp_path: Path) -> None:
    """A field the file does not declare stops the build, and so does an unlisted type."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "hotels_muni",
            HOTELS,
            [
                {
                    "year": "2022",
                    "municipality": "SYN Coast",
                    "lbldy": "SYN Coast AR",
                    "facility_type": "Hotels",
                    "nw_lmnsh": "الفنادق",
                    "number": 1,
                    "guests": 9,
                }
            ],
            tmp_path / "guests",
        )
    assert caught.value.name == "unknown_source_field"
    with pytest.raises(AdditionError) as caught_type:
        _run(
            "hotels_muni",
            HOTELS,
            [
                {
                    "year": "2022",
                    "municipality": "SYN Coast",
                    "lbldy": "SYN Coast AR",
                    "facility_type": "Rooms",
                    "nw_lmnsh": "الفنادق",
                    "number": 1,
                }
            ],
            tmp_path / "type",
        )
    assert caught_type.value.name == "facility_type"


def test_census_keeps_the_file_year_and_discards_geometry(tmp_path: Path) -> None:
    """Counts become two indicators. Shares and geometry are left out. The year is the file's."""
    entry = _entry(CENSUS)
    parsed = _run(
        "est_census_2015_muni",
        CENSUS,
        [
            {
                "year": "2015",
                "municipality": "SYN Coast",
                "lbldy": "SYN Coast AR",
                "establishments_number_dd_lmnshat": 9,
                "establishments_lmnshat": 12.5,
                "employees_number_dd_lmshtglwn": 20,
                "employees_lmshtglwn": 40.5,
                "geo_point": {"lat": "9.25", "lon": "1.25"},
                "geo_shape": {"type": "Feature"},
            }
        ],
        tmp_path,
        receipt={**RECEIPT, "source_modified": "2026-06-02"},
    )
    assert parsed.table == "pub_census_2015_municipality"  # type: ignore[attr-defined]
    assert parsed.rows == (  # type: ignore[attr-defined]
        {
            "municipality_code": "syn_coast",
            "indicator": "employees",
            "value": Decimal("20.0000"),
            "unit": "persons",
            **_lineage(entry.key, "2015", METHOD_CENSUS),
        },
        {
            "municipality_code": "syn_coast",
            "indicator": "establishments",
            "value": Decimal("9.0000"),
            "unit": "establishments",
            **_lineage(entry.key, "2015", METHOD_CENSUS),
        },
    )
    rendered = repr(parsed.rows)  # type: ignore[attr-defined]
    assert "9.25" not in rendered
    assert "12.5" not in rendered
    assert _coverage(parsed, "percent_share_unheld") == 2
    assert _coverage(parsed, "geometry_discarded") == 2
    question = parsed.questions[0]  # type: ignore[attr-defined]
    assert "percent" in question.inventory
    assert "establishments" in question.contract


def test_a_census_year_other_than_the_title_is_kept(tmp_path: Path) -> None:
    """The period is the year cell. It is not rewritten to the census title."""
    parsed = _run(
        "est_census_2015_muni",
        CENSUS,
        [
            {
                "year": "2014",
                "municipality": "SYN Coast",
                "lbldy": "SYN Coast AR",
                "establishments_number_dd_lmnshat": 1,
                "establishments_lmnshat": 100.0,
                "employees_number_dd_lmshtglwn": 1,
                "employees_lmshtglwn": 100.0,
                "geo_point": {"lat": "0", "lon": "0"},
                "geo_shape": {"type": "Feature"},
            }
        ],
        tmp_path,
    )
    assert {row["period"] for row in parsed.rows} == {"2014"}  # type: ignore[attr-defined]


def test_duplicate_hotel_key_stops(tmp_path: Path) -> None:
    """Two rows with one contract key publish nothing."""
    row = {
        "year": "2022",
        "municipality": "SYN Coast",
        "lbldy": "SYN Coast AR",
        "facility_type": "Hotels",
        "nw_lmnsh": "الفنادق",
        "number": 1,
    }
    with pytest.raises(AdditionError) as caught:
        _run("hotels_muni", HOTELS, [row, dict(row)], tmp_path)
    assert caught.value.name == "duplicate_key"


def test_lineage_is_refused_one_field_at_a_time(tmp_path: Path) -> None:
    """Clearing source, period, retrieval, method, licence or hash refuses the figure."""
    parsed = _run("permits_muni", PERMIT_ANNUAL, [_permit()], tmp_path)
    row = dict(parsed.rows[0])  # type: ignore[attr-defined]
    require_lineage(row)
    for field in LINEAGE:
        broken = dict(row)
        broken[field] = ""
        with pytest.raises(AdditionError) as caught:
            require_lineage(broken)
        assert caught.value.name == "lineage_incomplete"


def test_an_empty_receipt_hash_stops(tmp_path: Path) -> None:
    """A figure with no hash is refused before it is returned."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_ANNUAL,
            [_permit()],
            tmp_path,
            receipt={"retrieved_utc": "2026-03-04T05:06:07Z", "sha256": ""},
        )
    assert caught.value.name == "lineage_incomplete"


def test_a_second_code_map_and_a_missing_geography_stop(tmp_path: Path) -> None:
    """The review may not carry a municipality code, and a slug needs a geography."""
    coded = json.loads(json.dumps(_map()))
    coded["geography"][f"permits_muni/{PERMIT_ANNUAL}"]["municipality_code"] = (
        "syn_coast"
    )
    with pytest.raises(AdditionError) as caught:
        _run("permits_muni", PERMIT_ANNUAL, [_permit()], tmp_path / "code", coded)
    assert caught.value.name == "second_mapping"
    missing = json.loads(json.dumps(_map()))
    missing["geography"].pop(f"hotels_muni/{HOTELS}")
    with pytest.raises(AdditionError) as caught_geo:
        _run(
            "hotels_muni",
            HOTELS,
            [
                {
                    "year": "2022",
                    "municipality": "SYN Coast",
                    "lbldy": "SYN Coast AR",
                    "facility_type": "Hotels",
                    "nw_lmnsh": "الفنادق",
                    "number": 1,
                }
            ],
            tmp_path / "geo",
            missing,
        )
    assert caught_geo.value.name == "geography_undeclared"


def test_one_declared_spelling_is_not_enough(tmp_path: Path) -> None:
    """A single declared spelling cannot stand in for the bilingual lookup."""
    field_map = json.loads(json.dumps(_map()))
    field_map["geography"][f"permits_muni/{PERMIT_MONTH}"]["published_names"] = [
        "SYN Coast"
    ]
    with pytest.raises(AdditionError) as caught:
        _run("permits_muni", PERMIT_MONTH, [_month()], tmp_path, field_map)
    assert caught.value.name == "municipality_spellings"


def test_no_frame_file_stops(tmp_path: Path) -> None:
    """The municipal lookup is the frame file. A missing frame stops the build."""
    with pytest.raises(AdditionError) as caught:
        PARSERS["pop_muni_age"](
            _entry(POPULATION),
            [],
            RECEIPT,
            _map(),
            {"frame": tmp_path / "absent", "review": REVIEW},
        )
    assert caught.value.name == "crosswalk_missing"


def test_an_empty_export_has_no_period(tmp_path: Path) -> None:
    """A file with no row has no observed period."""
    with pytest.raises(AdditionError) as caught:
        _run("pop_muni_age", POPULATION, [], tmp_path)
    assert caught.value.name == "period_absent"


def test_a_permit_shape_without_a_type_field_stops(tmp_path: Path) -> None:
    """A row that is neither a permit nor a certificate is not given a document type."""
    entry = _entry(PERMIT_ANNUAL)
    from dataclasses import replace

    bare = replace(
        entry,
        columns=(
            ("year", "string"),
            ("municipality", "string"),
            ("lbldy", "string"),
            ("count", "integer"),
        ),
    )
    with pytest.raises(AdditionError) as caught:
        PARSERS["permits_muni"](
            bare,
            [_permit()],
            RECEIPT,
            _map(),
            {"frame": _frame(tmp_path), "review": REVIEW},
        )
    assert caught.value.name == "document_type"


def test_a_broken_field_map_stops(tmp_path: Path) -> None:
    """A geography block that is not a map stops the build."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_ANNUAL,
            [_permit()],
            tmp_path,
            {"geography": "no"},
        )
    assert caught.value.name == "field_map_unreadable"


def test_a_non_text_municipality_stops(tmp_path: Path) -> None:
    """A municipality cell that is not text stops before any code is chosen."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_ANNUAL,
            [_permit(municipality=1)],
            tmp_path,
        )
    assert caught.value.name == "category_unparsed"


def test_fencing_belongs_to_permits_and_not_to_certificates(tmp_path: Path) -> None:
    """FENCING is an annual permit type. A certificate with that type stops."""
    annual = _run(
        "permits_muni",
        PERMIT_ANNUAL,
        [_permit(permit_type="FENCING", nw_lrkhs="تحويط")],
        tmp_path / "annual",
    )
    assert annual.rows[0]["permit_type"] == "FENCING"  # type: ignore[attr-defined]
    assert annual.rows[0]["document_type"] == "building_permit"  # type: ignore[attr-defined]
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_CERT,
            [_certificate(certificate_type="FENCING")],
            tmp_path / "certificate",
        )
    assert caught.value.name == "category_unlisted"


def test_certificate_building_arabic_must_match_the_reviewed_pair(
    tmp_path: Path,
) -> None:
    """ADDITIONS has one reviewed Arabic label. A different label stops the build."""
    with pytest.raises(AdditionError) as caught:
        _run(
            "permits_muni",
            PERMIT_CERT,
            [_certificate(nw_lmbn="مباني سكنية")],
            tmp_path,
        )
    assert caught.value.name == "category_disagreement"


def test_the_review_file_is_read_when_the_field_map_has_no_geography(
    tmp_path: Path,
) -> None:
    """An empty field map loads the municipal review file from the review directory."""
    parsed = PARSERS["permits_muni"](
        _entry(PERMIT_ANNUAL),
        [_permit()],
        RECEIPT,
        {},
        {"frame": _frame(tmp_path), "review": REVIEW},
    )
    assert parsed.rows[0]["document_count"] == 4  # type: ignore[attr-defined]


def test_a_missing_review_file_stops(tmp_path: Path) -> None:
    """The fallback review file must be present."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AdditionError) as caught:
        PARSERS["permits_muni"](
            _entry(PERMIT_ANNUAL),
            [_permit()],
            RECEIPT,
            {},
            {"frame": _frame(tmp_path / "frame"), "review": empty},
        )
    assert caught.value.name == "field_map_unreadable"


def test_parsers_are_registered_by_source_id() -> None:
    """The four families are the parsers this module exports."""
    assert set(PARSERS) == set(FAMILIES)


def test_a_missing_broken_or_non_utf8_municipal_review_stops(tmp_path: Path) -> None:
    """A review file that cannot be opened, decoded or parsed stops by name."""
    entry = _entry(PERMIT_ANNUAL)
    frame = _frame(tmp_path / "frame")
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(AdditionError) as absent:
        PARSERS["permits_muni"](
            entry, [], RECEIPT, {}, {"frame": frame, "review": missing}
        )
    assert absent.value.name == "field_map_unreadable"
    syntax = tmp_path / "syntax"
    syntax.mkdir()
    (syntax / "additions_municipal.yaml").write_text("geography: [\n", encoding="utf-8")
    with pytest.raises(AdditionError) as broken:
        PARSERS["permits_muni"](
            entry, [], RECEIPT, {}, {"frame": frame, "review": syntax}
        )
    assert broken.value.name == "field_map_unreadable"
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "additions_municipal.yaml").write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(AdditionError) as decoded:
        PARSERS["permits_muni"](entry, [], RECEIPT, {}, {"frame": frame, "review": raw})
    assert decoded.value.name == "field_map_unreadable"
