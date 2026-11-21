"""Invented project crosswalks and a source-receipted code-only target."""

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


@pytest.mark.parametrize("missing_key_field", [False, True])
def test_csv_country_target(tmp_path: Path, missing_key_field: bool):
    c, page, row, document, path, _good = specimen(tmp_path)
    target = b"unrelated\nINV\n" if missing_key_field else b"iso3\nINV\n"
    (tmp_path / "invented-countries.csv").write_bytes(target)
    row.update(
        target_resource="invented-countries.csv", target_sha256=sha256_hex(target)
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    crosswalk = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    if missing_key_field:
        assert isinstance(crosswalk, InvestmentFailure)
        assert crosswalk.check == "crosswalk_target"
    else:
        assert not isinstance(crosswalk, InvestmentFailure), crosswalk
        spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
        result = parse_fdi(
            page.body,
            replace(spec.dashboard, crosswalk=crosswalk),
            replace(b._envelope(), page_sha256=sha256_hex(page.body)),
        )
        assert not isinstance(result, InvestmentFailure), result
        assert result[0][0]["source_country_iso3"] == "INV"


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
    assert record["mapping_coverage"]["municipality_code"] == "not mapped"
    # A different issued ID with the same name must not inherit the mapping.
    other = b.dashboard_page((b.invented_record(project_id=1002),))
    refreshed = parse_fdi(
        other, shape, replace(envelope, page_sha256=sha256_hex(other))
    )
    assert not isinstance(refreshed, InvestmentFailure), refreshed
    assert refreshed[0][0]["source_country_iso3"] is None
    assert refreshed[0][0]["mapping_coverage"]["source_country_iso3"] == "not mapped"


@pytest.mark.parametrize("refresh", ["page_only", "source_values", "issued_id"])
def test_refreshed_snapshot_keeps_batch_with_unmapped_slots(tmp_path: Path, refresh):
    """INVENTED refreshes cannot inherit any slot from the old reviewed page."""
    c, page, row, document, path, _good = specimen(tmp_path)
    targets = {
        "source_country_iso3": "INV",
        "municipality_code": "SYN-area-AA-0001",
        "place_key": "SYN-place-AA-0001",
    }
    target = json.dumps([{"iso3": targets["source_country_iso3"], **targets}]).encode()
    (tmp_path / "invented-target.yaml").write_bytes(target)
    document["mappings"] = [
        {
            **row,
            "column": column,
            "target_key": key,
            "target_resource": "invented-target.yaml",
            "target_sha256": sha256_hex(target),
        }
        for column, key in targets.items()
    ]
    path.write_text(json.dumps(document), encoding="utf-8")
    crosswalk = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert not isinstance(crosswalk, InvestmentFailure), crosswalk
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    shape = replace(spec.dashboard, crosswalk=crosswalk)
    envelope = replace(b._envelope(), page_sha256=sha256_hex(page.body))
    control = parse_fdi(page.body, shape, envelope)
    assert not isinstance(control, InvestmentFailure), control
    assert {column: control[0][0][column] for column in targets} == targets

    if refresh == "page_only":
        body = page.body + b"\n"
    elif refresh == "source_values":
        body = b.dashboard_page((b.invented_record(src_country_name="Invented Other"),))
    else:
        body = b.dashboard_page((b.invented_record(project_id=1002),))
    assert sha256_hex(body) != envelope.page_sha256
    result = parse_fdi(body, shape, replace(envelope, page_sha256=sha256_hex(body)))
    assert not isinstance(result, InvestmentFailure), result
    records, empty_coordinates = result
    assert len(records) == 1
    assert empty_coordinates == control[1]
    record = records[0]
    assert {column: record[column] for column in targets} == dict.fromkeys(targets)
    assert record["mapping_coverage"] == dict.fromkeys(targets, "not mapped")
    assert record["crosswalk_sha256"] == crosswalk.sha256
    assert record["page_sha256"] == sha256_hex(body)


def test_current_snapshot_maps_only_reviewed_issued_ids(tmp_path: Path):
    """INVENTED same-name rows and a stale mapping never borrow a current slot."""
    c, _page, row, document, path, _good = specimen(tmp_path)
    body = b.dashboard_page((b.invented_record(), b.invented_record(project_id=1002)))
    stale = {**row, "project_id": 1002}
    row["snapshot_sha256"] = sha256_hex(body)
    document["mappings"].append(stale)
    path.write_text(json.dumps(document), encoding="utf-8")
    crosswalk = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert not isinstance(crosswalk, InvestmentFailure), crosswalk
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    result = parse_fdi(
        body,
        replace(spec.dashboard, crosswalk=crosswalk),
        replace(b._envelope(), page_sha256=sha256_hex(body)),
    )
    assert not isinstance(result, InvestmentFailure), result
    records, _empty_coordinates = result
    assert len(records) == 2
    assert records[0]["source_country_iso3"] == "INV"
    assert records[0]["mapping_coverage"] == {
        "source_country_iso3": "reviewed",
        "municipality_code": "not mapped",
        "place_key": "not mapped",
    }
    assert records[1]["source_country_iso3"] is None
    assert records[1]["municipality_code"] is None
    assert records[1]["place_key"] is None
    assert records[1]["mapping_coverage"] == dict.fromkeys(
        ("source_country_iso3", "municipality_code", "place_key"), "not mapped"
    )


@pytest.mark.parametrize("digits", [8, 11])
@pytest.mark.parametrize("prefix", ["", "invented_"])
def test_review_reference_digit_runs_are_refused(tmp_path: Path, digits, prefix):
    """INVENTED identifier-shaped references are assembled only at runtime."""
    c, _page, row, document, path, good = specimen(tmp_path)
    assert not isinstance(good, InvestmentFailure), good
    row["review_reference"] = prefix + "1" * digits
    path.write_text(json.dumps(document), encoding="utf-8")
    result = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert isinstance(result, InvestmentFailure), result
    assert result.check == "crosswalk_review"


@pytest.mark.parametrize("digits", [7, 9, 10, 12])
@pytest.mark.parametrize("prefix", ["", "invented_"])
def test_review_reference_other_digit_runs_are_accepted(tmp_path: Path, digits, prefix):
    """INVENTED near-miss references stay valid; only eight and eleven refuse."""
    c, _page, row, document, path, _good = specimen(tmp_path)
    row["review_reference"] = prefix + "1" * digits
    path.write_text(json.dumps(document), encoding="utf-8")
    result = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert not isinstance(result, InvestmentFailure), result
    assert result.mappings[0].review_reference == row["review_reference"]


def invented_municipality_codes() -> bytes:
    """Code-only source shape with invented values, never the fetched extract."""
    return (
        "municipality_code,source_id,source_sha256,retrieved_utc\n"
        + f"SYN042,bnd_zone_2020,{'a' * 64},2024-01-31T15:00:00Z\n"
    ).encode()


def test_municipality_code_target_source_chain(tmp_path: Path):
    from custodian.tests.fixtures.frame.invented import invented_layer

    import eii_custodian.publicdata.investment_crosswalk as c
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    entry = next(row for row in load_registry() if row.key == "bnd_zone_2020")
    cache = tmp_path / "cache"
    payload = invented_layer("bnd_zone_2020")
    payload["features"][0]["attributes"]["MUNICIPAL_CODE"] = "SYN042"
    body = json.dumps(payload).encode()
    write_cached(cache, entry, body, retrieved_utc="2024-01-31T15:00:00Z")
    newer = json.dumps({**payload, "invented_unselected": True}).encode()
    write_cached(cache, entry, newer, retrieved_utc="2024-02-01T15:00:00Z")
    digest = c.write_municipality_codes(cache, entry, digest=sha256_hex(body))
    expected = invented_municipality_codes().replace(
        b"a" * 64, sha256_hex(body).encode()
    )
    target = cache / "review/municipality_codes.csv"
    assert target.read_bytes() == expected
    assert digest == sha256_hex(expected)
    assert not (c._REVIEW / "municipality_codes.csv").exists()


@pytest.mark.parametrize(
    ("plant", "check"),
    [
        ("control", None),
        ("absent_code", "crosswalk_target"),
        ("manufactured_key", "crosswalk_target"),
        ("names_file", "name_derived_key"),
        ("changed_byte", "crosswalk_target_hash"),
    ],
)
def test_municipality_code_target(tmp_path: Path, plant, check):
    """An invented project uses only a pinned member of the supplied code list."""
    c, page, row, document, path, _good = specimen(tmp_path)
    target = invented_municipality_codes()
    cache = tmp_path / "cache"
    (cache / "review").mkdir(parents=True)
    target_path = cache / "review/municipality_codes.csv"
    target_path.write_bytes(target)
    row.update(
        column="municipality_code",
        target_key="SYN042",
        target_resource=target_path.name,
        target_sha256=sha256_hex(target),
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    control = c.read_crosswalk(
        path, expected_sha256=sha256_hex(path.read_bytes()), cache=cache
    )
    assert not isinstance(control, InvestmentFailure), control
    assert control.mappings[0].target_key == "SYN042"
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    parsed = parse_fdi(
        page.body,
        replace(spec.dashboard, crosswalk=control),
        replace(b._envelope(), page_sha256=sha256_hex(page.body)),
    )
    assert not isinstance(parsed, InvestmentFailure), parsed
    assert parsed[0][0]["municipality_code"] == "SYN042"
    assert parsed[0][0]["mapping_coverage"]["municipality_code"] == "reviewed"

    if plant == "control":
        return
    if plant == "absent_code":
        row["target_key"] = "SYN099"
    elif plant == "manufactured_key":
        row["target_key"] = "SYN-area-AA-0001"
    elif plant == "names_file":
        # Even identical code-only bytes cannot make the names resource valid.
        (tmp_path / "municipality_names.csv").write_bytes(target)
        row["target_resource"] = "municipality_names.csv"
    else:
        target_path.write_bytes(target.replace(b"SYN042,bnd_", b"SYN099,bnd_", 1))
    path.write_text(json.dumps(document), encoding="utf-8")
    result = c.read_crosswalk(
        path, expected_sha256=sha256_hex(path.read_bytes()), cache=cache
    )
    assert isinstance(result, InvestmentFailure), result
    assert result.check == check


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


def test_crosswalk_tamper_and_changed_value_are_refused(tmp_path: Path):
    c, page, _row, _document, path, good = specimen(tmp_path)
    assert not isinstance(good, InvestmentFailure)
    digest = sha256_hex(path.read_bytes())
    path.write_text("{}", encoding="utf-8")
    assert c.read_crosswalk(path, expected_sha256=digest).check == "crosswalk_hash"
    spec = b.load_source_spec("fdi_projects", url=b.DASHBOARD_URL)
    shape = replace(spec.dashboard, crosswalk=good)
    changed = b.dashboard_page((b.invented_record(src_country_name="Invented Other"),))
    # Even a caller reusing the old envelope cannot change a mapped source value.
    envelope = replace(b._envelope(), page_sha256=sha256_hex(page.body))
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


def test_municipality_target_has_no_committed_fallback(tmp_path: Path):
    c, _page, row, document, path, _good = specimen(tmp_path)
    target = invented_municipality_codes()
    row.update(
        column="municipality_code",
        target_key="SYN042",
        target_resource="municipality_codes.csv",
        target_sha256=sha256_hex(target),
    )
    # A target beside the tracked crosswalk must never substitute for the cache.
    (tmp_path / "municipality_codes.csv").write_bytes(target)
    path.write_text(json.dumps(document))
    result = c.read_crosswalk(path, expected_sha256=sha256_hex(path.read_bytes()))
    assert isinstance(result, InvestmentFailure), result
    assert result.check == "crosswalk_target"


def test_municipality_cache_reaches_publication(tmp_path: Path, monkeypatch):
    c, page, row, document, path, _good = specimen(tmp_path)
    root = tmp_path / "run"
    cache = root / "data/public_cache"
    target = cache / "review/municipality_codes.csv"
    target.parent.mkdir(parents=True)
    target.write_bytes(invented_municipality_codes())
    row.update(
        column="municipality_code",
        target_key="SYN042",
        target_resource=target.name,
        target_sha256=sha256_hex(target.read_bytes()),
    )
    path.write_text(json.dumps(document))
    monkeypatch.setattr(c, "_REVIEW", tmp_path)
    assert b._run(root, monkeypatch, b._fdi_entry(), {b.DASHBOARD_URL: page.body}) == 0
    _, _, table = b._batch(root, "fdi_projects")
    assert table["rows"][0]["municipality_code"] == "SYN042"


def test_municipality_cache_reaches_native_assembly(tmp_path: Path, monkeypatch):
    from eii_custodian.publicdata.assembly_adapters import Production
    from eii_custodian.publicdata.assembly_native import read_investment
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    c, page, row, document, path, _good = specimen(tmp_path)
    root = tmp_path / "run"
    cache = root / "data/public_cache"
    target = cache / "review/municipality_codes.csv"
    target.parent.mkdir(parents=True)
    target.write_bytes(invented_municipality_codes())
    row.update(
        column="municipality_code",
        target_key="SYN042",
        target_resource=target.name,
        target_sha256=sha256_hex(target.read_bytes()),
    )
    path.write_text(json.dumps(document))
    monkeypatch.setattr(c, "_REVIEW", tmp_path)
    # A dropped cache argument must fail without reading the repository cache.
    monkeypatch.setattr(c, "_CACHE", tmp_path / "unused-cache")
    entry = b._fdi_entry()
    with monkeypatch.context() as publication:
        assert b._run(root, publication, entry, {b.DASHBOARD_URL: page.body}) == 0
    pointer, _, table = b._batch(root, entry.source_id)
    raw_identity = sha256_hex(page.body)
    build = Production(
        entries=(entry,),
        cache=cache,
        review=tmp_path,
        root=root,
        transport=lambda _url: pytest.fail("native assembly must stay offline"),
        clock=lambda: b.RETRIEVED,
        sleep=lambda _seconds: None,
        seed=0,
        environ={},
    )
    build.receipts[entry.key] = read_snapshot(cache / entry.key, raw_identity).sidecar

    read_investment(build, entry, raw_identity, pointer["manifest_sha256"])

    assert build.tables["fdi_projects"] == table["rows"]
    assert build.tables["fdi_projects"][0]["municipality_code"] == "SYN042"
    assert build.tables["fdi_projects"][0]["mapping_coverage"]["municipality_code"] == (
        "reviewed"
    )


@pytest.mark.parametrize("plant", ["missing", "file_symlink", "directory_symlink"])
def test_municipality_cached_target_refuses_missing_or_link(tmp_path: Path, plant):
    c, _page, row, document, path, _good = specimen(tmp_path)
    body = invented_municipality_codes()
    # Valid adjacent bytes cannot satisfy an explicitly supplied empty cache.
    adjacent = tmp_path / "municipality_codes.csv"
    adjacent.write_bytes(body)
    cache = tmp_path / "cache"
    cache.mkdir()
    review = cache / "review"
    if plant == "directory_symlink":
        review.symlink_to(tmp_path, target_is_directory=True)
    else:
        review.mkdir()
        if plant == "file_symlink":
            (review / adjacent.name).symlink_to(adjacent)
    row.update(
        column="municipality_code",
        target_key="SYN042",
        target_resource=adjacent.name,
        target_sha256=sha256_hex(body),
    )
    path.write_text(json.dumps(document))
    result = c.read_crosswalk(
        path, expected_sha256=sha256_hex(path.read_bytes()), cache=cache
    )
    assert isinstance(result, InvestmentFailure), result
    assert result.check == "crosswalk_target"


@pytest.mark.parametrize(
    "plant",
    [
        "wrong_source",
        "directory_symlink",
        "file_symlink",
        "partial_symlink",
        "source_tamper",
    ],
)
def test_municipality_code_writer_refusals(tmp_path: Path, plant):
    from custodian.tests.fixtures.frame.invented import invented_layer

    import eii_custodian.publicdata.investment_crosswalk as c
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.checks import FrameError
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    entry = next(row for row in load_registry() if row.key == "bnd_zone_2020")
    cache = tmp_path / "cache"
    body = json.dumps(invented_layer(entry.source_id)).encode()
    stored = write_cached(cache, entry, body)
    if plant == "wrong_source":
        with pytest.raises(ValueError, match=r"^municipality_codes_source$"):
            c.write_municipality_codes(
                cache, replace(entry, source_id="invented"), digest=sha256_hex(body)
            )
        return
    if plant == "source_tamper":
        stored.write_bytes(body + b" ")
        with pytest.raises(FrameError, match="snapshot_hash_mismatch"):
            c.write_municipality_codes(cache, entry, digest=sha256_hex(body))
        assert not (cache / "review/municipality_codes.csv").exists()
        return
    outside = tmp_path / "invented-untouched"
    outside.mkdir()
    sentinel = outside / "municipality_codes.csv"
    sentinel.write_bytes(b"invented sentinel")
    review = cache / "review"
    if plant == "directory_symlink":
        review.symlink_to(outside, target_is_directory=True)
    else:
        review.mkdir()
        filename = (
            "municipality_codes.csv"
            if plant == "file_symlink"
            else ".municipality_codes.csv.partial"
        )
        (review / filename).symlink_to(sentinel)
    with pytest.raises(ValueError, match=r"^municipality_codes_path$"):
        c.write_municipality_codes(cache, entry, digest=sha256_hex(body))
    assert sentinel.read_bytes() == b"invented sentinel"
