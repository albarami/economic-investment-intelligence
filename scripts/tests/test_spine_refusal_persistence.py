"""A failed audit records itself before another admission can be attempted."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from eii_custodian.publicdata.review.activity import read_review_csv, write_review_csv
from spine_review import draw_audit, prepare_review_inputs
from spine_triage_io import Refusal
from test_spine_refusals import case as case  # noqa: F401


def refuse_audit(case: Any) -> tuple[Path, tuple[Path, Path, Path], Path, bytes]:
    prepared = case.prepare()
    paths = case.returns(prepared)
    drawn = case.draw(prepared, paths)
    agreeing = paths[1].read_bytes()
    audited = list(read_review_csv(paths[1]))
    audited[0] = replace(
        audited[0],
        isic_class="",
        status="not_mappable_rejected",
        reason="reviewer_rejected",
    )
    write_review_csv(paths[1], audited)
    with pytest.raises(Refusal, match=r"^audit_decision_differs$"):
        case.assemble(prepared, paths, draw=drawn)
    return prepared, paths, drawn, agreeing


def test_cf5_same_draw_agreeing_audit_cannot_hide_refusal(case: Any) -> None:
    prepared, paths, drawn, agreeing = refuse_audit(case)
    paths[1].write_bytes(agreeing)
    with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
        case.assemble(prepared, paths, "invented-agreeing", draw=drawn)
    assert not (prepared.parent / "invented-agreeing").exists()


@pytest.mark.parametrize("stage", ["prepare", "draw"])
def test_unrecorded_refusal_blocks_next_stage(case: Any, stage: str) -> None:
    prepared, paths, _, _ = refuse_audit(case)
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
    prepared, _, _, _ = refuse_audit(case)
    record = json.loads(
        (prepared.parent / "invented-assembled/refusal.json").read_bytes()
    )
    archive = case.review.with_name("activity_spine_refusals.json")
    assert json.loads(archive.read_bytes()) == [record]
    assert not (prepared.parent / "invented-assembled/activity_spine.csv").exists()
