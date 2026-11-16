"""Closed review schemas of S2-T16 rulings G2, G3 and G4.

These loaders do not fetch, read an environment, or verify provider facts.
The caller supplies the committed review path or the local crosswalk path.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml

REQUEST_FILE = "busy_besttime_requests.yaml"
VENUE_FILE = "busy_besttime_venues.csv"
CROSSWALK_FILE = "venue_busyness_crosswalk.csv"
VENUE_COLUMNS = ("place_id", "category_group", "reviewer_role", "reviewed_on")
CROSSWALK_COLUMNS = ("place_id", "venue_key", "reviewer_role", "reviewed_on", "match")


class ReviewError(ValueError):
    """A review failed; messages contain schema names, never input values."""


def _date(value: object, filename: str, field: str) -> None:
    if not isinstance(value, str):
        raise ReviewError(f"{filename} {field}: expected ISO date text")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ReviewError(f"{filename} {field}: expected ISO date text") from None
    if parsed.isoformat() != value:
        raise ReviewError(f"{filename} {field}: expected ISO date text")


def load_requests(path: Path) -> tuple[int, int]:
    """Require reviewed positive costs and their key-free source and date (G2)."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ReviewError(f"{REQUEST_FILE} schema: unreadable") from None
    fields = {"forecast_credits", "query_credits", "source_page", "read_on"}
    if not isinstance(document, dict) or set(document) != fields:
        raise ReviewError(f"{REQUEST_FILE} schema: expected the four review keys")
    costs: list[int] = []
    for field in ("forecast_credits", "query_credits"):
        value = document[field]
        if type(value) is not int or value <= 0:
            raise ReviewError(f"{REQUEST_FILE} {field}: expected positive integer")
        costs.append(value)
    page = document["source_page"]
    if not isinstance(page, str):
        raise ReviewError(f"{REQUEST_FILE} source_page: expected key-free HTTPS page")
    try:
        parts = urlsplit(page)
        valid = (
            parts.scheme == "https"
            and bool(parts.hostname)
            and parts.username is None
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise ReviewError(f"{REQUEST_FILE} source_page: expected key-free HTTPS page")
    _date(document["read_on"], REQUEST_FILE, "read_on")
    return costs[0], costs[1]


def _rows(
    path: Path, filename: str, columns: tuple[str, ...]
) -> tuple[dict[str, str], ...]:
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, [])
            if header != list(columns):
                raise ReviewError(f"{filename} schema: wrong columns")
            found: list[dict[str, str]] = []
            seen: set[str] = set()
            for cells in reader:
                if len(cells) != len(columns) or any(
                    not cell.strip() for cell in cells
                ):
                    raise ReviewError(f"{filename} schema: wrong or empty cells")
                row = dict(zip(columns, cells, strict=True))
                _date(row["reviewed_on"], filename, "reviewed_on")
                if row["place_id"] in seen:
                    raise ReviewError(f"{filename} place_id: duplicate")
                seen.add(row["place_id"])
                found.append(row)
    except (OSError, UnicodeError, csv.Error):
        raise ReviewError(f"{filename} schema: unreadable") from None
    return tuple(found)


def load_venues(path: Path) -> tuple[dict[str, str], ...]:
    """Read G3's fixed venue list; a header-only list is legal."""
    return _rows(path, VENUE_FILE, VENUE_COLUMNS)


def load_crosswalk(path: Path) -> tuple[dict[str, str], ...]:
    """Read G4's reviewed matches; do not infer or repair a match."""
    rows = _rows(path, CROSSWALK_FILE, CROSSWALK_COLUMNS)
    for row in rows:
        if row["match"] not in {"matched", "no_match"}:
            raise ReviewError(f"{CROSSWALK_FILE} match: expected matched or no_match")
    return rows
