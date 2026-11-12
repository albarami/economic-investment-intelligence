"""Shared parts of the reference-notes check: the failure report, table shape, prose, subsections."""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field

from reference_notes_parse import (
    URL_RE,
    Ids,
    Table,
    date_problem,
    table_after,
)
from reference_notes_tables import (
    ALL_TABLES,
    OPENING,
    PREFIX,
    RULES,
    SETUP,
)

PROSE = "line is not a heading, a table row or the one opening or setup paragraph"


@dataclass
class Report:
    """The failures of one file: (line, rule index, text), sorted when read."""

    rel: str
    found: list[tuple[int, int, str]] = field(default_factory=list)
    rows: int = 0

    def fail(self, rule: str, line: int, detail: str) -> None:
        """Record one failure line `FAIL <rule>: <file>:<line>: <detail>`."""
        text = f"FAIL {rule}: {self.rel}:{line}: {detail}"
        self.found.append((line, RULES.index(rule), text))

    def lines(self) -> list[str]:
        """Return the failure lines ordered by line, then rule order, then text."""
        return [text for _, _, text in sorted(self.found)]


def check_shape(report: Report, tables: dict[str, Table]) -> Ids:
    """Judge header, separator, cell counts and ids of every table; return the clean ids."""
    ids: Ids = {}
    for name in list(tables):
        table, want = tables[name], ALL_TABLES[name]
        if table.header != list(want):
            report.fail(
                "table", table.line, 'header is not "| ' + " | ".join(want) + ' |"'
            )
            del tables[name]
            continue
        if not table.separator:
            report.fail("table", table.line + 1, "separator row missing")
        if not table.rows:
            report.fail("table", table.line, f'"{name}" has no row')
        good = []
        for n, row in table.rows:
            report.rows += 1
            if len(row) == len(want):
                good.append((n, row))
            else:
                report.fail(
                    "table", n, f"row has {len(row)} cells, expected {len(want)}"
                )
        tables[name] = table._replace(rows=good)
        if name not in PREFIX:
            continue
        seen: dict[str, int] = {}
        clean = True
        for n, row in table.rows:
            if len(row) != len(want):
                seen.setdefault(row[0], n)
            elif re.fullmatch(PREFIX[name] + "[1-9][0-9]*", row[0]) is None:
                report.fail("id", n, f'"{row[0]}" is not {PREFIX[name]} and a number')
                clean = False
            elif row[0] in seen:
                report.fail(
                    "id", n, f'"{row[0]}" repeated (first at line {seen[row[0]]})'
                )
                clean = False
            else:
                seen[row[0]] = n
        if clean:
            ids[name] = set(seen)
    return ids


def check_prose(
    report: Report,
    lines: list[str],
    span: tuple[int, int],
    coverage: bool,
    opening: tuple[str, ...] = OPENING,
) -> None:
    """Fail every line of a section that is not a heading, a table row or an allowed paragraph.

    Allowed: `### ` headings (judged by the subsection rule), one table per subsection (none
    before the first heading; the coverage section is one table), one opening line that starts
    with `Used here` or `The module`, and one setup line in `### Runs` that starts with
    `Setup` or `Same setup`. A coverage section has no paragraph.
    """
    sub, paragraph, blocks, in_table = "", False, 0, False
    for i in range(span[0] + 1, span[1]):
        line = lines[i]
        if line.startswith("### ") and not coverage:
            sub, paragraph, blocks, in_table = line[4:].strip(), False, 0, False
        elif line.startswith("|"):
            if not in_table:
                blocks += 1
                if (not sub and not coverage) or blocks > 1:
                    report.fail("prose", i + 1, PROSE)
            in_table = True
        elif line.strip():
            in_table = False
            wanted = () if coverage else SETUP if sub == "Runs" else opening
            if paragraph or not wanted or not line.startswith(wanted):
                report.fail("prose", i + 1, PROSE)
            paragraph = True
        else:
            in_table = False


def read_subsections(
    report: Report, lines: list[str], span: tuple[int, int], allowed: Collection[str]
) -> tuple[list[tuple[int, str]], dict[str, Table]]:
    """Find the `### ` subsections of lines[span[0]:span[1]].

    Returns the (line index, name) of every subsection and the table of each allowed
    subsection that has one; reports an unknown or repeated subsection or a missing table.
    """
    start, stop = span
    subs = [
        (i, ln[4:].strip())
        for i, ln in enumerate(lines[start:stop], start)
        if ln.startswith("### ")
    ]
    tables: dict[str, Table] = {}
    for i, name in subs:
        end = next((j for j, _ in subs if j > i), stop)
        if name not in allowed:
            report.fail("subsection", i + 1, f'unknown subsection "{name}"')
        elif name in tables:
            report.fail("subsection", i + 1, f'repeated subsection "{name}"')
        elif (table := table_after(lines, i + 1, end)) is None:
            report.fail("subsection", i + 1, f'subsection "{name}" has no table')
        else:
            tables[name] = table
    return subs, tables


def check_sources(
    report: Report, tables: dict[str, Table], ceiling: str | None
) -> None:
    """Judge the addresses and dates of the Pages read table and the dates of the Runs table."""
    for n, row in tables["Pages read"].rows if "Pages read" in tables else []:
        if URL_RE.fullmatch(row[1]) is None:
            report.fail("address", n, f'"{row[1]}" is not an address')
        if (problem := date_problem(row[3], ceiling)) is not None:
            report.fail("date", n, problem)
    for n, row in tables["Runs"].rows if "Runs" in tables else []:
        if (problem := date_problem(row[2], ceiling)) is not None:
            report.fail("date", n, problem)
