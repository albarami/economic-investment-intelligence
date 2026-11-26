"""Hand-made rows for design cooling capacity by municipality and sector."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.singles_entries import dcool_entry
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.frame.crosswalk import load_municipality_names, read_csv
from eii_custodian.publicdata.singles.dcool import CoolingError, parse_dcool

ROOT = repository_root(Path(__file__))


def _names() -> list[dict[str, str]]:
    review = ROOT / "custodian/publicdata/review"
    rows = read_csv(review / "municipality_names.csv")
    known = {row["municipality_code"] for row in rows}
    return load_municipality_names(review, known)


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2019-01-01",
        "project_status": "Invented status",
        "municipality": "Doha",
        "other": 1,
        "industrial": 2,
        "real_estate_development": 3,
        "sport": 4,
        "culture": "5",
        "health": 6,
        "transport": 7,
        "education": 9,
        "hotels": 10,
        "commercial": 12,
        "district_cooling_service_supply": 13,
        "lbldy": "الدوحة",
        "hl_lmshry": "مخترع",
        "geo_point": "invented-point",
        "geo_shape": "invented-shape",
    }
    row.update(changes)
    return row


def test_entry_declares_culture_as_text() -> None:
    # The registry row is built here; part R appends sources.yaml.
    entry = dcool_entry()
    kinds = dict(entry.columns)
    # J2 / join section 4b: the helper follows the registry row (string, integer).
    assert kinds["culture"] == "string"
    assert kinds["industrial"] == "integer"
    assert "geo_point" in kinds
    assert entry.release_tables == ("pub_district_cooling",)
    assert entry.slug == "design-cooling-capacity-by-status-municipality-and-sector-tr"


def test_fixture_file_unpivots() -> None:
    path = ROOT / "custodian/tests/fixtures/dcool/capacity.json"
    rows = parse_dcool(json.loads(path.read_text(encoding="utf-8")), _names())
    assert {row.sector_key for row in rows} >= {"culture", "industrial"}
    assert all(row.indicator.startswith("capacity_") for row in rows)


def test_unpivot_uses_the_municipality_map_and_drops_geometry() -> None:
    rows = parse_dcool((_row(),), _names())
    by_sector = {row.sector_key: row for row in rows}
    assert by_sector["culture"].value == Decimal("5")
    assert by_sector["culture"].municipality_code == "1"
    assert by_sector["industrial"].value == Decimal("2")
    assert by_sector["culture"].indicator == "capacity_invented_status"
    assert by_sector["culture"].unit == "TR"
    assert by_sector["culture"].period == "2019-01-01"
    assert "geo_point" not in by_sector["culture"].__dict__
    assert "project_status" not in by_sector["culture"].__dict__


def test_culture_integer_and_unmapped_municipality_fail() -> None:
    with pytest.raises(CoolingError) as culture:
        parse_dcool((_row(culture=5),), _names())
    assert culture.value.reason == "culture_type"
    with pytest.raises(CoolingError) as words:
        parse_dcool((_row(culture="five"),), _names())
    assert words.value.reason == "culture_type"
    with pytest.raises(CoolingError) as text_sector:
        parse_dcool((_row(industrial="2"),), _names())
    assert text_sector.value.reason == "sector_type"
    with pytest.raises(CoolingError) as missing:
        parse_dcool((_row(municipality="Invented Town"),), _names())
    assert missing.value.reason == "unmapped_municipality"
    with pytest.raises(CoolingError) as consumption:
        parse_dcool((_row(consumption=1),), _names())
    assert consumption.value.reason == "consumption"
    with pytest.raises(CoolingError) as duplicate:
        parse_dcool(
            (_row(), _row(industrial=4)),
            _names(),
        )
    assert duplicate.value.reason == "duplicate_key"


def test_an_empty_sector_cell_is_no_row_and_a_text_cell_still_fails() -> None:
    rows = parse_dcool((_row(industrial=None, culture=None),), _names())
    assert {row.sector_key for row in rows}.isdisjoint({"industrial", "culture"})
    assert "other" in {row.sector_key for row in rows}
    with pytest.raises(CoolingError) as text_sector:
        parse_dcool((_row(industrial="2"),), _names())
    assert text_sector.value.reason == "sector_type"


def test_each_published_status_is_its_own_capacity_indicator() -> None:
    """R1: the export is by status; one municipality and year has a row per status."""
    rows = parse_dcool(
        (
            _row(project_status="Operation Project"),
            _row(project_status="Project Under Construction"),
        ),
        _names(),
    )
    culture = sorted(row.indicator for row in rows if row.sector_key == "culture")
    assert culture == [
        "capacity_operation_project",
        "capacity_project_under_construction",
    ]
    with pytest.raises(CoolingError) as repeated:
        parse_dcool((_row(), _row()), _names())
    assert repeated.value.reason == "duplicate_key"
    for status in ("", "  ", None, 3):
        with pytest.raises(CoolingError) as bad:
            parse_dcool((_row(project_status=status),), _names())
        assert bad.value.reason == "project_status"


@pytest.mark.parametrize(
    ("raw", "kept"),
    [(None, None), (0, Decimal("0")), (7, Decimal("7"))],
)
def test_only_an_empty_ordinary_cell_is_no_row(raw: object, kept: object) -> None:
    rows = parse_dcool((_row(industrial=raw),), _names())
    values = [row.value for row in rows if row.sector_key == "industrial"]
    assert values == ([] if kept is None else [kept])


@pytest.mark.parametrize("raw", ["7", True, False, 1.5, [], {}])
def test_an_ordinary_cell_of_another_type_fails(raw: object) -> None:
    with pytest.raises(CoolingError) as wrong:
        parse_dcool((_row(industrial=raw),), _names())
    assert wrong.value.reason == "sector_type"


@pytest.mark.parametrize(
    ("raw", "reason"), [(5, "culture_type"), ("x", "culture_type")]
)
def test_culture_keeps_its_digit_text_rule(raw: object, reason: str) -> None:
    assert [
        row.value
        for row in parse_dcool((_row(culture=None),), _names())
        if row.sector_key == "culture"
    ] == []
    assert [
        row.value
        for row in parse_dcool((_row(culture="0"),), _names())
        if row.sector_key == "culture"
    ] == [Decimal("0")]
    with pytest.raises(CoolingError) as wrong:
        parse_dcool((_row(culture=raw),), _names())
    assert wrong.value.reason == reason


def test_a_missing_sector_field_and_a_duplicate_around_a_null_still_fail() -> None:
    row = _row()
    del row["industrial"]
    with pytest.raises(CoolingError) as missing:
        parse_dcool((row,), _names())
    assert missing.value.reason == "unexpected_column"
    only = dict.fromkeys((*_ORDINARY, "culture"))
    first = _row(**{**only, "industrial": 2})
    gap = _row(**{**only, "industrial": None})
    again = _row(**{**only, "industrial": 3})
    assert [row.value for row in parse_dcool((first, gap), _names())] == [Decimal(2)]
    with pytest.raises(CoolingError) as repeated:
        parse_dcool((first, gap, again), _names())
    assert repeated.value.reason == "duplicate_key"


@pytest.mark.parametrize(
    ("first", "second"),
    [("A/B", "A-B"), ("Operation Project", "operation project"), ("X", " X ")],
)
def test_two_statuses_of_one_indicator_refuse(first: str, second: str) -> None:
    """R1-DSTAT.rv1 F1: the status key is not injective; a collision refuses."""
    empty = dict.fromkeys(
        (
            "other",
            "real_estate_development",
            "sport",
            "culture",
            "health",
            "transport",
            "education",
            "hotels",
            "commercial",
            "district_cooling_service_supply",
        )
    )
    rows = (
        _row(project_status=first, **empty),
        _row(project_status=second, **{**empty, "industrial": None, "health": 6}),
    )
    with pytest.raises(CoolingError) as wrong:
        parse_dcool(rows, _names())
    assert wrong.value.reason == "project_status"


_ORDINARY = (
    "other",
    "industrial",
    "real_estate_development",
    "sport",
    "health",
    "transport",
    "education",
    "hotels",
    "commercial",
    "district_cooling_service_supply",
)


@given(
    sector=st.sampled_from(_ORDINARY),
    raw=st.one_of(
        st.none(),
        st.integers(min_value=-(10**12), max_value=10**12),
        st.text(max_size=6),
        st.booleans(),
        st.floats(allow_nan=True),
    ),
)
def test_every_ordinary_sector_cell_by_type(sector: str, raw: object) -> None:
    """R1-DCOOL.cf1 F1: null is no row, an integer is kept exactly, else sector_type."""
    if isinstance(raw, int) and not isinstance(raw, bool):
        rows = parse_dcool((_row(**{sector: raw}),), _names())
        assert [row.value for row in rows if row.sector_key == sector] == [Decimal(raw)]
    elif raw is None:
        rows = parse_dcool((_row(**{sector: raw}),), _names())
        assert [row for row in rows if row.sector_key == sector] == []
    else:
        with pytest.raises(CoolingError) as wrong:
            parse_dcool((_row(**{sector: raw}),), _names())
        assert wrong.value.reason == "sector_type"
