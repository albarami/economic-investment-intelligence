"""Native trade manifests keep their existing readers and exact decimal tokens."""

import importlib
import json
from pathlib import Path

import pytest
from custodian.tests.support.fetch_build import run_build
from custodian.tests.test_production_adapters import context


@pytest.mark.parametrize(
    "family,option",
    [
        ("baci", "stream_transport"),
        ("gravity", "gravity_stream"),
        ("atlas", "atlas_stream"),
    ],
)
def test_reviewed_native_manifest_runs_real_reader(
    tmp_path: Path, family: str, option: str
) -> None:
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    fixture = importlib.import_module(
        "custodian.tests.fixtures." + family + ".invented"
    )
    config = importlib.import_module(
        "eii_custodian.publicdata." + family + ".config"
    ).Config.from_mapping(fixture.configuration())
    row = fixture.entry()
    options = {option: fixture.stream, family + "_config": config}
    fetched = run_build(
        (row,),
        fixture.metadata,
        fixture_cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda seconds: None,
        **options,
    )
    assert fetched.failure is None
    identity = fetched.manifests[row.source_id]
    (fixture_cache / "snapshot_pins.json").write_text(json.dumps({row.key: identity}))
    build = context(fixture_cache, (row,))
    build.reviewed_selections()
    assert set(build.tables) == set(row.release_tables)
    assert build.receipts[row.key]["source_id"] == row.source_id
    assert build.tables
    # A manifest substitution must reach the native reader's own hash guard.
    path = fixture_cache / row.source_id / (identity + ".manifest.json")
    path.write_text("{}")
    error = getattr(
        importlib.import_module("eii_custodian.publicdata." + family + ".config"),
        family.title() + "Error",
    )
    with pytest.raises(error, match="manifest_hash"):
        context(fixture_cache, (row,)).reviewed_selections()


def test_investment_tables_use_reviewed_evidence_manifest_and_older_raw_page(
    tmp_path: Path, monkeypatch
) -> None:
    from custodian.tests import test_investment_build as fixture

    row = fixture._fdi_entry()
    body = fixture.dashboard_page()
    assert fixture._run(tmp_path, monkeypatch, row, {row.url: body}) == 0
    pointer, manifest, table = fixture._batch(tmp_path, row.source_id)
    raw = manifest["pages"][0]["sha256"]
    selected = pointer["manifest_sha256"]
    body2 = fixture.dashboard_page((fixture.invented_record(capex=("n", "14.5")),))
    assert fixture._run(tmp_path, monkeypatch, row, {row.url: body2}) == 0
    cache = tmp_path / "data/public_cache"
    (cache / "snapshot_pins.json").write_text(
        json.dumps({row.key: raw, row.key + "/evidence": selected})
    )
    (cache / row.key / "loadable.json").unlink()
    state = context(cache, (row,))
    state.reviewed_selections()
    assert state.tables["fdi_projects"][0]["capex_value"] == "12.5"
    assert state.tables["fdi_projects"] == table["rows"]


def test_gravity_numeric_measures_are_not_omitted_from_the_draw(tmp_path: Path) -> None:
    fixture_cache = tmp_path / "data" / "public_cache"
    fixture_cache.mkdir(parents=True)
    from custodian.tests.fixtures.gravity.invented import (
        configuration,
        entry,
        metadata,
        stream,
    )

    from eii_custodian.publicdata.assembly_reports import draw_tables
    from eii_custodian.publicdata.gravity.config import Config

    row = entry()
    outcome = run_build(
        (row,),
        metadata,
        fixture_cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda seconds: None,
        gravity_stream=stream,
        gravity_config=Config.from_mapping(configuration()),
    )
    (fixture_cache / "snapshot_pins.json").write_text(
        json.dumps({row.key: outcome.manifests[row.source_id]})
    )
    state = context(fixture_cache, (row,))
    state.reviewed_selections()
    figures = draw_tables(state)["pub_gravity_bilateral"]()
    ids = {figure.figure_id for figure in figures}
    for index, data in enumerate(state.tables["pub_gravity_bilateral"]):
        for field in ("distance", "gdp_origin", "gdp_destination"):
            if data[field] is not None:
                assert "pub_gravity_bilateral:" + str(index) + ":" + field in ids


@pytest.mark.parametrize("source", ["ilostat_qat", "wb_wdi", "imf_weo", "unctad_fdi"])
def test_benchmark_adapter_preserves_all_publisher_statuses_and_numeric_labels(
    tmp_path: Path, source: str
) -> None:
    from contextlib import contextmanager
    from dataclasses import asdict, replace

    from custodian.tests.test_benchmarks import row
    from custodian.tests.test_benchmarks_fetch import policy

    from eii_custodian.publicdata.assembly_reports import draw_tables
    from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response, StreamResponse

    p = policy(source)
    declared = next(e for e in load_registry() if e.source_id == source)
    declared = replace(
        declared,
        skip_reason="",
        publisher=p.publisher,
        landing_url=p.page,
        url=p.url,
        fetch_host="example.test",
        row_count_min=1,
        row_count_max=5,
        period_first="2020",
        period_last="2020",
        columns=(("invented", "string"),),
    )
    body = json.dumps(
        [
            asdict(replace(row(source, status), scale="1000"))
            for status in ("historical", "publisher_forecast", "unclassified")
        ]
    ).encode()

    @contextmanager
    def stream(url):
        yield StreamResponse(url, (), len(body), iter((body,)))

    result = fetch_benchmark(
        declared,
        p,
        lambda url: Response(url, b"invented-page", ()),
        stream,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
    )
    (tmp_path / "snapshot_pins.json").write_text(
        json.dumps({declared.key: result.digest})
    )
    state = context(tmp_path, (declared,))
    state.reviewed_selections()
    readers = draw_tables(state)
    assert len(readers) == 1
    figures = next(iter(readers.values()))()
    assert len(figures) == 3
    assert {figure.value for figure in figures} == {"12.50"}
    assert all(not figure.figure_id.endswith(":scale") for figure in figures)


def test_comtrade_adapter_uses_reviewed_parent_manifest_and_real_assembler(
    tmp_path: Path,
) -> None:
    from custodian.tests.fixtures.comtrade.invented import invented_entry
    from custodian.tests.test_comtrade import _clock, _ok, _sleep

    from eii_custodian.publicdata.assembly_reports import draw_tables
    from eii_custodian.publicdata.comtrade.fetch import fetch_source
    from eii_custodian.publicdata.fetch.transport import SlotSecrets

    row = invented_entry()
    result = fetch_source(
        row, tmp_path, _clock, _sleep, _ok, SlotSecrets("invented-header", "")
    )
    assert result.failure is None
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: result.digest}))
    state = context(tmp_path, (row,))
    state.reviewed_selections()
    figures = draw_tables(state)["pub_comtrade_trade"]()
    assert figures
    assert all(figure.figure_id.endswith(":value") for figure in figures)
    assert state.tables["pub_comtrade_trade"]


def test_draw_over_investment_tables(tmp_path: Path, monkeypatch) -> None:
    from custodian.tests import test_investment_build as fixture

    from eii_custodian.publicdata.assembly_io import write_record
    from eii_custodian.publicdata.assembly_reports import draw_tables
    from eii_custodian.publicdata.draw import draw

    entries = (fixture._fdi_entry(), fixture._agency_entry())
    pins = {}
    for row in entries:
        bodies = (
            {
                row.url: fixture.dashboard_page(
                    tuple(
                        fixture.invented_record(project_id=1001 + i) for i in range(12)
                    )
                )
            }
            if row.source_id == "fdi_projects"
            else fixture._agency_transport_bodies()
        )
        assert fixture._run(tmp_path, monkeypatch, row, bodies) == 0
        pointer, manifest, _table = fixture._batch(tmp_path, row.source_id)
        pins[row.key] = next(
            page["sha256"] for page in manifest["pages"] if page["url"] == row.url
        )
        pins[row.key + "/evidence"] = pointer["manifest_sha256"]
    cache = tmp_path / "data/public_cache"
    (cache / "snapshot_pins.json").write_text(json.dumps(pins))
    state = context(cache, entries)
    state.reviewed_selections()
    readers = draw_tables(state)
    assert set(readers) == {"fdi_projects", "pub_investqa_record", "pub_investqa_page"}
    assert readers["pub_investqa_page"]() == []
    fdi = readers["fdi_projects"]()
    assert {figure.figure_id for figure in fdi} == {
        "fdi_projects:" + str(index) + ":" + field
        for index in range(12)
        for field in ("capex_value", "jobs")
    }
    assert {
        figure.kind for figure in fdi if figure.figure_id.endswith(":capex_value")
    } == {"money"}
    assert {figure.kind for figure in fdi if figure.figure_id.endswith(":jobs")} == {
        "count"
    }
    # This agency contract stores heading blocks and links, with no numeric measures.
    assert readers["pub_investqa_record"]() == []
    write_record(cache, "assembly/build.json", {})
    selected = draw(readers, 17, cache / "assembly/build.json")
    assert len(selected) == 20
    assert all(figure in fdi for figure in selected)


def _agency_selected(tmp_path, monkeypatch, bodies=None):
    from custodian.tests import test_investment_build as fixture
    from custodian.tests.test_investment_bilingual import bilingual_utf8

    pages, originals = bilingual_utf8()
    if bodies:
        originals.update(bodies)
    row = fixture._agency_entry()
    assert fixture._run(tmp_path, monkeypatch, row, originals, pages=pages) == 0
    pointer, manifest, table = fixture._batch(tmp_path, row.source_id)
    cache = tmp_path / "data/public_cache"
    pins = {
        row.key: manifest["pages"][0]["sha256"],
        row.key + "/evidence": pointer["manifest_sha256"],
    }
    (cache / "snapshot_pins.json").write_text(json.dumps(pins))
    return row, cache, pointer, manifest, table


def test_agency_selected_release_writes_both_languages_and_inventory(
    tmp_path, monkeypatch
):
    row, cache, _pointer, _manifest, table = _agency_selected(tmp_path, monkeypatch)
    from eii_custodian.publicdata.investment_build import read_page_table

    page_table = read_page_table(cache / row.key / "evidence", _manifest)
    expected = page_table["page_rows"]
    assert len(expected) == 10
    assert {item["page_language"] for item in expected} == {"en", "ar"}
    assert table["schema_version"] == "pub_investqa_record.v1"
    assert all(item["extractor"] == "investqa_page_text@2" for item in expected)
    # Publish changed bytes but keep the earlier explicit reviewed selection.
    from custodian.tests import test_investment_build as fixture
    from custodian.tests.test_investment_bilingual import bilingual

    pages, bodies = bilingual()
    bodies = {
        url: body.replace(b"Invented", b"Changed") for url, body in bodies.items()
    }
    assert fixture._run(tmp_path, monkeypatch, row, bodies, pages=pages) == 0
    (cache / row.key / "loadable.json").unlink()
    state = context(cache, (row,))
    state.reviewed_selections()
    assert state.tables["pub_investqa_page"] == expected
    assert state.tables["pub_investqa_record"] == table["rows"]
    record = json.loads((cache / "assembly/reviewed_selections.json").read_bytes())
    entries = record["page_public_totals"]
    assert len(entries) == 10
    assert all(item["status"] == "not_applicable" for item in entries)
    assert all(item["reason"] == "source_only" for item in entries)


@pytest.mark.parametrize(
    "plant,check",
    [
        ("missing", "page_rows_missing"),
        ("version", "page_extractor_version"),
        ("text", "page_text_mismatch"),
        ("duplicate", "page_duplicate_key"),
        ("language", "page_language"),
    ],
)
def test_agency_assembly_rejects_tampered_page_rows(
    tmp_path, monkeypatch, plant, check
):
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot

    row, cache, pointer, manifest, table = _agency_selected(tmp_path, monkeypatch)
    from eii_custodian.publicdata.investment_build import read_page_table

    table = read_page_table(cache / row.key / "evidence", manifest)
    if plant == "missing":
        table.pop("page_rows", None)
    else:
        rows = table.setdefault("page_rows", [{}])
        if plant == "version":
            rows[0]["extractor"] = "investqa_page_text@old"
        elif plant == "text":
            rows[0]["page_text"] += " edited"
        elif plant == "duplicate":
            rows.append(dict(rows[0]))
        else:
            rows[0]["page_language"] = "ar"
    directory = cache / row.key / "evidence"
    body = json.dumps(table).encode()
    receipt = dict(
        read_snapshot(directory, manifest["page_table_snapshot_identity"]).sidecar
    )
    receipt.update(sha256=sha256_hex(body), bytes=len(body))
    snapshot = publish_snapshot(directory, "json", body, receipt)
    manifest.update(
        page_table_sha256=snapshot.sha256, page_table_snapshot_identity=snapshot.sha256
    )
    body = json.dumps(manifest).encode()
    receipt = dict(read_snapshot(directory, pointer["manifest_sha256"]).sidecar)
    receipt.update(sha256=sha256_hex(body), bytes=len(body))
    snapshot = publish_snapshot(directory, "json", body, receipt)
    (cache / "snapshot_pins.json").write_text(
        json.dumps(
            {
                row.key: manifest["pages"][0]["sha256"],
                row.key + "/evidence": snapshot.sha256,
            }
        )
    )
    with pytest.raises(AssemblyError, match=check):
        context(cache, (row,)).reviewed_selections()


def test_agency_release_contact_refusal_keeps_typed_records(tmp_path, monkeypatch):
    from custodian.tests import test_investment_build as fixture

    url = fixture.SECTOR_URL.replace("agency.invalid/", "agency.invalid/en/")
    body = (
        fixture.agency_bodies()[fixture.SECTOR_URL]
        .replace(
            b"</main>",
            ("<div>" + "invented" + "@" + "example.invalid</div></main>").encode(),
        )
        .replace(b"<body>", b'<head><meta charset="utf-8"></head><body>')
    )
    row, cache, _, manifest, records = _agency_selected(
        tmp_path, monkeypatch, {url: body}
    )
    from eii_custodian.publicdata.investment_build import read_page_table

    table = read_page_table(cache / row.key / "evidence", manifest)
    assert len(table["page_rows"]) == 9
    assert table["page_refusals"][0]["check"] == "page_contact_shape"
    assert any(item["page_url"] == url for item in records["rows"])
    state = context(cache, (row,))
    state.reviewed_selections()
    assert len(state.tables["pub_investqa_page"]) == 9
    assert any("page_contact_shape" in line for line in state.lines)
