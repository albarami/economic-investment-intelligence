"""Reusable register table builder; public and protected callers share validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.additions.storage import publish

from .contracts import (
    CARD_COLUMNS,
    METHOD,
    SNAPSHOT_COLUMNS,
    VERSION,
    column_type,
    refuse,
)
from .parse import parse
from .provenance import Capture, Frame, digest, month, validate_capture
from .validate import scan_artefact, scan_content, validate_release


@dataclass(frozen=True, repr=False)
class Built:
    tables: dict[str, list[dict[str, object]]]
    manifest: dict[str, Any]
    coverage: dict[str, tuple[str, ...]]

    def snapshot_reason(self, source: str, earlier: str, later: str) -> str | None:
        month(earlier)
        month(later)
        kept = self.coverage.get(source, ())
        return None if earlier in kept and later in kept else "snapshot_not_kept"


def build(
    output: Path,
    release_kind: str,
    frame: Frame,
    current: tuple[Capture, ...],
    snapshots: tuple[Capture, ...],
) -> Built:
    """Validate in memory, publish only Public projections; never retain raw CSV."""
    if release_kind not in {"public_only", "protected"}:
        refuse("release_kind")
    if len(current) != 2 or {item.source_id for item in current} != {
        "biz_register",
        "fc_register",
    }:
        refuse("current_sources")
    current_months = {item.source_id: month(item.period) for item in current}
    tables: dict[str, list[dict[str, object]]] = {
        "pub_register_company": [],
        "pub_register_snapshot": [],
    }
    receipts: list[dict[str, object]] = []
    card_content: set[str] = set()
    kept: dict[str, set[str]] = {"biz_register": set(), "fc_register": set()}
    for is_snapshot, batch in ((False, current), (True, snapshots)):
        for item in sorted(batch, key=lambda item: (item.source_id, item.period)):
            side = validate_capture(item)
            if is_snapshot:
                if item.period < "2026-11":
                    refuse("snapshot_month")
                if item.period in kept[item.source_id]:
                    refuse("duplicate_snapshot_month")
                kept[item.source_id].add(item.period)
                if item.period > current_months[item.source_id]:
                    refuse("snapshot_after_current")
            cards = parse(item.source_id, item.files, frame)
            for card in cards:
                for name in ("name_en", "name_ar", "registered_address"):
                    value = card[name]
                    if isinstance(value, str) and value:
                        card_content.add(value)
            # Reuse the full schema/identifier checks on historical cards too;
            # only their key, month, source and location are subsequently kept.
            validate_release(
                {"pub_register_company": cards, "pub_register_snapshot": []}, frame
            )
            if is_snapshot:
                tables["pub_register_snapshot"].extend(
                    {
                        "registration_number": row["registration_number"],
                        "period": item.period,
                        "source_id": item.source_id,
                        "registered_cell": row["registered_cell"],
                    }
                    for row in cards
                )
            else:
                tables["pub_register_company"].extend(cards)
            receipts.append(
                {
                    "use": "snapshot" if is_snapshot else "current",
                    "receipt": side,
                    "receipt_sha256": digest(
                        json.dumps(side, sort_keys=True, separators=(",", ":")).encode()
                    ),
                }
            )
    for rows in tables.values():
        rows.sort(
            key=lambda row: (
                str(row.get("period", "")),
                str(row["registration_number"]),
            )
        )
    keys = validate_release(tables, frame)
    coverage = {source: tuple(sorted(periods)) for source, periods in kept.items()}
    manifest: dict[str, Any] = dict(
        version=VERSION,
        method=METHOD,
        provenance="Public",
        release_kind=release_kind,
        frame_sha256=frame.sha256,
        receipts=receipts,
        snapshot_coverage=coverage,
    )
    report = {
        "method": METHOD,
        "version": VERSION,
        "source_status": "validated",
        "missing_snapshot_reason": "snapshot_not_kept",
    }
    scan_artefact(manifest, keys)
    scan_artefact(report, keys)
    scan_content(manifest, frozenset(card_content))
    scan_content(report, frozenset(card_content))
    specs = {
        "pub_register_company": CARD_COLUMNS,
        "pub_register_snapshot": SNAPSHOT_COLUMNS,
    }
    try:
        destination = publish(
            output,
            [
                (
                    name,
                    [(column, column_type(column)) for column in specs[name]],
                    [tuple(row[column] for column in specs[name]) for row in rows],
                )
                for name, rows in tables.items()
            ],
            manifest,
            report,
        )
        published = json.loads((destination / "manifest.json").read_bytes())
    except Exception:
        # The storage seam rolls back the whole set; no upstream diagnostic
        # (which might contain a value or an output path) crosses this adapter.
        refuse("register_publish_failed")
    return Built(tables, published, coverage)
