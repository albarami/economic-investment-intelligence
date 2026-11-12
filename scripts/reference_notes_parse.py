"""Reading and parsing helpers of the reference-notes check: files, tables, addresses, dates, cites."""

from __future__ import annotations

import datetime
import re
import stat
import tomllib
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from reference_notes_tables import DATE_FLOOR, OFFICIAL, PINS, QUOTE_WORDS

_PATH = (
    r"(docs/[A-Za-z0-9_.-]+\.md|docs/decisions/[A-Za-z0-9_.-]+\.md|AGENTS\.md|TASKS\.md"
    r"|OPEN_ITEMS\.md)"
)
_TASK_RE = re.compile(r"^TASKS\.md (S[0-9]+-T[0-9]+)$")
_ROW_RE = re.compile(rf'^{_PATH} section "([^"]+)" row "([^"]+)"$')
_ITEM_RE = re.compile(rf'^{_PATH} section "([^"]+)" item ([1-9][0-9]*)$')
_SECTION_RE = re.compile(rf'^{_PATH} section "([^"]+)"$')
_ID_RE = re.compile(rf"^{_PATH} ([A-Z]{{2,4}}-[0-9]+)$")
_ANCHOR_FORMS = (_ROW_RE, _ITEM_RE, _SECTION_RE, _ID_RE, _TASK_RE)
_HEADING_RE = re.compile(r"^#{1,6} (.+)$")
_SECTION_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)+\s+|\d+\.\s+)")
_TASK_MARK = "\u2014"
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


class _Anchor(NamedTuple):
    """One citation item that matches one of the five anchor forms."""

    path: str
    kind: str
    ident: str
    label: str


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


def read_regular(root: Path, rel: str) -> tuple[str | None, str]:
    """Read a regular UTF-8 file under `root`; return (text, "") or (None, problem)."""
    path = root / rel
    try:
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            return None, "not a regular file"
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, "missing"
    except OSError as error:
        return None, f"unreadable ({type(error).__name__})"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not UTF-8"
    return (text, "") if text.strip() else (None, "empty")


def split_cells(line: str) -> list[str]:
    """Split a pipe-table line into trimmed cells."""
    stripped = line.strip()
    inner = (
        stripped[1:-1] if stripped.endswith("|") and len(stripped) > 1 else stripped[1:]
    )
    return [cell.strip() for cell in inner.split("|")]


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


def _parse_anchor(item: str) -> _Anchor | None:
    """Return the anchor in `item`, or None when it matches none of the five forms."""
    task = _TASK_RE.fullmatch(item)
    if task is not None:
        return _Anchor("TASKS.md", "task", task.group(1), "")
    row = _ROW_RE.fullmatch(item)
    if row is not None:
        return _Anchor(row.group(1), "row", row.group(2), row.group(3))
    numbered = _ITEM_RE.fullmatch(item)
    if numbered is not None:
        return _Anchor(numbered.group(1), "item", numbered.group(2), numbered.group(3))
    section = _SECTION_RE.fullmatch(item)
    if section is not None:
        return _Anchor(section.group(1), "section", section.group(2), "")
    ident = _ID_RE.fullmatch(item)
    if ident is not None:
        return _Anchor(ident.group(1), "id", ident.group(2), "")
    return None


def _heading_text(line: str) -> str | None:
    """Return a heading line's text without hash marks or a leading section number."""
    match = _HEADING_RE.match(line)
    if match is None:
        return None
    return _SECTION_NUMBER_RE.sub("", match.group(1).strip(), count=1)


def _requirement_count(lines: list[str], ident: str) -> int:
    """Return how many table rows have `ident` as their first cell."""
    count = 0
    for line in lines:
        if line.startswith("|") and split_cells(line)[0] == ident:
            count += 1
    return count


def _section_span(lines: list[str], heading: str) -> str | tuple[int, int]:
    """Return the span after `heading`, or the problem when it is not found once."""
    found = [
        index for index, line in enumerate(lines) if _heading_text(line) == heading
    ]
    if len(found) != 1:
        return f'heading "{heading}" found {len(found)} times'
    start = found[0]
    end = next(
        (
            index
            for index, line in enumerate(lines)
            if index > start and _heading_text(line) is not None
        ),
        len(lines),
    )
    return start, end


def _anchor_problem(lines: list[str], anchor: _Anchor) -> str | None:
    """Return why `anchor` is missing from `lines`, or None when it is present."""
    if anchor.kind == "id":
        count = _requirement_count(lines, anchor.ident)
        if count != 1:
            return f'requirement "{anchor.ident}" found {count} times'
        return None
    if anchor.kind == "task":
        prefix = f"### {anchor.ident} {_TASK_MARK} "
        if any(line.startswith(prefix) for line in lines):
            return None
        return f'task "{anchor.ident}" has no heading'
    span = _section_span(lines, anchor.ident)
    if isinstance(span, str):
        return span
    if anchor.kind == "section":
        return None
    start, end = span
    body = lines[start + 1 : end]
    if anchor.kind == "row":
        found = any(
            line.startswith("|") and split_cells(line)[0] == anchor.label
            for line in body
        )
        if not found:
            return f'row "{anchor.label}" is not in that section'
        return None
    prefix = f"{anchor.label}. "
    if any(line.startswith(prefix) for line in body):
        return None
    return f"item {anchor.label} is not in that section"


def check_cite(root: Path, value: str) -> list[str]:
    """Return the problems of a pack citation, items split at `; `.

    An item is an anchor. The check proves that the anchor exists, not what its text says.
    """
    problems = []
    for item in value.split("; "):
        anchor = _parse_anchor(item)
        if anchor is None:
            problems.append(f'cite item "{item}" is not an anchor')
            continue
        text, _problem = read_regular(root, anchor.path)
        if text is None:
            problems.append(f"{anchor.path} is not a file")
            continue
        problem = _anchor_problem(text.splitlines(), anchor)
        if problem is not None:
            problems.append(problem)
    return problems


def mask_verified_anchors(root: Path, text: str) -> str:
    """Blank each verified anchor in `text`.

    A row label is part of the anchor. The check does not judge what that text says,
    so a claim word that occurs only inside a verified anchor is not a claim.
    Words outside a verified anchor are left as they are.
    """
    found: list[re.Match[str]] = []
    for pattern in _ANCHOR_FORMS:
        source = pattern.pattern.removeprefix("^").removesuffix("$")
        found.extend(re.finditer(source, text))
    found.sort(key=lambda match: (match.start(), match.start() - match.end()))
    taken: list[tuple[int, int]] = []
    chars = list(text)
    for match in found:
        start, end = match.span()
        if any(start < stop and end > begin for begin, stop in taken):
            continue
        if check_cite(root, match.group(0)):
            continue
        taken.append((start, end))
        for index in range(start, end):
            chars[index] = " "
    return "".join(chars)


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
