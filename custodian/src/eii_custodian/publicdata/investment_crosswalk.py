"""Lead-reviewed, snapshot-bound FDI identifier mappings. No name lookup."""

from __future__ import annotations

import csv
import io
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Literal

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry, RegistryError, read_yaml
from eii_custodian.publicdata.investment_contracts import (
    InvestmentFailure,
    SourceEnvelope,
    bare_digit_run,
    fail,
)

_COLUMNS = {
    "source_country_iso3": "iso3",
    "municipality_code": "municipality_code",
    "place_key": "place_key",
}
_FIELDS = frozenset(
    {
        "source_id",
        "snapshot_sha256",
        "key_basis",
        "project_id",
        "project_key",
        "column",
        "target_key",
        "target_resource",
        "target_sha256",
        "review_role",
        "review_date",
        "review_reference",
    }
)
_HASH = re.compile(r"[a-f0-9]{64}")
_FILE = re.compile(r"[a-z][a-z0-9_-]*\.(?:csv|yaml)")
_REFERENCE = re.compile(r"[A-Za-z0-9_:-]+")
_REVIEW = Path(__file__).resolve().parents[3] / "publicdata/review"
_CACHE = _REVIEW.parents[2] / "data/public_cache"


@dataclass(frozen=True)
class MappingRow:
    snapshot_sha256: str
    project_id: int
    project_key: str
    column: str
    target_key: str
    target_resource: str
    target_sha256: str
    review_date: str
    review_reference: str


@dataclass(frozen=True)
class ReviewedCrosswalk:
    """Immutable validated mappings, resource hash and optional loader origin."""

    sha256: str
    mappings: tuple[MappingRow, ...]
    origin: Literal["cache", "committed"] | None = None


def _failure(check: str) -> InvestmentFailure:
    return InvestmentFailure(
        1, "fdi_projects", "", check, "reviewed identifier crosswalk", "invalid"
    )


def read_crosswalk(
    path: Path,
    *,
    expected_sha256: str,
    cache: Path | None = None,
    targets: Path | None = None,
) -> ReviewedCrosswalk | InvestmentFailure:
    """Check a crosswalk against the caller's hash and validate its Public targets.

    Municipality codes live only in the supplied cache/review directory.
    Other targets are direct files in targets (default: beside the crosswalk),
    pinned per mapping.
    Only target keys are read, never a name-matching map or target review flags.
    The caller supplies the expected hash; this reader does not establish its
    approval or bind it to a separate trusted manifest.
    """
    try:
        if path.is_symlink() or sha256_hex(path.read_bytes()) != expected_sha256:
            return _failure("crosswalk_hash")
        document = read_yaml(path)
    except (OSError, RegistryError, UnicodeError):
        return _failure("crosswalk_hash")
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "mappings",
    }:
        return _failure("crosswalk_schema")
    if document["schema_version"] != "fdi_crosswalks.v1" or not isinstance(
        document["mappings"], list
    ):
        return _failure("crosswalk_schema")
    found: list[MappingRow] = []
    seen: set[tuple[str, int, str]] = set()
    for item in document["mappings"]:
        if isinstance(item, dict):
            snapshot, identifier, column = (
                item.get(key) for key in ("snapshot_sha256", "project_id", "column")
            )
            if (
                isinstance(snapshot, str)
                and isinstance(identifier, int)
                and isinstance(column, str)
                and (snapshot, identifier, column) in seen
            ):
                return _failure("crosswalk_duplicate")
        checked = _mapping(item, targets if targets is not None else path.parent, cache)
        if isinstance(checked, InvestmentFailure):
            return checked
        key = (checked.snapshot_sha256, checked.project_id, checked.column)
        seen.add(key)
        found.append(checked)
    # Refuse a crosswalk changed while its targets were being checked.
    try:
        intact = (
            not path.is_symlink() and sha256_hex(path.read_bytes()) == expected_sha256
        )
    except OSError:
        intact = False
    if not intact:
        return _failure("crosswalk_hash")
    return ReviewedCrosswalk(expected_sha256, tuple(found))


def load_crosswalk(cache: Path | None = None) -> ReviewedCrosswalk | InvestmentFailure:
    """Prefer cache review rows; the committed fallback must be schema-only.

    The hash checks read consistency, not approval against an independent pin.
    An empty mapping list leaves all slots null.
    """
    cache = _CACHE if cache is None else cache
    path = cache / "review/fdi_crosswalks.yaml"
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        return _failure("crosswalk_hash")
    origin: Literal["cache", "committed"] = "cache"
    try:
        path.lstat()
    except FileNotFoundError:
        path = _REVIEW / "fdi_crosswalks.yaml"
        origin = "committed"
    except OSError:
        return _failure("crosswalk_hash")
    try:
        digest = sha256_hex(path.read_bytes())
    except OSError:
        return _failure("crosswalk_hash")
    checked = read_crosswalk(path, expected_sha256=digest, cache=cache, targets=_REVIEW)
    if isinstance(checked, InvestmentFailure):
        return checked
    if origin == "committed" and checked.mappings:
        return _failure("crosswalk_schema")
    return replace(checked, origin=origin)


def _mapping(
    item: object, directory: Path, cache: Path | None
) -> MappingRow | InvestmentFailure:
    if not isinstance(item, dict) or set(item) != _FIELDS:
        return _failure("crosswalk_schema")
    identifier = item["project_id"]
    if (
        item["key_basis"] != "source_issued_identifier"
        or isinstance(identifier, bool)
        or not isinstance(identifier, int)
    ):
        return _failure("name_derived_key")
    if identifier < 0 or bare_digit_run(str(identifier)):
        return _failure("identifier_shape")
    if not all(
        isinstance(value, str) for key, value in item.items() if key != "project_id"
    ):
        return _failure("crosswalk_schema")
    if item["source_id"] != "fdi_projects" or item["column"] not in _COLUMNS:
        return _failure("crosswalk_schema")
    if (
        _HASH.fullmatch(item["snapshot_sha256"]) is None
        or re.fullmatch(r"fdi_[a-f0-9]{16}", item["project_key"]) is None
    ):
        return _failure("crosswalk_schema")
    if (
        item["review_role"] != "lead"
        or _REFERENCE.fullmatch(item["review_reference"]) is None
        or bare_digit_run(item["review_reference"])
    ):
        return _failure("crosswalk_review")
    try:
        if date.fromisoformat(item["review_date"]).isoformat() != item["review_date"]:
            return _failure("crosswalk_review")
    except ValueError:
        return _failure("crosswalk_review")
    resource = item["target_resource"]
    if resource == "municipality_names.csv" or _FILE.fullmatch(resource) is None:
        return _failure("name_derived_key")
    if resource == "municipality_codes.csv":
        if cache is None:
            return _failure("crosswalk_target")
        directory = cache / "review"
        if directory.is_symlink() or any(
            parent.is_symlink() for parent in directory.parents
        ):
            return _failure("crosswalk_target")
    target_path = directory / resource
    try:
        if target_path.is_symlink():
            return _failure("crosswalk_target")
        body = target_path.read_bytes()
    except OSError:
        return _failure("crosswalk_target")
    if sha256_hex(body) != item["target_sha256"]:
        return _failure("crosswalk_target_hash")
    try:
        if target_path.suffix == ".csv":
            targets: object = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        else:
            targets = read_yaml(target_path)
    except (OSError, RegistryError, UnicodeError, csv.Error):
        return _failure("crosswalk_target")
    try:
        intact = not target_path.is_symlink() and target_path.read_bytes() == body
    except OSError:
        intact = False
    if not intact:
        return _failure("crosswalk_target_hash")
    field = _COLUMNS[item["column"]]
    if not isinstance(targets, list) or not any(
        isinstance(row, dict)
        and field in row
        and isinstance(row[field], (str, int))
        and not isinstance(row[field], bool)
        and str(row[field]) == item["target_key"]
        for row in targets
    ):
        return _failure("crosswalk_target")
    return MappingRow(
        item["snapshot_sha256"],
        identifier,
        item["project_key"],
        item["column"],
        item["target_key"],
        resource,
        item["target_sha256"],
        item["review_date"],
        item["review_reference"],
    )


def mapped_columns(
    crosswalk: ReviewedCrosswalk | None,
    identifier: object,
    project_key: str,
    envelope: SourceEnvelope,
) -> dict[str, object] | InvestmentFailure:
    """Match issued ID and snapshot, checking source values; misses stay null."""
    values: dict[str, object] = dict.fromkeys(_COLUMNS)
    coverage = dict.fromkeys(_COLUMNS, "not mapped")
    if crosswalk is not None:
        selected = tuple(
            row
            for row in crosswalk.mappings
            if row.snapshot_sha256 == envelope.page_sha256
        )
        for row in selected:
            if row.project_id != identifier:
                continue
            if row.project_key != project_key:
                return fail(
                    envelope,
                    "crosswalk_source_value",
                    "reviewed source values",
                    "changed",
                )
            values[row.column] = row.target_key
            coverage[row.column] = "reviewed"
        values["crosswalk_sha256"] = crosswalk.sha256
    values["mapping_coverage"] = coverage
    return values


def source_membership(
    crosswalk: ReviewedCrosswalk | None,
    rows: tuple[Mapping[str, object], ...],
    envelope: SourceEnvelope,
) -> InvestmentFailure | None:
    """Refuse review rows whose issued identifier is absent from the selected page."""
    if crosswalk is None:
        return None
    identifiers = {row.get("project_id") for row in rows}
    if any(
        row.snapshot_sha256 == envelope.page_sha256
        and row.project_id not in identifiers
        for row in crosswalk.mappings
    ):
        return fail(
            envelope, "crosswalk_source_value", "present source identifier", "absent"
        )
    return None


def write_municipality_codes(cache: Path, entry: Entry, *, digest: str) -> str:
    """Lead-shell offline extract from a reviewed, verified bnd_zone_2020 snapshot.

    Like the district aliases, derived rows stay in the uncommitted cache/review
    directory. Return the target SHA-256 for each lead-reviewed crosswalk row;
    no source values or guessed retrieval dates are embedded in this module.
    """
    from eii_custodian.publicdata.frame.build import read_cached
    from eii_custodian.publicdata.frame.layers import layer_rows

    if entry.source_id != "bnd_zone_2020":
        raise ValueError("municipality_codes_source")
    payload, receipt = read_cached(cache, entry, digest=digest)
    rows = layer_rows(entry.source_id, payload)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ("municipality_code", "source_id", "source_sha256", "retrieved_utc")
    )
    for code in sorted({row["MUNICIPAL_CODE"] for row in rows}):
        writer.writerow(
            (code, entry.source_id, receipt["sha256"], receipt["retrieved_utc"])
        )
    body = buffer.getvalue().encode("utf-8")
    directory = cache / "review"
    if directory.is_symlink() or any(
        parent.is_symlink() for parent in directory.parents
    ):
        raise ValueError("municipality_codes_path")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "municipality_codes.csv"
    partial = directory / ".municipality_codes.csv.partial"
    if path.is_symlink() or partial.is_symlink():
        raise ValueError("municipality_codes_path")
    try:
        partial.write_bytes(body)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return sha256_hex(body)
