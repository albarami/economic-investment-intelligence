"""Invented counts with explicit source receipts, never real census values."""

from dataclasses import replace
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.census import census_rows, validate_tables
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.review.cache_fixture import select_fixture

REVIEW = repository_root(Path(__file__)) / "custodian/publicdata/review"


@cache
def entry(name):
    original = next(e for e in load_registry() if e.source_id == name)
    return replace(original, skip_reason="", publisher="Invented test publisher")


def test_four_census_contracts_and_keys():
    result = {}
    for source, table, key in [
        ("pop_muni", "pub_population_municipality", "municipality_code"),
        ("est_census", "pub_census_national", None),
        ("census_zone_hh", "pub_census_zone", "zone_code"),
        ("census_district_pop", "pub_census_district", "district_key"),
    ]:
        row = {
            "period": "2020",
            "indicator": "residents",
            "value": "17.0000",
            "unit": "persons",
        }
        if key:
            row[key] = "SYN-A"
        rows, ignored = census_rows(entry(source), [row], "2026-11-14T00:00:00Z", table)
        assert rows[0]["value"] == Decimal("17.0000")
        assert rows[0]["source_id"] == source
        assert "retrieved_utc" not in rows[0]
        assert ignored == []
        result[table] = rows
    validate_tables(
        result,
        {
            "municipality_code": {"SYN-A"},
            "zone_code": {"SYN-A"},
            "district_key": {"SYN-A"},
        },
    )
    result["pub_census_district"] *= 2
    with pytest.raises(FrameError, match="duplicate"):
        validate_tables(
            result,
            {
                "municipality_code": {"SYN-A"},
                "zone_code": {"SYN-A"},
                "district_key": {"SYN-A"},
            },
        )


@pytest.mark.parametrize(
    "source", ["census_2020_workbook", "est_census", "census_district_pop"]
)
def test_wrong_source_in_zone_fails(source):
    with pytest.raises(FrameError, match="release source"):
        census_rows(entry(source), [], "2026-11-14T00:00:00Z", "pub_census_zone")


def test_extra_zone_numeric_fields_are_reported():
    row = {
        "zone_code": "SYN-A",
        "period": "2020",
        "indicator": "residents",
        "value": "17",
        "unit": "persons",
        "invented_other": 23,
    }
    rows, ignored = census_rows(
        entry("census_zone_hh"), [row], "2026-11-14T00:00:00Z", "pub_census_zone"
    )
    assert ignored == ["census_zone_hh: not loaded: invented_other"]
    assert "invented_other" not in rows[0]


def test_non_count_indicator_and_wrong_unit_fail():
    row = {
        "zone_code": "SYN-A",
        "period": "2020",
        "indicator": "residents",
        "value": "17",
        "unit": "wrong",
    }
    with pytest.raises(FrameError, match="indicator/unit"):
        census_rows(
            entry("census_zone_hh"), [row], "2026-11-14T00:00:00Z", "pub_census_zone"
        )
    row.update(indicator="invented_other", unit="persons")
    with pytest.raises(FrameError, match="indicator/unit"):
        census_rows(
            entry("census_zone_hh"), [row], "2026-11-14T00:00:00Z", "pub_census_zone"
        )


def cache_fixture(tmp_path, source, payload):
    import json

    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )

    body = json.dumps(payload, sort_keys=True).encode()
    digest = sha256_hex(body)
    metadata = sidecar_for(
        source,
        digest=digest,
        nbytes=len(body),
        fetch_url=source.url,
        fetch_host=source.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=source.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(tmp_path / source.key, digest, source.extension, body, metadata)
    select_fixture(tmp_path, str(metadata["key"]), digest)
    return tmp_path / source.key / f"{digest}.{source.extension}"


def test_skipped_sources_have_empty_tables_and_named_reasons(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    entries = tuple(
        replace(e, skip_reason="SYN-disabled")
        for e in load_registry()
        if e.source_id in {"bnd_hdx", "bnd_muni_2025", "est_census"}
    )
    result = build_frame(tmp_path, entries, REVIEW)
    assert all(rows == [] for rows in result.tables.values())
    assert set(result.tables) == {
        "municipality",
        "zone",
        "district",
        "grid_cell",
        "gazetteer",
        "pub_population_municipality",
        "pub_census_national",
        "pub_census_zone",
        "pub_census_district",
    }
    assert "bnd_hdx: SYN-disabled" in result.report
    assert "bnd_muni_2025: SYN-disabled" in result.report
    assert "est_census: SYN-disabled" in result.report
    assert list(tmp_path.iterdir()) == []


def test_cache_hash_and_receipt_are_checked(tmp_path):
    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("pop_muni")
    path = cache_fixture(tmp_path, source, [])
    rows, receipt = read_cached(
        tmp_path,
        source,
        digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
    )
    assert rows == []
    assert receipt["publisher"] == "Invented test publisher"
    assert receipt["retrieved_utc"] == "2026-11-14T00:00:00Z"
    path.write_text("tampered")
    with pytest.raises(FrameError, match="hash"):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )


def test_population_column_on_geometry_and_substitution_fail():
    from eii_custodian.publicdata.frame.geometry import parse_boundaries, release_rows

    with pytest.raises(FrameError, match="geometry columns"):
        parse_boundaries([{"population": 17}], "zone")
    with pytest.raises(FrameError, match="release source"):
        release_rows([], "zone", "bnd_geob")


@pytest.mark.parametrize(
    "field", ["publisher", "title_en", "fetch_url", "retrieved_utc", "sha256"]
)
def test_cache_missing_provenance_fails(tmp_path, field):
    import json

    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("pop_muni")
    cache_fixture(tmp_path, source, [])
    path = next((tmp_path / source.key).glob("*.meta.json"))
    receipt = json.loads(path.read_text())
    del receipt[field]
    path.write_text(json.dumps(receipt))
    with pytest.raises(
        FrameError, match=rf"^{source.source_id}: snapshot_hash_mismatch$"
    ):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )


@pytest.mark.parametrize("field", ["source_id", "key", "licence_id", "licence_basis"])
def test_cache_mismatched_receipt_fails(tmp_path, field):
    import json

    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("pop_muni")
    cache_fixture(tmp_path, source, [])
    path = next((tmp_path / source.key).glob("*.meta.json"))
    receipt = json.loads(path.read_text())
    receipt[field] = "SYN-WRONG"
    path.write_text(json.dumps(receipt))
    with pytest.raises(FrameError, match="mismatch"):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )


def test_cache_missing_ambiguous_and_switched_off_fail(tmp_path):
    import json

    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("pop_muni")
    with pytest.raises(FrameError, match="snapshot_"):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )
    cache_fixture(tmp_path, source, [])
    path = next((tmp_path / source.key).glob("*.meta.json"))
    receipt = json.loads(path.read_text())
    receipt["switched_off"] = True
    path.write_text(json.dumps(receipt))
    with pytest.raises(
        FrameError, match=rf"^{source.source_id}: snapshot_hash_mismatch$"
    ):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )
    extra = path.with_name("duplicate.meta.json")
    extra.write_text(path.read_text())
    with pytest.raises(FrameError, match="snapshot_"):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )


@pytest.mark.parametrize("digest", ["a" * 63, "z" * 64])
def test_cache_malformed_hash_fails(tmp_path, digest):
    import json

    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("pop_muni")
    cache_fixture(tmp_path, source, [])
    path = next((tmp_path / source.key).glob("*.meta.json"))
    receipt = json.loads(path.read_text())
    receipt["sha256"] = digest
    path.write_text(json.dumps(receipt))
    with pytest.raises(
        FrameError, match=rf"^{source.source_id}: snapshot_hash_mismatch$"
    ):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )


def test_record_envelopes_and_unsupported_shapes():
    from eii_custodian.publicdata.frame.build import records

    row = {"SYN-field": "invented"}
    assert records([row], "SYN") == [row]
    assert records({"features": [{"attributes": row}]}, "SYN") == [row]
    assert records(
        {"features": [{"attributes": row, "geometry": "SYN-shape"}]}, "SYN"
    ) == [{**row, "geometry": "SYN-shape"}]
    for invalid in ({}, ["SYN-not-a-row"]):
        with pytest.raises(FrameError, match="unsupported source schema"):
            records(invalid, "SYN")


def test_all_skipped_frame_sources_have_named_reasons(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    names = {
        "bnd_hdx",
        "bnd_muni_2025",
        "bnd_zone_2020",
        "bnd_district_2020",
        "pop_muni",
        "est_census",
        "census_zone_sector",
        "census_zone_occ",
        "census_zone_hh",
        "census_zone_lab",
        "census_district_pop",
    }
    entries = tuple(
        replace(e, skip_reason="SYN-disabled")
        for e in load_registry()
        if e.source_id in names
    )
    result = build_frame(tmp_path, entries, REVIEW)
    assert result.report == [f"{name}: SYN-disabled" for name in sorted(names)] + [
        "frame: required geometry unavailable; dependent tables not built"
    ]


@pytest.mark.parametrize(
    "indicator,unit",
    [
        ("residents", "persons"),
        ("households", "households"),
        ("establishments", "establishments"),
        ("employees", "persons"),
    ],
)
def test_all_four_frozen_zone_counts(indicator, unit):
    row = {
        "zone_code": "SYN-A",
        "period": "2020",
        "indicator": indicator,
        "value": "17",
        "unit": unit,
    }
    rows, ignored = census_rows(
        entry("census_zone_hh"), [row], "2026-11-14T00:00:00Z", "pub_census_zone"
    )
    assert rows[0]["indicator"] == indicator
    assert rows[0]["unit"] == unit
    assert ignored == []


@pytest.mark.parametrize(
    "change,match",
    [
        ({"period": "2010"}, "period"),
        ({"value": "NaN"}, "value"),
        ({"value": "infinity"}, "value"),
        ({"value": "not numeric"}, "value"),
        ({"extra": "not numeric"}, "unexpected census column"),
    ],
)
def test_invalid_census_records_fail(change, match):
    row = {
        "zone_code": "SYN-A",
        "period": "2020",
        "indicator": "residents",
        "value": "17",
        "unit": "persons",
    }
    with pytest.raises(FrameError, match=match):
        census_rows(
            entry("census_zone_hh"),
            [{**row, **change}],
            "2026-11-14T00:00:00Z",
            "pub_census_zone",
        )


def test_census_missing_fields_date_and_disabled_source_fail():
    source = entry("census_zone_hh")
    with pytest.raises(FrameError, match="missing census columns"):
        census_rows(source, [{}], "2026-11-14T00:00:00Z", "pub_census_zone")
    with pytest.raises(FrameError, match="missing retrieval date"):
        census_rows(source, [], "", "pub_census_zone")
    for changed in (
        replace(source, skip_reason="SYN-disabled"),
        replace(source, source_id="invented_wrong_source"),
        replace(source, release_tables=()),
    ):
        with pytest.raises(FrameError, match="release source"):
            census_rows(changed, [], "2026-11-14T00:00:00Z", "pub_census_zone")


def test_release_table_unknown_district_and_missing_table_fail():
    tables = {
        name: []
        for name in (
            "pub_population_municipality",
            "pub_census_national",
            "pub_census_zone",
            "pub_census_district",
        )
    }
    known = {"municipality_code": set(), "zone_code": set(), "district_key": set()}
    row = {
        "district_key": "SYN-MISSING",
        "period": "2020",
        "indicator": "residents",
        "value": "17",
        "unit": "persons",
    }
    tables["pub_census_district"], _ = census_rows(
        entry("census_district_pop"),
        [row],
        "2026-11-14T00:00:00Z",
        "pub_census_district",
    )
    with pytest.raises(FrameError, match="unknown geography key"):
        validate_tables(tables, known)
    tables["pub_census_district"][0]["planted"] = "SYN-extra"
    with pytest.raises(FrameError, match="census columns"):
        validate_tables(tables, known)
    del tables["pub_population_municipality"]
    with pytest.raises(FrameError, match="missing table"):
        validate_tables(tables, known)


def test_cache_preserves_published_decimal_digits(tmp_path):
    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("pop_muni")
    body = b'[{"value":0.1234567890123456789}]'
    digest = sha256_hex(body)
    metadata = sidecar_for(
        source,
        digest=digest,
        nbytes=len(body),
        fetch_url=source.url,
        fetch_host=source.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=source.publisher,
        source_modified="",
        row_count=1,
        terms_sha256="",
    )
    commit_pair(tmp_path / source.key, digest, source.extension, body, metadata)
    select_fixture(tmp_path, str(metadata["key"]), digest)
    rows, _ = read_cached(
        tmp_path,
        source,
        digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
    )
    assert rows[0]["value"] == Decimal("0.1234567890123456789")


def test_confirmed_population_mapping_and_inventory():
    from eii_custodian.publicdata.frame.mapping import inspect_source

    payload = [
        {
            "year": "2020",
            "municipality": "Invented municipality",
            "lbldy": "بلدية تجريبية",
            "indicator": "residents",
            "lmw_shr": "سكان تجريبيون",
            "count": 17,
        }
    ]
    result = inspect_source("pop_muni", payload, {"residents": "residents"})
    assert result.rows == [
        {
            "period": "2020",
            "municipality_name": "Invented municipality",
            "indicator": "residents",
            "value": 17,
            "unit": "persons",
        }
    ]
    assert result.inventory == {
        "municipality": ("Invented municipality",),
        "lbldy": ("بلدية تجريبية",),
        "indicator": ("residents",),
        "lmw_shr": ("سكان تجريبيون",),
    }
    assert result.reason == ""


@pytest.mark.parametrize(
    "field", ["year", "municipality", "lbldy", "indicator", "lmw_shr", "count"]
)
@pytest.mark.parametrize("change", ["missing", "renamed", "unknown", "type"])
def test_confirmed_field_changes_refuse_by_name(field, change):
    from eii_custodian.publicdata.frame.mapping import inspect_source

    row = {
        "year": "2020",
        "municipality": "Invented municipality",
        "lbldy": "تجريبي",
        "indicator": "residents",
        "lmw_shr": "تجريبي",
        "count": 17,
    }
    if change == "missing":
        del row[field]
    elif change == "renamed":
        row["SYN-renamed"] = row.pop(field)
    elif change == "unknown":
        row["SYN-extra"] = 23
        field = "SYN-extra"
    else:
        row[field] = None
    with pytest.raises(FrameError, match=field):
        inspect_source("pop_muni", [row])


@pytest.mark.parametrize(
    "source",
    [
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_zone_hh",
        "census_zone_occ",
        "census_zone_lab",
        "census_zone_sector",
        "census_district_pop",
    ],
)
def test_unconfirmed_nested_fields_are_not_guessed(source):
    from eii_custodian.publicdata.frame.mapping import inspect_source

    with pytest.raises(FrameError, match="rings"):
        inspect_source(
            source,
            {
                "count": 1,
                "features": [
                    {
                        "attributes": {"SYN-unconfirmed": 17},
                        "geometry": {"SYN-unconfirmed": []},
                    }
                ],
            },
        )


def test_utility_inventory_includes_every_token_without_mapping_values():
    from eii_custodian.publicdata.frame.mapping import inspect_source

    for source in ("util_elec", "util_water"):
        result = inspect_source(
            source,
            [
                {"year": "2020", "zone_number": token, "value": 17}
                for token in ("SYN-Z", "SYN-Y", "SYN-Z")
            ],
        )
        assert result.inventory == {"zone_number": ("SYN-Y", "SYN-Z")}
        assert result.rows == []
        assert result.reason == "inventory_only: utility figures belong to S2-T03"


def test_unknown_population_indicator_preserves_inventory_and_skips():
    from eii_custodian.publicdata.frame.mapping import inspect_source

    result = inspect_source(
        "pop_muni",
        [
            {
                "year": "2020",
                "municipality": "Invented",
                "lbldy": "تجريبي",
                "indicator": "SYN-unknown",
                "lmw_shr": "تجريبي",
                "count": 17,
            }
        ],
    )
    assert result.rows == []
    assert "unreviewed_indicator: SYN-unknown" == result.reason
    assert result.inventory["indicator"] == ("SYN-unknown",)


def test_cache_inventory_runs_before_missing_frame_return(tmp_path, monkeypatch):
    import socket

    from eii_custodian.publicdata.frame.build import build_frame

    names = {
        "bnd_hdx",
        "bnd_muni_2025",
        "util_elec",
        "util_water",
        "pop_muni",
        "census_zone_hh",
    }
    entries = tuple(
        replace(e, skip_reason="SYN-disabled") if e.source_id == "bnd_hdx" else e
        for e in load_registry()
        if e.source_id in names
    )
    for source in entries:
        if source.source_id.startswith("util_"):
            cache_fixture(
                tmp_path,
                source,
                [{"year": "2020", "zone_number": "SYN-Z", "value": 17}],
            )
        elif source.source_id == "pop_muni":
            cache_fixture(
                tmp_path,
                source,
                [
                    {
                        "year": "2020",
                        "municipality": "Invented",
                        "lbldy": "تجريبي",
                        "indicator": "SYN-unknown",
                        "lmw_shr": "تجريبي",
                        "count": 17,
                    }
                ],
            )
        elif source.source_id == "census_zone_hh":
            cache_fixture(
                tmp_path,
                source,
                __import__(
                    "custodian.tests.fixtures.frame.invented",
                    fromlist=["invented_layer"],
                ).invented_layer("census_zone_hh"),
            )
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "socket", forbidden)
    result = build_frame(tmp_path, entries, REVIEW)
    assert result.inventory["util_elec"]["zone_number"] == ("SYN-Z",)
    assert result.inventory["util_water"]["zone_number"] == ("SYN-Z",)
    assert result.inventory["pop_muni"]["municipality"] == ("Invented",)
    assert any(
        "census_zone_hh: map_geometry_not_used" in line for line in result.report
    )
    assert any("util_elec: 1 unlisted zone numbers" in line for line in result.report)
    assert all(not rows for rows in result.tables.values())
    assert result.sources["pop_muni"]["method"] == "frame.v1"
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_metadata_links_never_become_geometry():
    from custodian.tests.fixtures.frame.invented import invented_geob_metadata

    from eii_custodian.publicdata.frame.mapping import inspect_source

    result = inspect_source("bnd_geob", [invented_geob_metadata()])
    assert result.rows == []
    assert result.inventory == {}
    assert (
        result.reason
        == "metadata_only: missing zone tokens and geometry; download links are not geometry"
    )


def test_all_confirmed_source_fields_refuse_changes():
    from custodian.tests.fixtures.frame.invented import invented_geob_metadata

    from eii_custodian.publicdata.frame.mapping import inspect_source

    for source, row in [
        ("bnd_geob", invented_geob_metadata()),
        ("util_elec", {"year": "2020", "zone_number": "SYN-Z", "value": 17}),
        ("util_water", {"year": "2020", "zone_number": "SYN-Z", "value": 17}),
    ]:
        for field in row:
            for change in ("missing", "rename", "type"):
                bad = dict(row)
                if change == "missing":
                    del bad[field]
                elif change == "rename":
                    bad["SYN-renamed"] = bad.pop(field)
                else:
                    bad[field] = None
                with pytest.raises(FrameError, match=field):
                    inspect_source(source, [bad])
        with pytest.raises(FrameError, match="SYN-extra"):
            inspect_source(source, [{**row, "SYN-extra": "invented"}])
    for payload, match in [(None, "list"), ([None], "object")]:
        with pytest.raises(FrameError, match=match):
            inspect_source("util_elec", payload)
    with pytest.raises(FrameError, match="no confirmed cache shape"):
        inspect_source("bnd_hdx", [])


@pytest.mark.parametrize(
    "source",
    [
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_zone_hh",
        "census_zone_occ",
        "census_zone_lab",
        "census_zone_sector",
        "census_district_pop",
    ],
)
def test_layer_envelope_field_changes_refuse(source):
    from eii_custodian.publicdata.frame.mapping import inspect_source

    for payload, match in [
        ({}, "count"),
        ({"count": 1}, "features"),
        ({"count": True, "features": []}, "count"),
        ({"count": 1, "features": {}}, "features"),
        ({"count": 1, "features": [], "SYN-extra": 0}, "SYN-extra"),
        ({"count": 1, "features": [{"attributes": {}}]}, "geometry"),
        ({"count": 1, "features": [{"geometry": {}}]}, "attributes"),
        ({"count": 1, "features": [{"attributes": [], "geometry": {}}]}, "attributes"),
        ({"count": 1, "features": [{"attributes": {}, "geometry": []}]}, "geometry"),
    ]:
        with pytest.raises(FrameError, match=match):
            inspect_source(source, payload)


def test_unfetched_boundary_shape_never_accepts_guessed_fields(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    with pytest.raises(FrameError, match=r"^bnd_hdx: snapshot_path_invalid$"):
        build_frame(
            tmp_path,
            (entry("bnd_hdx"), entry("bnd_muni_2025")),
            REVIEW,
        )
    assert list(tmp_path.iterdir()) == []


def test_raw_sources_all_skip_reasons_and_early_return(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    names = {
        "bnd_hdx",
        "bnd_muni_2025",
        "bnd_zone_2020",
        "bnd_district_2020",
        "pop_muni",
        "est_census",
        "census_zone_sector",
        "census_zone_occ",
        "census_zone_hh",
        "census_zone_lab",
        "census_district_pop",
    }
    entries = tuple(
        replace(e, skip_reason="SYN-disabled")
        for e in load_registry()
        if e.source_id in names
    )
    result = build_frame(tmp_path, entries, REVIEW)
    assert result.report == [f"{name}: SYN-disabled" for name in sorted(names)] + [
        "frame: required geometry unavailable; dependent tables not built"
    ]
    assert all(rows == [] for rows in result.tables.values())
    assert set(result.tables) == {
        "municipality",
        "zone",
        "district",
        "grid_cell",
        "gazetteer",
        "pub_population_municipality",
        "pub_census_national",
        "pub_census_zone",
        "pub_census_district",
    }
    assert result.sources == {}
    result = build_frame(tmp_path, (), REVIEW)
    assert result.report == [
        "frame: required geometry unavailable; dependent tables not built"
    ]


@pytest.mark.parametrize("level", ["municipality", "zone", "district", "gazetteer"])
def test_raw_hdx_admission_for_each_table(tmp_path, level):
    from eii_custodian.publicdata.frame.build import build_frame

    hdx = entry("bnd_hdx")
    hdx = replace(
        hdx, release_tables=tuple(t for t in hdx.release_tables if t != level)
    )
    with pytest.raises(
        FrameError, match=f"bnd_hdx: invalid release source for {level}"
    ):
        build_frame(tmp_path, (hdx, entry("bnd_muni_2025")), REVIEW)


def test_census_release_columns_match_dat_contract():
    for source, table, key in [
        ("pop_muni", "pub_population_municipality", "municipality_code"),
        ("est_census", "pub_census_national", None),
        ("census_zone_hh", "pub_census_zone", "zone_code"),
        ("census_district_pop", "pub_census_district", "district_key"),
    ]:
        record = {
            "period": "2020",
            "indicator": "residents",
            "value": 17,
            "unit": "persons",
        }
        expected = {"period", "indicator", "value", "unit", "source_id"}
        if key:
            record[key] = "SYN-A"
            expected.add(key)
        rows, _ = census_rows(entry(source), [record], "2026-11-14T00:00:00Z", table)
        assert set(rows[0]) == expected


def test_every_confirmed_source_is_inspected_with_receipt(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    layer_names = {
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_zone_hh",
        "census_zone_occ",
        "census_zone_lab",
        "census_zone_sector",
        "census_district_pop",
    }
    confirmed = layer_names | {"pop_muni", "util_elec", "util_water"}
    entries = tuple(
        e
        for e in load_registry()
        if e.source_id in confirmed | {"lic_active", "bnd_geob"}
    )
    for source in entries:
        if source.source_id in layer_names:
            payload = {"count": 0, "features": []}
        elif source.source_id == "bnd_geob":
            continue
        elif source.source_id in confirmed:
            payload = []
        else:
            continue
        cache_fixture(tmp_path, source, payload)
    result = build_frame(tmp_path, entries, REVIEW)
    assert set(result.inventory) == confirmed
    assert set(result.sources) == confirmed
    for source in layer_names:
        assert any(
            line.startswith(source + ": map_geometry_not_used:")
            for line in result.report
        )
    assert "bnd_geob" not in result.sources
    assert not (tmp_path / "bnd_geob").exists()
    assert result.inventory["pop_muni"] == {
        "municipality": (),
        "lbldy": (),
        "indicator": (),
        "lmw_shr": (),
    }


@pytest.mark.parametrize("unavailable", ["bnd_hdx"])
@pytest.mark.parametrize("mode", ["missing", "skipped"])
def test_each_required_licensed_boundary_stops_build(tmp_path, unavailable, mode):
    from eii_custodian.publicdata.frame.build import build_frame

    entries = [entry("bnd_hdx"), entry("bnd_muni_2025")]
    if mode == "missing":
        entries = [e for e in entries if e.source_id != unavailable]
    else:
        entries = [
            replace(e, skip_reason="SYN-disabled") if e.source_id == unavailable else e
            for e in entries
        ]
    result = build_frame(tmp_path, tuple(entries), REVIEW)
    assert (
        result.report[-1]
        == "frame: required geometry unavailable; dependent tables not built"
    )
    assert all(not rows for rows in result.tables.values())
    assert result.sources == {}
    assert list(tmp_path.iterdir()) == []


def test_nested_fields_are_closed_and_nulls_preserved():
    from copy import deepcopy

    from custodian.tests.fixtures.frame.invented import invented_layer

    from eii_custodian.publicdata.frame.layers import layer_rows

    for source in (
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_zone_sector",
        "census_zone_occ",
        "census_zone_hh",
        "census_zone_lab",
        "census_district_pop",
    ):
        payload = invented_layer(source)
        assert layer_rows(source, payload) == [payload["features"][0]["attributes"]]
        for field in payload["features"][0]["attributes"]:
            bad = deepcopy(payload)
            del bad["features"][0]["attributes"][field]
            with pytest.raises(FrameError, match=field):
                layer_rows(source, bad)
        bad = deepcopy(payload)
        bad["features"][0]["attributes"]["SYN_unknown"] = 0
        with pytest.raises(FrameError, match="SYN_unknown"):
            layer_rows(source, bad)
        bad = deepcopy(payload)
        bad["count"] = 2
        with pytest.raises(FrameError, match="count"):
            layer_rows(source, bad)
    assert (
        layer_rows("census_zone_hh", invented_layer("census_zone_hh"))[0]["Qatari"]
        is None
    )


def test_cached_zip_is_verified_before_parsing(tmp_path):
    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame.build import read_cached

    source = entry("bnd_hdx")
    body = b"invented corrupt ZIP"
    digest = sha256_hex(body)
    receipt = sidecar_for(
        source,
        digest=digest,
        nbytes=len(body),
        fetch_url=source.url,
        fetch_host=source.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=source.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(tmp_path / source.key, digest, source.extension, body, receipt)
    select_fixture(tmp_path, str(receipt["key"]), digest)
    assert (
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )[0]
        == body
    )
    (tmp_path / source.key / f"{digest}.{source.extension}").write_bytes(b"tampered")
    with pytest.raises(
        FrameError, match=rf"^{source.source_id}: snapshot_hash_mismatch$"
    ):
        read_cached(
            tmp_path,
            source,
            digest=reviewed_selections(tmp_path).get((source).key, "0" * 64),
        )


@pytest.mark.parametrize(
    "population_mode",
    [
        "normal",
        "whitespace",
        "unmapped_en",
        "unmapped_ar",
        "bad_key",
        "missing_source_spelling",
    ],
)
@pytest.mark.parametrize("census_mode", ["active", "skipped", "missing"])
def test_raw_build_uses_licensed_geometry_and_writes_derived_review(
    tmp_path, monkeypatch, census_mode, population_mode
):
    import csv
    import json
    import socket

    from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer

    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame.build import build_frame

    cache_dir, review, output = (
        tmp_path / name for name in ("cache", "review", "output")
    )
    review.mkdir()
    (review / "zones_without_districts.csv").write_text("zone_code,reason\n")
    arabic = "اسم تجريبي"
    (review / "municipality_names.csv").write_text(
        f"name,municipality_code\nInvented municipality,9\n{arabic},9\nDifferent invented spelling,9\nInvented municipality,9\n"
    )
    if population_mode == "missing_source_spelling":
        path = review / "municipality_names.csv"
        path.write_text(path.read_text().replace("Different invented spelling,9\n", ""))
    if population_mode == "bad_key":
        with (review / "municipality_names.csv").open("a") as handle:
            handle.write("Unused invented,SYN-absent\n")
    (review / "zone_crosswalk.csv").write_text(
        "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,census_district_pop,census_zone_hh,status\n42,42,42,42,42,42,matched\n"
    )
    (review / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nresidents,residents\n"
    )
    (review / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n"
    )
    (review / "greater_doha_municipalities.csv").write_text(
        "name\nDifferent invented spelling\n"
    )
    for name in ("showcase_gazetteer.yaml", "flagship_candidates.yaml"):
        (review / name).write_text(json.dumps([{"place_key": "SYN-" + name}]))
    names = (
        "bnd_hdx",
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_district_pop",
        "census_zone_hh",
        "pop_muni",
    )
    entries = tuple(entry(name) for name in names)
    if census_mode == "skipped":
        entries = tuple(
            replace(e, skip_reason="SYN-disabled")
            if e.source_id == "census_district_pop"
            else e
            for e in entries
        )
    elif census_mode == "missing":
        entries = tuple(e for e in entries if e.source_id != "census_district_pop")
    for source in entries:
        if source.source_id == "bnd_hdx":
            body = invented_archive()
        elif source.source_id == "pop_muni":
            body = json.dumps(
                [
                    {
                        "year": "2020",
                        "municipality": {
                            "whitespace": "  Invented\u00a0  municipality\t",
                            "unmapped_en": "Unmapped invented",
                        }.get(population_mode, "Invented municipality"),
                        "lbldy": "اسم مجهول"
                        if population_mode == "unmapped_ar"
                        else "اسم تجريبي",
                        "indicator": "residents",
                        "lmw_shr": "اسم تجريبي",
                        "count": 17,
                    }
                ]
            ).encode()
        else:
            body = json.dumps(invented_layer(source.source_id)).encode()
        digest = sha256_hex(body)
        receipt = sidecar_for(
            source,
            digest=digest,
            nbytes=len(body),
            fetch_url=source.url,
            fetch_host=source.fetch_host,
            retrieved_utc="2026-11-14T00:00:00Z",
            publisher=source.publisher,
            source_modified="",
            row_count=None,
            terms_sha256="",
        )
        commit_pair(cache_dir / source.key, digest, source.extension, body, receipt)
        select_fixture(cache_dir, str(receipt["key"]), digest)
    before = {
        p: p.read_bytes()
        for root in (cache_dir, review)
        for p in root.rglob("*")
        if p.is_file()
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("network attempted")

    monkeypatch.setattr(socket, "socket", forbidden)
    if population_mode in {
        "unmapped_en",
        "unmapped_ar",
        "bad_key",
        "missing_source_spelling",
    }:
        expected = {
            "unmapped_en": "pop_muni: municipality: 1 unmapped spellings",
            "unmapped_ar": "pop_muni: lbldy: 1 unmapped spellings",
            "bad_key": "municipality_names: unknown_key",
            "missing_source_spelling": "municipality source spelling: layer_name_en: unmapped",
        }[population_mode]
        with pytest.raises(FrameError) as error:
            build_frame(cache_dir, entries, review, output)
        assert str(error.value) == expected
        if population_mode not in {"bad_key", "missing_source_spelling"}:
            assert (output / "build_report.json").exists()
        return
    result = build_frame(cache_dir, entries, review, output)
    assert [line for line in result.report if line.startswith("frame:")] == [
        "frame: partial; place points remain"
    ]
    assert not any("cache_shape_unconfirmed" in line for line in result.report)
    for filename in ("showcase_gazetteer.yaml", "flagship_candidates.yaml"):
        assert (
            f"gazetteer: source point pending S2-T06: SYN-{filename}" in result.report
        )
    assert not any("language unconfirmed" in line for line in result.report)
    assert result.report[-1] == "frame: partial; place points remain"
    assert result.tables["pub_population_municipality"] == [
        {
            "municipality_code": "9",
            "period": "2020",
            "indicator": "residents",
            "value": Decimal(17),
            "unit": "persons",
            "source_id": "pop_muni",
        }
    ]
    assert result.sources["pop_muni"]["retrieved_utc"] == "2026-11-14T00:00:00Z"
    assert result.tables["municipality"][0]["municipality_code"] == "9"
    assert result.tables["municipality"][0]["source_id"] == "bnd_hdx"
    assert {row["zone_code"] for row in result.tables["grid_cell"]} == {"42"}
    assert {row["district_key"] for row in result.tables["grid_cell"]} == {
        "SYN042042042"
    }
    assert {row["resolution"] for row in result.tables["grid_cell"]} == {9}
    if census_mode == "active":
        assert result.tables["pub_census_district"] == [
            {
                "district_key": "SYN042042042",
                "period": "2020",
                "indicator": "residents",
                "value": Decimal(17),
                "unit": "persons",
                "source_id": "census_district_pop",
            }
        ]
    else:
        assert result.tables["pub_census_district"] == []
    assert result.tables["pub_census_zone"] == []
    assert (
        "census_zone_hh: not loaded: Qatari; nationality split not declared"
        in result.report
    )
    if census_mode == "active":
        assert (
            result.sources["census_district_pop"]["retrieved_utc"]
            == "2026-11-14T00:00:00Z"
        )
    with (output / "municipality_names.csv").open() as handle:
        assert list(csv.DictReader(handle)) == [
            {
                "hdx_code": "SYN042",
                "municipality_code": "9",
                "name_en": "Invented municipality",
                "name_ar": "اسم تجريبي",
                "layer_name_en": "Different invented spelling",
                "layer_name_ar": "اسم تجريبي",
            }
        ]
    with (output / "proposed_zone_crosswalk.csv").open() as handle:
        proposed = list(csv.DictReader(handle))
    assert any(row["bnd_hdx"] == "42" for row in proposed)
    assert any(row["bnd_zone_2020"] == "42" for row in proposed)
    assert (output / "proposed_population_indicators.csv").exists()
    assert sum("zone_without_district" in line for line in result.report) == 1
    assert sum("point_without_base_cell" in line for line in result.report) == 3
    assert before == {
        p: p.read_bytes()
        for root in (cache_dir, review)
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize("where", ["review", "cache", "review/child", "cache/child"])
def test_generated_review_cannot_overwrite_inputs(tmp_path, where):
    from eii_custodian.publicdata.frame.build import build_frame

    with pytest.raises(FrameError, match="review output overlaps inputs"):
        build_frame(tmp_path / "cache", (), tmp_path / "review", tmp_path / where)


@pytest.mark.parametrize("table", ["municipality", "zone", "district", "gazetteer"])
def test_raw_archive_release_admission_for_each_table(tmp_path, table):
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.frame.live import build_live_frame

    source = entry("bnd_hdx")
    source = replace(
        source, release_tables=tuple(t for t in source.release_tables if t != table)
    )
    with pytest.raises(FrameError, match=f"invalid release source for {table}"):
        build_live_frame(
            tmp_path, (source,), tmp_path, None, FrameResult({}, [], {}), {}
        )


def test_all_raw_geometry_columns_have_licensed_lineage():
    from custodian.tests.fixtures.frame.invented import invented_frame

    from eii_custodian.publicdata.frame.live import licensed_rows

    for kind, boundaries, key in zip(
        ("municipality", "zone", "district"),
        invented_frame(),
        ("municipality_code", "zone_code", "district_key"),
        strict=True,
    ):
        rows = licensed_rows(boundaries, kind)
        assert len(rows) == len(boundaries)
        for row, boundary in zip(rows, boundaries, strict=True):
            assert set(row) == {
                key,
                "municipality_code",
                "name_en",
                "name_ar",
                "geometry",
                "source_id",
            }
            assert row[key] == boundary.key
            assert row["name_en"] == boundary.name_en
            assert row["name_ar"] == boundary.name_ar
            assert row["geometry"].equals(boundary.geometry)
            assert row["source_id"] == "bnd_hdx"


def test_confirmed_portal_licences_do_not_hide_missing_adapters(tmp_path):
    from eii_custodian.publicdata.frame.build import inspect_cache

    names = {"zone_population", "census_hh_type_2020"}
    entries = tuple(e for e in load_registry() if e.source_id in names)
    result = inspect_cache(tmp_path, entries, REVIEW, reviewed_selections(tmp_path))
    for name in names:
        assert f"{name}: cache_shape_unconfirmed; no mapping attempted" in result.report
    assert all(not rows for rows in result.tables.values())
    assert result.sources == {}


@pytest.fixture
def measure_build(tmp_path):
    """Every integration case uses the production raw-cache entry point."""
    import json

    from custodian.tests.fixtures.frame.invented import invented_archive, invented_layer

    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame.build import build_frame

    arabic = "اسم تجريبي"
    review = tmp_path / "review"
    review.mkdir()
    (review / "zones_without_districts.csv").write_text("zone_code,reason\n")
    for filename, header in (
        (
            "municipality_names.csv",
            f"name,municipality_code\nDifferent invented spelling,9\nInvented municipality,9\n{arabic},9",
        ),
        (
            "zone_crosswalk.csv",
            "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,census_district_pop,census_zone_hh,census_zone_occ,census_zone_sector,census_zone_lab,status\n42,42,42,42,42,42,42,42,42,matched",
        ),
        ("district_layer_aliases.csv", "zone_code,layer_name,hdx_name"),
        ("greater_doha_municipalities.csv", "name\nDifferent invented spelling"),
    ):
        (review / filename).write_text(header + "\n")
    for filename in ("showcase_gazetteer.yaml", "flagship_candidates.yaml"):
        (review / filename).write_text("[]")
    names = (
        "bnd_hdx",
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_district_pop",
        "census_zone_sector",
        "census_zone_occ",
        "census_zone_hh",
        "census_zone_lab",
    )
    payloads = {n: invented_layer(n) for n in names if n != "bnd_hdx"}
    payloads["census_zone_sector"]["features"][0]["attributes"][
        "Total_Economic_active___15"
    ] = 16
    payloads["census_zone_hh"]["features"][0]["attributes"].update(
        Qatari=5, Non_Qatari=12
    )

    def run(change=None, omit=(), altered=None):
        if change:
            change(payloads)
        entries = tuple(
            (altered or {}).get(n, entry(n)) for n in names if n not in omit
        )
        cache_dir = tmp_path / "cache"
        for source in entries:
            body = (
                invented_archive()
                if source.source_id == "bnd_hdx"
                else json.dumps(payloads[source.source_id]).encode()
            )
            digest = sha256_hex(body)
            receipt = sidecar_for(
                source,
                digest=digest,
                nbytes=len(body),
                fetch_url=source.url,
                fetch_host=source.fetch_host,
                retrieved_utc="2026-11-14T00:00:00Z",
                publisher=source.publisher,
                source_modified="",
                row_count=None,
                terms_sha256="",
            )
            commit_pair(cache_dir / source.key, digest, source.extension, body, receipt)
            select_fixture(cache_dir, str(receipt["key"]), digest)
        return build_frame(cache_dir, entries, review)

    return run


def test_r4_measures_and_receipt_lineage(measure_build):
    result = measure_build()
    assert result.tables["pub_census_zone"] == [
        {
            "zone_code": "42",
            "period": "2020",
            "indicator": "employees",
            "value": Decimal(16),
            "unit": "persons",
            "source_id": "census_zone_sector",
        },
        {
            "zone_code": "42",
            "period": "2020",
            "indicator": "households",
            "value": Decimal(17),
            "unit": "households",
            "source_id": "census_zone_hh",
        },
    ]
    assert result.tables["pub_census_district"][0]["value"] == Decimal(17)
    for row in result.tables["pub_census_zone"] + result.tables["pub_census_district"]:
        receipt = result.sources[row["source_id"]]
        assert receipt["retrieved_utc"] == "2026-11-14T00:00:00Z"
        assert len(receipt["sha256"]) == 64
        assert receipt["publisher"] == "Invented test publisher"
        assert receipt["licence_basis"]
        assert receipt["method"] == "frame.v1"


@pytest.mark.parametrize(
    "plant",
    [
        "off_by_one",
        "sector_null",
        "occupation_null",
        "missing_zone",
        "extra_zone",
        "missing_sector",
        "missing_occ",
    ],
)
def test_r4_employee_crosscheck_fails_closed(measure_build, plant, tmp_path):
    if plant == "extra_zone":
        import csv

        path = tmp_path / "review" / "zone_crosswalk.csv"
        with path.open() as handle:
            columns = next(csv.reader(handle))
        with path.open("a") as handle:
            csv.DictWriter(handle, fieldnames=columns).writerow(
                {
                    "zone_code": "43",
                    "census_zone_occ": "43",
                    "status": "absent_in_source",
                }
            )
    from copy import deepcopy

    def change(payloads):
        sector = payloads["census_zone_sector"]["features"][0]["attributes"]
        occ = payloads["census_zone_occ"]
        if plant == "off_by_one":
            sector["Total_Economic_active___15"] += 1
        elif plant == "sector_null":
            sector["Total_Economic_active___15"] = None
        elif plant == "occupation_null":
            occ["features"][0]["attributes"]["Professionals"] = None
        elif plant == "missing_zone":
            occ.update(count=0, features=[])
        elif plant == "extra_zone":
            extra = deepcopy(occ["features"][0])
            extra["attributes"]["ZONE_NO"] = 43
            occ["features"].append(extra)
            occ["count"] = 2

    omit = {
        "missing_sector": ("census_zone_sector",),
        "missing_occ": ("census_zone_occ",),
    }.get(plant, ())
    with pytest.raises(FrameError, match=r"census_zone_sector.*census_zone_occ"):
        measure_build(change, omit=omit)


@pytest.mark.parametrize("field", ["Qatari", "Non_Qatari"])
def test_r4_null_household_has_no_total(measure_build, field):
    def change(payloads):
        payloads["census_zone_hh"]["features"][0]["attributes"][field] = None

    result = measure_build(change)
    assert [r["indicator"] for r in result.tables["pub_census_zone"]] == ["employees"]


def test_r4_matching_null_zones_and_null_district_emit_no_rows(measure_build):
    from eii_custodian.publicdata.frame.layers import COUNTS

    def change(payloads):
        for source in ("census_zone_sector", "census_zone_occ", "census_district_pop"):
            row = payloads[source]["features"][0]["attributes"]
            for field in COUNTS[source]:
                row[field] = None

    result = measure_build(change)
    assert [r["indicator"] for r in result.tables["pub_census_zone"]] == ["households"]
    assert result.tables["pub_census_district"] == []


def test_r4_zero_counts_are_present_and_other_is_not_employment(measure_build):
    from eii_custodian.publicdata.frame.layers import COUNTS

    def change(payloads):
        for source in ("census_zone_sector", "census_zone_occ", "census_zone_hh"):
            row = payloads[source]["features"][0]["attributes"]
            for field in COUNTS[source]:
                row[field] = 0
        payloads["census_zone_occ"]["features"][0]["attributes"].update(
            Other=71, Pop_Aged__above__15=71
        )

    result = measure_build(change)
    assert [r["value"] for r in result.tables["pub_census_zone"]] == [
        Decimal(0),
        Decimal(0),
    ]


def test_r4_inventory_has_exact_non_audit_reasons(measure_build):
    from eii_custodian.publicdata.frame.layers import COUNTS

    result = measure_build()
    expected = []
    for source, fields, reason in (
        (
            "census_zone_sector",
            COUNTS["census_zone_sector"][1:],
            "sector breakdown; not an audit count",
        ),
        (
            "census_zone_occ",
            ("Pop_Aged__above__15",),
            "people aged above 15; not residents",
        ),
        (
            "census_zone_occ",
            COUNTS["census_zone_occ"][1:],
            "occupation breakdown; not an audit count",
        ),
        ("census_zone_lab", COUNTS["census_zone_lab"], "unit not stated"),
    ):
        for field in fields:
            expected.append(f"{source}: not loaded: {field}; not_applicable; {reason}")
            assert field in result.inventory[source]
    assert sorted(
        line for line in result.report if "; not_applicable;" in line
    ) == sorted(expected)
    for field in ("Qatari", "Non_Qatari"):
        assert (
            f"census_zone_hh: not loaded: {field}; nationality split not declared"
            in result.report
        )
    assert not any(
        "nationality_group" in row for row in result.tables["pub_census_zone"]
    )


def test_r4_no_second_fixture_assembler():
    from eii_custodian.publicdata.frame import build

    assert not hasattr(build, "build_staged_frame")


def test_r4_boundary_without_release_tables_is_refused_before_cache(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    source = replace(entry("bnd_hdx"), release_tables=())
    with pytest.raises(FrameError, match="bnd_hdx: invalid release source"):
        build_frame(tmp_path, (source,), REVIEW)


def test_r4_declaring_a_split_does_not_invent_release_columns(measure_build):
    result = measure_build(
        altered={
            "census_zone_hh": replace(
                entry("census_zone_hh"), public_splits=("nationality",)
            )
        }
    )
    assert [r["indicator"] for r in result.tables["pub_census_zone"]] == [
        "employees",
        "households",
    ]
    for field in ("Qatari", "Non_Qatari"):
        assert (
            f"census_zone_hh: not loaded: {field}; Public nationality split requires a release split schema; not loaded"
            in result.report
        )


@pytest.mark.parametrize(
    "field",
    [
        "Legislators_Senior_Officials_An",
        "Professionals",
        "Technicians_And_Associate_Profe",
        "Clerks",
        "Service_Workers_And_Shop_And_Ma",
        "Skilled_Agricultural_And_Fisher",
        "Craft_And_Related_Trades_Worker",
        "Plant_And_Machine_Operators_And",
        "Elementary_Occupations",
    ],
)
def test_r4_every_named_occupation_contributes(measure_build, field):
    # Names come from the lead's note, independently of the implementation slice.
    def change(payloads):
        payloads["census_zone_occ"]["features"][0]["attributes"][field] += 1

    with pytest.raises(FrameError, match=r"census_zone_sector.*census_zone_occ"):
        measure_build(change)
