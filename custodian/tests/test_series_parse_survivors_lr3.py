"""LR3 exact validation text, partial dates and locale-independent CSV reads."""

import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_frame_live_survivors import _ascii_locale
from custodian.tests.test_public_series import fixture, series_cache

from eii_custodian.publicdata.series import parse


def _whole_text(found: object, literal: str) -> None:
    assert str(found) == literal


def _wrong_type(value: object) -> Any:
    return value


def test_source_must_contain_rows_whole_refusal(tmp_path):
    entry, digest = series_cache(tmp_path, "util_elec", _wrong_type({"SYN": 1}))
    with pytest.raises(ValueError) as caught:
        parse.selected_source(tmp_path, entry, digest)
    _whole_text(caught.value, "source must contain rows")


@pytest.mark.parametrize(
    "case,literal",
    [
        ("columns", "unconfirmed source columns"),
        ("mapping", "incomplete or duplicate field mapping"),
        ("row", "unknown or missing source fields: SYN-extra,invented_value"),
        ("type", "source field type mismatch"),
        ("table", "table identity comes from the source registry"),
    ],
)
def test_parse_rows_whole_refusals(tmp_path, case, literal):
    entry, _, _ = fixture(tmp_path)
    rows = [{"invented_value": "SYN-value"}]
    mapping = {"invented_value": "value"}
    if case == "columns":
        entry = replace(entry, columns=())
    elif case == "mapping":
        mapping = {}
    elif case == "row":
        rows = [{"SYN-extra": "SYN-value"}]
    elif case == "type":
        rows = _wrong_type([{"invented_value": 3}])
    else:
        entry = replace(entry, source_id="wage_occ")
        mapping = {"invented_value": "table_code"}
    with pytest.raises(ValueError) as caught:
        parse.parse_rows(entry, rows, mapping)
    _whole_text(caught.value, literal)


@pytest.mark.parametrize(
    "case,literal",
    [
        ("registry", "util_elec registry fields: SYN-a,SYN-b,value,zone_number"),
        ("row", "util_elec source fields: SYN-a,SYN-b,value,zone_number"),
    ],
)
def test_confirmed_fields_whole_refusals(tmp_path, case, literal):
    entry, _ = series_cache(tmp_path, "util_elec", [])
    if case == "registry":
        entry = replace(
            entry,
            columns=(("year", "string"), ("SYN-a", "string"), ("SYN-b", "string")),
        )
        row = {"year": "2025", "zone_number": "SYN-zone", "value": 3}
    else:
        row = {"year": "2025", "SYN-a": "SYN", "SYN-b": "SYN"}
    with pytest.raises(ValueError) as caught:
        parse.confirmed_rows(entry, [row])
    _whole_text(caught.value, literal)


@pytest.mark.parametrize("month", [1, 12])
def test_undated_year_accepts_boundary_month(month):
    assert parse.source_period("lic_cancelled", None, month) is None


def test_missing_month_accepts_present_valid_year():
    assert parse.source_period("lic_cancelled", "2025", None) is None


@pytest.mark.parametrize(
    "year,month,literal",
    [
        ("SYN", None, "lic_cancelled sn_llg: four digits required"),
        (None, 0, "lic_cancelled shhr_llg: integer month required"),
    ],
)
def test_partial_date_whole_refusals(year, month, literal):
    with pytest.raises(ValueError) as caught:
        parse.source_period("lic_cancelled", year, month)
    _whole_text(caught.value, literal)


def _review_root(tmp_path: Path, monkeypatch) -> Path:
    module = tmp_path / "src/eii_custodian/publicdata/series/parse.py"
    module.parent.mkdir(parents=True)
    review = tmp_path / "publicdata/review"
    review.mkdir(parents=True)
    monkeypatch.setattr(parse, "__file__", str(module))
    return review


def test_country_csv_preserves_quoted_carriage_returns_and_utf8(tmp_path, monkeypatch):
    review = _review_root(tmp_path, monkeypatch)
    for name, rows in (
        ("country_iso3.csv", [("name_en", "iso3"), ("SYN-référence\rname", "SYN")]),
        ("country_aliases.csv", [("name_en", "iso3"), ("SYN-écho\rname", "SYN")]),
    ):
        with (review / name).open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)
    with _ascii_locale():
        result = parse.country_crosswalk()
    assert result == {"SYN-référence\rname": "SYN", "SYN-écho\rname": "SYN"}


@pytest.mark.parametrize(
    "alias,literal",
    [
        ("SYN-alias,,SYN-invalid", "country alias: invalid unattributed reason"),
        ("SYN-alias,SYN-missing,", "country alias: absent reference code"),
        ("SYN-reference,SYN,", "country alias: repeated country name"),
    ],
)
def test_country_alias_whole_refusals(tmp_path, monkeypatch, alias, literal):
    review = _review_root(tmp_path, monkeypatch)
    (review / "country_iso3.csv").write_text("name_en,iso3\nSYN-reference,SYN\n")
    (review / "country_aliases.csv").write_text("name_en,iso3,reason\n" + alias + "\n")
    with pytest.raises(ValueError) as caught:
        parse.country_crosswalk()
    _whole_text(caught.value, literal)


@pytest.mark.parametrize(
    "source,value,literal",
    [
        (
            "cus_imp_2019",
            "SYN",
            "cus_imp_2019 hs8: expected eight digits; lengths require review",
        ),
        (
            "cus_imp_2025",
            "SYN",
            "cus_imp_2025 harmonized_system_code: integer code required",
        ),
    ],
)
def test_customs_code_whole_refusals(source, value, literal):
    with pytest.raises(ValueError) as caught:
        parse.customs_code(source, value)
    _whole_text(caught.value, literal)


def test_default_municipality_review_and_whole_refusal(tmp_path, monkeypatch):
    review = _review_root(tmp_path, monkeypatch)
    path = review / "municipality_aliases.json"
    row = {
        "source_name_ar": "SYN-alias",
        "frame_name_ar": "SYN-frame",
        "reviewer_role": "SYN-reviewer",
        "review_date": "2026-11-17",
    }
    path.write_text(json.dumps([row]))
    frame = (parse.Municipality("SYN-code", "SYN-frame"),)
    assert parse.municipality_names(frame) == {
        "SYN-frame": "SYN-code",
        "SYN-alias": "SYN-code",
    }
    row["reviewer_role"] = ""
    path.write_text(json.dumps([row]))
    with pytest.raises(ValueError) as caught:
        parse.municipality_names(frame)
    _whole_text(caught.value, "municipality alias: missing review or frame name")
