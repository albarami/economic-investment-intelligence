"""Reading and parsing helpers of the reference-notes check: files, tables, addresses and dates."""

from __future__ import annotations

import datetime
import re
import tomllib
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from pack_anchors import read_regular, split_cells
from reference_notes_tables import DATE_FLOOR, OFFICIAL, PINS, QUOTE_WORDS

URL_RE = re.compile(
    r"(?i)\b[a-z][a-z0-9+.-]*://[^\s|)>\]\"'`]+"
    r"|(?<![:\w])//[a-z0-9.-]+\.[a-z][^\s|)>\]\"'`]*"
)
SEPARATOR_RE = re.compile(r"\|(\s*:?-+:?\s*\|)+")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
FILE_DATE_RE = re.compile(r"(?m)^\| Date \| (\d{4}-\d{2}-\d{2}) \|$")
QUOTE_RE = re.compile(r'`?"([^"|]+)"`?')
VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
OFFICIAL_ONLY = "not on the list of official addresses"
USER_OR_PORT = "has user information or a port"
Ids = dict[str, set[str]]


class Table(NamedTuple):
    """A pipe table: line of its header, header cells, separator seen, body rows."""

    line: int
    header: list[str]
    separator: bool
    rows: list[tuple[int, list[str]]]


def quote_problem(kind: str, ident: str, quote: str) -> str | None:
    """Return why `quote` does not suit a row of `kind`, or None.

    A READ row needs a double-quoted phrase of QUOTE_WORDS words; any other kind needs `-`.
    """
    if kind == "READ":
        low, high = QUOTE_WORDS
        match = QUOTE_RE.fullmatch(quote)
        if match is None or not low <= len(match.group(1).split()) <= high:
            return f"{ident}: READ quote must be a double-quoted phrase of {low} to {high} words"
    elif quote != "-":
        return f'{ident}: {kind} quote must be "-"'
    return None


def source_problem(kind: str, ident: str, source: str, ids: Ids) -> str | None:
    """Return why `source` is not a page id (READ) or run id (OBSERVED) of the section, or None."""
    table, word = ("Pages read", "page") if kind == "READ" else ("Runs", "run")
    if kind in ("READ", "OBSERVED") and source not in ids.get(table, {source}):
        return f'{ident}: {kind} source "{source}" is not a {word} id of this section'
    return None


def table_after(lines: list[str], start: int, stop: int) -> Table | None:
    """Return the first pipe table in `lines[start:stop]` (rows start at column 0), or None."""
    i = start
    while i < stop and not lines[i].startswith("|"):
        i += 1
    block = []
    while i < stop and lines[i].startswith("|"):
        block.append((i + 1, lines[i]))
        i += 1
    if not block:
        return None
    separator = (
        len(block) > 1 and SEPARATOR_RE.fullmatch(block[1][1].strip()) is not None
    )
    body = block[2:] if separator else block[1:]
    return Table(
        block[0][0],
        split_cells(block[0][1]),
        separator,
        [(n, split_cells(t)) for n, t in body],
    )


def check_address(url: str) -> str | None:
    """Return why `url` is not an official address, or None when it is."""
    if not url.startswith("https://"):
        return "not https"
    try:
        parts = urlsplit(url)
    except ValueError:
        return OFFICIAL_ONLY
    try:
        port = parts.port
    except ValueError:
        return USER_OR_PORT
    if parts.username is not None or parts.password is not None or port is not None:
        return USER_OR_PORT
    if parts.query or parts.fragment or "?" in url or "#" in url:
        return "has a query or a fragment"
    if (
        "%" in parts.path
        or "\\" in parts.path
        or "//" in parts.path
        or ".." in parts.path.split("/")
    ):
        return "has an unsafe path"
    if not any(
        parts.hostname == host and parts.path.startswith(prefix)
        for host, prefix in OFFICIAL
    ):
        return OFFICIAL_ONLY
    return None


def valid_date(value: str) -> bool:
    """Return True for a calendar date written YYYY-MM-DD."""
    if DATE_RE.fullmatch(value) is None:
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def file_date(text: str) -> str | None:
    """Return the date of the file's `| Date |` header row, or None when absent or invalid."""
    match = FILE_DATE_RE.search(text)
    return match.group(1) if match and valid_date(match.group(1)) else None


def date_problem(value: str, ceiling: str | None) -> str | None:
    """Return why `value` is not a date from DATE_FLOOR to the file date, or None."""
    if not valid_date(value):
        return f'"{value}" is not a calendar date YYYY-MM-DD'
    if value < DATE_FLOOR or (ceiling is not None and value > ceiling):
        return f'"{value}" is outside {DATE_FLOOR} to {ceiling or "the file date"}'
    return None


def load_pins(root: Path) -> tuple[set[str] | None, str]:
    """Return the component names of pins.toml, or (None, problem)."""
    text, problem = read_regular(root, PINS)
    if text is None:
        return None, problem
    try:
        components = tomllib.loads(text).get("component")
    except tomllib.TOMLDecodeError:
        return None, "cannot be parsed (TOMLDecodeError)"
    if not isinstance(components, list) or not components:
        return None, "no component rows"
    names = {
        row["name"]
        for row in components
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    if any(
        not isinstance(row, dict) or not isinstance(row.get("name"), str)
        for row in components
    ):
        return None, "a component row has no name"
    return names, ""
