"""Seed-shopping regression and derivation invariants; invented inputs only."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest
import test_spine_review

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import (
    audit_sample,
    read_review_csv,
    write_review_csv,
)
from eii_custodian.publicdata.review.cache_fixture import real_feed_body, write_cached
from spine_triage_io import Refusal


@pytest.fixture
def workflow() -> Any:
    case = test_spine_review.SpineReviewTest()
    case.setUp()
    try:
        yield case
    finally:
        case.doCleanups()


def many_returns(case: Any) -> tuple[Path, tuple[Path, Path, Path]]:
    entry = next(e for e in load_registry() if e.key == "lic_active")
    activities = [
        dict(
            activity_code=f"5610{index:03d}",
            activity_name_ar="نشاط مخترع",
            active_count=1,
        )
        for index in range(35)
    ]
    write_cached(case.cache, entry, real_feed_body("lic_active", activities))
    prepared = case.prepare()
    return prepared, case.returns(prepared)


def test_c1_audit_all_then_shop_seed_refuses(workflow: Any) -> None:
    prepared, paths = many_returns(workflow)
    disagreements = {"5610000", "5610001"}
    audited = tuple(
        replace(
            row,
            status="not_mappable_rejected",
            reason="reviewer_rejected",
            isic_class="",
        )
        if row.code in disagreements
        else row
        for row in read_review_csv(paths[1])
    )
    write_review_csv(paths[1], audited)  # Auditor has already judged every code.
    codes = [row.code for row in audited]
    chosen = next(
        seed
        for seed in range(1000000000, 1000001000)
        if not disagreements.intersection(audit_sample(codes, seed))
    )
    makers = json.loads(paths[2].read_bytes())
    paths[2].write_text(json.dumps({**makers, "seed": chosen}))
    try:
        drawn = workflow.draw(prepared, paths)
    except Refusal as error:
        assert str(error) == "audit_seed_not_derived"
        return
    sampled = json.loads(drawn.read_bytes())["sampled_codes"]
    write_review_csv(paths[1], [row for row in audited if row.code in sampled])
    candidate = workflow.assemble(prepared, paths, draw=drawn)
    result = json.loads((candidate / "activity_spine_audits.json").read_bytes())[-1]
    assert result["errors"] == 0
    pytest.fail(f"C1 attack admitted with errors=0 using chosen seed {chosen}")


def refused_history(case: Any) -> dict[str, object]:
    from spine_review import audit_record

    prepared = case.prepare()
    paths = case.returns(prepared)
    makers = json.loads(paths[2].read_bytes())
    decisions = tuple(row for row in read_review_csv(paths[0]) if row.code_length == 7)
    refused = {
        **audit_record(decisions, read_review_csv(paths[1]), makers),
        "errors": 1,
        "draw_sha256": "a" * 64,
        "review_rows": [asdict(row) for row in decisions],
    }
    from test_spine_refusals import commit_refusals

    commit_refusals(case, [refused])
    return refused


def seed_oracle(decisions: object, previous: dict[str, Any] | None = None) -> int:
    import hashlib

    encoder = json.JSONEncoder(
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if previous is not None:
        previous = {
            key: previous[key]
            for key in (
                "codes",
                "review_rows_sha256",
                "seed",
                "sampled_codes",
                "errors",
            )
        }
        previous["codes"] = sorted(previous["codes"])
    prior = (
        b""
        if previous is None
        else hashlib.sha256(encoder.encode(previous).encode()).hexdigest().encode()
    )
    digest = hashlib.sha256(
        b"oi203-audit-seed:" + encoder.encode(decisions).encode() + b":" + prior
    ).digest()
    return 1000000000 + int.from_bytes(digest, "big") % 3294967296


@pytest.mark.parametrize(
    ("variant", "entry"),
    [
        ("chosen", "read_makers"),
        ("chosen", "draw"),
        ("chosen", "assemble"),
        ("without_prior", "read_makers"),
        ("without_prior", "draw"),
        ("free_text", "read_makers"),
        ("free_text", "draw"),
        ("free_text", "assemble"),
    ],
)
def test_non_derived_seed_exact_refusal(
    workflow: Any, variant: str, entry: str
) -> None:
    from spine_review import frozen_context, prepare_review_inputs, read_makers

    prior = refused_history(workflow) if variant == "without_prior" else None
    prepared = prepare_review_inputs(
        workflow.root,
        workflow.cache,
        workflow.review,
        "invented-seed-negative",
        workflow.preparer,
    )
    paths = workflow.returns(prepared)
    record = json.loads(paths[2].read_bytes())
    decisions = [
        dict(code=row.code, status=row.status, isic_class=row.isic_class)
        for row in read_review_csv(paths[0])
        if row.code_length == 7
    ]
    if variant == "chosen":
        seed = record["seed"] + (1 if record["seed"] < 4294967295 else -1)
    elif variant == "without_prior":
        seed = seed_oracle(decisions)
    else:
        seed = seed_oracle(
            [{**row, "reason": "reviewer_approved"} for row in decisions]
        )
    assert seed != record["seed"]
    drawn = workflow.draw(prepared, paths) if entry == "assemble" else None
    paths[2].write_text(json.dumps({**record, "seed": seed}))  # One input changes.
    with pytest.raises(Refusal, match=r"^audit_seed_not_derived$"):
        if entry == "read_makers":
            context, _ = frozen_context(workflow.root, prepared / "manifest.json")
            read_makers(
                workflow.root,
                paths[2],
                workflow.preparer,
                context,
                read_review_csv(paths[0]),
                [prior] if prior else [],
            )
        elif entry == "draw":
            workflow.draw(prepared, paths)
        else:
            workflow.assemble(prepared, paths, draw=drawn)
    assert not (prepared.parent / "invented-assembled").exists()


def test_refused_unchanged_batch_gets_fresh_derived_draw(workflow: Any) -> None:
    from spine_review import derived_audit_seed, prepare_review_inputs

    prior = refused_history(workflow)
    prepared = prepare_review_inputs(
        workflow.root,
        workflow.cache,
        workflow.review,
        "invented-resigned",
        workflow.preparer,
    )
    paths = workflow.returns(prepared)
    decisions = tuple(row for row in read_review_csv(paths[0]) if row.code_length == 7)
    before = derived_audit_seed(decisions, [])
    after = derived_audit_seed(decisions, [prior])
    assert before == prior["seed"]
    assert after != before
    drawn = workflow.draw(prepared, paths)
    assert json.loads(drawn.read_bytes())["seed"] == after


def test_run_id_and_maker_metadata_cannot_shop_draw(workflow: Any) -> None:
    from spine_review import draw_audit

    prepared, paths = many_returns(workflow)
    first = json.loads(workflow.draw(prepared, paths).read_bytes())
    makers = json.loads(paths[2].read_bytes())
    paths[2].write_text(
        json.dumps(
            {**makers, "batch_id": "invented-another-id", "audit_date": "2026-11-23"}
        )
    )
    second = draw_audit(
        workflow.root,
        prepared / "manifest.json",
        paths[0],
        paths[2],
        "invented-another-run",
    )
    record = json.loads((second / "draw.json").read_bytes())
    assert record["seed"] == first["seed"]
    assert record["sampled_codes"] == first["sampled_codes"]


def test_draw_record_derives_seed_instead_of_copying_maker_seed() -> None:
    from spine_review import draw_record

    evidence = dict(
        manifest="invented-manifest", signer="invented-signer", makers="invented-makers"
    )
    makers = dict(seed=1000000000, batch_id="invented-batch")
    record = draw_record(evidence, (), makers, [])
    assert record["seed"] == seed_oracle([])


def test_refused_history_retains_core_zero_error_admission(workflow: Any) -> None:
    from eii_custodian.publicdata.review.activity import SpineError
    from spine_review import prepare_review_inputs

    prior = refused_history(workflow)
    workflow.review.with_name("activity_spine_audits.json").write_text(
        json.dumps(
            [
                {
                    key: value
                    for key, value in prior.items()
                    if key not in ("draw_sha256", "review_rows")
                }
            ]
        )
    )
    prepared = prepare_review_inputs(
        workflow.root,
        workflow.cache,
        workflow.review,
        "invented-admission-limit",
        workflow.preparer,
    )
    paths = workflow.returns(prepared)
    drawn = workflow.draw(prepared, paths)
    with pytest.raises(SpineError, match=r"^model audit errors are not zero$"):
        workflow.assemble(prepared, paths, draw=drawn)
    assert not (prepared.parent / "invented-assembled").exists()
