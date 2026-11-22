"""A failed audit records itself before another admission can be attempted."""

import json
from typing import Any

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from test_spine_refusals import case as case
from test_spine_refusals import commit_refusals, refuse_audit, unit_refusal

from eii_custodian.publicdata.review.activity import audit_sample
from spine_refusals import previous_refusals
from spine_review import draw_audit, prepare_review_inputs
from spine_triage_io import Refusal


def test_cf5_same_draw_agreeing_audit_cannot_hide_refusal(case: Any) -> None:
    prepared, paths, drawn, agreeing, _ = refuse_audit(case)
    paths[1].write_bytes(agreeing)
    with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
        case.assemble(prepared, paths, "invented-agreeing", draw=drawn)
    assert not (prepared.parent / "invented-agreeing").exists()


@pytest.mark.parametrize("stage", ["prepare", "draw"])
def test_unrecorded_refusal_blocks_next_stage(case: Any, stage: str) -> None:
    prepared, paths, _, _, _ = refuse_audit(case)
    with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
        if stage == "prepare":
            prepare_review_inputs(
                case.root, case.cache, case.review, "invented-later", case.preparer
            )
        else:
            draw_audit(
                case.root,
                prepared / "manifest.json",
                paths[0],
                paths[2],
                "invented-later",
            )
    assert not (prepared.parent / "invented-later").exists()


def test_refusal_is_appended_as_identical_object(case: Any) -> None:
    prepared, _, _, _, _ = refuse_audit(case)
    record = json.loads(
        (prepared.parent / "invented-assembled/refusal.json").read_bytes()
    )
    archive = case.review.with_name("activity_spine_refusals.json")
    assert json.loads(archive.read_bytes()) == [record]
    assert not (prepared.parent / "invented-assembled/activity_spine.csv").exists()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_autoappend_keeps_prior_record_bytes(case: Any, count: int) -> None:
    from spine_review import derived_audit_seed

    signed, first = unit_refusal()
    records: list[dict[str, Any]] = []
    for _ in range(count):
        seed = derived_audit_seed(signed, records)
        records.append(
            {
                **first,
                "seed": seed,
                "sampled_codes": list(audit_sample(first["codes"], seed)),
            }
        )
    archive = case.review.with_name("activity_spine_refusals.json")
    body = (
        b" \r\n[\n"
        + b",\n".join(
            json.dumps(record, ensure_ascii=False, indent=2).encode()
            for record in records
        )
        + b"\n]\t "
    )
    archive.write_bytes(body)
    commit_refusals(case)
    prepared, _, _, _, _ = refuse_audit(case)
    refusal = json.loads(
        (prepared.parent / "invented-assembled/refusal.json").read_bytes()
    )
    emitted = archive.read_bytes()
    assert emitted.startswith(body[: body.rfind(b"]")])
    assert json.loads(emitted) == [*records, refusal]


def test_appended_refusal_cannot_be_committed_by_changing_bytes(case: Any) -> None:
    refuse_audit(case)
    archive = case.review.with_name("activity_spine_refusals.json")
    appended = archive.read_bytes()

    @given(st.binary())
    @example(b"")
    @example(b"\n")
    @example(b"\xff")
    def check(suffix: bytes) -> None:
        archive.write_bytes(appended + suffix)
        with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
            previous_refusals(case.root, case.review)

    check()


def test_commit_appended_refusal_requires_fresh_preparation(case: Any) -> None:
    prepared, paths, drawn, agreeing, _ = refuse_audit(case)
    archive = case.review.with_name("activity_spine_refusals.json")
    record = json.loads(archive.read_bytes())[0]
    commit_refusals(case)
    paths[1].write_bytes(agreeing)
    with pytest.raises(Refusal, match=r"^frozen_inputs_changed$"):
        case.assemble(prepared, paths, "invented-old-manifest", draw=drawn)
    fresh = prepare_review_inputs(
        case.root, case.cache, case.review, "invented-fresh", case.preparer
    )
    fresh_paths = case.returns(fresh)
    fresh_draw = case.draw(fresh, fresh_paths)
    assert json.loads(fresh_draw.read_bytes())["seed"] != record["seed"]
    candidate = case.assemble(fresh, fresh_paths, "invented-admitted", draw=fresh_draw)
    assert (
        json.loads((candidate / "activity_spine_audits.json").read_bytes())[0]["errors"]
        == 0
    )
    assert json.loads(archive.read_bytes()) == [record]
