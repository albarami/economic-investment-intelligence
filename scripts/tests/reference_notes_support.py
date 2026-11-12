"""Fixture trees and helpers for the reference-notes check tests."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_reference_notes as notes
import reference_notes_tables as tables

_SCRIPTS = Path(__file__).resolve().parent.parent
REPO = _SCRIPTS.parent
WEB = tables.WEB
DOCS = tables.DOCS
LINKS = tables.LINKS
PINS = tables.PINS
ASSIGNED = tables.ASSIGNED
SENTENCE = tables.ASSIGNED_SENTENCE
CONFIRMED = tables.CONFIRMED
UNVERIFIED = tables.UNVERIFIED
NOT_COVERED = tables.NOT_COVERED
CLAIM_WORDS = tables.CLAIM_WORDS
HOW = tables.HOW
COVERAGE = tables.COVERAGE


def run(root: Path) -> list[str]:
    """Run the check in-process and return its output lines."""
    return notes.run_checks(root)


def fails(lines: Sequence[str]) -> list[str]:
    """Return every output line except the summary."""
    return list(lines[:-1]) if lines else []


def summary(lines: Sequence[str]) -> str:
    """Return the last output line (the summary)."""
    return lines[-1] if lines else ""


def fail_line(rel: str, rule: str, line: int | None, detail: str) -> str:
    """Format one failure line the check prints."""
    if rule == "input":
        return f"FAIL {rule}: {rel}: {detail}"
    assert line is not None
    return f"FAIL {rule}: {rel}:{line}: {detail}"


def cli(
    args: Sequence[str], cwd: Path, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run check_reference_notes.py as a child with an explicit environment."""
    script = _SCRIPTS / "check_reference_notes.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=dict(env),
        cwd=cwd,
        timeout=60,
        check=False,
    )


def read(root: Path, rel: str) -> str:
    """Read a UTF-8 text file under the fixture root."""
    return (root / rel).read_text(encoding="utf-8")


def write(root: Path, rel: str, data: str | bytes) -> None:
    """Write a file under the fixture root, creating parent folders."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def edit(root: Path, rel: str, old: str, new: str) -> None:
    """Replace exactly one occurrence in a file."""
    text = read(root, rel)
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"edit {rel}: expected one occurrence, found {count}")
    write(root, rel, text.replace(old, new, 1))


def section_span(text: str, heading: str) -> tuple[int, int]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line == f"## {heading}":
            start = index
        elif start is not None and line.startswith("## "):
            return start, index
    if start is None:
        raise AssertionError(f"section {heading!r} not found")
    return start, len(lines)


def edit_in(root: Path, rel: str, library: str, old: str, new: str) -> None:
    """Replace exactly one occurrence inside a library or assigned section."""
    text = read(root, rel)
    start, stop = section_span(text, library)
    block = "\n".join(text.splitlines()[start:stop])
    count = block.count(old)
    if count != 1:
        raise AssertionError(
            f"edit_in {rel} {library}: expected one occurrence, found {count}"
        )
    new_block = block.replace(old, new, 1)
    lines = text.splitlines()
    lines[start:stop] = new_block.splitlines()
    write(root, rel, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def heading_line(root: Path, rel: str, section: str) -> int:
    """Return the 1-based line number of ``## {section}``."""
    target = f"## {section}"
    for index, line in enumerate(read(root, rel).splitlines(), 1):
        if line == target:
            return index
    raise AssertionError(f"heading {section!r} not found in {rel}")


def line_of(root: Path, rel: str, needle: str, index: int = 0) -> int:
    """Return the 1-based line number of a line containing ``needle`` (0-based match index)."""
    lines = read(root, rel).splitlines()
    hits = [line_no for line_no, line in enumerate(lines, 1) if needle in line]
    if len(hits) <= index:
        raise AssertionError(
            f"line_of {rel} {needle!r}: expected at least {index + 1} lines, found {len(hits)}"
        )
    return hits[index]


def line_matching(root: Path, rel: str, predicate: Callable[[str], bool]) -> int:
    """Return the 1-based line number of the sole line matching ``predicate``."""
    hits = [
        line_no
        for line_no, line in enumerate(read(root, rel).splitlines(), 1)
        if predicate(line)
    ]
    if len(hits) != 1:
        raise AssertionError(
            f"line_matching {rel}: expected one line, found {len(hits)}"
        )
    return hits[0]


def assigned_section() -> str:
    """Return the assigned-section block for the web fixture (without the heading)."""
    return _ASSIGNED_BODY


def _pin_names() -> list[str]:
    names: set[str] = set()
    for libs in tables.LIBRARIES.values():
        for lib in libs:
            names.update(lib.rows)
    names.add("other")
    return sorted(names)


def _pins_toml() -> str:
    rows = [
        (
            '  { name = "'
            + name
            + '", kind = "external", pin = "1", retreat = "none recorded", '
            'state = "recorded", first_use = "slice S1" },'
        )
        for name in _pin_names()
    ]
    return "schema = 1\n\ncomponent = [\n" + "\n".join(rows) + "\n]\n"


def _library_block(lib: tables.Library, pack_line: str) -> str:
    rows_joined = ", ".join(lib.rows)
    confirm_rows: list[str] = []
    for index, field in enumerate(lib.fields):
        pins_cell = rows_joined if index == 0 else "-"
        confirm_rows.append(f"| {field} | {CONFIRMED} | {pins_cell} | {pack_line} |")
    return f"""## {lib.name}

Used here: a fixture.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |

### Runs

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | old form | new form | READ | P1 | "three quoted words" |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | A read statement. | READ | P1 | "three quoted words" |
| S2 | An observed statement. | OBSERVED | R1 | - |
| S3 | A pack statement: {UNVERIFIED}. | PACK | {pack_line} | - |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
{chr(10).join(confirm_rows)}
"""


_ASSIGNED_BODY = f"""
{SENTENCE}

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |

### Runs

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |

### Font weights

| Id | Family | Subset | Weight | Files found in the package | Kind | Package and version | Date | Source |
|---|---|---|---|---|---|---|---|---|
| F1 | IBM Plex Sans | latin | 400 | ibm-plex-sans-latin-400-normal.woff2, ibm-plex-sans-latin-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F2 | IBM Plex Sans | latin | 500 | ibm-plex-sans-latin-500-normal.woff2, ibm-plex-sans-latin-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F3 | IBM Plex Sans | latin | 600 | ibm-plex-sans-latin-600-normal.woff2, ibm-plex-sans-latin-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F4 | IBM Plex Sans Arabic | arabic | 400 | ibm-plex-sans-arabic-arabic-400-normal.woff2, ibm-plex-sans-arabic-arabic-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R1 |
| F5 | IBM Plex Sans Arabic | arabic | 500 | ibm-plex-sans-arabic-arabic-500-normal.woff2, ibm-plex-sans-arabic-arabic-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R1 |
| F6 | IBM Plex Sans Arabic | arabic | 600 | ibm-plex-sans-arabic-arabic-600-normal.woff2, ibm-plex-sans-arabic-arabic-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R1 |

### Icon package licence

| Id | Package and version | Licence identifier | Licence file | Kind | Source | Quote | Date |
|---|---|---|---|---|---|---|---|
| C1 | icons 1.0.0 | Apache-2.0 | LICENSE in the package | OBSERVED | R1 | - | 2026-11-12 |
| C2 | icons | Apache 2.0 License | LICENSE in the repository root | READ | P1 | "three quoted words" | 2026-11-12 |
""".strip()


def _coverage_block(rel: str) -> str:
    libs = tables.LIBRARIES[rel]
    first, second = libs[0].name, libs[1].name
    return f"""## {COVERAGE}

| Pack claim | Pack source | Where |
|---|---|---|
| A claim | docs/stub.md line 5 | {first} S1; {second} I1 |
| Another claim | AGENTS.md line 2 | {NOT_COVERED}no row for it |
"""


def fixture_notes(rel: str) -> str:
    """Return the full notes file content for a clean fixture tree."""
    title = (
        "# Reference notes (web fixture)\n"
        if rel == WEB
        else "# Reference notes (docs fixture)\n"
    )
    header = f"""{title}
| | |
|---|---|
| Date | 2026-11-12 |

[other notes]({LINKS[rel]})

## {HOW}

Fixture.
"""
    pack_line = "docs/stub.md line 5"
    body = "".join(
        _library_block(lib, pack_line) + "\n\n" for lib in tables.LIBRARIES[rel]
    )
    if rel == WEB:
        body += f"## {ASSIGNED}\n\n" + _ASSIGNED_BODY + "\n\n"
    body += _coverage_block(rel)
    return header + "\n" + body


def make_root(tmp: Path) -> Path:
    """Write a clean fixture tree under tmp and return tmp."""
    root = tmp
    write(
        root,
        "docs/stub.md",
        "\n".join(f"line {index}" for index in range(1, 31)) + "\n",
    )
    write(root, "AGENTS.md", "line one\nline two\nline three\n")
    write(root, PINS, _pins_toml())
    write(root, WEB, fixture_notes(WEB))
    write(root, DOCS, fixture_notes(DOCS))
    return root


def tree_digest(root: Path) -> dict[str, str]:
    """SHA-256 of every file in a fixture tree."""
    digest: dict[str, str] = {}
    for folder, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(folder) / name
            rel = path.relative_to(root).as_posix()
            digest[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def file_digest(path: Path) -> str:
    """SHA-256 of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_root() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    """Return a temporary directory and a clean fixture root inside it."""
    folder = tempfile.TemporaryDirectory()
    return folder, make_root(Path(folder.name))


def drop_assigned(root: Path) -> None:
    """Remove the whole Confirmations assigned section from the web notes file."""
    text = read(root, WEB)
    start, stop = section_span(text, ASSIGNED)
    lines = text.splitlines()
    write(root, WEB, "\n".join(lines[:start] + lines[stop:]) + "\n")


def remove_in_assigned(root: Path, *rows: str) -> None:
    """Delete one full table row line from the assigned section (each row once)."""
    text = read(root, WEB)
    start, stop = section_span(text, ASSIGNED)
    block = "\n".join(text.splitlines()[start:stop])
    for row in rows:
        needle = row if row.endswith("\n") else row + "\n"
        count = block.count(needle)
        if count != 1:
            raise AssertionError(
                f"remove_in_assigned: expected one occurrence of row, found {count}"
            )
        block = block.replace(needle, "", 1)
    lines = text.splitlines()
    lines[start:stop] = block.splitlines()
    write(root, WEB, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))


def assigned_font_table_line(root: Path) -> int:
    """Return the 1-based line of the font-weights table header in the web file."""
    return line_of(
        root,
        WEB,
        "| Id | Family | Subset | Weight | Files found in the package | Kind |",
    )


def assigned_icon_table_line(root: Path) -> int:
    """Return the 1-based line of the icon-licence table header in the web file."""
    return line_of(
        root,
        WEB,
        "| Id | Package and version | Licence identifier | Licence file | Kind |",
    )


def assigned_pages_p1_line(root: Path) -> int:
    """Return the 1-based line of the assigned section's P1 pages row."""
    needle = "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl |"
    return line_of(root, WEB, needle, index=3)


WEB_LIB = tables.LIBRARIES[WEB][0].name
DOCS_LIB = tables.LIBRARIES[DOCS][0].name
WEB_SECOND = tables.LIBRARIES[WEB][1].name
