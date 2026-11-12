"""Rules for the section of the confirmations assigned to this task: font weights, icon licence."""

from __future__ import annotations

from reference_notes_parse import (
    VERSION_RE,
    Ids,
    Table,
    date_problem,
    quote_problem,
    source_problem,
)
from reference_notes_report import (
    Report,
    check_prose,
    check_shape,
    check_sources,
    read_subsections,
)
from reference_notes_tables import (
    ASSIGNED_OPENING,
    ASSIGNED_SENTENCE,
    ASSIGNED_SUBS,
    FAMILIES,
    WEIGHTS,
)

NO_LICENCE = ("", "-")


def check_fonts(
    report: Report, table: Table, ids: Ids, ceiling: str | None
) -> list[str]:
    """Judge the font table; return the run ids its rows cite.

    Every row is OBSERVED, of a closed family and weight, with a run, a date, the woff2 and
    woff files of its subset and weight, and its family's package. Every family and weight
    needs at least one row.
    """
    cited: list[str] = []
    found: set[tuple[str, str]] = set()
    for n, row in table.rows:
        ident, family, subset, weight, files, kind, package, date, source = row
        package_name, _, version = package.rpartition(" ")
        if family not in FAMILIES:
            report.fail(
                "weights", n, f'{ident}: family "{family}" is not a known family'
            )
        elif (
            package_name != FAMILIES[family][0] or VERSION_RE.fullmatch(version) is None
        ):
            report.fail(
                "weights",
                n,
                f'{ident}: package "{package}" is not "{FAMILIES[family][0]} <version>"',
            )
        if weight not in WEIGHTS:
            report.fail(
                "weights",
                n,
                f'{ident}: weight "{weight}" is not one of {", ".join(WEIGHTS)}',
            )
        elif family in FAMILIES:
            names = [
                f"{FAMILIES[family][1]}{subset}-{weight}-normal.{e}"
                for e in ("woff2", "woff")
            ]
            if files not in (names[0], names[1], ", ".join(names)):
                report.fail(
                    "weights",
                    n,
                    f'{ident}: files "{files}" are not the woff2 or woff file of the subset and weight',
                )
        if kind != "OBSERVED":
            report.fail("kind", n, f'"{kind}" is not OBSERVED')
            continue
        cited.append(source)
        if (problem := source_problem(kind, ident, source, ids)) is not None:
            report.fail("source", n, problem)
        if (problem := date_problem(date, ceiling)) is not None:
            report.fail("date", n, problem)
        found.add((family, weight))
    for family in FAMILIES:
        for weight in WEIGHTS:
            if (family, weight) not in found:
                report.fail(
                    "weights", table.line, f"{family} {weight}: no OBSERVED row"
                )
    return cited


def check_icons(
    report: Report, table: Table, ids: Ids, ceiling: str | None
) -> tuple[list[str], set[str]]:
    """Judge the icon table; return the run ids and page ids its rows cite.

    Every row names a licence identifier and is READ or OBSERVED; at least one row is OBSERVED.
    """
    runs: list[str] = []
    pages: set[str] = set()
    observed = False
    for n, row in table.rows:
        ident, _, licence, _, kind, source, quote, date = row
        if licence in NO_LICENCE:
            report.fail("icon-licence", n, f"{ident}: licence identifier is empty")
        if kind not in ("READ", "OBSERVED"):
            report.fail("kind", n, f'"{kind}" is not READ or OBSERVED')
            continue
        observed = observed or (kind == "OBSERVED" and licence not in NO_LICENCE)
        if kind == "READ":
            pages.add(source)
        else:
            runs.append(source)
        if (problem := source_problem(kind, ident, source, ids)) is not None:
            report.fail("source", n, problem)
        if (problem := quote_problem(kind, ident, quote)) is not None:
            report.fail("quote", n, problem)
        if (problem := date_problem(date, ceiling)) is not None:
            report.fail("date", n, problem)
    if not observed:
        report.fail(
            "icon-licence", table.line, "no OBSERVED row with a licence identifier"
        )
    return runs, pages


def check_assigned(
    report: Report, lines: list[str], span: tuple[int, int], ceiling: str | None
) -> None:
    """Judge the section lines[span[0]:span[1]] of the confirmations assigned to this task."""
    start, stop = span
    check_prose(report, lines, span, False, ASSIGNED_OPENING)
    subs, tables = read_subsections(report, lines, span, ASSIGNED_SUBS)
    first = subs[0][0] if subs else stop
    paragraphs = [
        i for i in range(start + 1, first) if lines[i].strip() and lines[i][0] != "|"
    ]
    if not paragraphs:
        report.fail("assigned", start + 1, "the opening sentence is missing")
    for i in paragraphs:
        if lines[i] != ASSIGNED_SENTENCE:
            report.fail(
                "assigned",
                i + 1,
                "the opening line is not the sentence of the assignment",
            )
    present = {name for _, name in subs}
    for name in ASSIGNED_SUBS:
        if name not in present:
            report.fail("subsection", start + 1, f'missing subsection "{name}"')
    ids = check_shape(report, tables)
    check_sources(report, tables, ceiling)
    runs: list[str] = []
    pages: set[str] = set()
    if "Font weights" in tables:
        runs += check_fonts(report, tables["Font weights"], ids, ceiling)
    if "Icon package licence" in tables:
        more, seen = check_icons(report, tables["Icon package licence"], ids, ceiling)
        runs += more
        pages |= seen
    if "Font weights" not in tables or "Icon package licence" not in tables:
        return
    for name, word, cited in (
        ("Runs", "run", set(runs)),
        ("Pages read", "page", pages),
    ):
        for n, row in tables[name].rows if name in ids else []:
            if row[0] not in cited:
                report.fail("unused", n, f"{word} {row[0]} is cited by no row")
