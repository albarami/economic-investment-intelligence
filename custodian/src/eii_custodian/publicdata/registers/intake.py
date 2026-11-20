"""Lead-operated read-only sibling selection. No crawl, cache copy or network."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contracts import ROLES, refuse
from .provenance import Capture, month, validate_capture

_FILE_LIMIT = 256 * 1024 * 1024
_INDEX_LIMIT = 1024 * 1024
_COMPANIONS = {
    "companies": "qfc_companies.csv",
    "geocoded": "qfc_companies_geocoded.csv",
    "events": "qfc_events.csv",
}


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_file(path: Path, limit: int) -> bytes:
    """Bounded read with no-follow and before/after object checks; never write."""
    if path.name.startswith(".") or any(
        part in {".env", ".private", "vault", "public_cache"} for part in path.parts
    ):
        refuse("register_path")
    try:
        if path.absolute() != path.resolve() or any(
            parent.is_symlink() for parent in path.parents
        ):
            refuse("register_path")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                refuse("register_file_bound")
            body = handle.read(limit + 1)
            after = os.fstat(handle.fileno())
        if (
            len(body) > limit
            or _signature(before) != _signature(after)
            or _signature(after) != _signature(path.stat(follow_symlinks=False))
        ):
            refuse("register_file_changed")
    except OSError:
        refuse("register_file_unreadable")
    return body


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for key, value in pairs:
        if key in found:
            refuse("register_index_schema")
        found[key] = value
    return found


def _capture(primary: Path, source: str, value: object, *, historical: bool) -> Capture:
    if not isinstance(value, dict) or set(value) != {"receipt", "files"}:
        refuse("register_index_schema")
    side, names = value["receipt"], value["files"]
    if (
        not isinstance(side, dict)
        or not isinstance(names, dict)
        or set(names) != ROLES[source]
    ):
        refuse("register_index_schema")
    period = month(side.get("period"))
    files: dict[str, bytes] = {}
    for role, name in names.items():
        if historical:
            expected = period + "." + role + ".csv"
        elif source == "biz_register" or role == "companies":
            expected = primary.name
        else:
            expected = _COMPANIONS[role]
        if not isinstance(name, str) or name != expected or Path(name).name != name:
            refuse("register_sibling_selection")
        files[role] = read_file(primary.parent / name, _FILE_LIMIT)
    item = Capture(source, period, files, side)
    validate_capture(item)
    return item


def from_environment(
    environ: Mapping[str, str],
    *,
    index_hashes: Mapping[str, str] | None = None,
) -> tuple[tuple[Capture, ...], tuple[Capture, ...]]:
    """Only the lead calls this adapter. Tests pass an invented mapping explicitly.

    Each primary's `.register.json` index pins current and historical receipts.
    The module neither inspects os.environ nor searches any folder for files.
    """
    settings = (
        ("biz_register", "EII_REGISTER_FILE"),
        ("fc_register", "EII_FC_REGISTER_FILE"),
    )
    if any(not environ.get(setting) for _, setting in settings):
        refuse("register_setting_missing")
    if index_hashes is None or set(index_hashes) != set(ROLES):
        refuse("register_index_pin_missing")
    current: list[Capture] = []
    history: list[Capture] = []
    for source, setting in settings:
        primary = Path(environ[setting])
        if primary.suffix != ".csv":
            refuse("register_path")
        body = read_file(
            primary.with_name(primary.name + ".register.json"), _INDEX_LIMIT
        )
        from .provenance import digest

        pin = index_hashes[source]
        if (
            not isinstance(pin, str)
            or re.fullmatch(r"[a-f0-9]{64}", pin) is None
            or digest(body) != pin
        ):
            refuse("register_index_hash_mismatch")
        try:
            index = json.loads(body, object_pairs_hook=_object)
        except (ValueError, UnicodeError):
            refuse("register_index_schema")
        if (
            not isinstance(index, dict)
            or set(index) != {"version", "current", "snapshots"}
            or index["version"] != "register_siblings_v1"
            or not isinstance(index["snapshots"], list)
        ):
            refuse("register_index_schema")
        current.append(_capture(primary, source, index["current"], historical=False))
        seen: set[str] = set()
        for value in index["snapshots"]:
            item = _capture(primary, source, value, historical=True)
            if item.period in seen:
                refuse("duplicate_snapshot_month")
            seen.add(item.period)
            history.append(item)
    return tuple(current), tuple(history)
