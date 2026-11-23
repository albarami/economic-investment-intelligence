"""Minimal cache-only identity handoff; confirmation never publishes a value."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path

from eii_custodian.publicdata.busyness.policy import names_match
from eii_custodian.publicdata.busyness.review import (
    CROSSWALK_COLUMNS,
    CROSSWALK_FILE,
    _date,
    load_crosswalk,
)
from eii_custodian.publicdata.busyness.security import assert_clean
from eii_custodian.publicdata.comtrade.parse import ParseError, decode_members
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.snapshots import utc

HANDOFF_FILE = "busy_besttime/identity-handoff.json"
FIELDS = frozenset({"place_id", "venue_id", "venue_name", "sha256", "retrieved_utc"})
INPUT_FILES = ("review/" + CROSSWALK_FILE, "places_s2_t06/pub_place.jsonl")


def cache_path(cache: Path, name: str) -> Path:
    """Refuse cache aliases before reading or writing a handoff artefact."""
    path = cache / name
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("handoff_cache_alias")
    return path


def input_hashes(cache: Path) -> dict[str, str]:
    return {
        name: sha256_hex(cache_path(cache, name).read_bytes()) for name in INPUT_FILES
    }


def validate_handoff(value: object) -> list[dict[str, str]]:
    """Closed leaf types/keys prevent a raw provider document from being stored."""
    if not isinstance(value, list):
        raise ValueError("handoff_schema")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != FIELDS
            or any(
                not isinstance(item, str) or not item.strip() for item in row.values()
            )
        ):
            raise ValueError("handoff_schema")
        if row["place_id"] in seen:
            raise ValueError("handoff_duplicate")
        if re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) is None:
            raise ValueError("handoff_digest")
        try:
            utc(row["retrieved_utc"])
        except ValueError:
            raise ValueError("handoff_time") from None
        seen.add(row["place_id"])
        rows.append(row)
    return rows


def write_json(
    cache: Path, name: str, value: object, environ: Mapping[str, str]
) -> str:
    """Atomic writes only to caller-owned fixed cache paths, with secret refusal."""
    assert_clean(environ, value)
    payload = (json.dumps(value, sort_keys=True) + "\n").encode()
    path = cache_path(cache, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = cache_path(cache, name + ".partial")
    try:
        partial.write_bytes(payload)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return sha256_hex(payload)


def write_handoff(cache: Path, rows: object, environ: Mapping[str, str]) -> str:
    return write_json(cache, HANDOFF_FILE, validate_handoff(rows), environ)


def _document(body: bytes) -> object:
    try:
        return decode_members(body)
    except (ParseError, ValueError, UnicodeError):
        pass
    raise ValueError("handoff_schema") from None


def confirm_handoff(
    cache: Path,
    digest: str,
    reviewer_role: str,
    reviewed_on: str,
    environ: Mapping[str, str],
) -> None:
    """The lead explicitly approves these exact handoff bytes; check every identity."""
    body = cache_path(cache, HANDOFF_FILE).read_bytes()
    if sha256_hex(body) != digest:
        raise ValueError("handoff_changed")
    if not reviewer_role.strip():
        raise ValueError("handoff_reviewer")
    _date(reviewed_on, "handoff", "reviewed_on")
    rows = validate_handoff(_document(body))
    report = _document(
        cache_path(cache, "busy_besttime/bootstrap-run.json").read_bytes()
    )
    if (
        not isinstance(report, dict)
        or report.get("handoff_sha256") != digest
        or report.get("inputs") != input_hashes(cache)
    ):
        raise ValueError("handoff_inputs_changed")
    path = cache_path(cache, "review/" + CROSSWALK_FILE)
    crosswalk = {row["place_id"]: row for row in load_crosswalk(path)}
    places = {
        row["place_id"]: row
        for row in map(
            json.loads, cache_path(cache, INPUT_FILES[1]).read_text().splitlines()
        )
    }
    for row in rows:
        identifier = row["place_id"]
        if identifier not in crosswalk or crosswalk[identifier]["match"] != "pending":
            raise ValueError("handoff_not_pending")
        if identifier not in places or not names_match(
            places[identifier]["name"], row["venue_name"]
        ):
            raise ValueError("handoff_name_mismatch")
        crosswalk[identifier].update(
            venue_key=row["venue_id"],
            match="matched",
            reviewer_role=reviewer_role,
            reviewed_on=reviewed_on,
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CROSSWALK_COLUMNS)
    writer.writeheader()
    writer.writerows(crosswalk.values())
    payload = stream.getvalue()
    assert_clean(environ, payload)
    partial = cache_path(cache, "review/" + CROSSWALK_FILE + ".partial")
    try:
        partial.write_text(payload, encoding="utf-8", newline="")
        load_crosswalk(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
