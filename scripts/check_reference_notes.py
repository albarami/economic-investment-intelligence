"""Check the form of the reference notes (FE-02, TST-01).

Reads `web/REFERENCE_NOTES.md`, `docs/REFERENCE_NOTES.md` and `pins.toml`, and the pack
files that hold the anchors the notes cite. It checks that each anchor exists in its file
and not what the anchored text says. It writes nothing and uses no network. It does not
decide whether a quotation is still on its page: that is the work of the second reader.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from pack_anchors import check_cite, mask_verified_anchors, read_regular
from reference_notes_assigned import check_assigned
from reference_notes_parse import (
    URL_RE,
    Ids,
    Table,
    check_address,
    file_date,
    load_pins,
    quote_problem,
    source_problem,
    table_after,
)
from reference_notes_report import (
    Report,
    check_prose,
    check_shape,
    check_sources,
    read_subsections,
)
from reference_notes_tables import (
    ASSIGNED,
    CLAIM_WORDS,
    CONFIRMED,
    COVERAGE,
    DOCS,
    EXTRA_SECTIONS,
    FENCES,
    HOW,
    KINDS,
    LIBRARIES,
    LINKS,
    NOT_COVERED,
    PINS,
    TABLES,
    UNVERIFIED,
    WEB,
    Library,
)

LINK_RE = re.compile(r"\]\(([^)\s#]+)(?:#[^)\s]*)?\)")
CLAIM_RE = re.compile(r"\b(" + "|".join(CLAIM_WORDS) + r")\b", re.IGNORECASE)
PAGE_RE = re.compile(r"\bP[1-9][0-9]*\b")
ROW_ID_RE = re.compile(r"[IS][1-9][0-9]*")


def check_claims(
    report: Report,
    root: Path,
    name: str,
    rows: list[tuple[int, list[str]]],
    ids: Ids,
) -> tuple[list[str], set[str]]:
    """Judge Idioms and Statements rows; return the run ids and page ids that rows cite."""
    runs: list[str] = []
    pages: set[str] = set()
    idiom = name == "Idioms that changed"
    for n, row in rows:
        ident = row[0]
        kind, source, quote = (
            (row[3], row[4], row[5]) if idiom else (row[2], row[3], row[4])
        )
        claim = row[2] if idiom else row[1]
        text = " ".join(row[1:3] if idiom else row[1:2])
        if kind not in KINDS:
            report.fail("kind", n, f'"{kind}" is not READ, OBSERVED or PACK')
            continue
        if kind == "READ":
            pages.add(source)
        if kind == "OBSERVED":
            runs.append(source)
        if kind == "PACK":
            pages.update(PAGE_RE.findall(text))
            for problem in check_cite(root, source):
                report.fail("pack-cite", n, f"{ident}: {problem}")
        if (wrong := source_problem(kind, ident, source, ids)) is not None:
            report.fail("source", n, wrong)
        if (wrong := quote_problem(kind, ident, quote)) is not None:
            report.fail("quote", n, wrong)
        if kind == "PACK" and UNVERIFIED not in claim:
            report.fail("unverified", n, f'{ident}: PACK row lacks "{UNVERIFIED}"')
        if kind != "PACK" and UNVERIFIED in claim:
            report.fail("unverified", n, f'{ident}: {kind} row says "{UNVERIFIED}"')
        hit = CLAIM_RE.search(mask_verified_anchors(root, text))
        if hit:
            report.fail("claim-word", n, f'{ident}: word "{hit.group(1).lower()}"')
    return runs, pages


def check_confirmation(
    report: Report, root: Path, lib: Library, table: Table, pins: set[str] | None
) -> None:
    """Judge the S1 confirmation table: closed fields, literal value, pins rows, pack cites."""
    seen: set[str] = set()
    cited: set[str] = set()
    for n, (name, value, rows, source) in table.rows:
        if name not in lib.fields:
            report.fail("confirmation", n, f'unknown field "{name}"')
        elif name in seen:
            report.fail("confirmation", n, f'repeated field "{name}"')
        seen.add(name)
        if value != CONFIRMED:
            report.fail(
                "confirmation",
                n,
                f'field "{name}": value "{value}" is not "{CONFIRMED}"',
            )
        for problem in check_cite(root, source):
            report.fail("pack-cite", n, f"{name}: {problem}")
        for row in [] if rows == "-" else rows.split(", "):
            cited.add(row)
            if pins is not None and row not in pins:
                report.fail(
                    "pins-row",
                    n,
                    f'field "{name}": "{row}" is not a component of {PINS}',
                )
    for name in lib.fields:
        if name not in seen:
            report.fail("confirmation", table.line, f'missing field "{name}"')
    for row in lib.rows if pins is not None else ():
        if row not in cited:
            report.fail("pins-row", table.line, f'section cites no row "{row}"')


def check_section(
    report: Report,
    root: Path,
    lines: list[str],
    lib: Library,
    span: tuple[int, int],
    context: tuple[set[str] | None, str | None],
) -> set[str] | None:
    """Judge one library section lines[span[0]:span[1]]; return its row ids (None: unknown)."""
    pins, ceiling = context
    start = span[0]
    check_prose(report, lines, span, False)
    subs, tables = read_subsections(report, lines, span, TABLES)
    present = {name for _, name in subs}
    for name in TABLES:
        if name != "Runs" and name not in present:
            report.fail("subsection", start + 1, f'missing subsection "{name}"')
    ids = check_shape(report, tables)
    check_sources(report, tables, ceiling)
    observed: list[str] = []
    cited: set[str] = set()
    for name in ("Idioms that changed", "Statements"):
        if name in tables:
            more, pages = check_claims(report, root, name, tables[name].rows, ids)
            observed += more
            cited |= pages
    if "Idioms that changed" in tables and "Statements" in tables:
        if observed and "Runs" not in present:
            report.fail(
                "subsection",
                start + 1,
                'section has OBSERVED rows but no "Runs" subsection',
            )
        if "Runs" in present and not observed:
            report.fail(
                "subsection",
                next(i + 1 for i, name in subs if name == "Runs"),
                'section has a "Runs" subsection but no OBSERVED row',
            )
        for n, row in tables["Runs"].rows if "Runs" in ids else []:
            if row[0] not in observed:
                report.fail("unused", n, f"run {row[0]} is cited by no row")
        for n, row in tables["Pages read"].rows if "Pages read" in ids else []:
            if row[0] not in cited:
                report.fail("unused", n, f"page {row[0]} is cited by no row")
    if "Slice S1 confirmation" in tables:
        check_confirmation(report, root, lib, tables["Slice S1 confirmation"], pins)
    if "Idioms that changed" in ids and "Statements" in ids:
        return ids["Idioms that changed"] | ids["Statements"]
    return None


def where_problem(where: str, known: dict[str, set[str] | None]) -> str | None:
    """Return why a Where cell is neither `not covered: <reason>` nor row ids, or None."""
    if where.startswith(NOT_COVERED):
        enough = len(where[len(NOT_COVERED) :].split()) >= 3
        return (
            None if enough else f'reason of "{NOT_COVERED.strip()}" has under 3 words'
        )
    for item in where.split("; "):
        name, _, ident = item.rpartition(" ")
        rows = known.get(name)
        if ROW_ID_RE.fullmatch(ident) is None or name not in known:
            return f'"{item}" is not a row of this file'
        if rows is not None and ident not in rows:
            return f'"{item}" is not a row of this file'
    return None


def check_coverage(
    report: Report,
    root: Path,
    lines: list[str],
    span: tuple[int, int],
    known: dict[str, set[str] | None],
) -> None:
    """Judge the coverage section: one table of pack claim, pack anchor and where it stands."""
    check_prose(report, lines, span, True)
    first = table_after(lines, span[0] + 1, span[1])
    if first is None:
        report.fail("coverage", span[0] + 1, "section has no table")
        return
    tables = {COVERAGE: first}
    check_shape(report, tables)
    for k, (n, row) in enumerate(
        tables[COVERAGE].rows if COVERAGE in tables else [], 1
    ):
        if not row[0]:
            report.fail("coverage", n, f"row {k}: claim is empty")
        for problem in check_cite(root, row[1]):
            report.fail("pack-cite", n, f"row {k}: {problem}")
        if (wrong := where_problem(row[2], known)) is not None:
            report.fail("coverage", n, f"row {k}: {wrong}")


def check_file(root: Path, rel: str, pins: set[str] | None) -> Report:
    """Judge one notes file."""
    report = Report(rel)
    text, problem = read_regular(root, rel)
    if text is None:
        report.found.append((0, 0, f"FAIL input: {rel}: {problem}"))
        return report
    lines = text.splitlines()
    ceiling = file_date(text)
    if ceiling is None:
        report.fail("date", 1, 'no valid "| Date |" row in the header table')
    if LINKS[rel] not in LINK_RE.findall(text):
        report.fail("cross-link", 1, f"no link to {LINKS[rel]}")
    for n, line in enumerate(lines, 1):
        if line.lstrip().startswith(FENCES):
            report.fail("fence", n, "code fence")
        if "<!--" in line:
            report.fail("fence", n, "HTML comment")
        for found in URL_RE.findall(line):
            url = found.rstrip(".,;:")
            if (reason := check_address(url)) is not None:
                report.fail("address", n, f"{url}: {reason}")
    heads = [(i, ln[3:].strip()) for i, ln in enumerate(lines) if ln.startswith("## ")]
    libs = LIBRARIES[rel]
    extra = EXTRA_SECTIONS[rel]
    required = (HOW, *(lib.name for lib in libs), *extra, COVERAGE)
    sound = True
    for name in required:
        count = sum(1 for _, head in heads if head == name)
        if count != 1:
            report.fail(
                "section", 1, f'section "{name}" found {count} times, expected once'
            )
            sound = False
    for i, head in heads:
        if head not in required:
            report.fail("section", i + 1, f'unknown section "{head}"')
            sound = False
    if not sound:
        return report
    spans = {
        name: (i, next((j for j, _ in heads if j > i), len(lines))) for i, name in heads
    }
    known: dict[str, set[str] | None] = {}
    for lib in libs:
        known[lib.name] = check_section(
            report, root, lines, lib, spans[lib.name], (pins, ceiling)
        )
    if ASSIGNED in extra:
        check_assigned(report, lines, spans[ASSIGNED], ceiling)
    check_coverage(report, root, lines, spans[COVERAGE], known)
    return report


def run_checks(root: Path) -> list[str]:
    """Return the output lines for the tree at `root`: failures, then the summary line."""
    pins, problem = load_pins(root)
    out = [] if pins is not None else [f"FAIL input: {PINS}: {problem}"]
    rows = 0
    for rel in (WEB, DOCS):
        report = check_file(root, rel, pins)
        rows += report.rows
        out += report.lines()
    libraries = sum(len(v) for v in LIBRARIES.values())
    result = "OK" if not out else f"{len(out)} failure(s)"
    return [*out, f"checked 2 files, {libraries} libraries, {rows} rows: {result}"]


def main(argv: list[str]) -> int:
    """Run the check; exit status 0 (no failure), 1 (failures) or 2 (usage)."""
    root = Path(__file__).resolve().parents[1]
    if argv:
        if len(argv) != 2 or argv[0] != "--root":
            print("usage: check_reference_notes.py [--root DIR]", file=sys.stderr)
            return 2
        root = Path(argv[1])
    lines = run_checks(root)
    print("\n".join(lines))
    return 0 if lines[-1].endswith(": OK") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
