"""Decision 0103: model-signed acknowledgements join the audited population.

Every code, name, role and date in this module is invented; nothing here reads
or signs a real queue.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import test_spine_review

from eii_custodian.publicdata.review.activity import (
    audit_sample,
    read_review_csv,
    write_review_csv,
)
from spine_triage_io import Refusal

SIGNER = "model review: invented_signer model, classification specialist"
AUDITOR = "model review: invented_auditor model, classification specialist"
LEGACY = "561099"  # The legacy code of the small invented queue.


@pytest.fixture
def case() -> Any:
    instance = test_spine_review.SpineReviewTest()
    instance.setUp()
    try:
        yield instance
    finally:
        instance.doCleanups()


def eligible(row: Any) -> bool:
    return bool(row.code_length == 7 and row.code[:4] == "5610")


def decisions_of(
    case: Any, prepared: Path, paths: tuple[Path, Path, Path]
) -> tuple[Any, ...]:
    """Read the decisions exactly as the keyed procedure does."""
    from spine_refusals import previous_refusals
    from spine_review import frozen_context, read_makers

    context, _ = frozen_context(case.root, prepared / "manifest.json")
    _, decisions = read_makers(
        case.root,
        paths[2],
        case.preparer,
        context,
        read_review_csv(paths[0]),
        previous_refusals(case.root, case.review),
    )
    return decisions


def returns(
    case: Any, ack_role: str, run_id: str, prepared: Path
) -> tuple[Path, Path, Path]:
    """Sign the prepared queue once; acknowledgement rows carry ``ack_role``."""
    from spine_review import derived_audit_seed

    rows: list[Any] = []
    for row in read_review_csv(prepared / "queue.csv"):
        if eligible(row):
            rows.append(
                replace(
                    row,
                    status="mapped",
                    reason="reviewer_approved",
                    isic_class=row.code[:4],
                    reviewed_by_role=SIGNER,
                    reviewed_on="2026-11-23",
                )
            )
        else:
            rows.append(
                replace(row, reviewed_by_role=ack_role, reviewed_on="2026-11-23")
            )
    decisions = tuple(
        row for row in rows if eligible(row) or row.reviewed_by_role == SIGNER
    )
    history = case.review.with_name("activity_spine_refusals.json")
    audits = json.loads(history.read_bytes()) if history.exists() else []
    record = dict(
        preparer_maker=case.preparer,
        signer_role=SIGNER,
        auditor_role=AUDITOR,
        batch_id="invented-batch",
        seed=derived_audit_seed(decisions, audits),
        audit_date="2026-11-24",
    )
    signed = case.cache / f"signed-{run_id}.csv"
    audited = case.cache / f"audited-{run_id}.csv"
    makers = case.cache / f"makers-{run_id}.json"
    write_review_csv(signed, rows)
    sampled = set(audit_sample([row.code for row in decisions], record["seed"]))
    write_review_csv(
        audited,
        [
            replace(row, reviewed_by_role=AUDITOR, reviewed_on="2026-11-24")
            for row in decisions
            if row.code in sampled
        ],
    )
    makers.write_text(json.dumps(record))
    return signed, audited, makers


def prepared_queue(case: Any, run_id: str) -> Path:
    from spine_review import prepare_review_inputs

    return prepare_review_inputs(
        case.root, case.cache, case.review, "ack-" + run_id, case.preparer
    )


def queue_shaped_like_the_real_one(case: Any) -> None:
    """271 eligible rows, 18 legacy rows, 7 invalid-prefix rows; all invented."""
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.review.cache_fixture import (
        real_feed_body,
        write_cached,
    )

    entry = next(e for e in load_registry() if e.key == "lic_active")
    rows: list[Any] = []
    for codes, count in (
        ((f"5610{index:03d}" for index in range(271)), 1),
        ((f"3{index:05d}" for index in range(18)), 9),
        ((f"99{index:05d}" for index in range(7)), 9),
    ):
        rows.extend(
            dict(
                activity_code=code,
                activity_name_ar="نشاط اصطناعي للاختبار",
                active_count=count,
            )
            for code in codes
        )
    write_cached(case.cache, entry, real_feed_body("lic_active", rows))


def test_signer_role_acknowledgements_join_the_whole_population(case: Any) -> None:
    queue_shaped_like_the_real_one(case)
    prepared = prepared_queue(case, "population")
    manifest = json.loads((prepared / "manifest.json").read_bytes())
    assert manifest["counts"] == dict(
        eligible_codes=271, acknowledgement_rows=25, excluded_groups=0
    )
    paths = returns(case, SIGNER, "population", prepared)
    decisions = decisions_of(case, prepared, paths)
    assert len(decisions) == 296
    assert {row.code_length for row in decisions} == {6, 7}
    seed = json.loads(paths[2].read_bytes())["seed"]
    drawn = case.draw(prepared, paths)
    assert set(json.loads(drawn.read_bytes())["sampled_codes"]) == set(
        audit_sample([row.code for row in decisions], seed)
    )
    candidate = case.assemble(prepared, paths, "invented-population", draw=drawn)
    audits = json.loads((candidate / "activity_spine_audits.json").read_bytes())
    assert audits[-1]["codes"] == sorted(row.code for row in decisions)


def test_other_model_role_refuses(case: Any) -> None:
    prepared = case.prepare()
    for run_id, role in (
        ("role-a", SIGNER.replace("invented_signer", "other_signer")),
        ("role-b", SIGNER.replace("classification", "classificatioN")),
    ):
        paths = returns(case, role, run_id, prepared)
        with pytest.raises(Refusal, match=r"^acknowledgement_role_invalid$"):
            decisions_of(case, prepared, paths)


def test_changed_acknowledgement_refuses(case: Any) -> None:
    prepared = case.prepare()
    paths = returns(case, SIGNER, "changed", prepared)
    signed = list(read_review_csv(paths[0]))
    index = next(position for position, row in enumerate(signed) if not eligible(row))
    original = signed[index]
    for changed in (
        replace(original, status="not_mappable_invalid_prefix"),
        replace(original, reason="invalid_isic_prefix"),
        replace(original, isic_class="5610"),
    ):
        signed[index] = changed
        write_review_csv(paths[0], signed)
        with pytest.raises(Refusal, match=r"^acknowledgement_decision_invalid$"):
            decisions_of(case, prepared, paths)
        signed[index] = original
        write_review_csv(paths[0], signed)


def test_person_acknowledgement_is_admitted_and_not_drawn(case: Any) -> None:
    prepared = case.prepare()
    paths = returns(case, "INVENTED acknowledgement", "person", prepared)
    decisions = decisions_of(case, prepared, paths)
    assert {row.code for row in decisions} == {"5610901", "5610902"}
    drawn = case.draw(prepared, paths)
    assert LEGACY not in json.loads(drawn.read_bytes())["sampled_codes"]
    case.assemble(prepared, paths, "invented-person", draw=drawn)


def test_drawn_acknowledgement_is_packeted_and_a_change_is_an_error(case: Any) -> None:
    prepared = case.prepare()
    paths = returns(case, SIGNER, "drawn", prepared)
    drawn = case.draw(prepared, paths)
    entries = json.loads(drawn.with_name("audit_packet.json").read_bytes())
    entry = next(row for row in entries if row["code"] == LEGACY)
    assert entry == dict(
        code=LEGACY,
        name_ar="نشاط اصطناعي للاختبار",
        status="not_mappable_legacy",
        reason="legacy_code_length",
        isic_class="",
    )
    assert all(
        set(row) == {"code", "name_ar", "prefix", "class_title_en", "class_title_ar"}
        for row in entries
        if row is not entry
    )
    audited = list(read_review_csv(paths[1]))
    write_review_csv(
        paths[1],
        [
            replace(row, status="not_mappable_invalid_prefix")
            if row.code == LEGACY
            else row
            for row in audited
        ],
    )
    with pytest.raises(Refusal, match=r"^audit_decision_differs$"):
        case.assemble(prepared, paths, draw=drawn)
    refusal = json.loads(
        (case.cache / "spine_review/invented-assembled/refusal.json").read_bytes()
    )
    assert refusal["errors"] == 1


def test_mixed_refusal_record_keeps_a_valid_seed_chain(case: Any) -> None:
    """A refused batch holding acknowledgement rows stays hash-verifiable."""
    from test_spine_refusals import commit_refusals

    prepared = case.prepare()
    paths = returns(case, SIGNER, "chain", prepared)
    audited = list(read_review_csv(paths[1]))
    write_review_csv(
        paths[1],
        [
            replace(row, status="not_mappable_invalid_prefix")
            if row.code == LEGACY
            else row
            for row in audited
        ],
    )
    with pytest.raises(Refusal, match=r"^audit_decision_differs$"):
        case.assemble(prepared, paths)
    commit_refusals(
        case,
        json.loads(case.review.with_name("activity_spine_refusals.json").read_bytes()),
    )
    prepared = prepared_queue(case, "chain-2")
    paths = returns(case, SIGNER, "chain-2", prepared)
    decisions_of(case, prepared, paths)  # The chained seed derivation holds.
