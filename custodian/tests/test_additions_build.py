"""The join pass publishes the fifteen decision-0017 tables. Fixtures are invented."""

from __future__ import annotations

import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path

import duckdb  # type: ignore[import-untyped]
import pytest

from eii_custodian.publicdata.additions.build import (
    _field_map,
    _tables,
    build_additions,
)
from eii_custodian.publicdata.additions.common import AdditionError, FamilyParse
from eii_custodian.publicdata.fetch.registry import Entry, load_registry

_REVIEW = Path(__file__).resolve().parents[1] / "publicdata" / "review"
_REVIEW_FILES = (
    "additions_property_venues.yaml",
    "additions_industry.yaml",
    "additions_municipal.yaml",
    "additions_splits.yaml",
    "venue_crosswalk.csv",
)
_RETRIEVED = "2026-03-04T05:06:07Z"
_LICENCE = "CC-BY-4.0"
_BASIS = "dataset"
_LINEAGE = (
    "source_key",
    "publisher",
    "licence_id",
    "licence_basis",
    "retrieved_utc",
    "sha256",
    "method",
)
_TWO = (
    "number-of-establishments-and-employees-by-size-of-establishment-"
    "and-main-economic-activity-two"
)
_METALS = "manufacture-of-basic-metals"
_TRADE = (
    "purchases-sales-and-stocks-during-the-year-by-type-of-trade-"
    "wholesale-and-retail-trade-all"
)
_CERTIFICATES = "annual-certificates-of-origin-by-type-and-importing-country"
_PERMIT = (
    "total-building-permits-issued-by-municipality-and-type-of-building-type-of-permit"
)
_POPULATION = "population-by-municipality-and-age-groups"
_HOTELS = "hotels-and-hotel-apartments-by-municipality"
HOTEL_RATING_BREAKDOWN = "hotel_rating=Two & One Star"
_CENSUS = (
    "distribution-of-business-establishments-and-employees-by-municipalities-"
    "according-to-census-2015"
)
_EMPLOYED = "employed-persons-15-years-and-above-by-gender-and-municipality"
_POP_F = "females-population-by-municipality-and-age-groups-december-2020"
_ACTIVE_F = (
    "economically-active-females-15-years-and-above-by-age-group-and-economic-activity"
)
_NAT_MALES = (
    "economically-active-non-qatari-males-15-years-and-above-"
    "by-occupation-and-economic-activity"
)
_COMP = (
    "number-of-employees-and-compensation-of-employees-"
    "by-nationality-and-main-economic-activity"
)
_STUDENTS = (
    "students-by-level-of-education-municipality-gender-type-of-education-"
    "and-nationality-2025-2026"
)
_HOTEL_GUESTS = "hotel-guests-by-nationality-hotel-rating-and-hotel-stays"
_SIZE = "Establishments with 10 Employees and More"
_SIZE_AR = "المنشآت 10 مشتغلين فأكثر"
_EST_METHOD = "eii_custodian.publicdata.additions.industry.parse_establishment_size@1"
_MFG_METHOD = "eii_custodian.publicdata.additions.industry.parse_manufacturing@1"
_LOG_METHOD = "eii_custodian.publicdata.additions.industry.parse_logistics@1"
_PERMIT_METHOD = "eii_custodian.publicdata.additions.municipal.parse_permits@1"
_POPULATION_METHOD = "eii_custodian.publicdata.additions.municipal.parse_population@1"
_HOTELS_METHOD = "eii_custodian.publicdata.additions.municipal.parse_hotels@1"
_CENSUS_METHOD = "eii_custodian.publicdata.additions.municipal.parse_census@1"
_SPLIT_METHOD = "eii_custodian.publicdata.additions.splits.parse@1"
_COUNCIL = "National Planning Council"
_COMMERCE = "Ministry of Commerce and Industry"
_CHAMBER = "Qatar Chamber of Commerce & Industry"
_EDUCATION = "Ministry of Education and Higher Education"


def _varchar(*names: str) -> tuple[tuple[str, str], ...]:
    return tuple((name, "VARCHAR") for name in names)


def _columns(
    key: tuple[str, ...], measures: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    return _varchar(*key) + measures + _varchar(*_LINEAGE)


_EST_KEY = ("table_code", "activity_key", "size_class", "period", "indicator")
_MFG_KEY = ("table_code", "period", "breakdown_key", "indicator")
_TRADE_KEY = ("trade_type", "period", "indicator")
_PERMIT_KEY = (
    "municipality_code",
    "period",
    "document_type",
    "permit_type",
    "building_type",
)
_AGE_KEY = ("municipality_code", "period", "age_group", "indicator")
_HOTEL_KEY = ("municipality_code", "period", "facility_type")
_CENSUS_KEY = ("municipality_code", "period", "indicator")
_LABOUR_KEY = ("municipality_code", "period", "sex", "indicator")
_AGE_SEX_KEY = ("municipality_code", "period", "age_group", "sex", "indicator")
_ACTIVE_KEY = ("period", "sex", "age_group", "activity_key", "indicator")
_NAT_KEY = (
    "period",
    "nationality_group",
    "sex",
    "occupation_key",
    "activity_key",
    "indicator",
)
_COMP_KEY = ("table_code", "period", "activity_key", "nationality_group", "indicator")
_STUDENT_KEY = (
    "municipality_code",
    "period",
    "education_level",
    "education_type",
    "sex",
    "nationality_group",
    "indicator",
)
_VISITOR_KEY = (
    "table_code",
    "period",
    "nationality_group",
    "breakdown_key",
    "indicator",
)
_VALUE_18_2 = (("value", "DECIMAL(18,2)"), ("unit", "VARCHAR"))
_VALUE_18_4 = (("value", "DECIMAL(18,4)"), ("unit", "VARCHAR"))
_EST_COLUMNS = _columns(_EST_KEY, _VALUE_18_2)
_MFG_COLUMNS = _columns(_MFG_KEY, _VALUE_18_4)
_TRADE_COLUMNS = _columns(_TRADE_KEY, _VALUE_18_2)
_LOG_COLUMNS = _columns(_MFG_KEY, _VALUE_18_2)
_PERMIT_COLUMNS = _columns(_PERMIT_KEY, (("document_count", "INTEGER"),))
_AGE_COLUMNS = _columns(_AGE_KEY, _VALUE_18_4)
_HOTEL_COLUMNS = _columns(_HOTEL_KEY, (("facility_count", "INTEGER"),))
_CENSUS_COLUMNS = _columns(_CENSUS_KEY, _VALUE_18_4)
_LABOUR_COLUMNS = _columns(_LABOUR_KEY, _VALUE_18_4)
_AGE_SEX_COLUMNS = _columns(_AGE_SEX_KEY, _VALUE_18_4)
_ACTIVE_COLUMNS = _columns(_ACTIVE_KEY, _VALUE_18_4)
_NAT_COLUMNS = _columns(_NAT_KEY, _VALUE_18_4)
_COMP_COLUMNS = _columns(_COMP_KEY, _VALUE_18_2)
_STUDENT_COLUMNS = _columns(_STUDENT_KEY, (("value", "INTEGER"), ("unit", "VARCHAR")))
_VISITOR_COLUMNS = _columns(_VISITOR_KEY, _VALUE_18_2)
_PROPERTY_KEY = ("district_key", "period", "unit_type")
_VENUE_KEY = ("venue_key", "period", "indicator")
_PROPERTY_COLUMNS = (
    ("district_key", "VARCHAR"),
    ("municipality_code", "VARCHAR"),
    ("period", "VARCHAR"),
    ("unit_type", "VARCHAR"),
    ("deal_count", "INTEGER"),
    ("median_price", "DECIMAL(14,2)"),
    ("price_basis", "VARCHAR"),
    *_varchar(*_LINEAGE),
)
_VENUE_COLUMNS = (
    ("venue_key", "VARCHAR"),
    ("venue_kind", "VARCHAR"),
    ("name_en", "VARCHAR"),
    ("name_ar", "VARCHAR"),
    ("region", "VARCHAR"),
    ("place_id", "VARCHAR"),
    ("period", "VARCHAR"),
    ("indicator", "VARCHAR"),
    ("value", "INTEGER"),
    ("unit", "VARCHAR"),
    *_varchar(*_LINEAGE),
)
_TABLES = (
    ("pub_establishment_size", _EST_KEY, _EST_COLUMNS),
    ("pub_manufacturing", _MFG_KEY, _MFG_COLUMNS),
    ("pub_trade_wr", _TRADE_KEY, _TRADE_COLUMNS),
    ("pub_trade_logistics", _MFG_KEY, _LOG_COLUMNS),
    ("pub_building_permits", _PERMIT_KEY, _PERMIT_COLUMNS),
    ("pub_population_age", _AGE_KEY, _AGE_COLUMNS),
    ("pub_hotels_municipality", _HOTEL_KEY, _HOTEL_COLUMNS),
    ("pub_census_2015_municipality", _CENSUS_KEY, _CENSUS_COLUMNS),
    ("pub_labour_sex_municipality", _LABOUR_KEY, _LABOUR_COLUMNS),
    ("pub_population_age_sex", _AGE_SEX_KEY, _AGE_SEX_COLUMNS),
    ("pub_active_sex_age", _ACTIVE_KEY, _ACTIVE_COLUMNS),
    ("pub_active_nationality_occupation", _NAT_KEY, _NAT_COLUMNS),
    ("pub_compensation_nationality", _COMP_KEY, _COMP_COLUMNS),
    ("pub_students", _STUDENT_KEY, _STUDENT_COLUMNS),
    ("pub_visitor_markets", _VISITOR_KEY, _VISITOR_COLUMNS),
    ("pub_property_resi", _PROPERTY_KEY, _PROPERTY_COLUMNS),
    ("pub_venue_visits", _VENUE_KEY, _VENUE_COLUMNS),
)


def _filled(columns: tuple[tuple[str, str], ...]) -> dict[str, object]:
    row: dict[str, object] = {}
    for name, kind in columns:
        if kind == "INTEGER":
            row[name] = 1
        elif kind.startswith("DECIMAL"):
            scale = int(kind.split(",")[1][:-1])
            row[name] = Decimal("1." + ("0" * scale))
        else:
            row[name] = "kept"
    return row


def _parsed(table: str, rows: tuple[dict[str, object], ...]) -> FamilyParse:
    return FamilyParse(table, rows, (), "", "", ())


def _measure(columns: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    for name, kind in columns:
        if kind != "VARCHAR":
            return name, kind
    raise AssertionError("table has no measure")


@pytest.mark.parametrize(("table", "key", "columns"), _TABLES)
def test_duplicate_key_is_exactly_the_contract_key(
    table: str, key: tuple[str, ...], columns: tuple[tuple[str, str], ...]
) -> None:
    """Two rows that share the key are refused. Each key column, alone, separates them."""
    measure, kind = _measure(columns)
    same = _filled(columns)
    other = _filled(columns)
    if kind == "INTEGER":
        other[measure] = 2
    else:
        scale = int(kind.split(",")[1][:-1])
        other[measure] = Decimal("2." + ("0" * scale))
    with pytest.raises(AdditionError) as caught:
        _tables((_parsed(table, (same, other)),))
    assert caught.value.name == "duplicate_key"
    for column in key:
        left = _filled(columns)
        right = _filled(columns)
        right[column] = "other-key"
        built = _tables((_parsed(table, (left, right)),))
        assert built[0][0] == table
        assert len(built[0][2]) == 2


def test_an_unknown_table_name_stops() -> None:
    """A parse result that names a table outside the catalogue is refused."""
    with pytest.raises(AdditionError) as caught:
        _tables((_parsed("pub_invented", ({"value": Decimal("1")},)),))
    assert caught.value.name == "unknown_table"


def test_a_row_must_carry_exactly_the_table_columns() -> None:
    """A missing field and an extra field each stop, and neither is dropped."""
    row = _filled(_EST_COLUMNS)
    missing = dict(row)
    del missing["unit"]
    with pytest.raises(AdditionError) as absent:
        _tables((_parsed("pub_establishment_size", (missing,)),))
    assert absent.value.name == "table_columns_mismatch"
    extra = dict(row)
    extra["note"] = "spare"
    with pytest.raises(AdditionError) as added:
        _tables((_parsed("pub_establishment_size", (extra,)),))
    assert added.value.name == "table_columns_mismatch"


def test_a_value_outside_the_column_stops_and_is_not_rounded() -> None:
    """More decimal places, more integer digits, a fraction, or a boolean stops."""
    wide = _filled(_EST_COLUMNS)
    wide["value"] = Decimal("1.234")
    with pytest.raises(AdditionError) as places:
        _tables((_parsed("pub_establishment_size", (wide,)),))
    assert places.value.name == "value_out_of_column"
    huge = _filled(_EST_COLUMNS)
    huge["value"] = Decimal("1" + ("0" * 16))
    with pytest.raises(AdditionError) as digits:
        _tables((_parsed("pub_establishment_size", (huge,)),))
    assert digits.value.name == "value_out_of_column"
    fraction = _filled(_PERMIT_COLUMNS)
    fraction["document_count"] = Decimal("1.5")
    with pytest.raises(AdditionError) as integral:
        _tables((_parsed("pub_building_permits", (fraction,)),))
    assert integral.value.name == "value_out_of_column"
    fitting = _filled(_EST_COLUMNS)
    fitting["value"] = Decimal("1.23")
    kept = _tables((_parsed("pub_establishment_size", (fitting,)),))
    assert kept[0][2][0][_EST_COLUMNS.index(("value", "DECIMAL(18,2)"))] == Decimal(
        "1.23"
    )
    bounded = _filled(_EST_COLUMNS)
    bounded["value"] = Decimal("1" + ("0" * 15))
    _tables((_parsed("pub_establishment_size", (bounded,)),))
    flagged = _filled(_PERMIT_COLUMNS)
    flagged["document_count"] = True
    with pytest.raises(AdditionError) as true_bit:
        _tables((_parsed("pub_building_permits", (flagged,)),))
    assert true_bit.value.name == "value_out_of_column"
    false_bit = _filled(_EST_COLUMNS)
    false_bit["value"] = False
    with pytest.raises(AdditionError) as false_value:
        _tables((_parsed("pub_establishment_size", (false_bit,)),))
    assert false_value.value.name == "value_out_of_column"


def test_a_null_or_empty_key_part_stops() -> None:
    """A key part that is null or empty is not published."""
    missing = _filled(_LOG_COLUMNS)
    missing["period"] = None
    with pytest.raises(AdditionError) as absent:
        _tables((_parsed("pub_trade_logistics", (missing,)),))
    assert absent.value.name == "key_part_missing"
    blank = _filled(_LOG_COLUMNS)
    blank["period"] = ""
    with pytest.raises(AdditionError) as empty:
        _tables((_parsed("pub_trade_logistics", (blank,)),))
    assert empty.value.name == "key_part_missing"


def test_an_integer_must_be_finite_and_inside_32_bit_bounds() -> None:
    """Infinity, a signalling NaN, and a value outside 32-bit bounds stop."""
    for number in (
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("sNaN"),
        2147483648,
        -2147483649,
    ):
        row = _filled(_PERMIT_COLUMNS)
        row["document_count"] = number
        with pytest.raises(AdditionError) as caught:
            _tables((_parsed("pub_building_permits", (row,)),))
        assert caught.value.name == "value_out_of_column"
    upper = _filled(_PERMIT_COLUMNS)
    upper["document_count"] = 2147483647
    kept = _tables((_parsed("pub_building_permits", (upper,)),))
    assert 2147483647 in kept[0][2][0]
    lower = _filled(_PERMIT_COLUMNS)
    lower["document_count"] = -2147483648
    kept_lower = _tables((_parsed("pub_building_permits", (lower,)),))
    assert -2147483648 in kept_lower[0][2][0]


def test_a_positive_exponent_counts_toward_the_integer_digits() -> None:
    """A power of ten uses its exponent when the integer width is judged."""
    huge = _filled(_EST_COLUMNS)
    huge["value"] = Decimal("1E+16")
    with pytest.raises(AdditionError) as caught:
        _tables((_parsed("pub_establishment_size", (huge,)),))
    assert caught.value.name == "value_out_of_column"
    fitting = _filled(_EST_COLUMNS)
    fitting["value"] = Decimal("1E+15")
    _tables((_parsed("pub_establishment_size", (fitting,)),))


def test_trailing_zero_digits_past_the_scale_stay_refused() -> None:
    """A decimal is not shortened to the column scale, even when the extra digits are zero."""
    wide = _filled(_EST_COLUMNS)
    wide["value"] = Decimal("1.230")
    with pytest.raises(AdditionError) as caught:
        _tables((_parsed("pub_establishment_size", (wide,)),))
    assert caught.value.name == "value_out_of_column"


def test_a_float_is_refused_in_every_column() -> None:
    """A float is never converted into a decimal, an integer or text."""
    whole = _filled(_PERMIT_COLUMNS)
    whole["document_count"] = 1.0
    with pytest.raises(AdditionError) as integral:
        _tables((_parsed("pub_building_permits", (whole,)),))
    assert integral.value.name == "value_out_of_column"
    measure = _filled(_EST_COLUMNS)
    measure["value"] = 1.0
    with pytest.raises(AdditionError) as decimal:
        _tables((_parsed("pub_establishment_size", (measure,)),))
    assert decimal.value.name == "value_out_of_column"
    text = _filled(_EST_COLUMNS)
    text["unit"] = 1.0
    with pytest.raises(AdditionError) as label:
        _tables((_parsed("pub_establishment_size", (text,)),))
    assert label.value.name == "value_out_of_column"
    integral_decimal = _filled(_PERMIT_COLUMNS)
    integral_decimal["document_count"] = Decimal("1E+2")
    kept = _tables((_parsed("pub_building_permits", (integral_decimal,)),))
    assert Decimal("1E+2") in kept[0][2][0]


def test_a_text_column_refuses_a_number() -> None:
    """A year given as a number is not stored as text."""
    numbered = _filled(_EST_COLUMNS)
    numbered["period"] = 2020
    with pytest.raises(AdditionError) as key:
        _tables((_parsed("pub_establishment_size", (numbered,)),))
    assert key.value.name == "key_part_missing"
    unit = _filled(_EST_COLUMNS)
    unit["unit"] = 2020
    with pytest.raises(AdditionError) as text:
        _tables((_parsed("pub_establishment_size", (unit,)),))
    assert text.value.name == "value_out_of_column"


def test_lineage_values_must_be_present() -> None:
    """An empty or missing publisher, licence, retrieval time or digest stops the row."""
    for field in (
        "publisher",
        "licence_id",
        "licence_basis",
        "retrieved_utc",
        "sha256",
    ):
        for blank in ("", None):
            row = _filled(_EST_COLUMNS)
            row[field] = blank
            with pytest.raises(AdditionError) as caught:
                _tables((_parsed("pub_establishment_size", (row,)),))
            assert caught.value.name == "lineage_incomplete"


def test_a_null_is_accepted_only_under_the_column_condition() -> None:
    """Median price may be null when the deal count is zero. Other nulls stop."""
    empty = _filled(_PROPERTY_COLUMNS)
    empty["deal_count"] = 0
    empty["median_price"] = None
    kept = _tables((_parsed("pub_property_resi", (empty,)),))
    price_at = _PROPERTY_COLUMNS.index(("median_price", "DECIMAL(14,2)"))
    assert kept[0][2][0][price_at] is None
    priced = _filled(_PROPERTY_COLUMNS)
    priced["median_price"] = None
    with pytest.raises(AdditionError) as median:
        _tables((_parsed("pub_property_resi", (priced,)),))
    assert median.value.name == "value_out_of_column"
    museum = _filled(_VENUE_COLUMNS)
    museum["venue_kind"] = "museum_or_exhibition"
    museum["region"] = None
    museum["name_ar"] = None
    museum["place_id"] = None
    kept_venue = _tables((_parsed("pub_venue_visits", (museum,)),))
    names = [name for name, _kind in _VENUE_COLUMNS]
    published = kept_venue[0][2][0]
    assert published[names.index("region")] is None
    assert published[names.index("name_ar")] is None
    assert published[names.index("place_id")] is None
    health = _filled(_VENUE_COLUMNS)
    health["venue_kind"] = "health_centre"
    health["region"] = None
    with pytest.raises(AdditionError) as region:
        _tables((_parsed("pub_venue_visits", (health,)),))
    assert region.value.name == "value_out_of_column"
    untitled = _filled(_VENUE_COLUMNS)
    untitled["name_en"] = None
    with pytest.raises(AdditionError) as name:
        _tables((_parsed("pub_venue_visits", (untitled,)),))
    assert name.value.name == "value_out_of_column"
    unit = _filled(_EST_COLUMNS)
    unit["unit"] = None
    with pytest.raises(AdditionError) as measure:
        _tables((_parsed("pub_establishment_size", (unit,)),))
    assert measure.value.name == "value_out_of_column"


def test_a_field_map_that_is_not_a_mapping_stops(tmp_path: Path) -> None:
    """A YAML list is not a field map."""
    listed = tmp_path / "listed.yaml"
    listed.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(AdditionError) as caught:
        _field_map(listed)
    assert caught.value.name == "field_map_unreadable"


def test_an_unreadable_field_map_stops(tmp_path: Path) -> None:
    """A missing, unparsable or non-UTF-8 field map stops by name."""
    missing = tmp_path / "missing.yaml"
    with pytest.raises(AdditionError) as absent:
        _field_map(missing)
    assert absent.value.name == "field_map_unreadable"
    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [\n", encoding="utf-8")
    with pytest.raises(AdditionError) as syntax:
        _field_map(broken)
    assert syntax.value.name == "field_map_unreadable"
    raw = tmp_path / "raw.yaml"
    raw.write_bytes(b"\xff\xfe not text")
    with pytest.raises(AdditionError) as decoded:
        _field_map(raw)
    assert decoded.value.name == "field_map_unreadable"


def _entry(source_id: str, slug: str) -> Entry:
    return next(
        entry
        for entry in load_registry()
        if entry.source_id == source_id and entry.slug == slug
    )


def _publish(
    tmp_path: Path,
    source_id: str,
    slug: str,
    raw: list[dict[str, object]],
    *,
    country: bool,
) -> tuple[Path, str, Entry]:
    entry = _entry(source_id, slug)
    body = json.dumps(raw).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    cache = tmp_path / "cache"
    folder = cache / entry.key
    folder.mkdir(parents=True)
    (folder / f"{digest}.json").write_bytes(body)
    (folder / f"{digest}.meta.json").write_text(
        json.dumps({"retrieved_utc": _RETRIEVED, "sha256": digest}),
        encoding="utf-8",
    )
    review = tmp_path / "review"
    review.mkdir()
    for name in _REVIEW_FILES:
        target = review / name
        shutil.copyfile(_REVIEW / name, target)
    if country:
        text = (review / "additions_industry.yaml").read_text(encoding="utf-8")
        text = text.replace(
            "country_crosswalk: []\n",
            'country_crosswalk:\n  - published_label: "SYN Land"\n    iso3: "SLL"\n',
            1,
        )
        (review / "additions_industry.yaml").write_text(text, encoding="utf-8")
    frame = tmp_path / "frame"
    frame.mkdir()
    (frame / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "SYN Coast,syn_coast\n"
        "SYN Coast AR,syn_coast\n"
        "North Ward,north_ward\n"
        "حي مخترع,north_ward\n",
        encoding="utf-8",
    )
    destination = build_additions(
        cache, (entry,), {entry.key: digest}, review, frame, tmp_path / "out"
    )
    return destination, digest, entry


def _expected(
    columns: tuple[tuple[str, str], ...],
    body: dict[str, object],
    digest: str,
) -> tuple[object, ...]:
    full = dict(body)
    full["licence_id"] = _LICENCE
    full["licence_basis"] = _BASIS
    full["retrieved_utc"] = _RETRIEVED
    full["sha256"] = digest
    return tuple(full[name] for name, _kind in columns)


def _read(path: Path) -> tuple[list[tuple[str, str]], list[tuple[object, ...]]]:
    location = path.as_posix()
    described = duckdb.sql(
        f"DESCRIBE SELECT * FROM read_parquet('{location}')"
    ).fetchall()
    types = [(str(item[0]), str(item[1])) for item in described]
    found = duckdb.sql(f"SELECT * FROM read_parquet('{location}')").fetchall()
    return types, [tuple(row) for row in found]


@pytest.mark.parametrize(
    ("source_id", "slug", "table", "columns", "raw", "bodies", "country", "coverage"),
    (
        (
            "est_size_act",
            _TWO,
            "pub_establishment_size",
            _EST_COLUMNS,
            [
                {
                    "year": "2015",
                    "activity_code": "11",
                    "size_of_establishment": _SIZE,
                    "hjm_lmnsh": _SIZE_AR,
                    "indicator": "Employees",
                    "lbyn": "SYN-IND",
                    "value": 14,
                }
            ],
            [
                {
                    "table_code": _TWO,
                    "activity_key": "11",
                    "size_class": _SIZE,
                    "period": "2015",
                    "indicator": "employees",
                    "value": Decimal("14.00"),
                    "unit": "to_be_confirmed",
                    "source_key": f"est_size_act/{_TWO}",
                    "publisher": _COUNCIL,
                    "method": _EST_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "mfg_industry",
            _METALS,
            "pub_manufacturing",
            _MFG_COLUMNS,
            [
                {
                    "year": "2019",
                    "license_type": "Industrial License",
                    "nw_ltrkhys": "SYN-AR",
                    "number_of_firms": 4,
                    "investment_million_qatari_riyals": "10",
                    "number_of_labour": 7,
                }
            ],
            [
                {
                    "table_code": _METALS,
                    "period": "2019",
                    "breakdown_key": "licence_type=Industrial License",
                    "indicator": name,
                    "value": Decimal(figure),
                    "unit": unit,
                    "source_key": f"mfg_industry/{_METALS}",
                    "publisher": _COMMERCE,
                    "method": _MFG_METHOD,
                }
                for name, figure, unit in (
                    ("firms", "4.0000", "to_be_confirmed"),
                    ("investment", "10.0000", "qar_million"),
                    ("labour", "7.0000", "to_be_confirmed"),
                )
            ],
            False,
            None,
        ),
        (
            "trade_wr",
            _TRADE,
            "pub_trade_wr",
            _TRADE_COLUMNS,
            [
                {
                    "year": "2018",
                    "type_of_trade": "SYN Retail Group",
                    "nw_ltjr": "SYN-AR",
                    "measure": "Purchases",
                    "lmw_shr": "SYN-AR",
                    "breakdown": "Imported",
                    "ltfsyl": "SYN-AR",
                    "value": 3,
                }
            ],
            [],
            False,
            ("breakdown_not_in_key", 1),
        ),
        (
            "trade_logistics",
            _CERTIFICATES,
            "pub_trade_logistics",
            _LOG_COLUMNS,
            [
                {
                    "year": "2020",
                    "type_of_certificate": "Certificates of Origin",
                    "nw_lshhd": "SYN-AR",
                    "importing_country": "SYN Land",
                    "ldwl_lmstwrd": "SYN-AR",
                    "number_of_issued_certificates": 6,
                }
            ],
            [
                {
                    "table_code": _CERTIFICATES,
                    "period": "2020",
                    "breakdown_key": (
                        "certificate_type=Certificates of Origin|importing_country=SLL"
                    ),
                    "indicator": "certificates",
                    "value": Decimal("6.00"),
                    "unit": "to_be_confirmed",
                    "source_key": f"trade_logistics/{_CERTIFICATES}",
                    "publisher": _CHAMBER,
                    "method": _LOG_METHOD,
                }
            ],
            True,
            None,
        ),
        (
            "permits_muni",
            _PERMIT,
            "pub_building_permits",
            _PERMIT_COLUMNS,
            [
                {
                    "year": "2022",
                    "building_type": "RESIDENTIAL BUILDINGS",
                    "nw_lmbn": "مباني سكنية",
                    "permit_type": "VILLA",
                    "nw_lrkhs": "فيلا",
                    "municipality": "SYN Coast",
                    "lbldy": "SYN Coast AR",
                    "count": 4,
                }
            ],
            [
                {
                    "municipality_code": "syn_coast",
                    "period": "2022",
                    "document_type": "building_permit",
                    "permit_type": "VILLA",
                    "building_type": "RESIDENTIAL BUILDINGS",
                    "document_count": 4,
                    "source_key": f"permits_muni/{_PERMIT}",
                    "publisher": _COUNCIL,
                    "method": _PERMIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "pop_muni_age",
            _POPULATION,
            "pub_population_age",
            _AGE_COLUMNS,
            [
                {
                    "years": "2020",
                    "age_groups": "5 - 9",
                    "lbldy": "SYN Coast AR",
                    "municipality": "SYN Coast",
                    "count": 12,
                }
            ],
            [
                {
                    "municipality_code": "syn_coast",
                    "period": "2020",
                    "age_group": "5 - 9",
                    "indicator": "residents",
                    "value": Decimal("12.0000"),
                    "unit": "persons",
                    "source_key": f"pop_muni_age/{_POPULATION}",
                    "publisher": _COUNCIL,
                    "method": _POPULATION_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "hotels_muni",
            _HOTELS,
            "pub_hotels_municipality",
            _HOTEL_COLUMNS,
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
            [
                {
                    "municipality_code": "syn_coast",
                    "period": "2022",
                    "facility_type": "Hotel Apartments",
                    "facility_count": 3,
                    "source_key": f"hotels_muni/{_HOTELS}",
                    "publisher": _COUNCIL,
                    "method": _HOTELS_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "est_census_2015_muni",
            _CENSUS,
            "pub_census_2015_municipality",
            _CENSUS_COLUMNS,
            [
                {
                    "year": "2015",
                    "municipality": "SYN Coast",
                    "lbldy": "SYN Coast AR",
                    "establishments_number_dd_lmnshat": 9,
                    "establishments_lmnshat": "12.5",
                    "employees_number_dd_lmshtglwn": 20,
                    "employees_lmshtglwn": "40.5",
                    "geo_point": {"lat": "9.25", "lon": "1.25"},
                    "geo_shape": {"type": "Feature"},
                }
            ],
            [
                {
                    "municipality_code": "syn_coast",
                    "period": "2015",
                    "indicator": "employees",
                    "value": Decimal("20.0000"),
                    "unit": "persons",
                    "source_key": f"est_census_2015_muni/{_CENSUS}",
                    "publisher": _COUNCIL,
                    "method": _CENSUS_METHOD,
                },
                {
                    "municipality_code": "syn_coast",
                    "period": "2015",
                    "indicator": "establishments",
                    "value": Decimal("9.0000"),
                    "unit": "establishments",
                    "source_key": f"est_census_2015_muni/{_CENSUS}",
                    "publisher": _COUNCIL,
                    "method": _CENSUS_METHOD,
                },
            ],
            False,
            None,
        ),
        (
            "lf_muni_sex",
            _EMPLOYED,
            "pub_labour_sex_municipality",
            _LABOUR_COLUMNS,
            [
                {
                    "year": "2022",
                    "municipality": "North Ward",
                    "lbldy": "حي مخترع",
                    "gender": "Females",
                    "ljns": "اناث",
                    "number": 4,
                }
            ],
            [
                {
                    "municipality_code": "north_ward",
                    "period": "2022",
                    "sex": "female",
                    "indicator": "employed",
                    "value": Decimal("4"),
                    "unit": "persons",
                    "source_key": f"lf_muni_sex/{_EMPLOYED}",
                    "publisher": _COUNCIL,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "pop_muni_age_sex",
            _POP_F,
            "pub_population_age_sex",
            _AGE_SEX_COLUMNS,
            [
                {
                    "years": "2016",
                    "fy_t_l_mr_blsnwt": "1 - 4",
                    "age_groups_in_years": "1 - 4",
                    "lbldy": "حي مخترع",
                    "municipality": "North Ward",
                    "value": 6,
                    "geo_point": None,
                    "geo_shape": {"kind": "invented"},
                }
            ],
            [
                {
                    "municipality_code": "north_ward",
                    "period": "2016",
                    "age_group": "1 - 4",
                    "sex": "female",
                    "indicator": "residents",
                    "value": Decimal("6"),
                    "unit": "persons",
                    "source_key": f"pop_muni_age_sex/{_POP_F}",
                    "publisher": _COUNCIL,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "active_sex_age_act",
            _ACTIVE_F,
            "pub_active_sex_age",
            _ACTIVE_COLUMNS,
            [
                {
                    "year": "2019",
                    "age_group": "15 - 19",
                    "economic_activity": "Education",
                    "lnsht_lqtsdy": "تعليم",
                    "total": 7,
                }
            ],
            [
                {
                    "period": "2019",
                    "sex": "female",
                    "age_group": "15 - 19",
                    "activity_key": "Education",
                    "indicator": "economically_active",
                    "value": Decimal("7"),
                    "unit": "persons",
                    "source_key": f"active_sex_age_act/{_ACTIVE_F}",
                    "publisher": _COUNCIL,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "active_nat_occ_act",
            _NAT_MALES,
            "pub_active_nationality_occupation",
            _NAT_COLUMNS,
            [
                {
                    "year": "2018",
                    "economic_activity": "Education",
                    "lnsht_lqtsdy": "تعليم",
                    "occupation": "Clerks",
                    "lmhn": "كتبة",
                    "total": 3,
                }
            ],
            [
                {
                    "period": "2018",
                    "nationality_group": "non_qatari",
                    "sex": "male",
                    "occupation_key": "Clerks",
                    "activity_key": "Education",
                    "indicator": "economically_active",
                    "value": Decimal("3"),
                    "unit": "persons",
                    "source_key": f"active_nat_occ_act/{_NAT_MALES}",
                    "publisher": _COUNCIL,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "comp_nat_act",
            _COMP,
            "pub_compensation_nationality",
            _COMP_COLUMNS,
            [
                {
                    "year": "2018",
                    "code": "06",
                    "main_economic_activity": "B Mining and quarrying",
                    "main_economic_activity_ar": "تعدين",
                    "economic_activity": "quarrying",
                    "economic_activity_ar": "محاجر",
                    "labor_indicator": "Number of Employees",
                    "labor_indicator_ar": "عدد",
                    "nationality": "Qatari",
                    "nationality_ar": "قطريون",
                    "value": 4,
                }
            ],
            [
                {
                    "table_code": "bulletin",
                    "period": "2018",
                    "activity_key": "06",
                    "nationality_group": "qatari",
                    "indicator": "employees",
                    "value": Decimal("4"),
                    "unit": "to_be_confirmed",
                    "source_key": f"comp_nat_act/{_COMP}",
                    "publisher": _COUNCIL,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "students_muni",
            _STUDENTS,
            "pub_students",
            _STUDENT_COLUMNS,
            [
                {
                    "year": "2025-2026",
                    "municipality": "North Ward",
                    "lbldy": "حي مخترع",
                    "level_of_education": "Pre primary",
                    "lmrhl_lt_lymy": "ما قبل",
                    "type_of_education": "Government",
                    "nw_lt_lym": "حكومي",
                    "nationality": "Non Qatari",
                    "ljnsy": "غير قطري",
                    "gender": "Female",
                    "ljns": "انثى",
                    "number_of_students": 12,
                }
            ],
            [
                {
                    "municipality_code": "north_ward",
                    "period": "2025-2026",
                    "education_level": "Pre primary",
                    "education_type": "Government",
                    "sex": "female",
                    "nationality_group": "non_qatari",
                    "indicator": "students",
                    "value": 12,
                    "unit": "persons",
                    "source_key": f"students_muni/{_STUDENTS}",
                    "publisher": _EDUCATION,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
        (
            "visitors_markets",
            _HOTEL_GUESTS,
            "pub_visitor_markets",
            _VISITOR_COLUMNS,
            [
                {
                    "year": "2021",
                    "nationality": "Qataris",
                    "ljnsy": "قطريون",
                    "hotel_rating": "Two & One Star",
                    "drj_lfndq": "نجمتان",
                    "metric": "Nights",
                    "lmqys": "ليالي",
                    "number": "1.5",
                }
            ],
            [
                {
                    "table_code": "hotel_guests",
                    "period": "2021",
                    "nationality_group": "Qataris",
                    "breakdown_key": HOTEL_RATING_BREAKDOWN,
                    "indicator": "nights",
                    "value": Decimal("1.5"),
                    "unit": "to_be_confirmed",
                    "source_key": f"visitors_markets/{_HOTEL_GUESTS}",
                    "publisher": _COUNCIL,
                    "method": _SPLIT_METHOD,
                }
            ],
            False,
            None,
        ),
    ),
)
def test_each_table_round_trips_from_invented_rows(
    tmp_path: Path,
    source_id: str,
    slug: str,
    table: str,
    columns: tuple[tuple[str, str], ...],
    raw: list[dict[str, object]],
    bodies: list[dict[str, object]],
    country: bool,
    coverage: tuple[str, int] | None,
) -> None:
    """Invented rows publish with the contract columns, types and lineage."""
    destination, digest, _entry_row = _publish(
        tmp_path, source_id, slug, raw, country=country
    )
    path = destination / "tables" / f"{table}.parquet"
    types, rows = _read(path)
    assert types == list(columns)
    assert rows == [_expected(columns, body, digest) for body in bodies]
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    listed = {item["name"]: item["rows"] for item in manifest["tables"]}
    assert listed[table] == len(bodies)
    if coverage is not None:
        report = json.loads(
            (destination / "build_report.json").read_text(encoding="utf-8")
        )
        assert {"reason": coverage[0], "count": coverage[1]} in report["coverage"]
        assert rows == []
