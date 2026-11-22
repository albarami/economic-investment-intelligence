"""Offline preparation and admission under decision 0075; no gateway calls."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.registry import load_registry, parse_yaml
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.review.activity import (
    _MODEL_LIKE,
    CODE_SYSTEM_VERSION,
    ActivityInputs,
    ReviewRow,
    SpineError,
    SupplierMembership,
    audit_maker,
    audit_rows_sha256,
    audit_sample,
    basket_membership,
    binding_path,
    encode_review_code,
    finalise_spine,
    load_activity_inputs,
    read_activity_rows,
    read_review_csv,
    review_binding,
    write_queue_csv,
    write_review_csv,
)
from spine_triage_io import (
    Context,
    Refusal,
    codes,
    contained,
    file_hash,
    output_path,
    source_receipts,
)
from versions_inputs import _pairs, read_input


def json_bytes(value: object) -> bytes:
    """One reproducible UTF-8 representation, also used for exact audit binding."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()


def binding_document(inputs: ActivityInputs) -> dict[str, object]:
    binding = review_binding(CODE_SYSTEM_VERSION, inputs.classes)
    return {
        "code_system_version": binding.code_system_version,
        "inputs": [
            dict(name=name, code=code, sha256=sha)
            for name, code, sha in binding.input_sha256
        ],
    }


def checked_tree(root: Path, path: Path) -> Path:
    path = contained(root, path)
    for child in path.rglob("*"):
        contained(root, child)
    return path


def derive(root: Path, cache: Path, review: Path) -> tuple[Context, dict[str, object]]:
    """Use the same verified feeds and basket membership as Production.spine_graph."""
    cache = checked_tree(root, cache)
    if not cache.is_relative_to(root / "data/public_cache"):
        raise Refusal("cache_location_invalid")
    review = contained(root, review)
    baskets = contained(root, review.with_name("baskets.yaml"))
    audit_path = contained(root, review.with_name("activity_spine_audits.json"))
    contained(root, binding_path(review))
    selected = reviewed_selections(cache)
    entries = load_registry()
    activities, _, _ = read_activity_rows(cache, entries, selected)
    playbook, suppliers = basket_membership(
        parse_yaml(baskets.read_bytes()), activities
    )
    inputs = load_activity_inputs(
        cache,
        playbook,
        supplier_membership=suppliers,
        review_path=review,
        selections=selected,
    )
    hashes, receipts = source_receipts(cache, selected)
    for name, path in (
        ("review", review),
        ("baskets", baskets),
        ("binding", binding_path(review)),
        ("audits", audit_path),
    ):
        hashes[name] = file_hash(path) if path.exists() else "absent"
    membership = dict(
        playbook_codes=[encode_review_code(c) for c in playbook],
        supplier_codes=[encode_review_code(c) for c in suppliers.codes],
        supplier_complete=True,
    )
    return Context(root, cache, inputs, hashes, receipts), membership


def eligible_rows(inputs: ActivityInputs) -> tuple[ReviewRow, ...]:
    classes = {row.code for row in inputs.classes}
    return tuple(
        ReviewRow(**asdict(row))
        for row in inputs.spine.queue
        if row.code_length == 7 and row.code[:4] in classes
    )


def snapshot(context: Context, membership: dict[str, object]) -> dict[str, object]:
    return dict(
        inputs=context.hashes,
        sources=context.receipts,
        membership=membership,
        spine=asdict(context.inputs.manifest)
        if context.inputs.manifest is not None
        else None,
    )


def fresh_target(context: Context, run_id: str) -> Path:
    return output_path(context, run_id, stage="spine_review")


def maker_token(value: object) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value) is None
    ):
        raise Refusal("preparer_maker_invalid")
    return value.casefold()


def publish(context: Context, run_id: str, files: dict[str, bytes]) -> Path:
    """Validate before this call; stage complete bytes and rename into a fresh folder."""
    target = fresh_target(context, run_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        staged = Path(temporary) / "result"
        staged.mkdir()
        for name, body in files.items():
            (staged / name).write_bytes(body)
        staged.rename(target)
    return target


def prepare_review_inputs(
    root: Path, cache: Path, review: Path, run_id: str, preparer_maker: str
) -> Path:
    preparer = maker_token(preparer_maker)
    context, membership = derive(root, cache, review)
    fresh_target(context, run_id)
    eligible = eligible_rows(context.inputs)
    classes = {row.code: row for row in context.inputs.classes}
    packet = [
        dict(
            code=row.code,
            name_ar=row.name_ar,
            prefix=row.code[:4],
            class_title_en=classes[row.code[:4]].label_en,
            class_title_ar=classes[row.code[:4]].label_ar,
        )
        for row in eligible
    ]
    files = {
        "membership.json": json_bytes(membership),
        "queue.binding.json": json_bytes(binding_document(context.inputs)),
        "signer_packet.json": json_bytes(packet),
    }
    with tempfile.TemporaryDirectory(dir=context.cache) as temporary:
        path = Path(temporary) / "queue.csv"
        write_queue_csv(path, context.inputs.spine.queue)
        files["queue.csv"] = path.read_bytes()
    manifest = dict(
        method="spine_review.prepare.v1",
        cache=str(context.cache.relative_to(root)),
        review=str(contained(root, review).relative_to(root)),
        preparer_maker=preparer,
        snapshot=snapshot(context, membership),
        counts=dict(
            eligible_codes=len(eligible),
            acknowledgement_rows=len(context.inputs.spine.queue) - len(eligible),
            excluded_groups=len(context.inputs.left_out),
        ),
        outputs={
            name: hashlib.sha256(body).hexdigest() for name, body in files.items()
        },
    )
    files["manifest.json"] = json_bytes(manifest)
    return publish(context, run_id, files)


def read_object(root: Path, path: Path) -> dict[str, Any]:
    path = contained(root, path)
    value, error = read_input(root, str(path.relative_to(root)), "json")
    if error is not None or not isinstance(value, dict):
        raise Refusal("json_input_invalid")
    return value


def frozen_context(root: Path, manifest: Path) -> tuple[Context, dict[str, Any]]:
    """Rederive all inputs, not just the signer's selected class titles."""
    manifest = contained(root, manifest)
    payload = read_object(root, manifest)
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "method",
            "cache",
            "review",
            "preparer_maker",
            "snapshot",
            "counts",
            "outputs",
        }
        or payload["method"] != "spine_review.prepare.v1"
    ):
        raise Refusal("manifest_contract_invalid")
    maker_token(payload["preparer_maker"])
    context, membership = derive(root, Path(payload["cache"]), Path(payload["review"]))
    if json_bytes(snapshot(context, membership)) != json_bytes(payload["snapshot"]):
        raise Refusal("frozen_inputs_changed")
    if not isinstance(payload["outputs"], dict) or set(payload["outputs"]) != {
        "queue.csv",
        "membership.json",
        "queue.binding.json",
        "signer_packet.json",
    }:
        raise Refusal("manifest_outputs_invalid")
    for name, digest in payload["outputs"].items():
        if file_hash(contained(root, manifest.parent / name)) != digest:
            raise Refusal("prepared_output_changed")
    return context, payload


def read_makers(root: Path, path: Path, preparer: str) -> dict[str, Any]:
    record = read_object(root, path)
    if not isinstance(record, dict) or set(record) != {
        "preparer_maker",
        "signer_role",
        "auditor_role",
        "batch_id",
        "seed",
        "audit_date",
    }:
        raise Refusal("maker_record_invalid")
    if maker_token(record["preparer_maker"]) != preparer:
        raise Refusal("preparer_maker_changed")
    signer = audit_maker(record["signer_role"])
    auditor = audit_maker(record["auditor_role"])
    if signer in (preparer, auditor):
        raise Refusal("signer_maker_conflict")
    if (
        type(record["seed"]) is not int
        or not 1000000000 <= record["seed"] <= 4294967295
    ):
        raise Refusal("audit_seed_invalid")
    return record


def decision_rows(
    context: Context, signed: tuple[ReviewRow, ...], role: str
) -> tuple[ReviewRow, ...]:
    queue = {row.code: row for row in context.inputs.spine.queue}
    if {row.code for row in signed} != set(queue):
        raise Refusal("signer_coverage_differs")
    eligible = {row.code for row in eligible_rows(context.inputs)}
    for row in signed:
        held = queue[row.code]
        if row.code_length != held.code_length or row.name_ar != held.name_ar:
            raise Refusal("judgement_identity_differs")
        if row.code in eligible:
            expected = {
                "mapped": (row.code[:4], "reviewer_approved"),
                "not_mappable_rejected": ("", "reviewer_rejected"),
            }
            if (row.isic_class, row.reason) != expected.get(row.status):
                raise Refusal("signer_decision_invalid")
            if row.reviewed_by_role != role:
                raise Refusal("signer_role_differs")
        elif (row.status, row.reason, row.isic_class) != (held.status, held.reason, ""):
            raise Refusal("acknowledgement_decision_invalid")
        elif _MODEL_LIKE.match(row.reviewed_by_role):
            raise Refusal("acknowledgement_role_invalid")
    return tuple(row for row in signed if row.code in eligible)


def audit_record(
    signed: tuple[ReviewRow, ...],
    audited: tuple[ReviewRow, ...],
    makers: dict[str, Any],
) -> dict[str, object]:
    sampled = audit_sample([row.code for row in signed], makers["seed"])
    if {row.code for row in audited} != set(sampled):
        raise Refusal("auditor_coverage_differs")
    by_code = {row.code: row for row in signed}
    for row in audited:
        if (
            row.reviewed_by_role != makers["auditor_role"]
            or row.reviewed_on != makers["audit_date"]
        ):
            raise Refusal("auditor_identity_differs")
        expected = by_code[row.code]
        if (row.code_length, row.name_ar, row.isic_class, row.status, row.reason) != (
            expected.code_length,
            expected.name_ar,
            expected.isic_class,
            expected.status,
            expected.reason,
        ):
            raise Refusal("audit_decision_differs")
    return dict(
        batch_id=makers["batch_id"],
        codes=sorted(by_code),
        review_rows_sha256=audit_rows_sha256(signed),
        seed=makers["seed"],
        sampled_codes=sampled,
        signer_role=makers["signer_role"],
        auditor_role=makers["auditor_role"],
        errors=0,
        audit_date=makers["audit_date"],
    )


def input_hashes(root: Path, paths: dict[str, Path]) -> dict[str, str]:
    checked = {name: contained(root, path) for name, path in paths.items()}
    return {
        name: file_hash(path) if path.exists() else "absent"
        for name, path in checked.items()
    }


def previous_audits(root: Path, review: Path) -> tuple[bytes, list[Any]]:
    """Strict duplicate-key parsing with the original bytes retained for append."""
    path = contained(root, review.with_name("activity_spine_audits.json"))
    body = path.read_bytes() if path.exists() else b"[]\n"
    try:
        payload = json.loads(body, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError) as error:
        raise Refusal("previous_audits_invalid") from error
    if not isinstance(payload, list):
        raise Refusal("previous_audits_invalid")
    return body, payload


def require_fresh_seed(audits: list[Any], seed: int) -> None:
    if any(isinstance(row, dict) and row.get("seed") == seed for row in audits):
        raise Refusal("audit_seed_reused")


def append_audit(
    body: bytes, audits: list[Any], batch: dict[str, object] | None
) -> bytes:
    """Append inside the list, preserving earlier records' exact bytes."""
    if batch is None:
        return body
    end = body.rfind(b"]")
    return (
        body[:end]
        + (b"," if audits else b"")
        + json_bytes(batch).rstrip(b"\n")
        + body[end:]
    )


def draw_record(
    evidence: dict[str, str], decisions: tuple[ReviewRow, ...], makers: dict[str, Any]
) -> dict[str, Any]:
    return dict(
        manifest_sha256=evidence["manifest"],
        signer_rows_sha256=evidence["signer"],
        maker_record_sha256=evidence["makers"],
        seed=makers["seed"],
        batch_id=makers["batch_id"],
        sampled_codes=list(
            audit_sample([row.code for row in decisions], makers["seed"])
        ),
    )


def draw_audit(
    root: Path, manifest: Path, signer_rows: Path, maker_record: Path, run_id: str
) -> Path:
    returned = dict(manifest=manifest, signer=signer_rows, makers=maker_record)
    evidence = input_hashes(root, returned)
    context, frozen = frozen_context(root, manifest)
    fresh_target(context, run_id)
    makers = read_makers(root, maker_record, frozen["preparer_maker"])
    decisions = decision_rows(
        context, read_review_csv(contained(root, signer_rows)), makers["signer_role"]
    )
    _, earlier = previous_audits(root, Path(frozen["review"]))
    require_fresh_seed(earlier, makers["seed"])
    drawn = draw_record(evidence, decisions, makers)
    packet = json.loads(
        (contained(root, manifest).parent / "signer_packet.json").read_bytes()
    )
    sampled = drawn["sampled_codes"]
    audit_packet = [entry for entry in packet if entry["code"] in sampled]
    frozen_context(root, manifest)
    if input_hashes(root, returned) != evidence:
        raise Refusal("returned_inputs_changed")
    return publish(
        context,
        run_id,
        {"draw.json": json_bytes(drawn), "audit_packet.json": json_bytes(audit_packet)},
    )


def assemble_audited_review(
    root: Path,
    manifest: Path,
    signer_rows: Path,
    auditor_rows: Path,
    maker_record: Path,
    run_id: str,
    draw: Path,
) -> Path:
    context, frozen = frozen_context(root, manifest)
    fresh_target(context, run_id)
    returned = dict(
        manifest=manifest,
        signer=signer_rows,
        auditor=auditor_rows,
        makers=maker_record,
        draw=draw,
    )
    evidence = input_hashes(root, returned)
    makers = read_makers(root, maker_record, frozen["preparer_maker"])
    signed = read_review_csv(contained(root, signer_rows))
    decisions = decision_rows(context, signed, makers["signer_role"])
    if read_object(root, draw) != draw_record(evidence, decisions, makers):
        raise Refusal("draw_changed")
    audited = read_review_csv(contained(root, auditor_rows))
    batch = audit_record(decisions, audited, makers)
    previous = read_review_csv(contained(root, Path(frozen["review"])))
    queue_codes = {row.code for row in signed}
    candidate = tuple(row for row in previous if row.code not in queue_codes) + signed
    old_bytes, old_audits = previous_audits(root, Path(frozen["review"]))
    require_fresh_seed(old_audits, makers["seed"])
    audits = append_audit(old_bytes, old_audits, batch if decisions else None)
    binding = {
        **binding_document(context.inputs),
        "audit_sha256": hashlib.sha256(audits).hexdigest(),
    }
    with tempfile.TemporaryDirectory(dir=context.cache) as temporary:
        staged = Path(temporary)
        review = staged / "activity_spine.csv"
        write_review_csv(review, candidate)
        binding_path(review).write_bytes(json_bytes(binding))
        (staged / "activity_spine_audits.json").write_bytes(audits)
        verify_candidate(root, context, frozen, review)
        # Re-read the frozen inputs and return hashes before committing output.
        frozen_context(root, manifest)
        if input_hashes(root, returned) != evidence:
            raise Refusal("returned_inputs_changed")
        files = {path.name: path.read_bytes() for path in staged.iterdir()}
    files["assembly.json"] = json_bytes(
        dict(
            inputs=evidence,
            outputs={
                name: hashlib.sha256(body).hexdigest() for name, body in files.items()
            },
        )
    )
    return publish(context, run_id, files)


def verify_candidate(
    root: Path, context: Context, frozen: dict[str, Any], review: Path
) -> ActivityInputs:
    """Candidate admission and finalisation use the original mandatory membership."""
    for path in (
        review,
        binding_path(review),
        review.with_name("activity_spine_audits.json"),
    ):
        contained(root, path)
    membership = frozen["snapshot"]["membership"]
    inputs = load_activity_inputs(
        context.cache,
        codes(membership["playbook_codes"]),
        supplier_membership=SupplierMembership(
            codes(membership["supplier_codes"]), True
        ),
        review_path=review,
    )
    try:
        finalise_spine(inputs.spine)
    except SpineError as error:
        raise Refusal("mandatory_review_missing") from error
    return inputs


def finalise_check(root: Path, manifest: Path, review: Path, run_id: str) -> Path:
    review = contained(root, review)
    returned = dict(
        manifest=manifest,
        review=review,
        binding=binding_path(review),
        audits=review.with_name("activity_spine_audits.json"),
    )
    evidence = input_hashes(root, returned)
    context, frozen = frozen_context(root, manifest)
    fresh_target(context, run_id)
    inputs = verify_candidate(root, context, frozen, review)
    frozen_context(root, manifest)
    if input_hashes(root, returned) != evidence:
        raise Refusal("returned_inputs_changed")
    return publish(
        context,
        run_id,
        {
            "result.json": json_bytes(
                dict(
                    method="spine_review.finalise.v1",
                    state="complete",
                    inputs=evidence,
                    snapshot=frozen["snapshot"],
                    spine=asdict(inputs.manifest)
                    if inputs.manifest is not None
                    else None,
                )
            )
        },
    )
