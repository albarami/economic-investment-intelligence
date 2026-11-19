"""Invented identifier crosswalks; no fetched name or value is a fixture."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests import test_investment_build as b

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.investment_contracts import InvestmentFailure
from eii_custodian.publicdata.investment_parse import parse_fdi


def specimen(tmp_path: Path):
    """Write only invented targets, with deliberately pending target reviews."""
    import eii_custodian.publicdata.investment_crosswalk as c

    page = b.made_dashboard()
    target = b'[{"iso3":"INV","human_reviewed":false}]'
    (tmp_path / "invented-countries.yaml").write_bytes(target)
    row = {
        "source_id": "fdi_projects",
        "snapshot_sha256": sha256_hex(page.body),
        "key_basis": "source_issued_identifier",
        "project_id": 1001,
        "project_key": b._independent_key(page.tokens[0]),
        "column": "source_country_iso3",
        "target_key": "INV",
        "target_resource": "invented-countries.yaml",
        "target_sha256": sha256_hex(target),
        "review_role": "lead",
        "review_date": "2026-11-19",
        "review_reference": "invented-review",
    }
    document = {"schema_version": "fdi_crosswalks.v1", "mappings": [row]}
    path = tmp_path / "fdi_crosswalks.yaml"
    path.write_text(json.dumps(document), encoding="utf-8")
    digest = sha256_hex(path.read_bytes())
    crosswalk = c.read_crosswalk(path, expected_sha256=digest)
    return c, page, row, document, path, crosswalk


def test_review_covers_both_sides_and_identifier_lookup(tmp_path: Path):
    _c, page, row, _document, path, crosswalk = specimen(tmp_path)
    assert not isinstance(crosswalk, InvestmentFailure)
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    shape = replace(spec.dashboard, crosswalk=crosswalk)
    envelope = replace(b._envelope(), page_sha256=sha256_hex(page.body))
    result = parse_fdi(page.body, shape, envelope)
    assert not isinstance(result, InvestmentFailure), result
    record = result[0][0]
    assert record["source_country_iso3"] == "INV"
    assert record["municipality_code"] is None
    assert record["place_key"] is None
    assert record["source_country"] == "Inventedland"
    assert record["project_key"] == row["project_key"]
    assert record["crosswalk_sha256"] == sha256_hex(path.read_bytes())
    assert record["mapping_coverage"]["municipality_code"] == "unmapped"
    # A different issued ID with the same name must not inherit the mapping.
    other = b.dashboard_page((b.invented_record(project_id=1002),))
    refused = parse_fdi(other, shape, replace(envelope, page_sha256=sha256_hex(other)))
    assert getattr(refused, "check", "") == "crosswalk_snapshot"


@pytest.mark.parametrize(
    ("plant", "check"),
    [
        ("review_role", "crosswalk_review"),
        ("review_date", "crosswalk_review"),
        ("review_reference", "crosswalk_review"),
        ("unknown_target", "crosswalk_target"),
        ("missing_target", "crosswalk_target"),
        ("target_hash", "crosswalk_target_hash"),
        ("duplicate", "crosswalk_duplicate"),
        ("conflict", "crosswalk_duplicate"),
        ("name_key", "name_derived_key"),
        ("hashed_name_key", "name_derived_key"),
        ("name_map_path", "name_derived_key"),
        ("restricted_content", "crosswalk_schema"),
        ("identifier", "identifier_shape"),
        ("missing_key_field", "crosswalk_target"),
    ],
)
def test_crosswalk_plants(tmp_path: Path, plant: str, check: str):
    c, _page, _row, document, path, good = specimen(tmp_path)
    assert not isinstance(good, InvestmentFailure)
    broken = copy.deepcopy(document)
    item = broken["mappings"][0]
    if plant.startswith("review_"):
        item[plant] = ""
    elif plant == "unknown_target":
        item["target_key"] = "UNKNOWN"
    elif plant == "missing_target":
        (tmp_path / item["target_resource"]).unlink()
    elif plant == "target_hash":
        item["target_sha256"] = "ef" * 32
    elif plant in {"duplicate", "conflict"}:
        broken["mappings"].append(dict(item))
        if plant == "conflict":
            broken["mappings"][1]["target_key"] = "OTHER"
    elif plant == "name_key":
        item["project_id"] = "invented-name"
    elif plant == "hashed_name_key":
        item["key_basis"] = "hash_of_matched_name"
    elif plant == "name_map_path":
        item["target_resource"] = "municipality_names.csv"
    elif plant == "restricted_content":
        item["source_name"] = "Invented fetched text"
    elif plant == "identifier":
        item["project_id"] = int("1" * 8)
    elif plant == "missing_key_field":
        body = b'[{"unrelated":"INV"}]'
        (tmp_path / item["target_resource"]).write_bytes(body)
        item["target_sha256"] = sha256_hex(body)
        item["target_key"] = "None"
    path.write_text(json.dumps(broken), encoding="utf-8")
    result = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert getattr(result, "check", "") == check


def test_crosswalk_tamper_stale_source_and_changed_value(tmp_path: Path):
    c, page, _row, _document, path, good = specimen(tmp_path)
    assert not isinstance(good, InvestmentFailure)
    digest = sha256_hex(path.read_bytes())
    path.write_text("{}", encoding="utf-8")
    assert c.read_crosswalk(path, expected_sha256=digest).check == "crosswalk_hash"
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    shape = replace(spec.dashboard, crosswalk=good)
    envelope = replace(b._envelope(), page_sha256="ef" * 32)
    assert parse_fdi(page.body, shape, envelope).check == "crosswalk_snapshot"
    changed = b.dashboard_page((b.invented_record(src_country_name="Invented Other"),))
    # Even a caller reusing the old envelope cannot change a mapped source value.
    envelope = replace(envelope, page_sha256=sha256_hex(page.body))
    assert parse_fdi(changed, shape, envelope).check == "crosswalk_source_value"


@pytest.mark.parametrize("column", ["country_iso3", "municipality_code", "place_key"])
def test_legacy_name_lookup_is_refused(column: str):
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    shape = replace(spec.dashboard, **{column: {"Invented Bay": "invented"}})
    result = parse_fdi(b.dashboard_page(), shape, b._envelope())
    assert getattr(result, "check", "") == "name_derived_key"


@pytest.mark.parametrize(
    "column,field,key",
    [
        ("municipality_code", "municipality_code", "SYN-area-AA-0001"),
        ("place_key", "place_key", "SYN-place-AA-0001"),
    ],
)
def test_all_target_columns_and_publication_path(
    tmp_path: Path, monkeypatch, column, field, key
):
    c, page, row, document, path, _good = specimen(tmp_path)
    target = json.dumps(
        [{field: key, "arabic_review": "pending native review"}]
    ).encode()
    (tmp_path / "invented-target.yaml").write_bytes(target)
    document["mappings"].append(
        {
            **row,
            "column": column,
            "target_key": key,
            "target_resource": "invented-target.yaml",
            "target_sha256": sha256_hex(target),
        }
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(c, "_REVIEW", tmp_path)
    assert (
        b._run(
            tmp_path / "run", monkeypatch, b._fdi_entry(), {b.DASHBOARD_URL: page.body}
        )
        == 0
    )
    _, _, table = b._batch(tmp_path / "run", "fdi_projects")
    assert table["rows"][0][column] == key
    assert table["rows"][0]["source_country_iso3"] == "INV"
    assert table["rows"][0]["lat"] == "10.123456789012"


def test_crosswalk_configuration_refuses_name_map_path(tmp_path: Path, monkeypatch):
    import yaml

    import eii_custodian.publicdata.investment_build as build

    document = yaml.safe_load(build._PAGES.read_text())
    document["sources"]["fdi_projects"]["municipality_code"] = "municipality_names.csv"
    path = tmp_path / "invented-pages.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    monkeypatch.setattr(build, "_PAGES", path)
    assert (
        build.load_source_spec("fdi_projects", url=b.DASHBOARD_URL).check
        == "name_derived_key"
    )


def test_absent_source_identifier_is_refused(tmp_path: Path):
    c, page, _row, document, path, _good = specimen(tmp_path)
    document["mappings"][0]["project_id"] = 1002
    path.write_text(json.dumps(document), encoding="utf-8")
    crosswalk = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert not isinstance(crosswalk, InvestmentFailure)
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    result = parse_fdi(
        page.body,
        replace(spec.dashboard, crosswalk=crosswalk),
        replace(b._envelope(), page_sha256=sha256_hex(page.body)),
    )
    assert result.check == "crosswalk_source_value"


@pytest.mark.parametrize(
    "plant", ["target_changed_during_read", "crosswalk_removed_during_read"]
)
def test_crosswalk_integrity_change_during_read_is_refused(
    tmp_path: Path, monkeypatch, plant
):
    c, _page, _row, _document, path, _good = specimen(tmp_path)
    digest = sha256_hex(path.read_bytes())
    original = c.read_yaml

    def changed(target):
        document = original(target)
        if target.name == "invented-countries.yaml":
            if plant == "target_changed_during_read":
                target.write_bytes(b'[{"iso3":"INV","changed":true}]')
            else:
                path.unlink()
        return document

    monkeypatch.setattr(c, "read_yaml", changed)
    result = c.read_crosswalk(path, expected_sha256=digest)
    expected = (
        "crosswalk_target_hash"
        if plant == "target_changed_during_read"
        else "crosswalk_hash"
    )
    assert getattr(result, "check", "") == expected
