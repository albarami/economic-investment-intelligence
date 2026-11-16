"""Read a verified cache. This module has no transport and opens no connection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.comtrade.parse import ParseError, TradeRow, parse_body
from eii_custodian.publicdata.comtrade.partition import gap_size
from eii_custodian.publicdata.comtrade.policy import (
    PARSER_METHOD,
    PARSER_VERSION,
    Descriptor,
    Policy,
    SafeRefusal,
    selection_sha256,
)
from eii_custodian.publicdata.fetch.receipts import sha256_hex

MANIFEST_NAME = "manifest.json"


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


def assemble(cache: Path, key: str, policy: Policy) -> Assembly:
    """Assemble cached children. A missing manifest or a bad child hash is refused."""
    directory = cache / key
    path = directory / MANIFEST_NAME
    if not path.is_file():
        raise SafeRefusal("manifest_missing", _bare(policy), "assemble")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafeRefusal("manifest_unreadable", _bare(policy), "assemble") from exc
    if not isinstance(loaded, dict) or loaded.get("complete") is not True:
        raise SafeRefusal("manifest_incomplete", _bare(policy), "assemble")
    if loaded.get("selection_sha256") != selection_sha256(policy):
        raise SafeRefusal("selection_changed", _bare(policy), "assemble")
    children = loaded.get("children")
    if not isinstance(children, list) or not children:
        raise SafeRefusal("manifest_incomplete", _bare(policy), "assemble")
    rows: list[TradeRow] = []
    for child in children:
        if not isinstance(child, dict):
            raise SafeRefusal("child_hash", _bare(policy), "assemble")
        child_key = child.get("key")
        digest = child.get("sha256")
        if not isinstance(child_key, str) or not isinstance(digest, str):
            raise SafeRefusal("child_hash", _bare(policy), "assemble")
        body_path = directory / f"{digest}.json"
        if not body_path.is_file():
            raise SafeRefusal("child_missing", _bare(policy), child_key)
        body = body_path.read_bytes()
        if sha256_hex(body) != digest:
            raise SafeRefusal("child_hash", _bare(policy), child_key)
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
    requested = _int_field(loaded, "requested_cells")
    present = _int_field(loaded, "present_cells")
    try:
        gap = gap_size(requested, present)
    except ValueError as exc:
        raise SafeRefusal("coverage_gap", _bare(policy), "assemble") from exc
    if gap != 0 or loaded.get("gap_cells") != 0:
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
        manifest_sha256=sha256_hex(path.read_bytes()),
        policy_sha256=str(loaded.get("policy_sha256")),
        selection_sha256=str(loaded.get("selection_sha256")),
        parser_method=PARSER_METHOD,
        parser_version=PARSER_VERSION,
        price_amount=policy.price_amount,
        price_currency=policy.price_currency,
        price_retrieved_on=policy.price_retrieved_on,
        price_source=policy.price_source,
        price_unavailable_reason=policy.price_unavailable_reason,
    )


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
    descriptor: Descriptor = partition.descriptor(policy, "keyed")
    return descriptor
