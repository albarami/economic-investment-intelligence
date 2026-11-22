"""Closed identity and cache boundary for the separate tender acquisition."""

import json
import shutil
from pathlib import Path

from .bounded import file_hash
from .registry import Entry
from .snapshots import read_snapshot, reviewed_selections

OWN_RUN_KEYS = frozenset({"tenders_pub"})
OWN_RUN_CACHE_RELATIVE = "data/public_cache_tenders"
OWN_RUN_REASON = "own_run_pending"
OWN_RUN_CAVEAT = "tender_fetch_own_run"


def is_own_run_entry(entry: Entry) -> bool:
    return (
        entry.key in OWN_RUN_KEYS
        and entry.source_id == "tenders_pub"
        and entry.kind == "paged_cards"
        and entry.skip_reason == ""
    )


def is_tender_entry(entry: Entry) -> bool:
    """Name a tender row before kind or skip changes can reach transport."""
    return entry.key in OWN_RUN_KEYS or entry.source_id == "tenders_pub"


def own_run_cache(cache: Path) -> Path:
    """Keep the second cache a sibling of the ordinary public cache."""
    return cache.parent / "public_cache_tenders"


def _copy_snapshot(source: Path, destination: Path, identity: str) -> None:
    """Copy only verified immutable index, receipt and body bytes."""
    snapshot = read_snapshot(source, identity)
    paths = (
        source / "index" / f"{identity}.json",
        snapshot.receipt_path,
        snapshot.path,
    )
    for path in paths:
        target = destination / path.relative_to(source)
        if target.exists():
            if file_hash(target) != file_hash(path):
                raise ValueError("tender_handoff_conflict")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    copied = read_snapshot(destination, identity)
    if copied.sidecar != snapshot.sidecar or copied.body != snapshot.body:
        raise ValueError("tender_handoff_invalid")


def handoff_completed_archive(
    main_cache: Path, tender_cache: Path, entry: Entry, stamp: str
) -> tuple[str, dict[str, object]] | None:
    """Adopt only a pinned, completed and fully evidenced ordinary archive."""
    from eii_custodian.publicdata.assembly_tenders import (
        terms_body_hash,
        verify_archive_terms,
        verify_intake_match,
    )
    from eii_custodian.publicdata.confirm_s2_t13 import (
        completion_evidence,
        load_confirmation,
    )

    from .resume import RunRecord

    identity = reviewed_selections(main_cache).get(entry.key)
    if identity is None:
        return None
    try:
        journal = json.loads((main_cache / "build-run.json").read_bytes())
        log = json.loads((main_cache / "build-log.json").read_bytes())
        rows = log["terms"]
        terms = [
            row for row in rows if isinstance(row, dict) and row.get("key") == entry.key
        ]
        item = journal.get("entries", {}).get(entry.key, {})
        if (
            journal.get("state") not in {"interrupted", "complete"}
            or item.get("completed") is not True
            or len(terms) != 1
        ):
            raise ValueError("tender_handoff_incomplete")
        RunRecord(main_cache, journal, True).proven_pages(
            entry, item, legacy_intake=True
        )
        archive = read_snapshot(main_cache / entry.key, identity)
        verify_archive_terms(archive.body, archive.sidecar)
        completion_evidence(
            load_confirmation(
                main_cache.parent.parent
                / "custodian/publicdata/review/s2_t13_confirmation.yaml"
            ),
            entry,
            archive.sidecar,
        )
        raw_terms = terms_body_hash(main_cache, entry, terms)
        if archive.sidecar.get("terms_sha256") != terms[0].get("terms_sha256"):
            raise ValueError("tender_handoff_terms_invalid")
        verify_intake_match(main_cache, archive.body, stamp)
        _copy_snapshot(main_cache / entry.key, tender_cache / entry.key, identity)
        _copy_snapshot(
            main_cache / entry.key / "terms",
            tender_cache / entry.key / "terms",
            raw_terms,
        )
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("tender_handoff_refused") from None
    return identity, terms[0]
