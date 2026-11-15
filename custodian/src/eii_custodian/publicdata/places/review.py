"""Loaders for the committed review files and their uncommitted cache copies."""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from eii_custodian.publicdata.places import PlacesError

VERIFIED_COLUMNS = (
    "place_id",
    "check_date",
    "reviewer_role",
    "verification_link",
    "status",
    "source_id",
)
ATTRIBUTION_COLUMNS = ("dataset_token", "licence")
CATEGORY_COLUMNS = ("basic_category", "category_class")
GAZETTEER_KEYS = (
    "place_key",
    "kind",
    "name_en",
    "name_ar",
    "aliases",
    "source_id",
    "record_key",
    "arabic_review",
)
AREA_KEYS = ("place_key", "mode", "cutoff_minutes", "source_id", "record_key")
STATUSES = frozenset({"verified_open", "closed_or_moved", "not_found", "duplicate"})
ACCEPTED_SOURCES = frozenset(
    {"tenant_directory", "official_website", "public_authority"}
)
REFUSED_SOURCES = frozenset(
    {"review_site", "delivery_platform", "booking_platform", "map_search"}
)
CATEGORY_CLASSES = frozenset({"restaurant", "italian_restaurant", "other"})
_CHECK_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Verification:
    """One pub_place_verification row."""

    place_id: str
    check_date: str
    reviewer_role: str
    verification_link: str
    status: str
    source_id: str


def load_verified_places(
    committed: Path,
    cache: Path | None,
    known_place_ids: frozenset[str],
    build_date: date,
) -> tuple[str, tuple[Verification, ...]]:
    """Load verification rows. An orphan, a repeated date or a bad status refuses."""
    path, origin = _choose(committed, cache)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != VERIFIED_COLUMNS:
            raise PlacesError("verified_header")
        raw = [
            item
            for item in reader
            if any((value or "").strip() for value in item.values())
        ]
    rows = tuple(_verification(item, known_place_ids, build_date) for item in raw)
    _refuse_same_date(rows)
    return origin, rows


def load_attribution(
    committed: Path, cache: Path | None
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Load the dataset-token attribution table."""
    path, origin = _choose(committed, cache)
    rows = _csv(path, ATTRIBUTION_COLUMNS, "attribution_header")
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in rows:
        token = item["dataset_token"].strip()
        licence = item["licence"].strip()
        if token == "" or licence == "":
            raise PlacesError("attribution_row")
        if token in seen:
            raise PlacesError("duplicate_token")
        seen.add(token)
        found.append((token, licence))
    return origin, tuple(found)


def load_categories(
    committed: Path, cache: Path | None
) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Load the category class table. An unknown class refuses the file."""
    path, origin = _choose(committed, cache)
    rows = _csv(path, CATEGORY_COLUMNS, "category_header")
    found: list[tuple[str, str]] = []
    for item in rows:
        label = item["basic_category"].strip()
        kind = item["category_class"].strip()
        if label == "":
            raise PlacesError("category_row")
        if kind not in CATEGORY_CLASSES:
            raise PlacesError("unknown_category_class")
        found.append((label, kind))
    return origin, tuple(found)


def load_showcase_areas(
    committed: Path, cache: Path | None
) -> tuple[str, tuple[Mapping[str, object], ...]]:
    """Load showcase area definitions. An empty list is the committed header."""
    path, origin = _choose(committed, cache)
    rows = _yaml_list(path)
    checked = tuple(_area(item) for item in rows)
    return origin, checked


def load_showcase_gazetteer(
    committed: Path, cache: Path | None
) -> tuple[str, tuple[Mapping[str, object], ...]]:
    """Load showcase gazetteer keys. Null source keys stay null."""
    path, origin = _choose(committed, cache)
    return origin, tuple(_keys(item, GAZETTEER_KEYS) for item in _yaml_list(path))


def load_flagship_candidates(
    committed: Path, cache: Path | None
) -> tuple[str, tuple[Mapping[str, object], ...]]:
    """Load flagship candidate keys. The use field is optional."""
    path, origin = _choose(committed, cache)
    return origin, tuple(_keys(item, GAZETTEER_KEYS) for item in _yaml_list(path))


def accept_verification(
    row: Verification, known_place_ids: frozenset[str], build_date: date
) -> Verification:
    """Apply the loader's per-row checks to one in-memory verification."""
    return _checked(
        _normalised_field(row.place_id),
        _normalised_field(row.check_date),
        _normalised_field(row.reviewer_role),
        _normalised_field(row.verification_link),
        _normalised_field(row.status),
        _normalised_field(row.source_id),
        known_place_ids,
        build_date,
    )


def refuse_same_date(rows: Sequence[Verification]) -> None:
    """Refuse two checks of one place on the same parsed date."""
    _refuse_same_date(rows)


def latest_status(rows: Sequence[Verification]) -> dict[str, Verification]:
    """Keep the latest parsed check date for each place."""
    found: dict[str, Verification] = {}
    for row in rows:
        current = found.get(row.place_id)
        if current is None or _parsed_date(row.check_date) > _parsed_date(
            current.check_date
        ):
            found[row.place_id] = row
    return found


def _choose(committed: Path, cache: Path | None) -> tuple[Path, str]:
    if cache is not None and cache.is_file():
        return cache, "cache"
    return committed, "committed"


def _verification(
    item: Mapping[str, str | None], known: frozenset[str], build_date: date
) -> Verification:
    return _checked(
        _text(item, "place_id"),
        _text(item, "check_date"),
        _text(item, "reviewer_role"),
        _text(item, "verification_link"),
        _text(item, "status"),
        _text(item, "source_id"),
        known,
        build_date,
    )


def _checked(
    place_id: str,
    check_date: str,
    role: str,
    link: str,
    status: str,
    source: str,
    known: frozenset[str],
    build_date: date,
) -> Verification:
    if place_id not in known:
        raise PlacesError("orphan_place_id")
    parsed = _parsed_date(check_date)
    if parsed > build_date:
        raise PlacesError("bad_check_date")
    if role == "":
        raise PlacesError("missing_role")
    if link == "":
        raise PlacesError("missing_link")
    _require_link(link)
    if status not in STATUSES:
        raise PlacesError("unknown_status")
    if source in REFUSED_SOURCES:
        raise PlacesError("verification_source_refused")
    if source not in ACCEPTED_SOURCES:
        raise PlacesError("verification_source_unknown")
    return Verification(place_id, parsed.isoformat(), role, link, status, source)


def _parsed_date(value: str) -> date:
    if _CHECK_DATE.fullmatch(value) is None:
        raise PlacesError("bad_check_date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PlacesError("bad_check_date") from exc


def _require_link(link: str) -> None:
    parts = urlsplit(link)
    if parts.scheme != "https" or not parts.hostname:
        raise PlacesError("link_form")


def _refuse_same_date(rows: Sequence[Verification]) -> None:
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.place_id, _parsed_date(row.check_date).isoformat())
        if key in seen:
            raise PlacesError("duplicate_place_date")
        seen.add(key)


def _text(item: Mapping[str, str | None], name: str) -> str:
    value = item.get(name)
    if value is None:
        return ""
    return _normalised_field(value)


def _normalised_field(value: str) -> str:
    return value.strip()


def _csv(
    path: Path, columns: tuple[str, ...], reason: str
) -> tuple[dict[str, str], ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != columns:
            raise PlacesError(reason)
        return tuple(
            {key: value or "" for key, value in item.items()}
            for item in reader
            if any((value or "").strip() for value in item.values())
        )


def _yaml_list(path: Path) -> list[object]:
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return []
    if not isinstance(loaded, list):
        raise PlacesError("review_list")
    return loaded


def _keys(item: object, required: tuple[str, ...]) -> Mapping[str, object]:
    if not isinstance(item, dict):
        raise PlacesError("review_row")
    missing = [key for key in required if key not in item]
    if missing:
        raise PlacesError("missing_key")
    return item


def _area(item: object) -> Mapping[str, object]:
    row = _keys(item, AREA_KEYS)
    if row.get("mode") != "walk" or row.get("cutoff_minutes") != 10:
        raise PlacesError("showcase_area")
    if not isinstance(row.get("place_key"), str) or row.get("place_key") == "":
        raise PlacesError("showcase_area")
    return row
