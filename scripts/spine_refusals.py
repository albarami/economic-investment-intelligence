"""Committed refusal evidence and canonical projections for the offline review."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import fields
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.review.activity import (
    ReviewRow,
    SpineError,
    _audit_codes,
    audit_rows_sha256,
    audit_sample,
)
from spine_triage_io import Refusal, contained
from versions_inputs import _pairs, git_environment


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def previous_refusals(root: Path, review: Path) -> list[Any]:
    """Require tracked working bytes equal to HEAD, including an empty archive."""
    path = contained(root, review.with_name("activity_spine_refusals.json"))
    relative = str(path.relative_to(root))
    try:
        body = path.read_bytes()
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            env=git_environment(os.environ),
            capture_output=True,
            check=False,
        )
        committed = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:" + relative],
            env=git_environment(os.environ),
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise Refusal("refusal_history_uncommitted") from error
    if tracked.returncode != 0 or committed.returncode != 0 or committed.stdout != body:
        raise Refusal("refusal_history_uncommitted")
    try:
        payload = json.loads(body, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as error:
        raise Refusal("refusal_record_invalid") from error
    if not isinstance(payload, list):
        raise Refusal("refusal_record_invalid")
    return payload


def refusal_projection(record: dict[str, Any]) -> dict[str, Any]:
    return dict(
        codes=sorted(record["codes"]),
        review_rows_sha256=record["review_rows_sha256"],
        seed=record["seed"],
        sampled_codes=record["sampled_codes"],
        errors=record["errors"],
    )


def seed_from_previous(
    decisions: tuple[ReviewRow, ...], previous: dict[str, Any] | None
) -> int:
    judgements = [
        dict(code=row.code, status=row.status, isic_class=row.isic_class)
        for row in sorted(decisions, key=lambda row: row.code)
    ]
    prior = (
        hashlib.sha256(canonical_json(refusal_projection(previous)))
        .hexdigest()
        .encode("ascii")
        if previous is not None
        else b""
    )
    digest = hashlib.sha256(
        b"oi203-audit-seed:" + canonical_json(judgements) + b":" + prior
    )
    return 1000000000 + int(digest.hexdigest(), 16) % 3294967296


def refusal_rows(record: Any) -> tuple[ReviewRow, ...]:
    """Retain historical signed rows so re-signing can change dates or decisions."""
    try:
        codes = _audit_codes(record["codes"], "refusal_record_invalid", nonempty=True)
        rows = tuple(ReviewRow(**row) for row in record["review_rows"])
        names = {field.name for field in fields(ReviewRow)} - {"code_length"}
        valid_rows = all(
            type(row.code_length) is int
            and row.code_length == 7
            and all(isinstance(getattr(row, name), str) for name in names)
            for row in rows
        )
        if (
            not valid_rows
            or sorted(codes) != sorted(row.code for row in rows)
            or record["review_rows_sha256"] != audit_rows_sha256(rows)
            or type(record["seed"]) is not int
            or type(record["errors"]) is not int
            or not 0 < record["errors"] <= len(record["sampled_codes"])
            or record["sampled_codes"]
            != list(audit_sample([row.code for row in rows], record["seed"]))
        ):
            raise Refusal("refusal_record_invalid")
    except (KeyError, TypeError, UnicodeError, SpineError) as error:
        raise Refusal("refusal_record_invalid") from error
    return rows


def derived_audit_seed(decisions: tuple[ReviewRow, ...], refusals: list[Any]) -> int:
    """L-1471: verify every historical link before using its normalized projection."""
    latest: dict[tuple[str, ...], dict[str, Any]] = {}
    for record in refusals:
        rows = refusal_rows(record)
        codes = tuple(sorted(row.code for row in rows))
        if record["seed"] != seed_from_previous(rows, latest.get(codes)):
            raise Refusal("refusal_record_invalid")
        latest[codes] = record
    codes = tuple(sorted(row.code for row in decisions))
    return seed_from_previous(decisions, latest.get(codes))
