"""Invented S2 outputs and receipts exercise the production envelope adapter."""

from __future__ import annotations

import hashlib
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from custodian.tests.test_frame_live_survivors import _build, _world
from hypothesis import example, given
from hypothesis import strategies as st
from public_assembly_fixture import approve, dump, inputs

from eii_core.manifest import ColumnSpec
from eii_custodian.publicdata.fetch.registry import PUBLIC_RECEIPT_KINDS
from eii_custodian.publicdata.frame import live
from eii_custodian.publicdata.grids.build import (
    FACT_LINEAGE,
    SOURCE_REGISTRY,
    GridResult,
)
from eii_custodian.release import producer
from eii_custodian.release.assembly import read_assembly


@pytest.fixture(scope="module")
def warm_frame_entry_cache(tmp_path_factory):
    with tempfile.TemporaryDirectory(
        prefix="INVENTED-warm-", dir=tmp_path_factory.getbasetemp()
    ) as folder:
        _world(Path(folder))


def frame_with_grids(tmp_path, tables, lineage_names):
    with tempfile.TemporaryDirectory(prefix="INVENTED-frame-", dir=tmp_path) as folder:
        prepared = _world(Path(folder))
        grids = GridResult(
            {
                **tables,
                **{name: [{"INVENTED-lineage": name}] for name in lineage_names},
            },
            {},
            {},
        )
        with patch.object(live, "build_grids", return_value=grids):
            return _build(prepared, Path(folder) / "output")


@pytest.mark.parametrize("lineage_name", [FACT_LINEAGE, SOURCE_REGISTRY])
def test_frame_keeps_each_grid_lineage_by_product(tmp_path, lineage_name):
    rows = [dict(cell=1, period="2026-01")]
    result = frame_with_grids(tmp_path, {"pub_night_lights": rows}, [lineage_name])
    assert result.tables[lineage_name] == [{"INVENTED-lineage": lineage_name}]
    assert result.tables["pub_night_lights"] == rows


@given(
    tables=st.dictionaries(
        st.text(alphabet="abc", max_size=4).map("INVENTED-grid-".__add__),
        st.just([{"INVENTED-value": "INVENTED-row"}]),
        max_size=4,
    )
)
@example({})
@example({"INVENTED-grid-a": [{"INVENTED-value": "INVENTED-row"}]})
def test_frame_preserves_every_grid_table(
    tmp_path_factory, warm_frame_entry_cache, tables
):
    lineage = {
        name: [{"INVENTED-lineage": name}] for name in (FACT_LINEAGE, SOURCE_REGISTRY)
    }
    with tempfile.TemporaryDirectory(
        prefix="INVENTED-property-", dir=tmp_path_factory.getbasetemp()
    ) as folder:
        result = frame_with_grids(Path(folder), tables, list(lineage))
    assert all(result.tables[name] == rows for name, rows in tables.items())
    assert all(result.tables[name] == rows for name, rows in lineage.items())


def test_frame_record_to_producer_ignores_grid_by_products(tmp_path):
    rows = [dict(cell=1, period="2026-01")]
    frame = frame_with_grids(
        tmp_path,
        {"pub_night_lights": rows},
        [FACT_LINEAGE, SOURCE_REGISTRY],
    )
    cache = tmp_path / "INVENTED-cache"
    spec = inputs(cache)
    phase = json.loads((cache / "assembly/gis_property_singles.json").read_bytes())
    dump(
        cache / "assembly/frame.json",
        dict(
            method="public-assembly.frame",
            method_version="1",
            source_chain=phase["source_chain"],
            table_sources={"pub_night_lights": ["INVENTED-source"]},
            tables={
                name: frame.tables[name]
                for name in ("pub_night_lights", FACT_LINEAGE, SOURCE_REGISTRY)
            },
        ),
    )
    spec["tables"].append(
        dict(
            name="pub_night_lights",
            phase="frame",
            columns=[
                dict(name="cell", logical_type="cell", nullable=False),
                dict(name="period", logical_type="month", nullable=False),
            ],
            source_keys=["INVENTED-source"],
        )
    )
    dump(cache / "review/release_spec.json", spec)
    approve(cache)
    document = producer.produce(cache)
    tables = {item["name"]: item for item in document["tables"]}
    assert tables["pub_night_lights"]["rows"] == [
        dict(cell=1, period="2026-01", source_id="INVENTED-source")
    ]
    chain = tables["fact_lineage"]["rows"]
    assert {item["table_name"] for item in chain} == set(tables)
    edge = next(item for item in chain if item["table_name"] == "pub_night_lights")
    assert edge["source_id"] == "INVENTED-source"
    assert edge["transform"] == (
        "eii_custodian.publicdata.assembly_adapters.Production.frame@1"
    )
    source = next(
        row
        for row in tables["source_registry"]["rows"]
        if row["source_id"] == edge["source_id"]
    )
    assert source["publisher"] == "INVENTED-publisher"
    assert source["licence"] == "INVENTED-licence"
    assert source["retrieved_on"] == "2026-01-02"
    assert source["sha256"] == spec["sources"]["INVENTED-source"]["body"]["sha256"]


def test_same_inputs_produce_identical_envelope_review_and_full_chain(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    spec = inputs(cache)
    expected = approve(cache)
    producer.produce(cache)
    paths = [
        cache / "assembly" / name for name in ("release.json", "release_review.json")
    ]
    first = [path.read_bytes() for path in paths]
    assert read_assembly(cache) == expected
    producer.produce(cache)
    assert [path.read_bytes() for path in paths] == first
    tables = {item["name"]: item for item in expected["tables"]}
    row = tables["pub_bank_credit"]["rows"][0]
    assert row == dict(period="2026", value="25.00", source_id="INVENTED-source")
    chain = tables["fact_lineage"]["rows"]
    assert {item["table_name"] for item in chain} == set(tables)
    edge = next(item for item in chain if item["table_name"] == "pub_bank_credit")
    assert edge["transform"] == (
        "eii_custodian.publicdata.assembly_adapters.Production.gis_property_singles@1"
    )
    assert edge["input_class"] == "public"
    source = tables["source_registry"]["rows"][0]
    assert source["sha256"] == spec["sources"]["INVENTED-source"]["body"]["sha256"]
    assert source["publisher"] == "INVENTED-publisher"
    assert source["licence"] == "INVENTED-licence"
    assert source["retrieved_on"] == "2026-01-02"
    assert expected["sources"][0]["source_id"] == edge["source_id"]
    assert "assembly/final_audit.json" in expected["files"]
    for link in spec["sources"]["INVENTED-source"].values():
        if isinstance(link, dict):
            assert expected["files"][link["path"]] == link["sha256"]


def change_receipt(cache, spec, mutate):
    ref = spec["sources"]["INVENTED-source"]["receipt"]
    path = cache / ref["path"]
    receipt = json.loads(path.read_bytes())
    mutate(receipt)
    ref["sha256"] = dump(path, receipt)
    dump(cache / "review/release_spec.json", spec)


def change_phase(cache, mutate):
    path = cache / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    mutate(phase)
    dump(path, phase)


def change_citation(cache, spec, fields):
    """Reseal both copies so a chain comparison cannot mask a receipt guard."""
    change_receipt(cache, spec, lambda receipt: receipt.update(fields))
    change_phase(
        cache, lambda phase: phase["source_chain"]["INVENTED-source"].update(fields)
    )


def refuses_without_candidate(cache, reason):
    with pytest.raises(ValueError, match="^" + reason + "$"):
        producer.prepare(cache)
    for name in ("release_candidate.json", "release.json", "release_review.json"):
        assert not (cache / "assembly" / name).exists()


def two_source_inputs(cache):
    """Two distinct INVENTED receipt/body pairs bound to the same table."""
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    spec = inputs(cache)
    first = spec["sources"]["INVENTED-source"]
    receipt = json.loads((cache / first["receipt"]["path"]).read_bytes())
    receipt.pop("sha256")
    receipt.pop("bytes")
    receipt.update(
        source_id="INVENTED-second",
        key="INVENTED-second",
        title_en="INVENTED-second-series",
        fetch_url="https://invented.invalid/second",
    )
    snapshot = publish_snapshot(cache / "INVENTED-second", "json", b"[]", receipt)
    spec["sources"]["INVENTED-second"] = dict(
        format="sidecar",
        receipt=dict(
            path=snapshot.receipt_path.relative_to(cache).as_posix(),
            sha256=hashlib.sha256(snapshot.receipt_path.read_bytes()).hexdigest(),
        ),
        body=dict(
            path=snapshot.path.relative_to(cache).as_posix(), sha256=snapshot.sha256
        ),
    )
    keys = ["INVENTED-source", "INVENTED-second"]
    spec["tables"][0]["source_keys"] = keys
    dump(cache / "review/release_spec.json", spec)

    def bind(phase):
        phase["source_chain"]["INVENTED-second"] = dict(snapshot.sidecar)
        phase["table_sources"]["pub_bank_credit"] = keys

    change_phase(cache, bind)
    return spec


@pytest.mark.parametrize("link", ["receipt", "body"])
def test_missing_receipt_or_body_is_refused(tmp_path, link):
    spec = inputs(tmp_path)
    (tmp_path / spec["sources"]["INVENTED-source"][link]["path"]).unlink()
    with pytest.raises(ValueError, match="producer_receipt_missing"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize("link", ["receipt", "body"])
def test_hash_mismatch_is_refused(tmp_path, link):
    spec = inputs(tmp_path)
    (tmp_path / spec["sources"]["INVENTED-source"][link]["path"]).write_bytes(b"{}")
    with pytest.raises(ValueError, match="producer_hash_mismatch"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "kind",
    [
        "synthetic_feed",
        "simulation_output",
        "INVENTED-unknown",
        "cdse_backup",
        "citation_only",
    ],
)
def test_non_public_receipt_kind_is_refused_even_with_resealed_hash(tmp_path, kind):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.update(kind=kind))
    with pytest.raises(ValueError, match="producer_non_public"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "field",
    ["title_en", "publisher", "licence_id", "retrieved_utc", "fetch_url", "sha256"],
)
def test_incomplete_source_chain_is_refused(tmp_path, field):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.pop(field))
    with pytest.raises(ValueError, match="producer_receipt_" + field + "_invalid"):
        producer.prepare(tmp_path)


def test_receipt_body_hash_disagreement_is_refused_after_resealing(tmp_path):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.update(sha256="ab" * 32))
    change_phase(
        tmp_path,
        lambda phase: phase["source_chain"]["INVENTED-source"].update(sha256="ab" * 32),
    )
    refuses_without_candidate(tmp_path, "producer_receipt_body_hash_mismatch")


@pytest.mark.parametrize(
    "name",
    [
        "INVENTED-unknown",
        "resident_pay",
        "presence_count",
        "source_registry",
        "fact_lineage",
    ],
)
def test_unknown_or_non_public_table_is_refused(tmp_path, name):
    spec = inputs(tmp_path)
    phase_path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(phase_path.read_bytes())
    phase["tables"][name] = phase["tables"].pop("pub_bank_credit")
    dump(phase_path, phase)
    spec["tables"][0]["name"] = name
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_table_refused"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "plant",
    [
        "method",
        "method_version",
        "source_keys",
        "row_source",
        "extra_field",
        "omitted_table",
        "phase_source",
    ],
)
def test_fact_without_complete_chain_or_schema_refuses(tmp_path, plant):
    spec = inputs(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    if plant in {"method", "method_version"}:
        phase.pop(plant)
    elif plant == "source_keys":
        spec["tables"][0]["source_keys"] = []
    elif plant == "row_source":
        phase["tables"]["pub_bank_credit"][0]["source_id"] = "INVENTED-other"
    elif plant == "extra_field":
        phase["tables"]["pub_bank_credit"][0]["untyped_number"] = 5
    elif plant == "omitted_table":
        spec["tables"] = []
    else:
        phase["source_chain"]["INVENTED-source"]["sha256"] = "ab" * 32
    dump(path, phase)
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(
        ValueError, match=r"producer_chain_incomplete|producer_schema_refused"
    ):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "plant",
    ["missing", "hash", "same_maker", "verdict", "code", "extra_key", "blank_builder"],
)
def test_review_never_fabricated_or_rebound_for_changed_inputs(tmp_path, plant):
    inputs(tmp_path)
    approve(tmp_path)
    path = tmp_path / "review/release_approval.json"
    review = json.loads(path.read_bytes())
    if plant == "missing":
        path.unlink()
    else:
        if plant == "hash":
            review["input_sha256"] = "ab" * 32
        elif plant == "same_maker":
            review["reviewer"] = " INVENTED-BUILDER "
        elif plant == "verdict":
            review["verdict"] = "PENDING"
        elif plant == "extra_key":
            review["note"] = "INVENTED-extra"
        elif plant == "blank_builder":
            review["builder"] = "  "
        else:
            review["code_version"] = "ab" * 20
        dump(path, review)
    with pytest.raises(
        ValueError,
        match={
            "missing": "candidate_written_approval_missing",
            "hash": "approval_hash_mismatch",
            "same_maker": "approval_same_maker",
            "verdict": "approval_verdict_invalid",
            "code": "approval_code_mismatch",
            "extra_key": "approval_fields_invalid",
            "blank_builder": "approval_builder_invalid",
        }[plant],
    ):
        producer.produce(tmp_path)
    assert (tmp_path / "assembly/release_candidate.json").is_file()
    assert not (tmp_path / "assembly/release.json").exists()
    assert not (tmp_path / "assembly/release_review.json").exists()


def test_stale_approval_does_not_sign_changed_phase_rows(tmp_path):
    inputs(tmp_path)
    approve(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["tables"]["pub_bank_credit"][0]["value"] = "26.00"
    dump(path, phase)
    with pytest.raises(ValueError, match="approval_hash_mismatch"):
        producer.produce(tmp_path)


def test_native_manifest_receipt_uses_same_adapter(tmp_path):
    spec = inputs(tmp_path)
    ref = spec["sources"]["INVENTED-source"]
    receipt = json.loads((tmp_path / ref["receipt"]["path"]).read_bytes())
    path = "INVENTED-source/INVENTED.manifest.json"
    digest = dump(tmp_path / path, dict(receipt=receipt, outputs={}))
    ref.update(format="manifest", receipt=dict(path=path, sha256=digest))
    dump(tmp_path / "review/release_spec.json", spec)
    approve(tmp_path)
    producer.produce(tmp_path)
    assert read_assembly(tmp_path)["sources"][0]["publisher"] == receipt["publisher"]


@pytest.mark.parametrize("plant", ["traversal", "absolute", "symlink"])
def test_input_paths_stay_inside_cache(tmp_path, plant):
    cache = tmp_path / "INVENTED-cache"
    spec = inputs(cache)
    ref = spec["sources"]["INVENTED-source"]["body"]
    if plant == "traversal":
        ref["path"] = "../INVENTED-outside"
    elif plant == "absolute":
        ref["path"] = "/INVENTED-outside"
    else:
        (cache / "INVENTED-alias").symlink_to(
            cache / "INVENTED-source", target_is_directory=True
        )
        ref["path"] = ref["path"].replace("INVENTED-source/", "INVENTED-alias/")
    dump(cache / "review/release_spec.json", spec)
    with pytest.raises(
        ValueError,
        match="assembly_path_invalid"
        if plant == "symlink"
        else "assembly_output_invalid",
    ):
        producer.prepare(cache)


def test_pending_final_audit_remains_blocking(tmp_path):
    inputs(tmp_path)
    path = tmp_path / "assembly/final_audit.json"
    audit = json.loads(path.read_bytes())
    audit["oi03"]["state"] = "pending"
    dump(path, audit)
    with pytest.raises(ValueError, match="assembly_gate_pending"):
        producer.prepare(tmp_path)


def test_artifact_bytes_are_bound_and_copied_as_descriptors(tmp_path):
    spec = inputs(tmp_path)
    path = "artefacts/INVENTED-evidence.json"
    digest = dump(tmp_path / path, dict(method="INVENTED-evidence.v1"))
    spec["artefacts"] = [dict(path=path, sha256=digest)]
    dump(tmp_path / "review/release_spec.json", spec)
    approve(tmp_path)
    producer.produce(tmp_path)
    envelope = read_assembly(tmp_path)
    assert envelope["artefacts"] == spec["artefacts"]
    assert envelope["files"][path] == digest


def test_spec_does_not_supply_or_override_original_rows(tmp_path):
    spec = inputs(tmp_path)
    spec["tables"][0]["rows"] = [dict(value="999.00")]
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_schema_refused"):
        producer.prepare(tmp_path)


def test_producer_reader_and_native_build_release_end_to_end(tmp_path):
    from eii_product.store.release_check import check_release
    from operations.build import build_release

    root = Path(__file__).resolve().parents[2]
    cache = tmp_path / "INVENTED-cache"
    graph_inputs(cache)
    expected = approve(cache)
    assert not (cache / "assembly/release.json").exists()
    destination = build_release(
        tmp_path,
        code_root=root,
        cache=cache,
        extensions=root / "data/engine_extensions",
    )
    assert read_assembly(cache) == expected
    checked = check_release(destination)
    assert checked.document["release_id"] == destination.name
    assert checked.document["sources"] == expected["sources"]
    assert list((tmp_path / ".operations/build").iterdir()) == []


def test_existing_s2_bank_builder_supplies_original_rows_and_receipt(tmp_path):
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_source_completeness import entry

    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    spec = inputs(tmp_path)
    row = replace(
        entry(),
        source_id="bank_credit_act",
        key="INVENTED-source",
        release_tables=("pub_bank_credit",),
        publisher="INVENTED-publisher",
        title_en="INVENTED-bank-credit",
    )
    write_cached(
        tmp_path,
        row,
        json.dumps(
            [
                dict(
                    year="2026",
                    economic_activity="INVENTED-activity",
                    lnsht_lqtsdy="INVENTED-label",
                    value=25,
                )
            ]
        ).encode(),
    )
    pins = json.loads((tmp_path / "snapshot_pins.json").read_bytes())
    state = context(tmp_path, (row,))
    state.selected = pins
    state.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    state.gis_property_singles()
    phase = json.loads((tmp_path / "assembly/gis_property_singles.json").read_bytes())
    assert phase["table_sources"] == {"pub_bank_credit": [row.key]}
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    snapshot = read_snapshot(tmp_path / row.key, pins[row.key])
    spec["sources"][row.key] = dict(
        format="sidecar",
        receipt=dict(
            path=snapshot.receipt_path.relative_to(tmp_path).as_posix(),
            sha256=hashlib.sha256(snapshot.receipt_path.read_bytes()).hexdigest(),
        ),
        body=dict(
            path=snapshot.path.relative_to(tmp_path).as_posix(), sha256=snapshot.sha256
        ),
    )
    spec["tables"][0]["columns"].extend(
        [
            dict(name="activity_key", logical_type="string", nullable=False),
            dict(name="unit", logical_type="string", nullable=True),
        ]
    )
    dump(tmp_path / "review/release_spec.json", spec)
    approve(tmp_path)
    result = producer.produce(tmp_path)
    table = next(item for item in result["tables"] if item["name"] == "pub_bank_credit")
    assert table["rows"] == [
        dict(
            period="2026",
            activity_key="INVENTED-activity",
            value="25.00",
            unit=None,
            source_id=row.key,
        )
    ]


@pytest.mark.parametrize("selected_phase", ["gis_property_singles", "series_stage"])
def test_duplicate_table_in_another_phase_cannot_hide_behind_spec(
    tmp_path, selected_phase
):
    spec = inputs(tmp_path)
    phase = json.loads((tmp_path / "assembly/gis_property_singles.json").read_bytes())
    phase["method"] = "public-assembly.series_stage"
    phase["tables"]["pub_bank_credit"][0]["value"] = "99.00"
    dump(tmp_path / "assembly/series_stage.json", phase)
    spec["tables"][0]["phase"] = selected_phase
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_schema_refused"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize("binding", ["source_tables", "table_sources"])
def test_declared_phase_input_cannot_be_left_out_of_fact_lineage(tmp_path, binding):
    inputs(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase[binding] = (
        {
            "INVENTED-source": ["pub_bank_credit"],
            "INVENTED-required-other": ["pub_bank_credit"],
        }
        if binding == "source_tables"
        else {"pub_bank_credit": ["INVENTED-source", "INVENTED-required-other"]}
    )
    dump(path, phase)
    with pytest.raises(ValueError, match="producer_chain_incomplete"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize("field", ["provenance", "origin", "input_class"])
@pytest.mark.parametrize("kind", ["synthetic", "simulated", "INVENTED-unknown"])
def test_generated_or_unknown_row_kind_never_gets_a_public_lineage(
    tmp_path, field, kind
):
    inputs(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["tables"]["pub_bank_credit"][0][field] = kind
    dump(path, phase)
    with pytest.raises(ValueError, match="producer_non_public"):
        producer.prepare(tmp_path)


def test_json_decimal_lexeme_is_preserved_without_binary_float(tmp_path):
    inputs(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    path.write_text(path.read_text().replace('"25.00"', "25.00"))
    candidate = producer.prepare(tmp_path)
    table = next(
        item for item in candidate["tables"] if item["name"] == "pub_bank_credit"
    )
    assert table["rows"][0]["value"] == "25.00"


@pytest.mark.parametrize("value", ["25.001", "NaN", "Infinity", True, "INVENTED-text"])
def test_numeric_value_cannot_be_silently_rounded_or_coerced(tmp_path, value):
    inputs(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["tables"]["pub_bank_credit"][0]["value"] = value
    dump(path, phase)
    with pytest.raises(ValueError, match="producer_schema_refused"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize("plant", ["nullable", "type", "duplicate"])
def test_column_schema_must_be_typed_and_unambiguous(tmp_path, plant):
    spec = inputs(tmp_path)
    column = spec["tables"][0]["columns"][0]
    if plant == "nullable":
        column["nullable"] = "INVENTED-wrong-type"
    elif plant == "type":
        column["logical_type"] = "INVENTED-wrong-type"
    else:
        spec["tables"][0]["columns"].append(dict(column))
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_schema_refused"):
        producer.prepare(tmp_path)


def test_unknown_phase_version_cannot_be_attributed_to_current_builder(tmp_path):
    inputs(tmp_path)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["method_version"] = "INVENTED-unimplemented"
    dump(path, phase)
    with pytest.raises(ValueError, match="producer_chain_incomplete"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "url",
    [
        "https://invented.invalid/credit?api_key=INVENTED-token",
        "https://invented.invalid/credit#INVENTED-fragment",
        "https://INVENTED-user:INVENTED-token" + chr(64) + "invented.invalid/credit",
    ],
    ids=["query", "fragment", "userinfo"],
)
def test_citation_url_cannot_carry_credentials(tmp_path, url):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.update(fetch_url=url))
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["source_chain"]["INVENTED-source"]["fetch_url"] = url
    dump(path, phase)
    with pytest.raises(ValueError, match="producer_receipt_url_invalid"):
        producer.prepare(tmp_path)
    assert not (tmp_path / "assembly/release_candidate.json").exists()


@pytest.mark.parametrize("link", ["receipt", "body"])
def test_both_missing_files_report_missing_receipt_before_hash_or_chain(tmp_path, link):
    spec = inputs(tmp_path)
    (tmp_path / spec["sources"]["INVENTED-source"][link]["path"]).unlink()
    with pytest.raises(ValueError, match="producer_receipt_missing"):
        producer.produce(tmp_path)
    assert not (tmp_path / "assembly/release_candidate.json").exists()


def graph_inputs(cache):
    """The existing S2 graph writer, with invented Public and lineage nodes."""
    from eii_custodian.publicdata.review.graph import (
        _EDGE_TYPES,
        _NODE_TYPES,
        EDGE_COLUMNS,
        NODE_COLUMNS,
        GraphEdge,
        GraphNode,
        _write_parquet,
    )

    spec = inputs(cache)
    phase_path = cache / "assembly/gis_property_singles.json"
    phase = json.loads(phase_path.read_bytes())
    graph = cache / "assembly/graph"
    graph.mkdir()
    nodes = [
        GraphNode(
            "activity:INVENTED-activity",
            "activity",
            "INVENTED-activity",
            "INVENTED-label",
            "",
            "public",
            "INVENTED-source",
        ),
        GraphNode(
            "source:INVENTED-source",
            "source",
            "INVENTED-source",
            "INVENTED-publisher",
            "",
            "lineage",
            "INVENTED-source",
        ),
    ]
    edges = [
        GraphEdge(
            "INVENTED-edge",
            "sourced_from",
            nodes[0].node_id,
            nodes[1].node_id,
            "lineage",
            "lineage",
            None,
            None,
            None,
            None,
            None,
            "INVENTED-source",
        )
    ]
    _write_parquet(graph / "graph_node.parquet", NODE_COLUMNS, _NODE_TYPES, nodes)
    _write_parquet(graph / "graph_edge.parquet", EDGE_COLUMNS, _EDGE_TYPES, edges)
    dump(
        cache / "assembly/spine_graph.json",
        dict(
            method="public-assembly.spine_graph",
            method_version="1",
            source_chain=phase["source_chain"],
            spine={},
            manifest={},
            left_out=[],
        ),
    )
    for name, columns in (("graph_node", NODE_COLUMNS), ("graph_edge", EDGE_COLUMNS)):
        spec["tables"].append(
            dict(
                name=name,
                phase="spine_graph",
                source_keys=["INVENTED-source"],
                columns=[
                    dict(
                        name=column,
                        logical_type="decimal(18,6)"
                        if column in {"attr_value", "attr_value_2"}
                        else "string",
                        nullable=column
                        in {
                            "period",
                            "attr_value",
                            "attr_value_2",
                            "attr_unit",
                            "attr_unit_2",
                        },
                    )
                    for column in columns
                ],
            )
        )
    dump(cache / "review/release_spec.json", spec)
    return spec


def test_existing_s2_graph_parquet_outputs_enter_the_envelope(tmp_path):
    graph_inputs(tmp_path)
    approve(tmp_path)
    document = producer.produce(tmp_path)
    tables = {item["name"]: item for item in document["tables"]}
    assert len(tables["graph_node"]["rows"]) == 2
    assert tables["graph_node"]["rows"][1]["provenance"] == "lineage"
    assert tables["graph_edge"]["rows"][0]["provenance"] == "lineage"
    assert {edge["table_name"] for edge in tables["fact_lineage"]["rows"]} == set(
        tables
    )
    assert "assembly/graph/graph_node.parquet" in document["files"]
    assert "assembly/graph/graph_edge.parquet" in document["files"]


@pytest.mark.parametrize("table", ["graph_node", "graph_edge"])
def test_generated_graph_row_refuses_even_with_otherwise_public_receipts(
    tmp_path, table
):
    from eii_custodian.publicdata.review import graph

    graph_inputs(tmp_path)
    path = tmp_path / "assembly/graph" / (table + ".parquet")
    from eii_custodian.publicdata.review.cache_fixture import read_parquet

    rows = [
        dict(row, provenance="synthetic") for row in read_parquet(path.read_bytes())
    ]
    columns = graph.NODE_COLUMNS if table == "graph_node" else graph.EDGE_COLUMNS
    types = graph._NODE_TYPES if table == "graph_node" else graph._EDGE_TYPES
    graph._write_parquet(
        path, columns, types, [tuple(row[column] for column in columns) for row in rows]
    )
    with pytest.raises(ValueError, match="producer_non_public"):
        producer.prepare(tmp_path)


@given(
    st.one_of(
        st.integers(min_value=-(10**8), max_value=10**8).map(lambda cents: cents * 100),
        st.integers(min_value=-(10**12), max_value=10**12),
    )
)
@example(0)
@example((10**6) * 10**4)
@example((10**6 - 1) * 10**4)
@example(1)
def test_decimal_encoding_matches_exact_decimal_storage_oracle(integer):
    value = Decimal(integer).scaleb(-4)
    column = ColumnSpec("value", "decimal(8,2)", False)
    fits = abs(value) < Decimal("1000000") and value == value.quantize(Decimal("0.01"))
    if fits:
        encoded = producer._value(value, column)
        assert encoded == str(value)
        assert Decimal(encoded) == value
    else:
        with pytest.raises(ValueError, match="producer_schema_refused"):
            producer._value(value, column)


def test_row_input_list_cannot_reference_an_unreleased_source(tmp_path):
    spec = inputs(tmp_path)
    spec["tables"][0]["columns"].append(
        dict(name="source_ids", logical_type="string", nullable=False)
    )
    dump(tmp_path / "review/release_spec.json", spec)
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["tables"]["pub_bank_credit"][0]["source_ids"] = (
        "INVENTED-source;INVENTED-missing"
    )
    dump(path, phase)
    with pytest.raises(ValueError, match="producer_chain_incomplete"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "path", [".env", "INVENTED-source/.env", ".private/INVENTED-body"]
)
def test_forbidden_input_name_is_refused_before_any_file_read(tmp_path, path):
    spec = inputs(tmp_path)
    spec["sources"]["INVENTED-source"]["body"]["path"] = path
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_path_refused"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("built_at", 5),
        ("build_id", ""),
        ("rules_version_id", []),
        ("release_contract_version", "INVENTED-unsupported"),
    ],
)
def test_common_build_metadata_is_typed_and_supported(tmp_path, field, value):
    spec = inputs(tmp_path)
    spec["scalars"][field] = value
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_schema_refused"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize("field", ["licence_id", "licence_basis"])
def test_citation_keeps_existing_licence_or_basis_policy_without_terms_gate(
    tmp_path, field
):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.update({field: ""}))
    path = tmp_path / "assembly/gis_property_singles.json"
    phase = json.loads(path.read_bytes())
    phase["source_chain"]["INVENTED-source"][field] = ""
    dump(path, phase)
    approve(tmp_path)
    producer.produce(tmp_path)
    document = read_assembly(tmp_path)
    assert document["sources"][0]["licence" if field == "licence_id" else field] == ""


@pytest.mark.parametrize("version", [True, "1", 2])
def test_spec_version_is_the_supported_integer(tmp_path, version):
    spec = inputs(tmp_path)
    spec["version"] = version
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match="producer_schema_refused"):
        producer.prepare(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "INVENTED-other"),
        ("publisher", "INVENTED-other"),
        ("licence_id", "INVENTED-other"),
        ("licence_basis", "INVENTED-other"),
        ("retrieved_utc", "2026-01-03T00:00:00Z"),
        ("fetch_url", "https://invented.invalid/other"),
    ],
)
def test_phase_chain_field_disagreeing_with_receipt_is_refused(tmp_path, field, value):
    inputs(tmp_path)
    change_phase(
        tmp_path,
        lambda phase: phase["source_chain"]["INVENTED-source"].update({field: value}),
    )
    refuses_without_candidate(tmp_path, "producer_chain_incomplete")


def test_citation_without_licence_or_basis_is_refused(tmp_path):
    spec = inputs(tmp_path)
    change_citation(tmp_path, spec, dict(licence_id="", licence_basis=""))
    # Decide the producer guard directly as well as the later chain check.
    with pytest.raises(ValueError, match=r"^producer_receipt_licence_missing$"):
        producer._source(
            tmp_path, "INVENTED-source", spec["sources"]["INVENTED-source"], {}
        )
    refuses_without_candidate(tmp_path, "producer_receipt_licence_missing")


@pytest.mark.parametrize("field", ["origin", "provenance", "input_class"])
def test_receipt_level_generated_class_is_refused(tmp_path, field):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.update({field: "synthetic"}))
    refuses_without_candidate(tmp_path, "producer_non_public")


@pytest.mark.parametrize(
    "fields",
    [dict(publisher="   "), dict(key="INVENTED-other-key"), dict(switched_off=True)],
    ids=["blank_publisher", "wrong_key", "switched_off"],
)
def test_unusable_or_misbound_receipt_is_refused(tmp_path, fields):
    spec = inputs(tmp_path)
    change_citation(tmp_path, spec, fields)
    refuses_without_candidate(
        tmp_path,
        {
            "publisher": "producer_receipt_publisher_invalid",
            "key": "producer_receipt_key_mismatch",
            "switched_off": "producer_receipt_switched_off",
        }[next(iter(fields))],
    )


@pytest.mark.parametrize(
    "fields",
    [
        dict(fetch_url="https:///credit"),
        dict(fetch_url="https://invented.invalid/a b"),
        dict(fetch_url="https://invented.invalid/a\tb"),
        dict(retrieved_utc="2026-13-45T00:00:00Z"),
    ],
    ids=["hostless", "space", "control", "invalid_date"],
)
def test_citation_url_and_retrieval_date_are_well_formed(tmp_path, fields):
    spec = inputs(tmp_path)
    change_citation(tmp_path, spec, fields)
    refuses_without_candidate(
        tmp_path,
        "producer_receipt_date_invalid"
        if "retrieved_utc" in fields
        else "producer_receipt_url_invalid",
    )


def test_row_without_tag_under_two_sources_is_refused(tmp_path):
    two_source_inputs(tmp_path)
    refuses_without_candidate(tmp_path, "producer_chain_incomplete")


def test_non_graph_row_cannot_claim_lineage_provenance(tmp_path):
    inputs(tmp_path)
    change_phase(
        tmp_path,
        lambda phase: phase["tables"]["pub_bank_credit"][0].update(
            provenance="lineage"
        ),
    )
    refuses_without_candidate(tmp_path, "producer_non_public")


def test_row_input_list_cannot_be_empty(tmp_path):
    spec = inputs(tmp_path)
    spec["tables"][0]["columns"].append(
        dict(name="source_ids", logical_type="string", nullable=False)
    )
    dump(tmp_path / "review/release_spec.json", spec)
    change_phase(
        tmp_path,
        lambda phase: phase["tables"]["pub_bank_credit"][0].update(source_ids=""),
    )
    refuses_without_candidate(tmp_path, "producer_chain_incomplete")


@pytest.mark.parametrize(
    "logical,value",
    [("int", "7"), ("int", True), ("int", 2**63), ("bool", 1), ("string", 7)],
    ids=["text_int", "bool_int", "overflow_int", "int_bool", "int_string"],
)
def test_typed_values_are_not_coerced(tmp_path, logical, value):
    spec = inputs(tmp_path)
    spec["tables"][0]["columns"].append(
        dict(name="INVENTED_extra", logical_type=logical, nullable=False)
    )
    dump(tmp_path / "review/release_spec.json", spec)
    change_phase(
        tmp_path,
        lambda phase: phase["tables"]["pub_bank_credit"][0].update(
            INVENTED_extra=value
        ),
    )
    refuses_without_candidate(tmp_path, "producer_schema_refused")


@pytest.mark.parametrize(
    "logical,value",
    [
        ("date", "2026-13-45"),
        ("timestamp", "2026-13-45T00:00:00Z"),
        ("geometry", {"wkb_hex": "INVENTED-invalid-hex"}),
        ("geometry", {"wkb_hex": 7}),
    ],
    ids=["date", "timestamp", "geometry_value", "geometry_type"],
)
def test_typed_decode_errors_have_closed_schema_refusal(tmp_path, logical, value):
    spec = inputs(tmp_path)
    column = dict(name="INVENTED_extra", logical_type=logical, nullable=False)
    if logical == "geometry":
        column.update(geometry_type="POINT", srid=4326)
    spec["tables"][0]["columns"].append(column)
    dump(tmp_path / "review/release_spec.json", spec)
    change_phase(
        tmp_path,
        lambda phase: phase["tables"]["pub_bank_credit"][0].update(
            INVENTED_extra=value
        ),
    )
    refuses_without_candidate(
        tmp_path,
        "input_type_invalid"
        if logical == "geometry" and value == {"wkb_hex": 7}
        else "producer_schema_refused",
    )


@pytest.mark.parametrize("logical", ["date", "month", "timestamp", "geometry"])
@pytest.mark.parametrize("error_type", [ValueError, TypeError])
def test_decode_exception_mapping_covers_each_typed_branch(
    monkeypatch, logical, error_type
):
    def reject(value, column):
        raise error_type("INVENTED-decode-error")

    monkeypatch.setattr(producer, "decode", reject)
    column = ColumnSpec("INVENTED_extra", logical, False)
    value = (
        {"wkb_hex": "INVENTED-invalid"} if logical == "geometry" else "INVENTED-invalid"
    )
    with pytest.raises(
        ValueError,
        match=r"^input_type_invalid$"
        if error_type is TypeError
        else r"^producer_schema_refused$",
    ):
        producer._value(value, column)


def test_omitted_graph_phase_table_cannot_disappear_from_release(tmp_path):
    spec = graph_inputs(tmp_path)
    spec["tables"] = [
        table for table in spec["tables"] if table["name"] != "graph_edge"
    ]
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(tmp_path, "producer_chain_incomplete")


def test_empty_spec_tables_without_a_phase_is_refused(tmp_path):
    spec = inputs(tmp_path)
    (tmp_path / "assembly/gis_property_singles.json").unlink()
    spec["tables"] = []
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(tmp_path, "producer_chain_incomplete")


@pytest.mark.parametrize("rewrite", [False, True], ids=["append", "rewrite"])
def test_gazetteer_combination_preserves_complete_frame_prefix(tmp_path, rewrite):
    spec = inputs(tmp_path)
    phase = json.loads((tmp_path / "assembly/gis_property_singles.json").read_bytes())
    original = [dict(name_en="INVENTED-a")]
    dump(
        tmp_path / "assembly/frame.json",
        dict(
            method="public-assembly.frame",
            method_version="1",
            source_chain=phase["source_chain"],
            tables=dict(gazetteer=original),
        ),
    )
    combined = [dict(name_en="INVENTED-rewritten")] if rewrite else original
    change_phase(
        tmp_path,
        lambda phase: phase["tables"].update(
            gazetteer=[*combined, dict(name_en="INVENTED-b")]
        ),
    )
    spec["tables"].append(
        dict(
            name="gazetteer",
            phase="gis_property_singles",
            columns=[dict(name="name_en", logical_type="string", nullable=False)],
            source_keys=["INVENTED-source"],
        )
    )
    dump(tmp_path / "review/release_spec.json", spec)
    if rewrite:
        refuses_without_candidate(tmp_path, "producer_schema_refused")
    else:
        candidate = producer.prepare(tmp_path)
        table = next(
            table for table in candidate["tables"] if table["name"] == "gazetteer"
        )
        assert table["rows"] == [*original, dict(name_en="INVENTED-b")]


def test_spec_cannot_list_the_same_table_twice(tmp_path):
    spec = inputs(tmp_path)
    spec["tables"].append(dict(spec["tables"][0]))
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(tmp_path, "producer_schema_refused")


@pytest.mark.parametrize("plant", ["empty", "duplicate", "unknown"])
def test_table_source_keys_must_be_nonempty_unique_and_released(tmp_path, plant):
    spec = inputs(tmp_path)
    spec["tables"][0]["source_keys"] = {
        "empty": [],
        "duplicate": ["INVENTED-source", "INVENTED-source"],
        "unknown": ["INVENTED-source", "INVENTED-unreleased"],
    }[plant]
    dump(tmp_path / "review/release_spec.json", spec)
    change_phase(tmp_path, lambda phase: phase.pop("table_sources"))
    refuses_without_candidate(tmp_path, "producer_chain_incomplete")


@pytest.mark.parametrize(
    "plant",
    [
        "hash_keys",
        "source_keys",
        "spec_keys",
        "scalar_keys",
        "format",
        "hash_case",
        "hash_short",
    ],
)
def test_input_spec_and_hash_references_have_closed_shapes(tmp_path, plant):
    spec = inputs(tmp_path)
    source = spec["sources"]["INVENTED-source"]
    if plant == "hash_keys":
        source["body"]["size"] = 1
    elif plant == "source_keys":
        source["note"] = "INVENTED-extra"
    elif plant == "spec_keys":
        spec["rows"] = []
    elif plant == "scalar_keys":
        spec["scalars"]["INVENTED_extra"] = "INVENTED-extra"
    elif plant == "format":
        source["format"] = "INVENTED-format"
    elif plant == "hash_case":
        source["body"]["sha256"] = source["body"]["sha256"].upper()
    else:
        source["body"]["sha256"] = source["body"]["sha256"][:-1]
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(
        tmp_path,
        "producer_receipt_format_invalid"
        if plant == "format"
        else "producer_schema_refused",
    )


@pytest.mark.parametrize("value", ["INVENTED-commit", "AB" * 20, "ab" * 19])
def test_code_version_is_a_full_lowercase_commit_hash(tmp_path, value):
    spec = inputs(tmp_path)
    spec["scalars"]["code_version"] = value
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(tmp_path, "producer_schema_refused")


def test_artefact_descriptors_must_be_a_list(tmp_path):
    spec = inputs(tmp_path)
    spec["artefacts"] = {}
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(tmp_path, "producer_schema_refused")


def test_artefact_path_must_use_artefacts_namespace(tmp_path):
    spec = inputs(tmp_path)
    path = "INVENTED-source/INVENTED-evidence.json"
    digest = dump(tmp_path / path, dict(method="INVENTED-evidence.v1"))
    spec["artefacts"] = [dict(path=path, sha256=digest)]
    dump(tmp_path / "review/release_spec.json", spec)
    refuses_without_candidate(tmp_path, "producer_path_refused")


@pytest.mark.parametrize("table", ["graph_node", "graph_edge"])
def test_missing_graph_file_has_closed_receipt_refusal(tmp_path, table):
    graph_inputs(tmp_path)
    (tmp_path / "assembly/graph" / (table + ".parquet")).unlink()
    refuses_without_candidate(tmp_path, "producer_receipt_missing")


def test_missing_final_audit_has_closed_receipt_refusal(tmp_path):
    inputs(tmp_path)
    (tmp_path / "assembly/final_audit.json").unlink()
    refuses_without_candidate(tmp_path, "producer_receipt_missing")


def test_final_audit_must_be_an_object(tmp_path):
    inputs(tmp_path)
    dump(tmp_path / "assembly/final_audit.json", [])
    with pytest.raises(ValueError, match=r"^producer_schema_refused$"):
        producer._read(tmp_path, "assembly/final_audit.json", {})
    refuses_without_candidate(tmp_path, "producer_schema_refused")


def test_same_inputs_in_two_cache_folders_give_identical_bytes(tmp_path):
    first, second = tmp_path / "INVENTED-cache", tmp_path / "INVENTED-other-cache"
    for cache in (first, second):
        two_source_inputs(cache)
        change_phase(
            cache,
            lambda phase: phase["tables"]["pub_bank_credit"][0].update(
                source_id="INVENTED-source"
            ),
        )
        approve(cache)
        producer.produce(cache)
    names = ("release_candidate.json", "release.json", "release_review.json")
    for name in names:
        assert (first / "assembly" / name).read_bytes() == (
            second / "assembly" / name
        ).read_bytes()

    # Reordering a bound input changes its digest and its approval. Its output
    # tables/citations must retain the same deterministic source order.
    spec_path = second / "review/release_spec.json"
    spec = json.loads(spec_path.read_bytes())
    spec["tables"][0]["source_keys"].reverse()
    dump(spec_path, spec)
    approve(second)
    producer.produce(second)
    left, right = read_assembly(first), read_assembly(second)
    for field in ("version", "scalars", "sources", "tables", "artefacts"):
        assert left[field] == right[field]
    lineage = next(
        table for table in right["tables"] if table["name"] == "fact_lineage"
    )
    assert [
        row["source_id"]
        for row in lineage["rows"]
        if row["table_name"] == "pub_bank_credit"
    ] == ["INVENTED-second", "INVENTED-source"]
    assert left["files"].pop("review/release_spec.json") != right["files"].pop(
        "review/release_spec.json"
    )
    assert left["files"] == right["files"]


def test_native_build_release_command_returns_success_and_verified_export(
    tmp_path, capsys
):
    from functools import partial
    from unittest.mock import patch

    from commands.main import main
    from eii_product.store.release_check import check_release
    from operations.build import build_release

    code = Path(__file__).resolve().parents[2]
    cache = tmp_path / "data/public_cache"
    graph_inputs(cache)
    expected = approve(cache)
    # Only relocate the invented operator root. Sandbox and validator defaults
    # remain the real run_in_sandbox and check_release implementations.
    with patch(
        "commands.build_release.build_release",
        partial(
            build_release, code_root=code, extensions=code / "data/engine_extensions"
        ),
    ):
        assert main(["build-release"], {}, tmp_path) == 0
    assert "PASS build-release:" in capsys.readouterr().out
    exports = list((tmp_path / "data/releases").iterdir())
    assert len(exports) == 1
    checked = check_release(exports[0])
    assert checked.document["release_id"] == exports[0].name
    assert checked.document["sources"] == expected["sources"]
    assert list((tmp_path / ".operations/build").iterdir()) == []


def test_public_receipt_kinds_are_exactly_the_approved_release_set():
    assert PUBLIC_RECEIPT_KINDS == frozenset(
        {
            "awards_intake",
            "besttime",
            "comtrade_api",
            "https_file",
            "paged_cards",
            "paged_layer",
            "portal_dataset",
            "public_dataset",
            "public_document",
            "public_page",
            "reviewed_config",
            "terms_page",
        }
    )


@pytest.mark.parametrize(
    "kind", ["cdse_backup", "citation_only", "register_file", "company_web"]
)
def test_refused_receipt_kind_never_reads_its_body(tmp_path, monkeypatch, kind):
    spec = inputs(tmp_path)
    change_receipt(tmp_path, spec, lambda receipt: receipt.update(kind=kind))
    body_path = tmp_path / spec["sources"]["INVENTED-source"]["body"]["path"]
    read_bytes = Path.read_bytes

    def guarded_read(path):
        if path == body_path:
            raise AssertionError("refused_source_body_read")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(ValueError, match="producer_non_public"):
        producer.prepare(tmp_path)
