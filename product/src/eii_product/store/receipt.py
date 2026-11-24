"""The loader's receipt. It is not a manifest artefact."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

RECEIPT_NAME = "load_receipt.json"
PARTIAL_NAME = ".load_receipt.json.partial"
PROTECTED_RECEIPT_FIELDS = (
    "parameter_set",
    "protected_sha256",
    "rules_version_id",
    "window_key",
)
FREEZE_REASON = "freeze_refused_public_only"


class ReceiptRefusal(Exception):
    """A receipt that is missing, unfinished or not this release."""

    def __init__(self, reason: str) -> None:
        """Refuse a reason outside the receipt's closed list."""
        if reason not in {
            "receipt_forbidden_field",
            "receipt_missing",
            "receipt_not_complete",
            "receipt_release_mismatch",
            "receipt_unreadable",
        }:
            message = "refusal reason invalid"
            raise ValueError(message)
        self.reason = reason
        super().__init__(reason)


def write_receipt(
    folder: Path,
    release_id: str,
    tables: Mapping[str, Sequence[object]],
    digests: Mapping[str, str],
    durations_ms: Mapping[str, int],
    engines: Sequence[str] = ("embedded", "postgres"),
    before_rename: Callable[[], None] | None = None,
) -> None:
    """Write the receipt by counting rows. A failure leaves no receipt file."""
    body = {
        "digests": {name: digests[name] for name in sorted(digests)},
        "durations_ms": {name: durations_ms[name] for name in sorted(durations_ms)},
        "engines": list(engines),
        "release_id": release_id,
        "row_counts": {name: len(tables[name]) for name in sorted(tables)},
        "state": "complete",
        "tables": sorted(tables),
    }
    for field in PROTECTED_RECEIPT_FIELDS:
        if field in body:
            raise ReceiptRefusal("receipt_forbidden_field")
    payload = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    partial = folder / PARTIAL_NAME
    target = folder / RECEIPT_NAME
    try:
        partial.write_bytes(payload)
        if before_rename is not None:
            before_rename()
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def read_receipt(folder: Path, release_id: str) -> dict[str, object]:
    """Read a complete receipt of this release. Refuse the protected-window fields."""
    path = folder / RECEIPT_NAME
    if not path.is_file():
        raise ReceiptRefusal("receipt_missing")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ReceiptRefusal("receipt_unreadable") from None
    if type(parsed) is not dict:
        raise ReceiptRefusal("receipt_unreadable")
    for field in PROTECTED_RECEIPT_FIELDS:
        if field in parsed:
            raise ReceiptRefusal("receipt_forbidden_field")
    if parsed.get("state") != "complete":
        raise ReceiptRefusal("receipt_not_complete")
    if parsed.get("release_id") != release_id:
        raise ReceiptRefusal("receipt_release_mismatch")
    return parsed


def refuse_public_only_freeze(document: Mapping[str, object]) -> str | None:
    """A public_only release is never frozen and never enters the export register."""
    if document.get("release_kind") == "public_only":
        return FREEZE_REASON
    return None
