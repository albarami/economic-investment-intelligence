"""Native trade manifests keep their existing readers and exact decimal tokens."""

import importlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.support.fetch_build import run_build
from custodian.tests.test_production_adapters import context
from hypothesis import given, settings
from hypothesis import strategies as st


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
    assert_agency_release(state.tables["pub_investqa_record"], table["rows"])
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
    assert any(item["page_url"] == url for item in state.tables["pub_investqa_record"])
    assert any("page_contact_shape" in line for line in state.lines)


AGENCY_COLUMNS = set(
    "record_type record_key parent_key sequence title_en title_ar reference "
    "link_url activity_keys parameter_key value unit duration_months as_stated "
    "period page_url source_id".split()
)


def assert_agency_release(released, cached):
    """Document 03 section 7.3; cache paragraphs cannot be release columns."""
    released_types = {
        ("page", "sector"): "sector",
        ("page", "opportunity"): "opportunity",
        ("page", "incentive"): "incentive",
        ("page", "law"): "law",
        ("block", "opportunity"): "opportunity",
        ("block", "setup_step"): "setup_step",
    }
    expected = [
        (
            released_types[(grain, item["record_type"])],
            item["page_url"],
            item["title"] if grain == "page" else item["heading"],
        )
        for item in cached
        for grain in ("page" if item["ordinal"] is None else "block",)
        if item.get("language") == "en"
        and (grain, item["record_type"]) in released_types
    ]
    assert sorted(
        (row["record_type"], row["page_url"], row["title_en"]) for row in released
    ) == sorted(expected)
    for row in released:
        assert set(row) == AGENCY_COLUMNS
        assert row["record_type"] in {
            "sector",
            "opportunity",
            "incentive",
            "setup_step",
            "law",
        }
        source = next(
            item
            for item in cached
            if item["page_url"] == row["page_url"]
            and (item["title"] or item["heading"]) == row["title_en"]
        )
        if row["title_ar"] is not None:
            candidates = [
                item
                for item in cached
                if item["page_url"] == source["page_url"]
                and item["record_type"] == source["record_type"]
            ]
            counterparts = [
                item
                for item in cached
                if item["page_url"] == source["page_url"].replace("/en/", "/ar/")
                and item.get("language") == "ar"
                and item["record_type"] == source["record_type"]
            ]
            counterpart = counterparts[candidates.index(source)]
            field = "title" if counterpart["ordinal"] is None else "heading"
            assert row["title_ar"] == counterpart[field]
        assert row["source_id"] == source["source_id"]
        assert row["sequence"] == (
            source["ordinal"] if row["record_type"] == "setup_step" else None
        )
        for field in (
            "parameter_key",
            "value",
            "unit",
            "duration_months",
            "as_stated",
            "period",
        ):
            assert row[field] is None


def _projection_input(tmp_path, monkeypatch):
    from custodian.tests.test_investment_bilingual import bilingual_utf8

    from eii_custodian.publicdata.investment_build import read_page_table

    _, bodies = bilingual_utf8()
    for url in tuple(bodies):
        if "/ar/" in url:
            alternate = url.replace("/ar/", "/en/")
            bodies[url] = bodies[url].replace(
                b"</head>",
                f'<link rel="alternate" hreflang="en" href="{alternate}"></head>'.encode(),
            )
    entry, cache, _, manifest, table = _agency_selected(tmp_path, monkeypatch, bodies)
    pages = read_page_table(cache / entry.key / "evidence", manifest)["page_rows"]
    rows = [
        {key: value for key, value in row.items() if key != "join_key"}
        for row in table["rows"]
    ]
    return rows, pages


def _project(rows, pages, activities=None):
    from eii_custodian.publicdata.assembly_native import project_agency_records

    lines = []
    result = project_agency_records(rows, pages, activities or {}, lines)
    return result, lines


def test_agency_projection_exact_columns_pairing_and_omissions(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    from copy import deepcopy

    before = deepcopy((rows, pages))
    result, lines = _project(rows, pages)
    assert_agency_release(result, rows)
    assert (rows, pages) == before
    assert len({row["record_key"] for row in result}) == len(result)
    assert {
        ("page" if row["ordinal"] is None else "block", row["record_type"])
        for row in rows
        if row["language"] == "en"
    } >= {
        ("page", "sector"),
        ("page", "opportunity"),
        ("page", "incentive"),
        ("page", "law"),
        ("block", "opportunity"),
        ("block", "setup_step"),
    }
    assert all(row["title_ar"] for row in result)
    for row in result:
        page = next(page for page in pages if page["page_url"] == row["page_url"])
        assert row["record_key"].startswith(page["page_key"])
        assert "/en/" in row["page_url"]
    parameters = [row for row in rows if row["record_type"] == "incentive_parameter"]
    assert len(lines) == len(parameters)
    for row in parameters:
        assert (
            f"OMITTED pub_investqa_record {row['page_url']} check=parameter_kind reason=unclassified"
            in lines
        )
    assert not any(row["record_type"] == "incentive_parameter" for row in result)


def test_agency_projection_activity_mapping_and_unmapped(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    plain, _ = _project(rows, pages)
    target = next(row for row in plain if row["record_type"] == "sector")
    mapped, _ = _project(
        rows, pages, {target["record_key"]: "invented_beta;invented_alpha"}
    )
    assert (
        next(row for row in mapped if row["record_key"] == target["record_key"])[
            "activity_keys"
        ]
        == "invented_beta;invented_alpha"
    )
    assert all(row["activity_keys"] is None for row in plain)
    assert all(
        row["activity_keys"] is None
        for row in mapped
        if row["record_key"] != target["record_key"]
    )


def test_agency_projection_unmatched_block_structure(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    removed = next(
        row
        for row in rows
        if row["language"] == "ar"
        and row["record_type"] == "setup_step"
        and "/setup/" in row["page_url"]
    )
    rows.remove(removed)
    assert any(
        row["page_url"] == removed["page_url"] and row["record_type"] == "setup_step"
        for row in rows
    )
    result, lines = _project(rows, pages)
    affected = [
        row
        for row in result
        if row["record_type"] == "setup_step"
        and row["page_url"] == removed["page_url"].replace("/ar/", "/en/")
    ]
    assert affected
    assert all(row["title_ar"] is None for row in affected)
    assert all(
        f"NULLED pub_investqa_record {row['record_key']} {row['page_url']} check=title_ar reason=pair_unmatched"
        in lines
        for row in affected
    )


def test_agency_projection_unresolved_key_is_reported(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    rows[0]["page_url"] = "https://agency.invalid/"
    url = rows[0]["page_url"]
    result, lines = _project(rows, pages)
    assert not any(row["page_url"] == url for row in result)
    assert (
        f"OMITTED pub_investqa_record {url} check=record_key reason=unresolved" in lines
    )


@pytest.mark.parametrize(
    "plant,code",
    [
        ("unknown", "unknown_field"),
        ("title", "missing_title"),
        ("type", "type_refused"),
        ("collision", "key_collision"),
    ],
)
def test_agency_projection_refuses_one_changed_input(
    tmp_path, monkeypatch, plant, code
):
    from eii_custodian.publicdata.assembly import AssemblyError

    rows, pages = _projection_input(tmp_path, monkeypatch)
    if plant == "unknown":
        rows[0]["unexpected"] = None
    elif plant == "title":
        target = next(
            row
            for row in rows
            if row["ordinal"] is None
            and row["record_type"] == "sector"
            and row["language"] == "en"
        )
        target["title"] = None
    elif plant == "type":
        rows[0]["record_type"] = "sector_block"
    else:
        pages.append({**pages[0], "page_url": pages[0]["page_url"] + "/different"})
    with pytest.raises(AssemblyError, match="^assembly_agency_record_" + code + "$"):
        _project(rows, pages)


def test_agency_projected_rows_reach_draw(tmp_path, monkeypatch):
    from eii_custodian.publicdata.assembly_reports import draw_tables

    entry, cache, _, _, table = _agency_selected(tmp_path, monkeypatch)
    state = context(cache, (entry,))
    state.reviewed_selections()
    assert_agency_release(state.tables["pub_investqa_record"], table["rows"])
    assert any(
        row["sequence"] is not None for row in state.tables["pub_investqa_record"]
    )
    assert draw_tables(state)["pub_investqa_record"]() == []


def test_agency_projection_lineage_reachable(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    entry, cache, pointer, manifest, table = _agency_selected(tmp_path, monkeypatch)
    state = context(cache, (entry,))
    state.reviewed_selections()
    assert_agency_release(state.tables["pub_investqa_record"], table["rows"])
    row = state.tables["pub_investqa_record"][0]
    original = next(
        item for item in table["rows"] if item["page_url"] == row["page_url"]
    )
    assert row["source_id"] == entry.source_id
    assert state.table_sources["pub_investqa_record"] == {entry.key}
    receipt = state.receipts[entry.key]
    assert receipt["source_id"] == row["source_id"]
    for field in (
        "publisher",
        "licence_id",
        "licence_basis",
        "decision_record",
        "terms_sha256",
        "terms_url",
    ):
        assert receipt[field] == original[field]
    page = next(
        item
        for item in state.tables["pub_investqa_page"]
        if item["page_url"] == row["page_url"]
    )
    assert page["page_sha256"] == original["page_sha256"]
    assert page["retrieved_on"] == original["retrieved_utc"][:10]
    raw = read_snapshot(cache / entry.key, page["page_sha256"])
    assert raw.sidecar["retrieved_utc"] == original["retrieved_utc"]
    assert original["provenance"] == "public"
    # The table-source binding retains the selected immutable evidence files.
    cached = read_snapshot(
        cache / entry.key / "evidence", manifest["table_snapshot_identity"]
    )
    assert state.files[cached.path.relative_to(cache).as_posix()] == cached.sha256
    archived = json.loads(cached.body)["rows"]
    archived_original = next(
        item for item in archived if item["record_key"] == original["record_key"]
    )
    assert archived_original["provenance"] == original["provenance"]
    snapshot = read_snapshot(cache / entry.key / "evidence", pointer["manifest_sha256"])
    assert state.files[snapshot.path.relative_to(cache).as_posix()] == snapshot.sha256
    stored_manifest = json.loads(snapshot.body)
    assert stored_manifest["parser_method"] == original["method"]
    assert stored_manifest["parser_version"] == original["method_version"]


def test_agency_projection_columns_match_document():
    from custodian.tests.test_draw_contract_columns import contract_columns

    from eii_custodian.publicdata.assembly_native import _AGENCY_COLUMNS

    assert set(_AGENCY_COLUMNS) == AGENCY_COLUMNS
    assert AGENCY_COLUMNS == contract_columns()["pub_investqa_record"] | {"source_id"}


def test_agency_projection_opportunity_parent(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    sector = next(row for row in rows if row["record_type"] == "sector")
    block = next(
        row
        for row in rows
        if row["page_url"] == sector["page_url"] and row["ordinal"] is not None
    )
    block["record_type"] = "opportunity"
    result, _ = _project(rows, pages)
    page = next(row for row in result if row["record_type"] == "sector")
    child = next(
        row
        for row in result
        if row["page_url"] == page["page_url"] and row["record_type"] == "opportunity"
    )
    assert child["parent_key"] == page["record_key"]


def test_agency_projection_rejects_page_block_key_collision(tmp_path, monkeypatch):
    from eii_custodian.publicdata.assembly import AssemblyError

    rows, pages = _projection_input(tmp_path, monkeypatch)
    source = next(
        row
        for row in rows
        if row["record_type"] == "opportunity"
        and row["ordinal"] is not None
        and row["language"] == "en"
    )
    page = next(page for page in pages if page["page_url"] == source["page_url"])
    other = next(
        page
        for page in pages
        if page["page_language"] == "en" and page["page_url"] != source["page_url"]
    )
    other["page_key"] = f"{page['page_key']}_{source['ordinal']}"
    with pytest.raises(AssemblyError, match=r"^assembly_agency_record_key_collision$"):
        _project(rows, pages)


@given(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_/",
        min_size=1,
        max_size=60,
    )
)
def test_agency_release_key_normalization_is_idempotent(path):
    from eii_custodian.publicdata.investment_agency import release_page_key

    key = release_page_key("https://agency.invalid/" + path)
    assert release_page_key(key) == key
    assert not key.startswith("_") and not key.endswith("_")
    assert "__" not in key


def test_agency_projection_copies_titles_without_editing(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    english = next(
        row
        for row in rows
        if row["record_type"] == "sector" and row["language"] == "en"
    )
    arabic = next(
        row
        for row in rows
        if row["record_type"] == "sector" and row["language"] == "ar"
    )
    english["title"] = "  Invented sector title  "
    arabic["title"] = "  عنوان قطاع مخترع  "
    result, _ = _project(rows, pages)
    sector = next(row for row in result if row["record_type"] == "sector")
    assert sector["title_en"] == english["title"]
    assert sector["title_ar"] == arabic["title"]


def test_agency_projection_refuses_unmapped_paragraph_kind(tmp_path, monkeypatch):
    from eii_custodian.publicdata import assembly_native as native
    from eii_custodian.publicdata.assembly import AssemblyError

    rows, pages = _projection_input(tmp_path, monkeypatch)
    monkeypatch.delitem(native._AGENCY_TYPES, ("block", "sector_block"))
    with pytest.raises(AssemblyError, match=r"^assembly_agency_record_type_refused$"):
        _project(rows, pages)


@pytest.mark.parametrize(
    "kind", ["setup", "sector_block", "law_block", "block", "incentive_parameter"]
)
def test_agency_projection_omits_only_closed_container_and_paragraph_kinds(
    tmp_path, monkeypatch, kind
):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    source = next(
        row
        for row in rows
        if row["language"] == "en" and (row["ordinal"] is None) == (kind == "setup")
    )
    source = {**source, "record_type": kind}
    result, lines = _project([source], pages)
    assert result == []
    assert lines == (
        [
            f"OMITTED pub_investqa_record {source['page_url']} check=parameter_kind reason=unclassified"
        ]
        if kind == "incentive_parameter"
        else []
    )


def test_agency_projection_missing_english_records_is_reported(tmp_path, monkeypatch):
    rows, pages = _projection_input(tmp_path, monkeypatch)
    result, lines = _project([row for row in rows if row["language"] == "ar"], pages)
    assert result == []
    for url in {row["page_url"] for row in rows if row["language"] == "ar"}:
        assert (
            f"OMITTED pub_investqa_record {url} check=record_key reason=unresolved"
            in lines
        )


def test_agency_projection_never_guesses_an_arabic_alternate(tmp_path, monkeypatch):
    rows, _pages = _projection_input(tmp_path, monkeypatch)
    source = next(
        row for row in rows if row["language"] == "ar" and row["ordinal"] is None
    )
    result, lines = _project([source], [])
    assert result == []
    assert lines == [
        f"OMITTED pub_investqa_record {source['page_url']} check=record_key reason=unresolved"
    ]


@pytest.mark.parametrize("ordinal", [True, "1", 0, -1])
def test_agency_projection_refuses_invalid_source_ordinal(
    tmp_path, monkeypatch, ordinal
):
    from eii_custodian.publicdata.assembly import AssemblyError

    rows, pages = _projection_input(tmp_path, monkeypatch)
    source = next(
        row
        for row in rows
        if row["record_type"] == "setup_step" and row["language"] == "en"
    )
    source["ordinal"] = ordinal
    with pytest.raises(AssemblyError, match=r"^assembly_agency_record_type_refused$"):
        _project(rows, pages)


def test_agency_projection_reads_activity_keys_from_spec(tmp_path, monkeypatch):
    from dataclasses import replace

    from eii_custodian.publicdata import investment_build

    entry, cache, _, _, _ = _agency_selected(tmp_path, monkeypatch)
    original = investment_build.load_source_spec
    key = "en_sectors_invented_textiles"

    def mapped(*args, **kwargs):
        return replace(
            original(*args, **kwargs),
            activity_keys={key: "invented_beta;invented_alpha"},
        )

    monkeypatch.setattr(investment_build, "load_source_spec", mapped)
    state = context(cache, (entry,))
    state.reviewed_selections()
    result = state.tables["pub_investqa_record"]
    assert (
        next(row for row in result if row["record_key"] == key)["activity_keys"]
        == "invented_beta;invented_alpha"
    )
    assert all(
        row["activity_keys"] is None for row in result if row["record_key"] != key
    )


def test_agency_projection_missing_language_is_reported(tmp_path, monkeypatch):
    rows, _pages = _projection_input(tmp_path, monkeypatch)
    source = next(
        row
        for row in rows
        if row["language"] == "en"
        and row["record_type"] == "sector"
        and row["ordinal"] is None
    )
    control, control_lines = _project([source], [])
    assert len(control) == 1
    assert control_lines == []
    del source["language"]
    result, lines = _project([source], [])
    assert result == []
    assert lines == [
        f"OMITTED pub_investqa_record {source['page_url']} check=record_key reason=unresolved"
    ]


def _parameter_pages():
    """Invented level-four blocks, with the cache's JSON text-item shape."""
    english = [
        ("Rent subsidy", "25% for 3 years"),
        ("Rent allowance", "QAR 1200 per month"),
        ("Salary subsidy", "40%"),
        ("Salary allowance", "QAR 800 per month"),
        ("Tax exemption", "Exemption applies"),
        ("Rent allowance", "QAR 500 one-off"),
        ("Rent subsidy", "up to 30%"),
        ("Land offer", "Land available"),
        ("Welcome", "Read the guide"),
    ]
    arabic = [
        ("دعم الإيجار", "25% لمدة 3 سنوات"),
        ("بدل الإيجار", "1200 ريال قطري شهرياً"),
        ("دعم الرواتب", "40%"),
        ("بدل الرواتب", "800 ريال قطري شهرياً"),
        ("إعفاء ضريبي", "يسري الإعفاء"),
        ("بدل الإيجار", "500 ريال قطري لمرة واحدة"),
        ("دعم الإيجار", "حتى 30%"),
    ]
    rows, pages = [], []
    for language, blocks in (("en", english), ("ar", arabic)):
        url = f"https://agency.invalid/{language}/incentives/invented"
        pages.append(
            dict(page_key="incentives_invented", page_language=language, page_url=url)
        )
        rows.append(
            dict(
                record_type="incentive",
                ordinal=None,
                level=None,
                title="Invented package" if language == "en" else "حزمة افتراضية",
                heading=None,
                text_items=None,
                page_url=url,
                source_id="investqa_pages",
                language=language,
            )
        )
        for ordinal, (heading, text) in enumerate(blocks, 1):
            rows.append(
                dict(
                    record_type="incentive_parameter",
                    ordinal=ordinal,
                    heading=heading,
                    level=4,
                    text_items=json.dumps([text]),
                    page_url=url,
                    source_id="investqa_pages",
                    language=language,
                )
            )
    return rows, pages


_PARAMETER_COMMON = dict(
    record_type="incentive_parameter",
    parent_key="incentives_invented",
    sequence=None,
    reference=None,
    link_url=None,
    activity_keys=None,
    period=None,
    page_url="https://agency.invalid/en/incentives/invented",
    source_id="investqa_pages",
)
PARAMETER_EXPECTED = [
    dict(
        _PARAMETER_COMMON,
        record_type="incentive",
        record_key="incentives_invented",
        parent_key=None,
        title_en="Invented package",
        title_ar="حزمة افتراضية",
        parameter_key=None,
        value=None,
        unit=None,
        duration_months=None,
        as_stated=None,
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:rent_share",
        title_en="Rent subsidy",
        title_ar="دعم الإيجار",
        parameter_key="rent_share",
        value="0.25",
        unit="ratio",
        duration_months=36,
        as_stated="Rent subsidy\n25% for 3 years",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:rent_amount",
        title_en="Rent allowance",
        title_ar="بدل الإيجار",
        parameter_key="rent_amount",
        value="1200",
        unit="qar_per_month",
        duration_months=None,
        as_stated="Rent allowance\nQAR 1200 per month",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:staff_share",
        title_en="Salary subsidy",
        title_ar="دعم الرواتب",
        parameter_key="staff_share",
        value="0.4",
        unit="ratio",
        duration_months=None,
        as_stated="Salary subsidy\n40%",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:staff_amount",
        title_en="Salary allowance",
        title_ar="بدل الرواتب",
        parameter_key="staff_amount",
        value="800",
        unit="qar_per_month",
        duration_months=None,
        as_stated="Salary allowance\nQAR 800 per month",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:other_5",
        title_en="Tax exemption",
        title_ar="إعفاء ضريبي",
        parameter_key="other",
        value=None,
        unit=None,
        duration_months=None,
        as_stated="Tax exemption\nExemption applies",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:other_6",
        title_en="Rent allowance",
        title_ar="بدل الإيجار",
        parameter_key="other",
        value="500",
        unit="QAR",
        duration_months=None,
        as_stated="Rent allowance\nQAR 500 one-off",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:other_7",
        title_en="Rent subsidy",
        title_ar="دعم الإيجار",
        parameter_key="other",
        value=None,
        unit="%",
        duration_months=None,
        as_stated="Rent subsidy\nup to 30%",
    ),
    dict(
        _PARAMETER_COMMON,
        record_key="incentives_invented:other_8",
        title_en="Land offer",
        title_ar=None,
        parameter_key="other",
        value=None,
        unit=None,
        duration_months=None,
        as_stated="Land offer\nLand available",
    ),
]


def test_incentive_parameter_literal_oracle():
    rows, pages = _parameter_pages()
    released, lines = _project(rows, pages)
    assert released == PARAMETER_EXPECTED
    assert lines == [
        "REPORT pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_missing",
        "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_kind reason=unclassified",
    ]


@pytest.mark.parametrize(
    "change,expected,reason",
    [
        (
            {"heading": "Salary subsidy"},
            ("staff_share", "0.25", "ratio", 36),
            "pair_missing",
        ),
        (
            {"text_items": '["USD 50 per month"]'},
            ("other", None, None, None),
            "pair_missing",
        ),
        ({"text_items": '["125%"]'}, ("other", None, "%", None), "pair_missing"),
        ({"text_items": '["up to 30%"]'}, ("other", None, "%", None), "pair_missing"),
        ({"text_items": '["20% and 30%"]'}, ("other", None, "%", None), "pair_missing"),
        (
            {"text_items": '["QAR 500 one-off for 3 years"]'},
            ("other", "500", "QAR", None),
            "pair_missing",
        ),
        (
            {"text_items": '["25%"]'},
            ("rent_share", "0.25", "ratio", None),
            "pair_missing",
        ),
        ({"heading": "Unknown benefit"}, None, "unclassified"),
    ],
)
def test_parameter_planted_inputs(change, expected, reason):
    rows, pages = _parameter_pages()
    row = {**rows[1], **change}
    released, lines = _project([row], pages)
    if expected is None:
        assert released == []
        assert lines == [
            f"OMITTED pub_investqa_record {row['page_url']} check=parameter_kind reason={reason}"
        ]
    else:
        assert len(released) == 1
        assert (
            tuple(
                released[0][key]
                for key in ("parameter_key", "value", "unit", "duration_months")
            )
            == expected
        )
        assert released[0]["title_ar"] is None
        assert lines == [
            f"REPORT pub_investqa_record {row['page_url']} check=parameter_pair reason={reason}"
        ]


@pytest.mark.parametrize(
    "change",
    [
        {"text_items": '["30% لمدة 3 سنوات"]'},
        {"heading": "بدل الإيجار"},
        {"text_items": '["25% لمدة 4 سنوات"]'},
    ],
)
def test_parameter_arabic_conflict_is_not_copied(change):
    rows, pages = _parameter_pages()
    arabic = {**rows[11], **change}
    released, lines = _project([rows[1], arabic], pages)
    assert released == []
    assert lines == [
        "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_value_mismatch"
    ]


def test_parameter_unknown_arabic_phrase_conflicts():
    rows, pages = _parameter_pages()
    released, lines = _project(
        [rows[1], {**rows[11], "heading": "معلومات عامة"}], pages
    )
    assert released == []
    assert lines == [
        "OMITTED pub_investqa_record https://agency.invalid/ar/incentives/invented check=parameter_kind reason=unclassified",
        "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_value_mismatch",
    ]


@pytest.mark.parametrize("items", ["null", "{}", "[4]"])
def test_parameter_malformed_text_refuses_specific_shape(items):
    rows, pages = _parameter_pages()
    with pytest.raises(ValueError, match=r"^parameter_text_shape$"):
        _project([{**rows[1], "text_items": items}], pages)


def test_parameter_contract_scale_is_not_rounded():
    rows, pages = _parameter_pages()
    result, lines = _project([{**rows[1], "text_items": '["25.12345%"]'}], pages)
    assert result[0]["parameter_key"] == "other"
    assert result[0]["value"] is None
    assert lines == [
        "REPORT pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_missing"
    ]


@settings(derandomize=True, max_examples=100)
@given(
    percent=st.integers(min_value=0, max_value=10000),
    amount=st.integers(min_value=0, max_value=999999),
)
def test_parameter_number_grammar(percent, amount):
    rows, pages = _parameter_pages()
    percentage = Decimal(percent) / Decimal(100)
    result, _ = _project(
        [{**rows[1], "text_items": json.dumps([f"{percentage}%"])}], pages
    )
    assert Decimal(result[0]["value"]) == percentage / Decimal(100)
    result, _ = _project(
        [
            {
                **rows[1],
                "heading": "Rent allowance",
                "text_items": json.dumps([f"QAR {amount} per month"]),
            }
        ],
        pages,
    )
    assert Decimal(result[0]["value"]) == Decimal(amount)
    result, _ = _project(
        [{**rows[1], "text_items": json.dumps([f"{percentage}% and {amount}%"])}], pages
    )
    assert result[0]["parameter_key"] == "other"
    assert result[0]["value"] is None


@pytest.mark.parametrize("text", ["-25%", ".25%", "99.999999999999999999999999999999%"])
def test_parameter_invalid_share_never_becomes_usable(text):
    rows, pages = _parameter_pages()
    result, _ = _project([{**rows[1], "text_items": json.dumps([text])}], pages)
    assert (result[0]["parameter_key"], result[0]["value"]) == ("other", None)


@pytest.mark.parametrize(
    "wording",
    [
        "25% in 2099",
        "forecast 25%",
        "projected rent support: 25%",
        "expected support: 25%",
    ],
)
def test_parameter_forward_looking_figure_is_omitted(wording):
    rows, pages = _parameter_pages()
    row = {
        **rows[1],
        "text_items": json.dumps([wording]),
        "retrieved_utc": "2026-11-27T00:00:00Z",
    }
    result, lines = _project([row], pages)
    assert result == []
    assert lines == [
        "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_period reason=forward_looking"
    ]


def test_parameter_stated_period_and_arabic_digits():
    rows, pages = _parameter_pages()
    english = {
        **rows[1],
        "text_items": '["25% in 2024"]',
        "retrieved_utc": "2026-11-27T00:00:00Z",
    }
    arabic = {
        **rows[11],
        "text_items": '["٢٥٪ في ٢٠٢٤"]',
        "retrieved_utc": "2026-11-27T00:00:00Z",
    }
    result, lines = _project([english, arabic], pages)
    assert (result[0]["value"], result[0]["period"], result[0]["title_ar"]) == (
        "0.25",
        "2024",
        "دعم الإيجار",
    )
    assert lines == []


@pytest.mark.parametrize(
    "wording",
    ["متوقع 25% لمدة 3 سنوات", "تشير التوقعات إلى دعم بنسبة 25% لمدة 3 سنوات"],
)
def test_parameter_arabic_forecast_is_omitted(wording):
    rows, pages = _parameter_pages()
    result, lines = _project(
        [rows[1], {**rows[11], "text_items": json.dumps([wording])}], pages
    )
    assert result == []
    assert lines == [
        "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_period reason=forward_looking"
    ]


def test_parameter_fractional_month_duration_is_not_invented():
    rows, pages = _parameter_pages()
    result, lines = _project(
        [{**rows[1], "text_items": '["25% for 1.5 months"]'}], pages
    )
    assert result[0]["duration_months"] is None
    assert result[0]["value"] == "0.25"
    assert lines == [
        "REPORT pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_missing"
    ]


def test_parameter_quantity_wrong_for_share_key():
    rows, pages = _parameter_pages()
    result, lines = _project([{**rows[1], "text_items": '["QAR 50 per month"]'}], pages)
    assert (result[0]["parameter_key"], result[0]["value"], result[0]["unit"]) == (
        "other",
        "50",
        "QAR",
    )
    assert lines == [
        "REPORT pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_missing"
    ]


def test_parameter_ambiguous_phrases_do_not_default_to_other():
    rows, pages = _parameter_pages()
    row = {**rows[1], "heading": "Rent subsidy and salary subsidy"}
    result, lines = _project([row], pages)
    assert result == []
    assert lines == [
        "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_kind reason=unclassified"
    ]


def test_parameter_amount_pair_compares_values_not_spelling():
    rows, pages = _parameter_pages()
    result, lines = _project(
        [rows[2], {**rows[12], "text_items": '["1200.0 ريال قطري شهرياً"]'}], pages
    )
    assert (result[0]["parameter_key"], result[0]["value"]) == ("rent_amount", "1200")
    assert lines == []


def test_parameter_other_preserves_stated_unit_spelling():
    rows, pages = _parameter_pages()
    result, lines = _project(
        [{**rows[2], "text_items": '["qar 500 one-off"]'}],
        pages,
    )
    assert (result[0]["parameter_key"], result[0]["value"], result[0]["unit"]) == (
        "other",
        "500",
        "qar",
    )
    assert lines == [
        "REPORT pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_pair reason=pair_missing"
    ]


@pytest.mark.parametrize(
    "language,heading,key,text,value,unit",
    [
        ("en", "Rent subsidy", "rent_share", "25%", "0.25", "ratio"),
        ("en", "Rental subsidy", "rent_share", "25%", "0.25", "ratio"),
        (
            "en",
            "Rent allowance",
            "rent_amount",
            "QAR 50 per month",
            "50",
            "qar_per_month",
        ),
        (
            "en",
            "Rental allowance",
            "rent_amount",
            "QAR 50 per month",
            "50",
            "qar_per_month",
        ),
        ("en", "Salary subsidy", "staff_share", "25%", "0.25", "ratio"),
        ("en", "Staff cost subsidy", "staff_share", "25%", "0.25", "ratio"),
        (
            "en",
            "Salary allowance",
            "staff_amount",
            "QAR 50 per month",
            "50",
            "qar_per_month",
        ),
        (
            "en",
            "Staff cost allowance",
            "staff_amount",
            "QAR 50 per month",
            "50",
            "qar_per_month",
        ),
        ("en", "Tax exemption", "other", "Exemption applies", None, None),
        ("en", "Land offer", "other", "Land available", None, None),
        ("ar", "دعم الإيجار", "rent_share", "25%", "0.25", "ratio"),
        ("ar", "دعم تكاليف الإيجار", "rent_share", "25%", "0.25", "ratio"),
        (
            "ar",
            "بدل الإيجار",
            "rent_amount",
            "50 ريال قطري شهرياً",
            "50",
            "qar_per_month",
        ),
        ("ar", "دعم الرواتب", "staff_share", "25%", "0.25", "ratio"),
        ("ar", "دعم الأجور", "staff_share", "25%", "0.25", "ratio"),
        (
            "ar",
            "بدل الرواتب",
            "staff_amount",
            "50 ريال قطري شهرياً",
            "50",
            "qar_per_month",
        ),
        (
            "ar",
            "بدل الأجور",
            "staff_amount",
            "50 ريال قطري شهرياً",
            "50",
            "qar_per_month",
        ),
        ("ar", "إعفاء ضريبي", "other", "يسري الإعفاء", None, None),
        ("ar", "تخصيص أرض", "other", "تتوفر أرض للمشروع", None, None),
    ],
)
def test_parameter_closed_phrase(language, heading, key, text, value, unit):
    from eii_custodian.publicdata.assembly_native import classify_parameter

    rows, _ = _parameter_pages()
    parsed = classify_parameter(
        {
            **rows[1],
            "language": language,
            "heading": heading,
            "text_items": json.dumps([text]),
        }
    )
    assert parsed is not None
    assert (parsed.key, parsed.value, parsed.unit) == (key, value, unit)


@pytest.mark.parametrize(
    "language,text,key,value,unit,duration",
    [
        ("en", "QAR 50 per month", "rent_amount", "50", "qar_per_month", None),
        ("en", "QAR 50 monthly", "rent_amount", "50", "qar_per_month", None),
        ("ar", "50 ريال قطري شهرياً", "rent_amount", "50", "qar_per_month", None),
        ("ar", "50 ريال قطري شهريا", "rent_amount", "50", "qar_per_month", None),
        ("en", "QAR 50 one-off for 3 years", "other", "50", "QAR", None),
        ("en", "QAR 50 one time for 3 years", "other", "50", "QAR", None),
        (
            "ar",
            "50 ريال قطري لمرة واحدة لمدة 3 سنوات",
            "other",
            "50",
            "ريال قطري",
            None,
        ),
    ],
)
def test_parameter_monthly_and_once_markers(language, text, key, value, unit, duration):
    from eii_custodian.publicdata.assembly_native import classify_parameter

    rows, _ = _parameter_pages()
    parsed = classify_parameter(
        {
            **rows[2],
            "language": language,
            "heading": "Rent allowance" if language == "en" else "بدل الإيجار",
            "text_items": json.dumps([text]),
        }
    )
    assert parsed is not None
    assert (parsed.key, parsed.value, parsed.unit, parsed.duration) == (
        key,
        value,
        unit,
        duration,
    )


@pytest.mark.parametrize(
    "text,number,unit",
    [
        ("for 1 month", "1", "month"),
        ("for 3 months", "3", "months"),
        ("for 1 year", "1", "year"),
        ("for 3 years", "3", "years"),
        ("لمدة 1 شهر", "1", "شهر"),
        ("لمدة 3 أشهر", "3", "أشهر"),
        ("لمدة 12 شهراً", "12", "شهراً"),
        ("لمدة 1 سنة", "1", "سنة"),
        ("لمدة 3 سنوات", "3", "سنوات"),
    ],
)
def test_parameter_duration_token_consumed_whole(text, number, unit):
    from eii_custodian.publicdata.assembly_native import _DURATION

    token = _DURATION.fullmatch(text)
    assert token is not None
    assert token.groups() == (number, unit)


@pytest.mark.parametrize(
    "marker", ["up to", "between", "حتى", "ما بين", "2-3", "2\u20133"]
)
def test_parameter_range_vocabulary(marker):
    from eii_custodian.publicdata.assembly_native import _RANGE

    assert _RANGE.fullmatch(marker) is not None


@pytest.mark.parametrize("marker", ["per month", "monthly", "شهرياً", "شهريا"])
def test_parameter_monthly_vocabulary_consumed_whole(marker):
    from eii_custodian.publicdata.assembly_native import _MONTHLY

    assert _MONTHLY.fullmatch(marker) is not None


@pytest.mark.parametrize(
    "english,arabic,heading,key,value,unit,duration,period,forward",
    [
        (
            "unexpected 25%",
            "٢٥٪ دون تغيير",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            None,
            False,
        ),
        (
            "unexpectedly 25%",
            "٢٥٪ دون تغيير",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            None,
            False,
        ),
        (
            "25%",
            "دعم غير متوقع بنسبة ٢٥٪",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            None,
            False,
        ),
        (
            "25%",
            "التكاليف غير المتوقعة بنسبة ٢٥٪",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            None,
            False,
        ),
        *[
            (
                "projected 25%",
                text,
                "Rent subsidy",
                "rent_share",
                "0.25",
                "ratio",
                None,
                None,
                True,
            )
            for text in (
                "النسبة المتوقعة ٢٥٪",
                "والمتوقع دعم بنسبة ٢٥٪",
                "التوقعات تشير إلى ٢٥٪",
                "وتوقعات الدعم بنسبة ٢٥٪",
            )
        ],
        *[
            (
                f"QAR 50 {term}",
                "\u0665\u0660 ريال قطري",
                "Rent allowance",
                "other",
                "50",
                "QAR",
                None,
                None,
                False,
            )
            for term in ("bimonthly", "semimonthly")
        ],
        (
            "25% none time",
            "٢٥٪",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            None,
            False,
        ),
        *[
            (
                f"25% {term}",
                "٢٥٪ مع مبلغ إضافي ٢٠٢٤",
                "Rent subsidy",
                "other",
                None,
                "%",
                None,
                None,
                False,
            )
            for term in ("within 2099", "bargain 2024")
        ],
        *[
            (
                "25% plus 2024",
                f"٢٥٪ {term}",
                "Rent subsidy",
                "other",
                None,
                "%",
                None,
                None,
                False,
            )
            for term in ("يكفي ٢٠٢٤", "إضافي ٢٠٢٤")
        ],
        (
            "25% in 2024",
            "٢٥٪ وفي ٢٠٢٤",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            "2024",
            False,
        ),
        (
            "25% therefor 12 months",
            "٢٥٪ مع مبلغ إضافي ١٢",
            "Rent subsidy",
            "other",
            None,
            "%",
            None,
            None,
            False,
        ),
        (
            "25% for 3 years",
            "٢٥٪ ولمدة ٣ سنوات",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            36,
            None,
            False,
        ),
        (
            "25%",
            "ودعم الإيجار ٢٥٪",
            "Rent subsidy",
            "rent_share",
            "0.25",
            "ratio",
            None,
            None,
            False,
        ),
    ],
)
def test_parameter_literal_boundaries(
    english, arabic, heading, key, value, unit, duration, period, forward
):
    rows, pages = _parameter_pages()
    en = {
        **rows[1],
        "heading": heading,
        "text_items": json.dumps([english]),
        "retrieved_utc": "2026-11-27T00:00:00Z",
    }
    ar = {
        **rows[11],
        "heading": "بدل الإيجار" if heading == "Rent allowance" else "دعم الإيجار",
        "text_items": json.dumps([arabic]),
        "retrieved_utc": "2026-11-27T00:00:00Z",
    }
    if arabic.startswith("ودعم"):
        ar["heading"] = "تفاصيل الدعم"
    result, lines = _project([en, ar], pages)
    if forward:
        assert result == []
        assert lines == [
            "OMITTED pub_investqa_record https://agency.invalid/en/incentives/invented check=parameter_period reason=forward_looking"
        ]
    else:
        assert lines == []
        assert [
            (
                r["parameter_key"],
                r["value"],
                r["unit"],
                r["duration_months"],
                r["period"],
            )
            for r in result
        ] == [(key, value, unit, duration, period)]


_CLOSED_ENGLISH = (
    "forecast",
    "projected",
    "expected",
    "for",
    "month",
    "months",
    "year",
    "years",
    "in",
    "QAR",
    "per month",
    "monthly",
    "one-off",
    "one time",
    "up to",
    "between",
    "rent subsidy",
    "rental subsidy",
    "rent allowance",
    "rental allowance",
    "salary subsidy",
    "staff cost subsidy",
    "salary allowance",
    "staff cost allowance",
    "tax exemption",
    "land offer",
)
_CLOSED_ARABIC = (
    "متوقع",
    "توقعات",
    "لمدة",
    "شهر",
    "أشهر",
    "شهراً",
    "سنة",
    "سنوات",
    "في",
    "ريال قطري",
    "شهرياً",
    "شهريا",
    "لمرة واحدة",
    "حتى",
    "ما بين",
    "دعم الإيجار",
    "دعم تكاليف الإيجار",
    "بدل الإيجار",
    "دعم الرواتب",
    "دعم الأجور",
    "بدل الرواتب",
    "بدل الأجور",
    "إعفاء ضريبي",
    "تخصيص أرض",
)


@pytest.mark.parametrize("term", _CLOSED_ENGLISH + _CLOSED_ARABIC)
def test_closed_term_positive_and_containing_word(term):
    import re

    from eii_custodian.publicdata.assembly_native import _closed_terms

    pattern = _closed_terms((term,))
    assert re.search(pattern, term)
    assert re.search(pattern, "س" + term) is None
    assert re.search(pattern, term + "س") is None
    if term in _CLOSED_ARABIC:
        for prefix in (
            "و",
            "ف",
            "ب",
            "ل",
            "ال",
            "وال",
            "بال",
            "فال",
            "لل",
            "وب",
            "ول",
            "وبال",
            "ولل",
        ):
            assert re.search(pattern, prefix + term)
            assert re.search(pattern, "س" + prefix + term) is None
            assert re.search(pattern, prefix + term + "س") is None


@settings(max_examples=100, derandomize=True)
@given(
    term=st.sampled_from(_CLOSED_ENGLISH + _CLOSED_ARABIC),
    tail=st.text(alphabet="xyzسصض", min_size=1, max_size=12),
)
def test_closed_term_generated_containing_words(term, tail):
    import re

    from eii_custodian.publicdata.assembly_native import _closed_terms

    pattern = _closed_terms((term,))
    assert re.search(pattern, tail + term) is None
    assert re.search(pattern, term + tail) is None


@pytest.mark.parametrize("marker", ("متوقع", "توقعات"))
@pytest.mark.parametrize("suffix", ("", "ة", "ات", "ين", "ون"))
def test_forward_closed_suffix_and_negation(marker, suffix):
    import re

    from eii_custodian.publicdata.assembly_native import _closed_terms

    pattern = _closed_terms((marker,), forward=True)
    assert re.search(pattern, "ال" + marker + suffix)
    assert re.search(pattern, "غير ال" + marker + suffix) is None
    assert re.search(pattern, "غير " + marker + suffix) is None
    assert re.search(pattern, marker + suffix + "س") is None
    assert re.search(pattern, "تغير " + marker + suffix)
