"""Local input and unsigned output contracts for S2-T05 (PUB-35)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.review.activity import (
    CODE_SYSTEM_VERSION,
    ActivityInputs,
    SpineRow,
    SupplierMembership,
    binding_path,
    decode_review_code,
    encode_review_code,
    load_activity_inputs,
    read_review_binding,
    read_review_csv,
    review_binding,
    write_queue_csv,
)
from eii_custodian.publicdata.review.cache_fixture import read_cached

SUGGESTION_COLUMNS = ("code", "candidate_isic_class", "suggestion", "memo_key")


class Refusal(ValueError):
    """Fixed diagnostic; never echo an input or provider body."""


@dataclass(frozen=True)
class Context:
    root: Path
    cache: Path
    inputs: ActivityInputs
    hashes: dict[str, str]
    receipts: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class Suggestion:
    code: str
    candidate_isic_class: str
    suggestion: str
    memo_key: str


@dataclass(frozen=True)
class Result:
    queue: tuple[SpineRow, ...]
    suggestions: tuple[Suggestion, ...]
    fallback: bool
    evidence: dict[str, object]


def contained(root: Path, path: Path) -> Path:
    """Refuse traversal and symlinks, including links within the permitted root."""
    root = root.resolve()
    candidate = path if path.is_absolute() else root / path
    if not candidate.is_relative_to(root) or ".." in candidate.parts:
        raise Refusal("input refused")
    current = root
    for part in candidate.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise Refusal("input refused")
    return candidate


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def codes(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise Refusal("input refused")
    return tuple(decode_review_code(item) for item in value)


def load_context(
    root: Path, cache: Path, review: Path, queue: Path, membership: Path
) -> Context:
    """Recompute through S2-T04; no triage-owned parser or admission rule."""
    root = root.resolve()
    cache = contained(root, cache)
    if not cache.is_relative_to(root / "data/public_cache"):
        raise Refusal("input refused")
    review, queue, membership = (
        contained(root, path) for path in (review, queue, membership)
    )
    payload = json.loads(membership.read_text())
    if not isinstance(payload, dict) or set(payload) != {
        "playbook_codes",
        "supplier_codes",
        "supplier_complete",
    }:
        raise Refusal("input refused")
    if payload["supplier_complete"] is not True:
        raise Refusal("input refused")
    # Check cache children before the existing reader follows any paths.
    for path in cache.rglob("*"):
        contained(root, path)
    contained(root, binding_path(review))
    selected = reviewed_selections(cache)
    inputs = load_activity_inputs(
        cache,
        codes(payload["playbook_codes"]),
        review_path=review,
        selections=selected,
        supplier_membership=SupplierMembership(codes(payload["supplier_codes"]), True),
    )
    supplied = read_review_csv(queue)
    if tuple(asdict(row) for row in supplied) != tuple(
        asdict(row) for row in inputs.spine.queue
    ):
        raise Refusal("input refused")
    expected = review_binding(CODE_SYSTEM_VERSION, inputs.classes)
    for path in (binding_path(review), binding_path(queue)):
        contained(root, path)
        if path.exists() and read_review_binding(path) != expected:
            raise Refusal("input refused")
    hashes = {
        "review": file_hash(review),
        "queue": file_hash(queue),
        "membership": file_hash(membership),
    }
    receipts = []
    for entry in load_registry():
        if entry.key in ("lic_active", "lic_cancelled", "cls_isic4"):
            body = read_cached(cache, entry, digest=selected[entry.key])
            hashes[entry.key + "_receipt"] = file_hash(body.receipt_path)
            receipts.append(
                {
                    key: body.sidecar[key]
                    for key in (
                        "source_id",
                        "publisher",
                        "landing_url",
                        "licence_id",
                        "licence_basis",
                        "retrieved_utc",
                        "sha256",
                    )
                }
            )
    return Context(root, cache, inputs, hashes, tuple(receipts))


def output_path(context: Context, run_id: str) -> Path:
    if re.fullmatch(r"[a-z][a-z0-9-]{0,63}", run_id) is None:
        raise Refusal("output refused")
    if re.search(r"(?<!\d)(?:\d{8}|\d{11})(?!\d)", run_id):
        raise Refusal("output refused")
    target = contained(context.root, context.cache / "spine_triage" / run_id)
    contained(context.root, context.root / "evals/typed_decisions/runs")
    if target.exists():
        raise Refusal("output refused")
    return target


def write_outputs(context: Context, run_id: str, result: Result) -> Path:
    """Write a fresh unsigned queue, separate suggestions and provenance."""
    target = output_path(context, run_id)
    target.mkdir(parents=True)
    write_queue_csv(target / "queue.csv", result.queue)
    with (target / "suggestions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(SUGGESTION_COLUMNS)
        for row in result.suggestions:
            writer.writerow(
                (
                    encode_review_code(row.code),
                    row.candidate_isic_class,
                    row.suggestion,
                    row.memo_key,
                )
            )
    binding = review_binding(CODE_SYSTEM_VERSION, context.inputs.classes)
    (target / "queue.binding.json").write_text(
        json.dumps(
            {
                "code_system_version": binding.code_system_version,
                "inputs": [
                    {"name": name, "code": code, "sha256": sha}
                    for name, code, sha in binding.input_sha256
                ],
            },
            sort_keys=True,
        )
        + "\n"
    )
    manifest = {
        "method": "spine_triage.v1",
        "inputs": context.hashes,
        "sources": context.receipts,
        "spine": asdict(context.inputs.manifest)
        if context.inputs.manifest is not None
        else None,
        "state": "fallback" if result.fallback else "complete",
        "evidence": result.evidence,
        "outputs": {
            name: file_hash(target / name)
            for name in ("queue.csv", "suggestions.csv", "queue.binding.json")
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    return target
