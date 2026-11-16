"""Read a verified cache. This module has no transport and opens no connection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.comtrade.parse import ParseError, TradeRow, parse_body
from eii_custodian.publicdata.comtrade.partition import (
    covered_leaves,
    gap_size,
    initial_partitions,
)
from eii_custodian.publicdata.comtrade.policy import (
    PARSER_METHOD,
    PARSER_VERSION,
    SOURCE_ID,
    Descriptor,
    Policy,
    SafeRefusal,
    policy_sha256,
    selection_sha256,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex

MANIFEST_NAME = "manifest.json"
_SHA = re.compile(r"\A[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class Assembly:
    """Typed rows, coverage and the source chain. No network is involved."""

    rows: tuple[TradeRow, ...]
    requested_cells: int
    present_cells: int
    gap_cells: int
    missing: tuple[str, ...]
    manifest_sha256: str
    policy_sha256: str
    selection_sha256: str
    parser_method: str
    parser_version: str
    price_amount: str
    price_currency: str
    price_retrieved_on: str
    price_source: str
    price_unavailable_reason: str
    source_id: str
    publisher: str
    licence_basis: str
    terms_sha256: str
    evidence_sha256: str
    retrieved_utc: str
    fetch_host: str


def assemble(
    cache: Path, key: str, policy: Policy, *, manifest_sha256: str
) -> Assembly:
    """Assemble cached children. A missing receipt or a bad child hash is refused."""
    directory = cache / key
    path = directory / MANIFEST_NAME
    if not path.is_file():
        raise SafeRefusal("manifest_missing", _bare(policy), "assemble")
    raw = path.read_bytes()
    if sha256_hex(raw) != manifest_sha256:
        raise SafeRefusal("manifest_hash", _bare(policy), "assemble")
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SafeRefusal("manifest_unreadable", _bare(policy), "assemble") from exc
    if not isinstance(loaded, dict) or loaded.get("complete") is not True:
        raise SafeRefusal("manifest_incomplete", _bare(policy), "assemble")
    if loaded.get("source_id") != SOURCE_ID:
        raise SafeRefusal("lineage_missing", _bare(policy), "assemble")
    if loaded.get("policy_sha256") != policy_sha256(policy):
        raise SafeRefusal("policy_changed", _bare(policy), "assemble")
    if loaded.get("selection_sha256") != selection_sha256(policy):
        raise SafeRefusal("selection_changed", _bare(policy), "assemble")
    if (
        loaded.get("parser_method") != PARSER_METHOD
        or loaded.get("parser_version") != PARSER_VERSION
    ):
        raise SafeRefusal("parser_identity", _bare(policy), "assemble")
    children = loaded.get("children")
    if not isinstance(children, list) or not children:
        raise SafeRefusal("manifest_incomplete", _bare(policy), "assemble")
    keys = _child_keys(children)
    if keys is None:
        raise SafeRefusal("duplicate_child", _bare(policy), "assemble")
    if not _selection_covered(policy, {key for key, _digest in keys}):
        raise SafeRefusal("manifest_incomplete", _bare(policy), "assemble")
    rows: list[TradeRow] = []
    chain: dict[str, str] | None = None
    for child_key, digest in keys:
        owners = {item for item, item_digest in keys if item_digest == digest}
        side = _receipt(directory, policy, child_key, digest, owners)
        if chain is None:
            chain = side
        elif side != chain:
            raise SafeRefusal("lineage_missing", _bare(policy), child_key)
        body_path = directory / f"{digest}.json"
        body = body_path.read_bytes()
        try:
            parsed = parse_body(
                body,
                policy,
                _descriptor(policy, child_key),
                source_version=policy.version,
                receipt_sha256=digest,
            )
        except ParseError as exc:
            raise SafeRefusal(exc.check, _bare(policy), child_key) from None
        rows.extend(parsed.rows)
    if chain is None:
        raise SafeRefusal("lineage_missing", _bare(policy), "assemble")
    requested = len(initial_partitions(policy))
    if loaded.get("requested_cells") != requested or loaded.get("gap_cells") != 0:
        raise SafeRefusal("coverage_gap", _bare(policy), "assemble")
    present = _int_field(loaded, "present_cells")
    try:
        gap = gap_size(requested, present)
    except ValueError as exc:
        raise SafeRefusal("coverage_gap", _bare(policy), "assemble") from exc
    if gap != 0:
        raise SafeRefusal("coverage_gap", _bare(policy), "assemble")
    missing = loaded.get("missing")
    if not isinstance(missing, list) or missing:
        raise SafeRefusal("coverage_gap", _bare(policy), "assemble")
    return Assembly(
        rows=tuple(rows),
        requested_cells=requested,
        present_cells=present,
        gap_cells=gap,
        missing=(),
        manifest_sha256=manifest_sha256,
        policy_sha256=str(loaded.get("policy_sha256")),
        selection_sha256=str(loaded.get("selection_sha256")),
        parser_method=PARSER_METHOD,
        parser_version=PARSER_VERSION,
        price_amount=policy.price_amount,
        price_currency=policy.price_currency,
        price_retrieved_on=policy.price_retrieved_on,
        price_source=policy.price_source,
        price_unavailable_reason=policy.price_unavailable_reason,
        source_id=chain["source_id"],
        publisher=chain["publisher"],
        licence_basis=chain["licence_basis"],
        terms_sha256=chain["terms_sha256"],
        evidence_sha256=chain["evidence_sha256"],
        retrieved_utc=chain["retrieved_utc"],
        fetch_host=chain["fetch_host"],
    )


def _child_keys(children: list[object]) -> list[tuple[str, str]] | None:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for child in children:
        if not isinstance(child, dict):
            return None
        child_key = child.get("key")
        digest = child.get("sha256")
        if not isinstance(child_key, str) or not isinstance(digest, str):
            return None
        if child_key in seen:
            return None
        seen.add(child_key)
        found.append((child_key, digest))
    return found


def _selection_covered(policy: Policy, present: set[str]) -> bool:
    covered: list[str] = []
    for cell in initial_partitions(policy):
        leaves = covered_leaves(policy, cell, present)
        if leaves is None:
            return False
        covered.extend(leaves)
    return set(covered) == present


def _receipt(
    directory: Path,
    policy: Policy,
    child_key: str,
    digest: str,
    owners: set[str],
) -> dict[str, str]:
    body_path = directory / f"{digest}.json"
    side_path = directory / f"{digest}.meta.json"
    if not body_path.is_file():
        raise SafeRefusal("child_missing", _bare(policy), child_key)
    if sha256_hex(body_path.read_bytes()) != digest:
        raise SafeRefusal("child_hash", _bare(policy), child_key)
    if not side_path.is_file():
        raise SafeRefusal("receipt_missing", _bare(policy), child_key)
    try:
        loaded = json.loads(side_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SafeRefusal("receipt_missing", _bare(policy), child_key) from exc
    if not isinstance(loaded, dict):
        raise SafeRefusal("receipt_missing", _bare(policy), child_key)
    if loaded.get("sha256") != digest or loaded.get("partition_key") not in owners:
        raise SafeRefusal("child_hash", _bare(policy), child_key)
    source_id = loaded.get("source_id")
    publisher = loaded.get("publisher")
    basis = loaded.get("licence_basis")
    terms = loaded.get("terms_sha256")
    evidence = loaded.get("evidence_sha256")
    retrieved = loaded.get("retrieved_utc")
    host = loaded.get("fetch_host")
    if (
        not isinstance(source_id, str)
        or source_id != SOURCE_ID
        or not isinstance(publisher, str)
        or publisher == ""
        or not isinstance(basis, str)
        or basis == ""
        or not isinstance(terms, str)
        or _SHA.fullmatch(terms) is None
        or not isinstance(evidence, str)
        or evidence != policy.evidence_sha256
        or not isinstance(retrieved, str)
        or "T" not in retrieved
        or not isinstance(host, str)
        or host == ""
    ):
        raise SafeRefusal("lineage_missing", _bare(policy), child_key)
    if loaded.get("policy_sha256") != policy_sha256(policy):
        raise SafeRefusal("policy_changed", _bare(policy), child_key)
    return {
        "source_id": source_id,
        "publisher": publisher,
        "licence_basis": basis,
        "terms_sha256": terms,
        "evidence_sha256": evidence,
        "retrieved_utc": retrieved,
        "fetch_host": host,
    }


def _bare(policy: Policy) -> str:
    host = policy.endpoint_templates[0].host
    return f"https://{host}/cached"


def _int_field(loaded: dict[str, object], name: str) -> int:
    value = loaded.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SafeRefusal("manifest_unreadable", "https://invalid.example/cached", name)
    return value


def _descriptor(policy: Policy, key: str) -> Descriptor:
    from eii_custodian.publicdata.comtrade.partition import Partition

    fields = dict(part.split("=", 1) for part in key.split("|") if "=" in part)
    sub = fields.get("sub", "")
    subdivision: list[tuple[str, str]] = []
    if sub:
        for item in sub.split(","):
            name, _, value = item.partition("=")
            if name:
                subdivision.append((name, value))
    partition = Partition(
        series_role=fields.get("role", ""),
        partner_code=fields.get("partner", ""),
        frequency=fields.get("frequency", ""),
        period=fields.get("period", ""),
        flow_code=fields.get("flow", ""),
        chapter=fields.get("chapter", ""),
        subdivision=tuple(subdivision),
    )
    return partition.descriptor(policy, "keyed")
