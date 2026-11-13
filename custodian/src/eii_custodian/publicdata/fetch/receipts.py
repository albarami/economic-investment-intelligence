"""Atomic cache writes. A failed replace leaves no partial file."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from eii_custodian.publicdata.fetch.registry import Entry


def sha256_hex(body: bytes) -> str:
    """Return the SHA-256 hex digest of body."""
    return hashlib.sha256(body).hexdigest()


def commit_pair(
    directory: Path,
    digest: str,
    extension: str,
    body: bytes,
    sidecar: dict[str, object],
) -> None:
    """Write the body and its sidecar, or leave the directory without either."""
    directory.mkdir(parents=True, exist_ok=True)
    body_final = directory / f"{digest}.{extension}"
    side_final = directory / f"{digest}.meta.json"
    body_partial = directory / f".{digest}.{extension}.partial"
    side_partial = directory / f".{digest}.meta.json.partial"
    try:
        body_partial.write_bytes(body)
        side_partial.write_text(_dump(sidecar), encoding="utf-8")
        os.replace(body_partial, body_final)
        os.replace(side_partial, side_final)
    except OSError:
        for path in (body_partial, side_partial, body_final, side_final):
            path.unlink(missing_ok=True)
        raise


def commit_citation(directory: Path, sidecar: dict[str, object]) -> None:
    """Write citation metadata and no fetched file."""
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / "citation.json"
    partial = directory / ".citation.json.partial"
    try:
        partial.write_text(_dump(sidecar), encoding="utf-8")
        os.replace(partial, final)
    except OSError:
        partial.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        raise


def sidecar_for(
    entry: Entry,
    *,
    digest: str,
    nbytes: int,
    fetch_url: str,
    fetch_host: str,
    retrieved_utc: str,
    publisher: str,
    source_modified: str,
    row_count: int | None,
    terms_sha256: str,
    switched_off: bool,
    portal_licence: str = "",
    portal_licence_url: str = "",
) -> dict[str, object]:
    """Build the section 3.1 sidecar. Empty optionals are JSON null."""
    return {
        "source_id": entry.source_id,
        "key": entry.key,
        "slug": entry.slug,
        "kind": entry.kind,
        "fetch_mode": "citation_only" if entry.kind == "citation_only" else "fetch",
        "title_en": entry.title_en,
        "publisher": publisher,
        "fetch_host": fetch_host,
        "fetch_url": fetch_url,
        "landing_url": entry.landing_url or None,
        "licence_id": entry.licence_id,
        "licence_basis": entry.licence_basis,
        "licence_url": entry.licence_url or None,
        "portal_licence": portal_licence or None,
        "portal_licence_url": portal_licence_url or None,
        "terms_sha256": terms_sha256 or None,
        "decision_record": entry.decision_record or None,
        "public_splits": list(entry.public_splits),
        "commit_allowed": entry.commit_allowed,
        "retrieved_utc": retrieved_utc,
        "sha256": digest,
        "bytes": nbytes,
        "source_modified": source_modified or None,
        "period_first": entry.period_first or None,
        "period_last": entry.period_last or None,
        "row_count": row_count,
        "columns": [{"name": name, "type": kind} for name, kind in entry.columns],
        "reconciliation": entry.reconciliation,
        "release_tables": list(entry.release_tables),
        "caveat_keys": list(entry.caveat_keys),
        "switched_off": switched_off,
    }


def cache_directory(cache: Path, key: str) -> Path:
    """Return the cache directory for one registry key."""
    return cache / key


def _dump(sidecar: dict[str, object]) -> str:
    return json.dumps(sidecar, sort_keys=True, ensure_ascii=True) + "\n"
