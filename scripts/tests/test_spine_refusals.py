"""Committed refusal-chain regressions; invented batches and isolated Git only."""

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest
import test_spine_review
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.review.activity import (
    audit_rows_sha256,
    audit_sample,
    read_review_csv,
    write_review_csv,
)
from spine_review import derived_audit_seed
from spine_triage_io import Refusal
from versions_inputs import git_environment


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        env=git_environment(os.environ),
        check=True,
        capture_output=True,
    )


def commit_refusals(case: Any, records: list[Any]) -> Path:
    path: Path = case.review.with_name("activity_spine_refusals.json")
    path.write_text(json.dumps(records, ensure_ascii=False))
    if not (case.root / ".git").exists():
        git(case.root, "init")
    git(case.root, "add", str(path.relative_to(case.root)))
    git(
        case.root,
        "-c",
        "user.name=Invented",
        "-c",
        "user.email=invented@invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        "test: record invented refusals",
    )
    return path


@pytest.fixture
def case() -> Any:
    fixture = test_spine_review.SpineReviewTest()
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.doCleanups()


def decisions_and_refusal(case: Any) -> tuple[tuple[Any, ...], dict[str, Any]]:
    prepared = case.prepare()
    paths = case.returns(prepared)
    signed = tuple(row for row in read_review_csv(paths[0]) if row.code_length == 7)
    seed = derived_audit_seed(signed, [])
    return signed, dict(
        codes=sorted(row.code for row in signed),
        review_rows_sha256=audit_rows_sha256(signed),
        seed=seed,
        sampled_codes=list(audit_sample([row.code for row in signed], seed)),
        errors=1,
        draw_sha256="a" * 64,
        review_rows=[asdict(row) for row in signed],
    )


def test_cf3_five_handwritten_records_cannot_supply_five_seeds(case: Any) -> None:
    from test_spine_review_seed import many_returns

    prepared, paths = many_returns(case)
    signed = tuple(row for row in read_review_csv(paths[0]) if row.code_length == 7)
    forged = [
        dict(codes=[row.code for row in signed], errors=1, batch_id=f"fake-{i}")
        for i in range(5)
    ]
    seeds = []
    for record in forged:
        try:
            seeds.append(derived_audit_seed(signed, [record]))
        except Refusal as error:
            assert str(error) == "refusal_record_invalid"
    assert seeds == [], f"hand-written records supplied seeds: {seeds}; {prepared.name}"


@pytest.mark.parametrize("stage", ["prepare", "draw", "assemble"])
@pytest.mark.parametrize(
    "change", ["untracked", "edited", "reordered", "key_order", "staged"]
)
def test_uncommitted_refusal_history_exact_reason(
    case: Any, stage: str, change: str
) -> None:
    from spine_review import prepare_review_inputs

    signed, record = decisions_and_refusal(case)
    second = {**record, "seed": derived_audit_seed(signed, [record])}
    second["sampled_codes"] = list(audit_sample(second["codes"], second["seed"]))
    path = commit_refusals(case, [record, second])
    prepared = prepare_review_inputs(
        case.root, case.cache, case.review, "invented-frozen", case.preparer
    )
    paths = case.returns(prepared)
    drawn = case.draw(prepared, paths) if stage == "assemble" else None
    if change == "untracked":
        git(case.root, "rm", "--cached", str(path.relative_to(case.root)))
    elif change == "edited":
        path.write_bytes(path.read_bytes() + b"\n")
    elif change == "staged":
        third = {
            **record,
            "seed": derived_audit_seed(signed, [record, second]),
            "batch_id": "forged",
        }
        third["sampled_codes"] = list(audit_sample(third["codes"], third["seed"]))
        path.write_text(json.dumps([record, second, third]))
        git(case.root, "add", str(path.relative_to(case.root)))
    elif change == "key_order":
        path.write_text(
            json.dumps(
                [{key: row[key] for key in reversed(row)} for row in (record, second)]
            )
        )
    else:
        path.write_text(json.dumps([second, record]))
    with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
        if stage == "prepare":
            prepare_review_inputs(
                case.root, case.cache, case.review, "invented-new", case.preparer
            )
        elif stage == "draw":
            case.draw(prepared, paths)
        else:
            case.assemble(prepared, paths, draw=drawn)
    assert signed


@pytest.mark.parametrize(
    "field", ["batch_id", "audit_date", "signer_role", "extra", "key_order", "codes"]
)
def test_refusal_metadata_cannot_change_seed(field: str) -> None:
    signed, record = unit_refusal()
    expected = derived_audit_seed(signed, [record])
    changed = dict(record)
    if field == "codes":
        changed[field] = list(reversed(record[field]))
    elif field == "key_order":
        changed = {key: record[key] for key in reversed(record)}
    else:
        changed[field] = "forged metadata"
    assert derived_audit_seed(signed, [changed]) == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", 1000000000),
        ("review_rows_sha256", "0" * 64),
        ("codes", ["5610901"]),
        ("sampled_codes", []),
        ("errors", 0),
        ("errors", True),
        ("errors", 31),
        ("review_rows", []),
        ("review_rows", [{}]),
        ("review_rows", None),
    ],
)
def test_invalid_refusal_record_exact_reason(field: str, value: Any) -> None:
    signed, record = unit_refusal()
    assert record[field] != value or type(record[field]) is not type(value)
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        derived_audit_seed(signed, [{**record, field: value}])


def test_refused_resigned_fresh_audit_finalises(case: Any) -> None:
    from spine_review import finalise_check, prepare_review_inputs

    prepared = case.prepare()
    paths = case.returns(prepared)
    signed_before = paths[0].read_bytes()
    drawn = case.draw(prepared, paths)
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
    refused = prepared.parent / "invented-assembled/refusal.json"
    record = json.loads(refused.read_bytes())
    assert record["errors"] == 1
    assert record["draw_sha256"] == hashlib.sha256(drawn.read_bytes()).hexdigest()
    assert not (refused.parent / "activity_spine.csv").exists()
    archive = commit_refusals(case, [record])
    assert refused.read_bytes().rstrip() in archive.read_bytes()
    resigned = prepare_review_inputs(
        case.root, case.cache, case.review, "invented-resigned", case.preparer
    )
    next_paths = case.returns(resigned)
    assert next_paths[0].read_bytes() == signed_before
    next_draw = case.draw(resigned, next_paths)
    assert json.loads(next_draw.read_bytes())["seed"] != record["seed"]
    candidate = case.assemble(resigned, next_paths, "invented-accepted", draw=next_draw)
    assert all(
        row["errors"] == 0
        for row in json.loads((candidate / "activity_spine_audits.json").read_bytes())
    )
    final = finalise_check(
        case.root,
        resigned / "manifest.json",
        candidate / "activity_spine.csv",
        "invented-final",
    )
    assert json.loads((final / "result.json").read_bytes())["state"] == "complete"


@given(
    st.text(),
    st.permutations(
        [
            "codes",
            "review_rows_sha256",
            "seed",
            "sampled_codes",
            "errors",
            "review_rows",
            "draw_sha256",
        ]
    ),
)
def test_refusal_projection_ignores_arbitrary_metadata(
    text: str, keys: list[str]
) -> None:
    signed, record = unit_refusal()
    changed = {key: record[key] for key in keys}
    changed.update(batch_id=text, audit_date=text, role=text, extra=text)
    assert derived_audit_seed(signed, [changed]) == derived_audit_seed(signed, [record])


@pytest.mark.parametrize("body", [b'[{"errors":1,"errors":2}]', b"[{", b"\xff", b"{}"])
def test_committed_refusals_strict_parse(case: Any, body: bytes) -> None:
    from spine_refusals import previous_refusals

    path = case.review.with_name("activity_spine_refusals.json")
    path.write_bytes(body)
    git(case.root, "add", str(path.relative_to(case.root)))
    git(
        case.root,
        "-c",
        "user.name=Invented",
        "-c",
        "user.email=invented@invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        "test: malformed archive",
    )
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        previous_refusals(case.root, case.review)


def test_missing_refusal_file_is_uncommitted(case: Any) -> None:
    from spine_refusals import previous_refusals

    case.review.with_name("activity_spine_refusals.json").unlink()
    with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
        previous_refusals(case.root, case.review)


def test_chain_order_and_historical_signed_rows(case: Any) -> None:
    signed, first = decisions_and_refusal(case)
    resigned = tuple(
        replace(
            row,
            reviewed_on="2026-11-22",
            status="not_mappable_rejected",
            reason="reviewer_rejected",
            isic_class="",
        )
        for row in signed
    )
    seed = derived_audit_seed(resigned, [first])
    second = {
        **first,
        "seed": seed,
        "review_rows_sha256": audit_rows_sha256(resigned),
        "review_rows": [asdict(row) for row in resigned],
    }
    second["sampled_codes"] = list(audit_sample(second["codes"], seed))
    assert derived_audit_seed(resigned, [first, second]) != seed
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        derived_audit_seed(resigned, [second, first])
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        derived_audit_seed(resigned, [first, first])


def test_refusals_are_frozen_even_after_new_commit(case: Any) -> None:
    from spine_review import prepare_review_inputs

    signed, record = decisions_and_refusal(case)
    prepared = prepare_review_inputs(
        case.root, case.cache, case.review, "invented-snapshot", case.preparer
    )
    paths = case.returns(prepared)
    commit_refusals(case, [record])
    with pytest.raises(Refusal, match=r"^frozen_inputs_changed$"):
        case.draw(prepared, paths)
    assert signed


def unit_refusal() -> tuple[tuple[Any, ...], dict[str, Any]]:
    from test_spine_review_seed import seed_oracle

    from eii_custodian.publicdata.review.activity import ReviewRow

    signed = tuple(
        ReviewRow(
            code,
            7,
            "نشاط مخترع",
            "5610",
            "mapped",
            "reviewer_approved",
            "model review: invented_signer model, specialist",
            "2026-11-21",
        )
        for code in ("5610901", "5610902")
    )
    seed = seed_oracle(
        [
            dict(code=row.code, status=row.status, isic_class=row.isic_class)
            for row in signed
        ]
    )
    return signed, dict(
        codes=[row.code for row in signed],
        review_rows_sha256=audit_rows_sha256(signed),
        seed=seed,
        sampled_codes=[row.code for row in signed],
        errors=1,
        review_rows=[asdict(row) for row in signed],
        draw_sha256="a" * 64,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("code_length", True),
        ("code_length", 6),
        ("name_ar", None),
        ("code", "561090"),
        ("code", "٥٦١٠٩٠١"),
        ("code", "561090x"),
    ],
)
def test_refusal_signed_row_shape(field: str, value: Any) -> None:
    from spine_refusals import refusal_rows

    signed, record = unit_refusal()
    changed = (replace(signed[0], **{field: value}), signed[1])
    record.update(
        review_rows=[asdict(row) for row in changed],
        review_rows_sha256=audit_rows_sha256(changed),
        codes=[row.code for row in changed],
    )
    if all(isinstance(row.code, str) and row.code.isascii() for row in changed):
        record["sampled_codes"] = list(audit_sample(record["codes"], record["seed"]))
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        refusal_rows(record)


@pytest.mark.parametrize("bad", [None, 1, [], {}, {"review_rows": "text"}])
def test_refusal_record_structure(bad: Any) -> None:
    signed, _ = unit_refusal()
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        derived_audit_seed(signed, [bad])


def test_duplicate_refusal_signed_rows() -> None:
    from spine_refusals import refusal_rows

    signed, record = unit_refusal()
    duplicated = (*signed, signed[0])
    record.update(
        codes=[row.code for row in duplicated],
        review_rows=[asdict(row) for row in duplicated],
        review_rows_sha256=audit_rows_sha256(duplicated),
        sampled_codes=list(
            audit_sample([row.code for row in duplicated], record["seed"])
        ),
    )
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        refusal_rows(record)


@pytest.mark.parametrize(
    "changed_file,reason",
    [
        ("signer", "returned_inputs_changed"),
        ("refusals", "refusal_history_uncommitted"),
    ],
)
def test_refusal_rechecks_inputs_before_publication(
    case: Any, changed_file: str, reason: str
) -> None:
    from unittest.mock import patch

    import spine_review

    prepared = case.prepare()
    paths = case.returns(prepared)
    drawn = case.draw(prepared, paths)
    audited = list(read_review_csv(paths[1]))
    audited[0] = replace(
        audited[0],
        isic_class="",
        status="not_mappable_rejected",
        reason="reviewer_rejected",
    )
    write_review_csv(paths[1], audited)
    original = spine_review.audit_record

    def change(*args: Any) -> Any:
        batch = original(*args)
        path = (
            paths[0]
            if changed_file == "signer"
            else case.review.with_name("activity_spine_refusals.json")
        )
        path.write_bytes(path.read_bytes() + b"\n")
        return batch

    with patch("spine_review.audit_record", side_effect=change):
        with pytest.raises(Refusal, match="^" + reason + "$"):
            case.assemble(prepared, paths, draw=drawn)
    assert not (prepared.parent / "invented-assembled").exists()


def test_audit_counts_all_differing_codes() -> None:
    from test_spine_review_properties import AUDITOR, SIGNER

    from spine_review import audit_record

    signed, _ = unit_refusal()
    makers = dict(
        batch_id="invented",
        seed=derived_audit_seed(signed, []),
        signer_role=SIGNER,
        auditor_role=AUDITOR,
        audit_date="2026-11-22",
    )
    audited = tuple(
        replace(
            row,
            reviewed_by_role=AUDITOR,
            reviewed_on="2026-11-22",
            isic_class="",
            status="not_mappable_rejected",
            reason="reviewer_rejected",
        )
        for row in signed
    )
    assert audit_record(signed, audited, makers)["errors"] == len(signed)


@pytest.mark.parametrize("command", ["ls-files", "show"])
def test_git_failure_refuses_even_with_matching_output(case: Any, command: str) -> None:
    from unittest.mock import patch

    import spine_refusals

    original = subprocess.run

    def failure(args: list[str], **kwargs: Any) -> Any:
        result = original(args, **kwargs)
        if command in args:
            result.returncode = 1
        return result

    with patch("spine_refusals.subprocess.run", side_effect=failure):
        with pytest.raises(Refusal, match=r"^refusal_history_uncommitted$"):
            spine_refusals.previous_refusals(case.root, case.review)


def test_other_batch_does_not_replace_latest_refusal() -> None:
    from test_spine_review_seed import seed_oracle

    signed, first = unit_refusal()
    other_rows = signed[:1]
    other = {
        **first,
        "codes": [other_rows[0].code],
        "review_rows_sha256": audit_rows_sha256(other_rows),
        "review_rows": [asdict(row) for row in other_rows],
        "sampled_codes": [other_rows[0].code],
        "seed": seed_oracle(
            [
                dict(code=row.code, status=row.status, isic_class=row.isic_class)
                for row in other_rows
            ]
        ),
    }
    assert derived_audit_seed(signed, [first, other]) == derived_audit_seed(
        signed, [first]
    )


@pytest.mark.parametrize("stage", ["draw", "assemble"])
def test_refusal_seeds_participate_in_freshness(case: Any, stage: str) -> None:
    from unittest.mock import patch

    from spine_review import prepare_review_inputs

    _, record = decisions_and_refusal(case)
    commit_refusals(case, [record])
    prepared = prepare_review_inputs(
        case.root, case.cache, case.review, "invented-freshness", case.preparer
    )
    paths = case.returns(prepared)
    makers = json.loads(paths[2].read_bytes())
    paths[2].write_text(json.dumps({**makers, "seed": record["seed"]}))
    with patch("spine_review.derived_audit_seed", return_value=record["seed"]):
        if stage == "assemble":
            with patch("spine_review.require_fresh_seed"):
                drawn = case.draw(prepared, paths)
            with pytest.raises(Refusal, match=r"^audit_seed_reused$"):
                case.assemble(prepared, paths, draw=drawn)
        else:
            with pytest.raises(Refusal, match=r"^audit_seed_reused$"):
                case.draw(prepared, paths)


def test_refusal_signed_rows_with_unpaired_surrogate() -> None:
    signed, record = unit_refusal()
    changed = [dict(row) for row in record["review_rows"]]
    changed[0]["name_ar"] = "\ud800"
    with pytest.raises(Refusal, match=r"^refusal_record_invalid$"):
        derived_audit_seed(signed, [{**record, "review_rows": changed}])
