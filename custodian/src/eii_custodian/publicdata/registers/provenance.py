"""Complete key-scoped file receipts and the exact frame ownership digest."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import date

import h3
from eii_custodian.publicdata.fetch.registry import LICENCE_BASES
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, utc

from .contracts import REGISTRY_KEYS, ROLES, refuse


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def month(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}", value) is None:
        refuse("snapshot_month")
    try:
        date.fromisoformat(value + "-01")
    except ValueError:
        refuse("snapshot_month")
    return value


@dataclass(frozen=True, repr=False)
class Capture:
    source_id: str
    period: str
    files: Mapping[str, bytes]
    receipt: Mapping[str, object]


@dataclass(frozen=True)
class Frame:
    cells: frozenset[int]

    def __post_init__(self) -> None:
        try:
            valid = all(
                type(cell) is int and h3.get_resolution(format(cell, "x")) in {8, 9}
                for cell in self.cells
            )
            for cell in self.cells:
                h3.cell_to_latlng(format(cell, "x"))
            # Preserve the frame's one-owner rule before resolving any location.
            parents = {
                h3.str_to_int(h3.cell_to_parent(format(cell, "x"), 8))
                for cell in self.cells
                if h3.get_resolution(format(cell, "x")) == 9
            }
        except (ValueError, TypeError, OverflowError):
            refuse("frame_schema")
        if not valid or parents & self.cells:
            refuse("frame_schema")

    @property
    def sha256(self) -> str:
        return digest(json.dumps(sorted(self.cells), separators=(",", ":")).encode())


def receipt_for(
    source_id: str,
    period: str,
    files: Mapping[str, bytes],
    *,
    publisher: str,
    dataset: str,
    retrieved_utc: str,
    licence_id: str,
    licence_basis: str,
    terms_words: str,
    terms_read_on: str,
    basis_note: str,
) -> dict[str, object]:
    """Metadata only. The lead supplies attribution; pending terms remain records."""
    if source_id not in ROLES:
        refuse("register_source")
    return dict(
        version="register_input_v1",
        kind="register_file",
        key=REGISTRY_KEYS[source_id],
        source_id=source_id,
        period=period,
        publisher=publisher,
        dataset=dataset,
        retrieved_utc=retrieved_utc,
        licence_id=licence_id,
        licence_basis=licence_basis,
        terms_words=terms_words,
        terms_read_on=terms_read_on,
        basis_note=basis_note,
        files={
            role: {"sha256": digest(body), "bytes": len(body)}
            for role, body in files.items()
        },
    )


def validate_capture(item: Capture) -> dict[str, object]:
    """Check every receipt field, every file, and the source/key/period binding."""
    source = item.source_id
    if source not in ROLES:
        refuse("register_source")
    period = month(item.period)
    side = item.receipt
    expected = {
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
    if set(side) != expected:
        refuse("receipt_schema")
    for name, value in {
        "version": "register_input_v1",
        "kind": "register_file",
        "key": REGISTRY_KEYS[source],
        "source_id": source,
        "period": period,
    }.items():
        if side[name] != value:
            refuse("receipt_binding")
    for name in expected - {"files"}:
        if not isinstance(side[name], str) or not str(side[name]).strip():
            refuse("receipt_metadata")
    for name in ("publisher", "dataset"):
        if str(side[name]).strip().casefold() in {"pending", "terms to be read"} or str(
            side[name]
        ).strip().casefold().startswith("lead receipt required"):
            refuse("receipt_metadata")
    if side["licence_basis"] not in LICENCE_BASES:
        refuse("receipt_metadata")
    try:
        stamp = utc(side["retrieved_utc"])
    except SnapshotError:
        refuse("receipt_retrieval")
    if stamp.strftime("%Y-%m") != period:
        refuse("receipt_month_mismatch")
    read_on = side["terms_read_on"]
    if read_on != "pending":
        if (
            not isinstance(read_on, str)
            or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", read_on) is None
        ):
            refuse("receipt_terms_date")
        try:
            date.fromisoformat(read_on)
        except ValueError:
            refuse("receipt_terms_date")
    metadata = side["files"]
    if (
        set(item.files) != ROLES[source]
        or not isinstance(metadata, dict)
        or set(metadata) != ROLES[source]
    ):
        refuse("receipt_files")
    for role, body in item.files.items():
        info = metadata[role]
        if (
            not isinstance(body, bytes)
            or not isinstance(info, dict)
            or set(info) != {"sha256", "bytes"}
        ):
            refuse("receipt_files")
        if (
            info["sha256"] != digest(body)
            or type(info["bytes"]) is not int
            or info["bytes"] != len(body)
        ):
            refuse("receipt_hash_mismatch")
    # Return a detached JSON-shaped copy. There are no file names or source rows.
    return deepcopy(dict(side))
