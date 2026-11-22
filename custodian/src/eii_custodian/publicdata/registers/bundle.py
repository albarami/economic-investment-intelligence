"""Assembly-side reader for the lead-staged register projection bundle.

The lead stages the published ``current/`` directory as ``register_bundle/`` in
the allowed cache and pins its manifest digest in ``register_bundle_pin.json``.
This reader re-checks the pin, manifest, receipt chain, table bytes and every
released row against the run's actual frame. It never reads a raw register
file, a private path or an ambient setting.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.registry import LICENCE_BASES
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, utc
from eii_custodian.publicdata.review.cache_fixture import read_parquet

from .contracts import METHOD, REGISTRY_KEYS, ROLES, VERSION, refuse
from .provenance import Frame, digest, month
from .validate import validate_release

BUNDLE = "register_bundle"
PIN = "register_bundle_pin.json"
_PIN_VERSION = "register_bundle_pin_v1"
_MANIFEST_LIMIT = 4 * 1024 * 1024
_TABLE_LIMIT = 256 * 1024 * 1024
_TABLES = ("pub_register_company", "pub_register_snapshot")
_RECEIPT_KEYS = {
    "version",
    "kind",
    "key",
    "source_id",
    "period",
    "publisher",
    "dataset",
    "retrieved_utc",
    "licence_id",
    "licence_basis",
    "terms_words",
    "terms_read_on",
    "basis_note",
    "files",
}
_HASH = re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True, repr=False)
class Bundle:
    """Validated projection bundle; holds only released rows and lineage."""

    tables: dict[str, tuple[dict[str, Any], ...]]
    manifest: dict[str, Any]
    manifest_sha256: str
    table_sha256: dict[str, str]
    coverage: dict[str, tuple[str, ...]]
    receipts: tuple[dict[str, Any], ...]
    current: dict[str, str]

    def snapshot_reason(self, source: str, earlier: str, later: str) -> str | None:
        """Same coverage answer as the writer: kept months or snapshot_not_kept."""
        month(earlier)
        month(later)
        kept = self.coverage.get(source, ())
        return None if earlier in kept and later in kept else "snapshot_not_kept"


def _read(path: Path, limit: int, reason: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            refuse("register_bundle_missing")
        body = path.read_bytes()
    except OSError:
        refuse("register_bundle_missing")
    if len(body) > limit:
        refuse(reason)
    return body


def _object(body: bytes, reason: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        found: dict[str, Any] = {}
        for key, value in items:
            if key in found:
                refuse(reason)
            found[key] = value
        return found

    try:
        value = json.loads(body, object_pairs_hook=pairs)
    except (ValueError, UnicodeError):
        refuse(reason)
    if not isinstance(value, dict):
        refuse(reason)
    return value


def _receipt(entry: object) -> tuple[str, str, str, str, dict[str, Any]]:
    """Validate one manifest receipt entry; return key, source, use, period, receipt."""
    if not isinstance(entry, dict) or set(entry) != {
        "use",
        "receipt",
        "receipt_sha256",
    }:
        refuse("register_bundle_receipt")
    use, side = entry["use"], entry["receipt"]
    if use not in {"current", "snapshot"}:
        refuse("register_bundle_receipt")
    if not isinstance(side, dict) or set(side) != _RECEIPT_KEYS:
        refuse("receipt_schema")
    source = side["source_id"] if isinstance(side["source_id"], str) else ""
    key = REGISTRY_KEYS.get(source, "")
    if (
        side["version"] != "register_input_v1"
        or side["kind"] != "register_file"
        or not key
        or side["key"] != key
    ):
        refuse("receipt_binding")
    period = month(side["period"])
    for name in _RECEIPT_KEYS - {"files"}:
        if not isinstance(side[name], str) or not side[name].strip():
            refuse("receipt_metadata")
    if side["licence_basis"] not in LICENCE_BASES:
        refuse("receipt_metadata")
    try:
        stamp = utc(side["retrieved_utc"])
    except SnapshotError:
        refuse("receipt_retrieval")
    if stamp.strftime("%Y-%m") != period:
        refuse("receipt_month_mismatch")
    files = side["files"]
    if not isinstance(files, dict) or set(files) != ROLES[source]:
        refuse("receipt_files")
    for info in files.values():
        if (
            not isinstance(info, dict)
            or set(info) != {"sha256", "bytes"}
            or not isinstance(info["sha256"], str)
            or _HASH.fullmatch(info["sha256"]) is None
            or type(info["bytes"]) is not int
            or info["bytes"] < 0
        ):
            refuse("receipt_files")
    canonical = json.dumps(side, sort_keys=True, separators=(",", ":")).encode()
    if entry["receipt_sha256"] != digest(canonical):
        refuse("register_bundle_receipt")
    return key, source, str(use), period, dict(side)


def _receipts(
    raw: object,
) -> tuple[tuple[dict[str, Any], ...], dict[str, str], dict[str, set[str]]]:
    if not isinstance(raw, list):
        refuse("register_bundle_manifest")
    current: dict[str, str] = {}
    snapshots: dict[str, set[str]] = {source: set() for source in ROLES}
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        key, source, use, period, side = _receipt(item)
        if use == "current":
            if source in current:
                refuse("register_bundle_source")
            current[source] = period
        else:
            if period < "2026-11":
                refuse("snapshot_month")
            if (source, period) in seen:
                refuse("duplicate_snapshot_month")
            seen.add((source, period))
            snapshots[source].add(period)
        entries.append(
            {
                "key": key,
                "use": use,
                "receipt": side,
                "receipt_sha256": item["receipt_sha256"],
            }
        )
    if set(current) != set(ROLES):
        refuse("register_bundle_source")
    for source, periods in snapshots.items():
        for period in periods:
            if period > current[source]:
                refuse("snapshot_after_current")
    return tuple(entries), current, snapshots


def _coverage(
    raw: object, snapshots: dict[str, set[str]]
) -> dict[str, tuple[str, ...]]:
    if not isinstance(raw, dict) or set(raw) != set(ROLES):
        refuse("register_bundle_manifest")
    coverage: dict[str, tuple[str, ...]] = {}
    for source, kept in snapshots.items():
        months = raw[source]
        if (
            not isinstance(months, list)
            or len(set(months)) != len(months)
            or months != sorted(months)
        ):
            refuse("register_bundle_manifest")
        for value in months:
            month(value)
        if set(months) != kept:
            refuse("register_bundle_period")
        coverage[source] = tuple(months)
    return coverage


def load_bundle(directory: Path, pin: Path, cells: frozenset[int]) -> Bundle:
    """Re-verify the staged bundle and its released rows; closed refusals only."""
    pin_body = _read(pin, _MANIFEST_LIMIT, "register_bundle_pin")
    reference = _object(pin_body, "register_bundle_pin")
    if (
        set(reference) != {"version", "manifest_sha256"}
        or reference["version"] != _PIN_VERSION
        or not isinstance(reference["manifest_sha256"], str)
        or _HASH.fullmatch(reference["manifest_sha256"]) is None
    ):
        refuse("register_bundle_pin")
    manifest_body = _read(
        directory / "manifest.json", _MANIFEST_LIMIT, "register_bundle_missing"
    )
    manifest_sha256 = digest(manifest_body)
    if manifest_sha256 != reference["manifest_sha256"]:
        refuse("register_bundle_pin")
    manifest = _object(manifest_body, "register_bundle_manifest")
    if set(manifest) != {
        "version",
        "method",
        "provenance",
        "release_kind",
        "frame_sha256",
        "receipts",
        "snapshot_coverage",
        "tables",
    }:
        refuse("register_bundle_manifest")
    if (
        manifest["version"] != VERSION
        or manifest["method"] != METHOD
        or manifest["provenance"] != "Public"
        or manifest["release_kind"] not in {"public_only", "protected"}
    ):
        refuse("register_bundle_manifest")
    frame = Frame(cells)
    if manifest["frame_sha256"] != frame.sha256:
        refuse("frame_hash_mismatch")
    receipts, current, snapshots = _receipts(manifest["receipts"])
    coverage = _coverage(manifest["snapshot_coverage"], snapshots)
    declared = manifest["tables"]
    if not isinstance(declared, list):
        refuse("register_bundle_table")
    specs: dict[str, tuple[int, str]] = {}
    for item in declared:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "rows", "sha256"}
            or type(item["rows"]) is not int
            or item["rows"] < 0
            or not isinstance(item["sha256"], str)
            or _HASH.fullmatch(item["sha256"]) is None
            or item["name"] in specs
        ):
            refuse("register_bundle_table")
        specs[item["name"]] = (item["rows"], item["sha256"])
    if set(specs) != set(_TABLES):
        refuse("register_bundle_table")
    tables_dir = directory / "tables"
    table_sha256: dict[str, str] = {}
    tables: dict[str, tuple[dict[str, Any], ...]] = {}
    for name, (count, expected) in specs.items():
        body = _read(
            tables_dir / (name + ".parquet"), _TABLE_LIMIT, "register_bundle_table"
        )
        if digest(body) != expected:
            refuse("register_bundle_table")
        try:
            rows = read_parquet(body)
        except Exception:
            refuse("register_bundle_table")
        if len(rows) != count:
            refuse("register_bundle_table")
        table_sha256[name] = expected
        tables[name] = tuple(dict(row) for row in rows)
    try:
        foreign = {
            path.name
            for path in tables_dir.iterdir()
            if path.name not in {name + ".parquet" for name in specs}
        }
    except OSError:
        refuse("register_bundle_missing")
    if foreign:
        refuse("register_bundle_table")
    validate_release(tables, frame)
    kept = {
        (source, period) for source, months in coverage.items() for period in months
    }
    for row in tables["pub_register_snapshot"]:
        if (row["source_id"], row["period"]) not in kept:
            refuse("register_bundle_period")
    return Bundle(
        tables=tables,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        table_sha256=table_sha256,
        coverage=coverage,
        receipts=receipts,
        current=current,
    )
