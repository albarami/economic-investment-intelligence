"""Actual writer inside the actual generator sandbox, on invented envelopes only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import public_release_fixture as fixture
import pytest

from eii_core.manifest import canonical_json
from eii_custodian.publicdata.gate_report import CONFIRMATION_TASKS
from eii_custodian.release.assembly import build, read_assembly
from eii_custodian.release.public_only import WriterRefusal
from eii_product.store.release_check import check_release
from operations.build import build_release

ROOT = Path(__file__).resolve().parents[2]


def json_value(value):
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return dict(wkb_hex=value.hex())
    raise TypeError("INVENTED-unsupported")


def envelope(cache):
    assembly = cache / "assembly"
    assembly.mkdir(parents=True)
    audit = dict(
        completeness=[dict(state="in use")],
        terms=[dict(own_words_state="pending")],
        oi03=dict(state="recorded"),
        confirmations=[
            dict(task=task, state="recorded") for task in CONFIRMATION_TASKS
        ],
        regressions=dict(missing=[], mismatch=""),
    )
    audit_path = assembly / "final_audit.json"
    audit_path.write_text(json.dumps(audit))
    tables = fixture.fixture_tables()
    document = dict(
        version=1,
        scalars=dict(fixture._scalars(), code_version="cd" * 20),
        sources=list(fixture._manifest_sources()),
        tables=[
            dict(
                name=table.name,
                columns=[asdict(c) for c in table.columns],
                rows=table.rows,
            )
            for table in tables
        ],
        artefacts=[],
        files={
            "assembly/final_audit.json": hashlib.sha256(
                audit_path.read_bytes()
            ).hexdigest()
        },
    )
    document = json.loads(json.dumps(document, default=json_value))
    (assembly / "release.json").write_text(json.dumps(document))
    review = dict(
        verdict="APPROVED",
        builder="INVENTED-builder",
        reviewer="INVENTED-other-maker",
        code_version="cd" * 20,
        input_sha256=hashlib.sha256(canonical_json(document).encode()).hexdigest(),
    )
    (assembly / "release_review.json").write_text(json.dumps(review))
    return document


def test_real_sandbox_writes_verified_public_export_and_removes_vault(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    expected = envelope(cache)
    target = build_release(
        tmp_path,
        code_root=ROOT,
        cache=cache,
        extensions=ROOT / "data/engine_extensions",
    )
    checked = check_release(target)
    assert checked.document["release_id"] == target.name
    assert checked.document["sources"] == expected["sources"]
    assert checked.document["code_version"] == "cd" * 20
    assert list((tmp_path / ".operations/build").iterdir()) == []
    before = (target / "manifest.json").read_bytes()
    repeated = build_release(
        tmp_path,
        code_root=ROOT,
        cache=cache,
        extensions=ROOT / "data/engine_extensions",
    )
    assert repeated == target
    assert (target / "manifest.json").read_bytes() == before


def test_review_and_bound_audit_each_refuse_without_native_engine(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    envelope(cache)
    read_assembly(cache)
    review_path = cache / "assembly/release_review.json"
    review = json.loads(review_path.read_bytes())
    review["input_sha256"] = "ab" * 32
    review_path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="approval_hash_mismatch"):
        read_assembly(cache)


@pytest.mark.parametrize("field", ["builder", "reviewer"])
@pytest.mark.parametrize("value", [[], True, "", " "])
def test_review_maker_must_be_a_nonempty_name(tmp_path, field, value):
    cache = tmp_path / "INVENTED-cache"
    envelope(cache)
    review_path = cache / "assembly/release_review.json"
    review = json.loads(review_path.read_bytes())
    review[field] = value
    review_path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="approval_" + field + "_invalid"):
        read_assembly(cache)


def test_same_maker_spelling_does_not_create_independence(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    envelope(cache)
    review_path = cache / "assembly/release_review.json"
    review = json.loads(review_path.read_bytes())
    review["reviewer"] = " INVENTED-BUILDER "
    review_path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="approval_same_maker"):
        read_assembly(cache)


@pytest.mark.parametrize(
    "table_name,field,value",
    [
        ("source_registry", "kind", "synthetic_feed"),
        ("source_registry", "kind", "simulation_output"),
        ("fact_lineage", "input_class", "synthetic"),
        ("fact_lineage", "input_class", "simulated"),
    ],
)
def test_reviewed_public_envelope_refuses_explicit_generated_producer(
    tmp_path, table_name, field, value
):
    cache = tmp_path / "INVENTED-input"
    document = envelope(cache)
    table = next(item for item in document["tables"] if item["name"] == table_name)
    assert field in table["rows"][0]
    table["rows"][0][field] = value
    # Keep review and every input hash coherent: the producing class, rather
    # than an unrelated envelope/review mismatch, must decide the refusal.
    (cache / "assembly/release.json").write_text(json.dumps(document))
    review_path = cache / "assembly/release_review.json"
    review = json.loads(review_path.read_bytes())
    review["input_sha256"] = hashlib.sha256(
        canonical_json(document).encode()
    ).hexdigest()
    review_path.write_text(json.dumps(review))
    read_assembly(cache)
    destination = tmp_path / "INVENTED-export"
    with pytest.raises(WriterRefusal, match="source_link_mismatch"):
        build(cache, destination)
    assert not destination.exists()
