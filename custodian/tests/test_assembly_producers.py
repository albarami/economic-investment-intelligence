"""Production bindings run existing builders on their invented fixtures."""

import json
import shutil
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from custodian.tests.test_activity_spine import BASKET_REFUSALS
from custodian.tests.test_baskets import invented_review
from custodian.tests.test_production_adapters import context

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.fetch.bounded import file_hash
from eii_custodian.publicdata.fetch.build import BuildOutcome
from eii_custodian.publicdata.fetch.registry import RegistryError
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.review.cache_fixture import (
    class_csv,
    read_cached,
    real_feed_body,
    write_cached,
)


def _spine_build(tmp_path: Path):
    from custodian.tests import test_activity_graph as fixture

    fixture._write_cached_feeds(tmp_path)
    write_cached(
        tmp_path,
        fixture._entry("lic_cancelled"),
        real_feed_body(
            "lic_cancelled",
            [
                {
                    "activity_code": "4630001",
                    "activity_name_ar": "مورد تجريبي",
                    "cancelled_count": 1,
                }
            ],
        ),
    )
    write_cached(
        tmp_path,
        fixture._entry("cls_isic4"),
        class_csv([("5610", fixture._RESTAURANT), ("4630", "Invented supplier")]),
    )
    review = tmp_path / "committed-review"
    review.mkdir()
    path = fixture._review_csv(review)
    fixture._binding_beside(
        path,
        titles=(("5610", fixture._RESTAURANT, ""), ("4630", "Invented supplier", "")),
    )
    path.rename(review / "activity_spine.csv")
    path.with_suffix(".binding.json").rename(review / "activity_spine.binding.json")
    fixture._allowlist_csv(review).rename(review / "category_allowlist.csv")
    baskets = invented_review()
    baskets["status"] = "reviewed: invented fixture"
    (review / "baskets.yaml").write_text(json.dumps(baskets))
    points = tmp_path / "places_s2_t06/pub_place.jsonl"
    points.parent.mkdir()
    points.write_text(json.dumps({"category": "restaurant"}) + "\n")
    build = context(
        tmp_path,
        tuple(
            fixture._entry(key)
            for key in ("lic_active", "lic_cancelled", "cls_isic4", "places_ovt")
        ),
    )
    build.review = review
    build.selected = reviewed_selections(tmp_path)
    build.receipts = {
        entry.key: read_cached(
            tmp_path, entry, digest=build.selected[entry.key]
        ).sidecar
        for entry in build.entries
    }
    build.files[points.relative_to(tmp_path).as_posix()] = file_hash(points)
    return build


def test_graph_calls_existing_spine_and_graph_in_release_mode(
    tmp_path: Path, monkeypatch
) -> None:
    from eii_custodian.publicdata.review import graph as graph_module

    actual_build, actual_write = graph_module.build_graph, graph_module.write_graph
    modes = []

    def build_graph(*args, **kwargs):
        modes.append(("build", kwargs.get("mode")))
        return actual_build(*args, **kwargs)

    def write_graph(*args, **kwargs):
        modes.append(("write", kwargs.get("mode")))
        return actual_write(*args, **kwargs)

    monkeypatch.setattr(graph_module, "build_graph", build_graph)
    monkeypatch.setattr(graph_module, "write_graph", write_graph)

    build = _spine_build(tmp_path)
    output = build.spine_graph()
    assert set(output) == {
        "assembly/spine_graph.json",
        "assembly/graph/graph_node.parquet",
        "assembly/graph/graph_edge.parquet",
    }
    record = json.loads((tmp_path / "assembly/spine_graph.json").read_text())
    assert record["manifest"]["source_hashes"]
    assert record["spine"]["rows"]
    assert modes == [("build", "release"), ("write", "release")]
    (tmp_path / "assembly/graph/graph_node.parquet").write_bytes(b"SYN-changed")
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        build.final_audit()


def test_spine_membership_from_baskets_queues_cancelled_only_supplier(
    tmp_path: Path,
) -> None:
    build = _spine_build(tmp_path)
    assert not (build.cache / "review/activity_membership.json").exists()
    build.spine_graph()
    record = json.loads((build.cache / "assembly/spine_graph.json").read_text())
    assert {"lic_active", "lic_cancelled", "cls_isic4"} <= set(record["source_chain"])
    assert record["membership"] == {
        "playbook_codes": ["5610101"],
        "supplier_codes": ["4630001"],
        "supplier_classes": ["4630"],
        "baskets_sha256": file_hash(build.review / "baskets.yaml"),
    }
    queued = {row["code"]: row for row in record["spine"]["queue"]}
    assert queued["4630001"]["status"] == "unreviewed"
    assert queued["4630001"]["reason"] == "awaiting_human_review"
    assert queued["4630001"]["isic_class"] == ""


def test_spine_baskets_hash_binds_the_bytes_parsed(tmp_path, monkeypatch):
    build = _spine_build(tmp_path)
    path = build.review / "baskets.yaml"
    original = path.read_bytes()
    reads = []

    def changing_reader(reader):
        def read(target, *args, **kwargs):
            content = reader(target, *args, **kwargs)
            if target == path:
                reads.append(content)
                path.write_bytes(original + b"\n# changed after the read\n")
            return content

        return read

    monkeypatch.setattr(Path, "read_text", changing_reader(Path.read_text))
    monkeypatch.setattr(Path, "read_bytes", changing_reader(Path.read_bytes))
    build.spine_graph()
    record = json.loads((build.cache / "assembly/spine_graph.json").read_text())
    assert record["membership"]["supplier_codes"] == ["4630001"]
    assert record["membership"]["baskets_sha256"] == sha256(original).hexdigest()
    assert reads == [original]


@pytest.mark.parametrize(
    "case,cause",
    [
        ("absent", FileNotFoundError),
        ("unreadable", PermissionError),
        ("malformed", RegistryError),
        ("missing_activity", KeyError),
        ("missing_inputs", KeyError),
        ("null_inputs", TypeError),
    ],
)
def test_spine_stage_wraps_basket_read_errors(tmp_path, monkeypatch, case, cause):
    build = _spine_build(tmp_path)
    path = build.review / "baskets.yaml"
    if case == "absent":
        path.unlink()
    elif case == "unreadable":

        def refusing_reader(reader):
            def read(target, *args, **kwargs):
                if target == path:
                    raise PermissionError("invented unreadable baskets")
                return reader(target, *args, **kwargs)

            return read

        monkeypatch.setattr(Path, "read_text", refusing_reader(Path.read_text))
        monkeypatch.setattr(Path, "read_bytes", refusing_reader(Path.read_bytes))
    elif case == "malformed":
        path.write_bytes(b"activities: [")
    else:
        document = json.loads(path.read_text())
        if case == "null_inputs":
            document["activities"][0]["inputs"] = None
        else:
            del document["activities"][0][case.removeprefix("missing_")]
        path.write_text(json.dumps(document))
    with pytest.raises(AssemblyError, match=r"^assembly_membership_invalid$") as error:
        build.spine_graph()
    assert isinstance(error.value.__cause__, cause)
    assert not (build.cache / "assembly/spine_graph.json").exists()
    assert not (build.cache / "assembly/graph").exists()


@pytest.mark.parametrize(
    "refusal,detail", BASKET_REFUSALS, ids=[r[0] for r in BASKET_REFUSALS]
)
def test_spine_stage_wraps_basket_refusals(tmp_path, monkeypatch, refusal, detail):
    from custodian.tests.test_activity_spine import invalid_basket

    from eii_custodian.publicdata.review.activity import SpineError

    build = _spine_build(tmp_path)
    (build.review / "baskets.yaml").write_text(
        json.dumps(invalid_basket(refusal, monkeypatch))
    )
    with pytest.raises(AssemblyError) as error:
        build.spine_graph()
    assert str(error.value) == "assembly_membership_invalid"
    assert isinstance(error.value.__cause__, SpineError)
    assert error.value.__cause__.detail == detail
    assert not (build.cache / "assembly/spine_graph.json").exists()
    assert not (build.cache / "assembly/graph").exists()


def test_spine_stage_refuses_existing_graph_directory(tmp_path):
    build = _spine_build(tmp_path)
    (build.cache / "assembly/graph").mkdir(parents=True)
    with pytest.raises(AssemblyError, match=r"^assembly_graph_exists$"):
        build.spine_graph()
    assert not (build.cache / "assembly/spine_graph.json").exists()


def test_frame_invokes_real_nested_build_and_refuses_missing_inventory(
    tmp_path: Path,
) -> None:
    from custodian.tests.test_frame_live_survivors import _world

    from eii_custodian.publicdata.buildings import BuildingError

    prepared = _world(tmp_path)
    build = context(prepared.cache, prepared.entries)
    build.review = prepared.review
    build.selected = reviewed_selections(prepared.cache)
    with pytest.raises(BuildingError, match="building_part_unregistered"):
        build.frame()
    assert build.frame_result is None
    assert "FAIL buildings check=building_part_unregistered" in build.lines
    assert not (prepared.cache / "assembly/frame.json").exists()


def test_frame_keeps_stac_lineage_without_claiming_a_metadata_release_table(
    tmp_path: Path, monkeypatch
) -> None:
    from custodian.tests.building_fixture import PARTS, world

    from eii_custodian.publicdata import assembly_adapters

    prepared = world(tmp_path)
    names = ("municipality", "zone", "district", "grid_cell", "gazetteer")
    prepared.entries = tuple(
        replace(
            row,
            release_tables=("gazetteer",)
            if row.key in PARTS
            else names
            if row.source_id == "bnd_hdx"
            else (),
        )
        for row in prepared.entries
    )
    build = context(prepared.cache, prepared.entries)
    build.selected = prepared.selected
    build.reviewed_selections()

    def frame(*_args, **_kwargs):
        # Use the real pinned building producer and manifest verifier. The
        # administrative frame and unrelated places outputs are invented here.
        prepared.produce()
        directory = prepared.cache / "places_s2_t06"
        directory.mkdir()
        for filename in (
            "pub_place.jsonl",
            "pub_place_verification.jsonl",
            "place_points.json",
            "build_report.json",
            "flagship_check.json",
        ):
            (directory / filename).write_text("[]")
        return FrameResult(
            {
                name: [
                    {"municipality_code": "SYN-M", "name_en": "SYN", "name_ar": "SYN"}
                ]
                for name in names
            },
            [],
            {"bnd_hdx": {"sha256": "a" * 64}, "bnd_zone_2020": {"sha256": "b" * 64}},
        )

    monkeypatch.setattr(assembly_adapters, "build_public_frame", frame)
    build.frame()
    record = json.loads((prepared.cache / "assembly/frame.json").read_text())
    for row in prepared.entries:
        if row.source_id != "bldg_ovt":
            continue
        assert row.key in record["source_chain"]
        assert build.source_tables.get(row.key, []) == list(row.release_tables)
        assert (row.key in build.table_sources["gazetteer"]) == (row.key in PARTS)


def _property_additions_build(tmp_path: Path):
    from custodian.tests import test_additions_property_venues as fixture

    row = fixture._entry("prop_resi_units")
    review = fixture._frame(tmp_path / "review")
    for name in ("additions_property_venues.yaml", "venue_crosswalk.csv"):
        shutil.copyfile(fixture.REVIEW / name, review / name)
    cache = tmp_path / "cache"
    digest = write_cached(cache, row, json.dumps([fixture._deal()]).encode()).stem
    build = context(cache, (row,))
    build.selected = {row.key: digest}
    build.review = review
    build.frame_result = FrameResult(
        {
            "district": [
                {"district_key": "syn_north", "municipality_code": "syn_coast"},
                {"district_key": "syn_inland", "municipality_code": "syn_inland"},
            ]
        },
        [],
        {},
    )
    build.reviewed_selections()
    return build, review


def test_additions_runs_real_bulletin_and_indexes_its_written_table(
    tmp_path: Path,
) -> None:
    build, _ = _property_additions_build(tmp_path)
    build.additions()
    assert build.tables["pub_property_resi"][0]["median_price"] == 10
    record = json.loads((build.cache / "assembly/additions.json").read_text())
    assert record["tables"]["pub_property_resi"][0]["deal_count"] == 1
    assert build.source_tables[build.entries[0].key] == ["pub_property_resi"]


def test_additions_checks_unused_crosswalk_keys_against_the_frame(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.frame.checks import FrameError

    build, review = _property_additions_build(tmp_path)
    path = review / "district_crosswalk.csv"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "SYN Unused,syn_coast,ZZZ999999999,two_language_exact\n",
        encoding="utf-8",
    )
    with pytest.raises(FrameError, match=r"^district_crosswalk: outside_frame$"):
        build.additions()


def test_fsq_reads_real_manifest_and_file_archive(tmp_path: Path) -> None:
    from custodian.tests.fixtures.places_fsq.invented import place, write_places
    from custodian.tests.test_places_fsq import _grid

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.places_fsq.constants import COPY_ROOT, RELEASE_KEY
    from eii_custodian.publicdata.places_fsq.fetch import _store

    row = next(e for e in load_registry() if e.key == RELEASE_KEY)
    path = tmp_path / "invented.parquet"
    write_places(path, [place()])
    release = "2032-04-05"
    identity = _store(
        row,
        tmp_path,
        b"metadata",
        [
            (
                "invented.parquet",
                path.read_bytes(),
                f"{COPY_ROOT}{release}/places/invented.parquet",
            )
        ],
        "",
        "",
        "2026-11-18T00:00:00Z",
        "data.source.coop",
        release=release,
        listing=(b"<html><body>invented</body></html>", COPY_ROOT),
        metadata_url=f"{COPY_ROOT}{release}/places/_metadata",
    )
    points = tmp_path / "places_s2_t06/pub_place.jsonl"
    points.parent.mkdir()
    points.write_text("")
    review = tmp_path / "review"
    review.mkdir()
    shutil.copyfile(
        Path("custodian/publicdata/review/places_fsq_policy.yaml"),
        review / "places_fsq_policy.yaml",
    )
    from eii_custodian.publicdata.places_fsq.policy import MAPPING_COLUMNS

    (review / "places_fsq_categories.csv").write_text(",".join(MAPPING_COLUMNS) + "\n")
    build = context(tmp_path, (row,))
    build.review = review
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: identity}))
    build.reviewed_selections()
    build.files[points.relative_to(tmp_path).as_posix()] = file_hash(points)
    build.frame_result = FrameResult({"grid_cell": _grid((51.5, 25.3))}, [], {})
    build.fsq()
    assert build.tables["pub_place_fsq"][0]["name_ar"] is None
    assert build.tables["pub_place_fsq"][0]["source_release"] == release
    assert (
        json.loads((tmp_path / "assembly/fsq.json").read_text())["coverage"][
            "name_ar_null"
        ]
        == 1
    )


def test_fsq_gate_evidence_compares_table_and_receipt_release(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_reports import gather_audit
    from eii_custodian.publicdata.assembly_sources import SOURCE_COMPONENTS
    from eii_custodian.publicdata.fetch.receipts import sidecar_for
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.places_fsq.constants import RELEASE_KEY

    assert SOURCE_COMPONENTS["places_fsq"] == frozenset((RELEASE_KEY,))
    entries = load_registry()
    row = next(e for e in entries if e.key == RELEASE_KEY)
    build = context(tmp_path, entries)
    release = "2032-04-05"
    build.tables["pub_place_fsq"] = [{"source_release": release}]
    build.receipts[row.key] = sidecar_for(
        row,
        digest="a" * 64,
        nbytes=0,
        fetch_url=row.url,
        fetch_host=row.fetch_host,
        retrieved_utc="2026-11-18T00:00:00Z",
        publisher=row.publisher,
        source_modified=release,
        row_count=None,
        terms_sha256="",
    )
    evidence = next(
        item
        for item in gather_audit(build)["confirmations"]
        if item["task"] == "S2-T15"
    )
    assert evidence["state"] == "recorded"
    build.receipts[row.key]["source_modified"] = "2031-02-03"
    evidence = next(
        item
        for item in gather_audit(build)["confirmations"]
        if item["task"] == "S2-T15"
    )
    assert evidence["state"] == "pending"


def test_investment_capture_calls_real_empty_registration_audit(tmp_path: Path) -> None:
    build = context(tmp_path)
    build.fetched = BuildOutcome((), None)
    build.investment_capture()
    assert json.loads((tmp_path / "assembly/investment_capture.json").read_text()) == {
        "attempts": [],
        "audit": [],
        "method": "public-assembly.investment_capture",
        "method_version": "1",
        "source_chain": {},
    }


def test_busyness_calls_existing_builder_with_local_review(tmp_path: Path) -> None:
    from custodian.tests import test_publicdata_besttime_build as fixture
    from custodian.tests.test_publicdata_besttime_parse import encode, forecast, query

    from eii_custodian.publicdata.fetch.transport import Response

    row, review, cache, env = fixture.setup(tmp_path)
    answers = iter((forecast(), query()))
    build = context(cache, (row,))
    build.review = review
    build.environ = env
    calls = []

    def transport(request):
        calls.append(str(request))
        return Response(str(request), encode(next(answers)), ())

    build.transport = transport
    build.busyness()
    record = json.loads((cache / "assembly/busyness.json").read_text())
    assert row.key in record["manifests"]
    assert len(calls) == 2


def test_gather_audit_on_registered_sources_without_cache_is_pending(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.assembly_reports import gather_audit
    from eii_custodian.publicdata.fetch.registry import load_registry

    build = context(tmp_path, load_registry())
    (tmp_path / "assembly").mkdir()
    # No page is claimed fetched: the audit must preserve missing evidence.
    audit = gather_audit(build)
    assert any(row["state"] == "failed" for row in audit["completeness"])
    assert audit["oi03"]["state"] == "pending"
    assert {row["task"] for row in audit["confirmations"]} == {
        "S2-T09",
        "S2-T12",
        "S2-T13",
        "S2-T15",
        "S2-T17",
        "S2-T19",
        "S2-T20",
    }
    assert (
        next(row for row in audit["confirmations"] if row["task"] == "S2-T09")["state"]
        == "pending"
    )


def test_series_calls_real_builder_and_preserves_regression_refusal(
    tmp_path: Path,
) -> None:
    from custodian.tests.test_public_series import series_cache

    row, digest = series_cache(
        tmp_path,
        "util_elec",
        [
            {"year": "2021", "zone_number": "69", "value": 7},
            {"year": "2025", "zone_number": "69", "value": 24},
            {"year": "2026", "zone_number": "69", "value": 5},
        ],
    )
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest}
    # Utility rows need no municipality join. The adapter must not demand one.
    with pytest.raises(AssemblyError, match="assembly_regression_refused"):
        build.series_stage()
    assert (
        json.loads((tmp_path / "series/internal/pub_zone_utility.json").read_text())[
            "rows"
        ][0]["value"]
        == 7
    )


def test_fetch_archive_invokes_fetch_seam_once_and_preserves_refusal(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.fetch.build import FetchFailure

    build = context(tmp_path)
    calls = []

    def fetch():
        calls.append("fetch")
        return BuildOutcome(
            ("SYN-line",), FetchFailure(6, "invented", "", "unreachable", "", "")
        )

    build.fetcher = fetch
    with pytest.raises(AssemblyError, match="assembly_fetch_refused"):
        build.fetch_archive()
    assert calls == ["fetch"]
    assert build.lines == ["SYN-line"]
    assert not (tmp_path / "assembly/fetch_archive.json").exists()


def test_confirmation_adapters_read_pending_t19_and_height_absence(
    tmp_path: Path,
) -> None:
    from eii_custodian.publicdata.assembly_reports import gather_audit
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.heights.model import HeightError

    build = context(tmp_path, load_registry())
    with pytest.raises(HeightError) as err:
        build.heights()
    assert err.value.name == "building_table_absent"
    rows = {row["task"]: row for row in gather_audit(build)["confirmations"]}
    assert rows["S2-T19"]["state"] == "pending"
    assert rows["S2-T19"]["references"] == ["s2_t19_confirmation.yaml"]
    assert rows["S2-T20"]["state"] == "pending"
    assert "height_rules.yaml" in rows["S2-T20"]["references"]


def test_series_indexes_existing_internal_rows_before_named_regression_refusal(
    tmp_path: Path,
) -> None:
    from custodian.tests.test_public_series import series_cache

    row, digest = series_cache(
        tmp_path,
        "util_elec",
        [
            {"year": "2021", "zone_number": "69", "value": 7},
            {"year": "2025", "zone_number": "69", "value": 24},
        ],
    )
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest}
    with pytest.raises(AssemblyError, match="assembly_regression_refused"):
        build.series_stage()
    assert build.tables["pub_zone_utility"][0]["value"] == 7
    result = json.loads((tmp_path / "assembly/series_stage.json").read_text())
    assert result["mismatch"] == "PUB-62"
    assert result["tables"]["pub_zone_utility"][1]["value"] == 24
    assert result["row_sources"]["pub_zone_utility"] == ["util_elec", "util_elec"]


def test_failed_new_run_clears_prior_report_before_source_read(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_io import write_record
    from eii_custodian.publicdata.fetch.build import FetchFailure

    stale = "assembly/s2_t08_draw.json"
    write_record(tmp_path, stale, {"figures": ["SYN-old"]})
    build = context(tmp_path)

    def refuse():
        assert not (tmp_path / stale).exists()
        assert (
            json.loads((tmp_path / "assembly/build.json").read_text())["figure_seed"]
            == 17
        )
        assert (tmp_path / "assembly/intake_evidence.json").is_file()
        return BuildOutcome((), FetchFailure(6, "invented", "", "unreachable", "", ""))

    build.fetcher = refuse
    with pytest.raises(AssemblyError, match="assembly_fetch_refused"):
        build.run()
    assert not (tmp_path / stale).exists()


def test_investment_capture_reports_both_retained_revisions_without_values(
    tmp_path: Path,
) -> None:
    from custodian.tests.investment_fixtures import invented_record
    from custodian.tests.test_investment_build import _fdi_entry
    from custodian.tests.test_investment_evidence import _archive_dashboard

    from eii_custodian.publicdata.investment_contracts import FetchAttempt

    old = _archive_dashboard(
        tmp_path, "2024-01-01", (invented_record(project_id=1001, capex=("n", "12.5")),)
    )
    new = _archive_dashboard(
        tmp_path, "2024-02-01", (invented_record(project_id=1001, capex=("n", "14.5")),)
    )
    row = _fdi_entry()
    build = context(tmp_path, (row,))
    build.fetched = BuildOutcome(
        (),
        None,
        investment_attempts=(FetchAttempt(row.source_id, row.key, "success", new, ""),),
    )
    build.investment_capture()
    record = json.loads((tmp_path / "assembly/investment_capture.json").read_text())
    identities = {
        r["revision_identity"]
        for r in record["audit"]
        if r["evidence_status"] == "observed_announcement"
    }
    assert identities == {old, new}
    assert "12.5" not in (tmp_path / "assembly/investment_capture.json").read_text()
    assert "14.5" not in (tmp_path / "assembly/investment_capture.json").read_text()


def test_busyness_actual_table_is_indexed_as_an_index_not_a_people_count(
    tmp_path: Path,
) -> None:
    from custodian.tests import test_publicdata_besttime_build as fixture
    from custodian.tests.test_publicdata_besttime_parse import encode, forecast, query

    from eii_custodian.publicdata.assembly_reports import draw_tables
    from eii_custodian.publicdata.fetch.transport import Response

    row, review, cache, env = fixture.setup(tmp_path)
    state = context(cache, (row,))
    state.review = review
    state.environ = env
    answers = iter((forecast(), query()))
    state.transport = lambda request: Response(str(request), encode(next(answers)), ())
    state.busyness()
    assert state.tables["pub_venue_busyness"]
    figures = draw_tables(state)["pub_venue_busyness"]()
    assert figures and all(figure.kind == "ratio" for figure in figures)
    assert all(figure.figure_id.endswith(":busyness_index") for figure in figures)


def test_height_adapter_refuses_a_missing_building_table(tmp_path: Path) -> None:
    from custodian.tests.fixtures.heights import invented

    from eii_custodian.publicdata.heights.step import HeightError

    cache = tmp_path / "data/public_cache"
    rows = (
        invented.entry("bldg_3dglobfp", extension="zip"),
        invented.entry("bldg_wsf3d", extension="tif"),
    )
    state = context(cache, rows)
    with pytest.raises(HeightError) as err:
        state.heights()
    assert err.value.name == "building_table_absent"
    assert not (cache / "assembly/heights.json").exists()
    assert state.data_files == {}


def test_a_noop_height_producer_over_earlier_valid_outputs_refuses(
    tmp_path: Path, monkeypatch
) -> None:
    """S2-P21 F3: outputs left by an earlier run never stand for this run's."""
    from custodian.tests.fixtures.heights import invented

    from eii_custodian.publicdata.heights import step

    buildings, globfp, wsf = invented.card_fixture(tmp_path)
    cache = tmp_path / "data/public_cache"
    rows = (
        invented.entry("bldg_3dglobfp", extension="zip"),
        invented.entry("bldg_wsf3d", extension="tif"),
    )
    for row, body in zip(rows, (globfp, wsf), strict=True):
        invented.store(cache, row, body)
    path = cache.parent / "assets/buildings/buildings.geojson"
    path.parent.mkdir(parents=True)
    path.write_bytes(buildings)
    from custodian.tests.building_fixture import bind_height_table

    rows = bind_height_table(cache, rows, path)
    initial = context(cache, rows)
    initial.selected = reviewed_selections(cache)
    initial.heights()
    output = cache.parent / "assets/heights"
    assert (output / "heights.json").is_file()
    assert (output / "manifest.heights.json").is_file()
    (cache / "assembly/heights.json").unlink()

    def noop(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(step, "build_heights", noop)
    state = context(cache, rows)
    state.selected = reviewed_selections(cache)
    with pytest.raises(AssemblyError) as err:
        state.heights()
    assert str(err.value) == "assembly_heights_incomplete"
    assert not (output / "heights.json").exists()
    assert not (output / "manifest.heights.json").exists()
    assert not (cache / "assembly/heights.json").exists()
    assert state.data_files == {}


def test_height_adapter_binds_real_asset_outputs_and_refuses_later_tampering(
    tmp_path: Path,
) -> None:
    from custodian.tests.fixtures.heights import invented

    from eii_custodian.publicdata.assembly_io import bound_files

    buildings, globfp, wsf = invented.card_fixture(tmp_path)
    cache = tmp_path / "data/public_cache"
    rows = (
        invented.entry("bldg_3dglobfp", extension="zip"),
        invented.entry("bldg_wsf3d", extension="tif"),
    )
    for row, body in zip(rows, (globfp, wsf), strict=True):
        invented.store(cache, row, body)
    path = cache.parent / "assets/buildings/buildings.geojson"
    path.parent.mkdir(parents=True)
    path.write_bytes(buildings)
    from custodian.tests.building_fixture import bind_height_table

    rows = bind_height_table(cache, rows, path)
    state = context(cache, rows)
    state.selected = reviewed_selections(cache)
    state.heights()
    result = json.loads((cache / "assembly/heights.json").read_text())
    assert result["state"] == "built"
    assert set(state.data_files) == {
        "assets/heights/heights.json",
        "assets/heights/manifest.heights.json",
        "assets/buildings/buildings.geojson",
        "assets/buildings/manifest.buildings.json",
    }
    bound_files(cache.parent, state.data_files)
    (cache.parent / "assets/heights/heights.json").write_text("[]")
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        state.final_audit()


def test_reconciliation_adapter_calls_real_builder_and_binds_both_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    from custodian.tests import test_trade_reconciliation_release as fixture

    from eii_custodian.publicdata import trade_reconciliation as native

    monkeypatch.setattr(native, "load_selection", fixture.selection)
    monkeypatch.setattr(native, "read_portal", fixture.portal)
    state = context(tmp_path)
    state.trade_reconciliation()
    record = json.loads((tmp_path / "assembly/trade_reconciliation.json").read_text())
    assert record["state"] == "built"
    assert (
        len([name for name in state.files if name.startswith("trade_reconciliation/")])
        == 2
    )
    name = next(
        name
        for name in state.files
        if name.startswith("trade_reconciliation/")
        and not name.endswith(".manifest.json")
    )
    (tmp_path / name).write_text("{}")
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        state.final_audit()


def test_seed_file_is_fsynced_before_first_phase_or_clock(
    tmp_path: Path, monkeypatch
) -> None:
    import os

    calls = []
    original = os.fsync

    def syncing(fd):
        calls.append("fsync")
        return original(fd)

    monkeypatch.setattr(os, "fsync", syncing)
    state = context(tmp_path)

    def clock():
        assert calls == ["fsync"]
        assert (
            json.loads((tmp_path / "assembly/build.json").read_text())["figure_seed"]
            == 17
        )
        raise AssemblyError("SYN-stopped-after-durable-seed")

    state.clock = clock
    with pytest.raises(AssemblyError, match="SYN-stopped-after-durable-seed"):
        state.run()


def test_reconciliation_adapter_preserves_explicit_typed_selection(
    tmp_path: Path, monkeypatch
) -> None:
    from custodian.tests import test_trade_reconciliation_release as fixture

    from eii_custodian.publicdata import trade_reconciliation as native

    monkeypatch.setattr(native, "load_selection", lambda: None)
    monkeypatch.setattr(native, "read_portal", fixture.portal)
    state = context(tmp_path)
    state.reconciliation_selection = fixture.selection()
    state.trade_reconciliation()
    assert (
        json.loads((tmp_path / "assembly/trade_reconciliation.json").read_text())[
            "state"
        ]
        == "built"
    )


def test_frame_credits_a_grid_table_whose_sources_are_keyed_by_entry_key(
    tmp_path: Path, monkeypatch
) -> None:
    # asm14 (L-1987): the grid producers key their receipts by entry key
    # (one per month or band), so a frame table of theirs was never indexed
    # and the draw refused it as assembly_draw_table_unindexed.
    from custodian.tests.building_fixture import PARTS, world

    from eii_custodian.publicdata import assembly_adapters

    prepared = world(tmp_path)
    names = ("municipality", "zone", "district", "grid_cell")
    prepared.entries = tuple(
        replace(
            row,
            release_tables=("pub_night_lights",)
            if row.key == PARTS[0]
            else names
            if row.source_id == "bnd_hdx"
            else (),
        )
        for row in prepared.entries
    )
    build = context(prepared.cache, prepared.entries)
    build.selected = prepared.selected
    build.reviewed_selections()

    def frame(*_args, **_kwargs):
        prepared.produce()
        directory = prepared.cache / "places_s2_t06"
        directory.mkdir()
        for filename in (
            "pub_place.jsonl",
            "pub_place_verification.jsonl",
            "place_points.json",
            "build_report.json",
            "flagship_check.json",
        ):
            (directory / filename).write_text("[]")
        tables = {
            name: [{"municipality_code": "SYN-M", "name_en": "SYN", "name_ar": "SYN"}]
            for name in names
        }
        tables["pub_night_lights"] = [{"cell": 1, "period": "2024-01"}]
        return FrameResult(
            tables,
            [],
            {
                "bnd_hdx": {"sha256": "a" * 64},
                "bnd_zone_2020": {"sha256": "b" * 64},
                PARTS[0]: {"sha256": "c" * 64},
            },
        )

    monkeypatch.setattr(assembly_adapters, "build_public_frame", frame)
    build.frame()
    assert build.tables["pub_night_lights"] == [{"cell": 1, "period": "2024-01"}]
    assert build.table_sources["pub_night_lights"] == {PARTS[0]}
    assert PARTS[1] not in build.table_sources["pub_night_lights"]
