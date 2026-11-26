"""Hand-made rows for design cooling capacity by municipality and sector."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.singles_entries import dcool_entry

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
    assert all(row.indicator == "capacity" for row in rows)


def test_unpivot_uses_the_municipality_map_and_drops_geometry() -> None:
    rows = parse_dcool((_row(),), _names())
    by_sector = {row.sector_key: row for row in rows}
    assert by_sector["culture"].value == Decimal("5")
    assert by_sector["culture"].municipality_code == "1"
    assert by_sector["industrial"].value == Decimal("2")
    assert by_sector["culture"].indicator == "capacity"
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
            (_row(), _row(project_status="Other invented status", industrial=4)),
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
