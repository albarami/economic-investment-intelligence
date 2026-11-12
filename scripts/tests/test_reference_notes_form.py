"""Form tests for web/docs reference notes and pins.toml."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_notes_support as sup

import reference_notes_tables as tables

WEB = sup.WEB
DOCS = sup.DOCS
LINKS = sup.LINKS
FIRST_WEB = tables.LIBRARIES[WEB][0].name
FIRST_DOCS = tables.LIBRARIES[DOCS][0].name
SECOND_WEB = tables.LIBRARIES[WEB][1].name


def _unlink(root: Path, rel: str) -> None:
    (root / rel).unlink()


def _unlink_mkdir(root: Path, rel: str) -> None:
    path = root / rel
    path.unlink()
    path.mkdir()


def _docs_symlink(root: Path) -> None:
    (root / DOCS).unlink()
    os.symlink(root / "docs/stub.md", root / DOCS)


def _pins_unlink_mkdir(root: Path) -> None:
    _unlink_mkdir(root, tables.PINS)


def _root() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    folder = tempfile.TemporaryDirectory()
    root = sup.make_root(Path(folder.name))
    return folder, root


class NotesForm(unittest.TestCase):
    def test_clean_fixture_passes(self) -> None:
        folder, root = _root()
        self.addCleanup(folder.cleanup)
        lines = sup.run(root)
        self.assertEqual(lines, ["checked 2 files, 6 libraries, 81 rows: OK"])

    def test_inputs_missing_and_malformed(self) -> None:
        cases: list[tuple[str, Callable[[Path], None], list[str], str]] = [
            (
                "web-missing",
                lambda r: _unlink(r, WEB),
                [sup.fail_line(WEB, "input", None, "missing")],
                "checked 2 files, 6 libraries, 36 rows: 1 failure(s)",
            ),
            (
                "docs-missing",
                lambda r: _unlink(r, DOCS),
                [sup.fail_line(DOCS, "input", None, "missing")],
                "checked 2 files, 6 libraries, 45 rows: 1 failure(s)",
            ),
            (
                "web-dir",
                lambda r: _unlink_mkdir(r, WEB),
                [sup.fail_line(WEB, "input", None, "not a regular file")],
                "checked 2 files, 6 libraries, 36 rows: 1 failure(s)",
            ),
            (
                "docs-symlink",
                _docs_symlink,
                [sup.fail_line(DOCS, "input", None, "not a regular file")],
                "checked 2 files, 6 libraries, 45 rows: 1 failure(s)",
            ),
            (
                "web-utf8",
                lambda r: sup.write(r, WEB, b"\xff\xfe"),
                [sup.fail_line(WEB, "input", None, "not UTF-8")],
                "checked 2 files, 6 libraries, 36 rows: 1 failure(s)",
            ),
            (
                "docs-empty",
                lambda r: sup.write(r, DOCS, "   \n"),
                [sup.fail_line(DOCS, "input", None, "empty")],
                "checked 2 files, 6 libraries, 45 rows: 1 failure(s)",
            ),
            (
                "pins-missing",
                lambda r: _unlink(r, tables.PINS),
                [sup.fail_line(tables.PINS, "input", None, "missing")],
                "checked 2 files, 6 libraries, 81 rows: 1 failure(s)",
            ),
            (
                "pins-decode",
                lambda r: sup.write(r, tables.PINS, "component = [\n"),
                [
                    sup.fail_line(
                        tables.PINS, "input", None, "cannot be parsed (TOMLDecodeError)"
                    )
                ],
                "checked 2 files, 6 libraries, 81 rows: 1 failure(s)",
            ),
            (
                "pins-no-rows",
                lambda r: sup.write(r, tables.PINS, "schema = 1\n"),
                [sup.fail_line(tables.PINS, "input", None, "no component rows")],
                "checked 2 files, 6 libraries, 81 rows: 1 failure(s)",
            ),
            (
                "pins-no-name",
                lambda r: sup.write(
                    r,
                    tables.PINS,
                    'schema = 1\n\ncomponent = [\n  { kind = "external" },\n]\n',
                ),
                [
                    sup.fail_line(
                        tables.PINS, "input", None, "a component row has no name"
                    )
                ],
                "checked 2 files, 6 libraries, 81 rows: 1 failure(s)",
            ),
            (
                "pins-dir",
                _pins_unlink_mkdir,
                [sup.fail_line(tables.PINS, "input", None, "not a regular file")],
                "checked 2 files, 6 libraries, 81 rows: 1 failure(s)",
            ),
        ]
        for name, plant, fails, summ in cases:
            with self.subTest(name=name):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                plant(root)
                lines = sup.run(root)
                self.assertEqual(sup.fails(lines), fails, lines)
                self.assertEqual(sup.summary(lines), summ)

    def test_cross_link(self) -> None:
        folder, _root_unused = _root()
        self.addCleanup(folder.cleanup)
        cases = [
            (
                "web-bad",
                lambda r: sup.edit(r, WEB, LINKS[WEB], "../docs/10_FRONTEND.md"),
                WEB,
                f"no link to {LINKS[WEB]}",
            ),
            (
                "docs-bad",
                lambda r: sup.edit(r, DOCS, LINKS[DOCS], "../web/10_FRONTEND.md"),
                DOCS,
                f"no link to {LINKS[DOCS]}",
            ),
            (
                "anchor-ok",
                lambda r: sup.edit(
                    r,
                    WEB,
                    f"]({LINKS[WEB]})",
                    f"]({LINKS[WEB]}#x)",
                ),
                None,
                None,
            ),
            (
                "self-link",
                lambda r: sup.edit(r, WEB, LINKS[WEB], "../web/REFERENCE_NOTES.md"),
                WEB,
                f"no link to {LINKS[WEB]}",
            ),
        ]
        for name, plant, rel, detail in cases:
            with self.subTest(name=name):
                sub = tempfile.TemporaryDirectory()
                self.addCleanup(sub.cleanup)
                subroot = sup.make_root(Path(sub.name))
                cast(Callable[[Path], None], plant)(subroot)
                lines = sup.run(subroot)
                if rel is None:
                    self.assertEqual(sup.fails(lines), [])
                else:
                    assert detail is not None
                    self.assertEqual(
                        sup.fails(lines),
                        [sup.fail_line(rel, "cross-link", 1, detail)],
                    )

    def test_sections(self) -> None:
        plants = [
            (
                "deck-rename",
                WEB,
                SECOND_WEB,
                f"## {SECOND_WEB}",
                "## deck.gl 9.5",
                SECOND_WEB,
                "deck.gl 9.5",
            ),
            (
                "pg-rename",
                DOCS,
                FIRST_DOCS,
                "## PostgreSQL 18",
                "## DuckDB 2.0",
                "PostgreSQL 18",
                None,
            ),
            (
                "claude-removed",
                DOCS,
                "Claude API",
                "## Claude API\n\n",
                "",
                "Claude API",
                None,
            ),
            ("how-removed", WEB, sup.HOW, f"## {sup.HOW}\n\n", "", sup.HOW, None),
            (
                "coverage-removed",
                WEB,
                sup.COVERAGE,
                f"## {sup.COVERAGE}\n\n",
                "",
                sup.COVERAGE,
                None,
            ),
            (
                "extra",
                WEB,
                FIRST_WEB,
                f"## {sup.COVERAGE}\n",
                f"## Extra claims\n\nline\n\n## {sup.COVERAGE}\n",
                "Extra claims",
                None,
            ),
        ]

        def drop_section(root: Path, rel: str, section: str) -> None:
            text = sup.read(root, rel)
            start, stop = sup.section_span(text, section)
            lines = text.splitlines()
            sup.write(root, rel, "\n".join(lines[:start] + lines[stop:]) + "\n")

        for name, rel, _ctx, old, new, unknown, miss in plants:
            with self.subTest(name=name):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                if name == "extra":
                    sup.edit(root, rel, old, new)
                    fails = [
                        sup.fail_line(
                            rel,
                            "section",
                            sup.heading_line(root, rel, "Extra claims"),
                            'unknown section "Extra claims"',
                        )
                    ]
                elif name == "pg-rename":
                    sup.edit(root, rel, old, new)
                    fails = [
                        sup.fail_line(
                            rel,
                            "section",
                            1,
                            'section "DuckDB 2.0" found 2 times, expected once',
                        ),
                        sup.fail_line(
                            rel,
                            "section",
                            1,
                            'section "PostgreSQL 18" found 0 times, expected once',
                        ),
                    ]
                elif name == "deck-rename":
                    sup.edit_in(root, rel, SECOND_WEB, old, new)
                    fails = [
                        sup.fail_line(
                            rel,
                            "section",
                            1,
                            f'section "{SECOND_WEB}" found 0 times, expected once',
                        ),
                        sup.fail_line(
                            rel,
                            "section",
                            sup.heading_line(root, rel, "deck.gl 9.5"),
                            'unknown section "deck.gl 9.5"',
                        ),
                    ]
                elif name in ("claude-removed", "how-removed", "coverage-removed"):
                    drop_section(root, rel, miss or unknown)
                    fails = [
                        sup.fail_line(
                            rel,
                            "section",
                            1,
                            f'section "{miss or unknown}" found 0 times, expected once',
                        ),
                    ]
                else:
                    sup.edit(root, rel, old, new)
                    fails = [
                        sup.fail_line(
                            rel,
                            "section",
                            1,
                            f'section "{miss}" found 0 times, expected once',
                        ),
                    ]
                lines = sup.run(root)
                self.assertEqual(sup.fails(lines), fails, lines)

    def test_subsections(self) -> None:
        lib = FIRST_WEB
        plants = [
            ("statements-rename", "### Statements", "### Notes", "Statements", "Notes"),
            (
                "extra-sub",
                "### Statements\n\n",
                "### Extra\n\n| x |\n|---|\n| y |\n\n### Statements\n\n",
                None,
                "Extra",
            ),
            (
                "repeat-statements",
                "### Statements\n\n",
                '### Statements\n\n| Id | Statement | Kind | Source | Quote |\n|---|---|---|---|---|\n| S9 | x | READ | P1 | "three quoted words" |\n\n### Statements\n\n',
                "Statements",
                None,
            ),
            ("pages-no-table", "### Pages read\n\n", "### Pages read\n\n", None, None),
            (
                "observed-to-read",
                "| S2 | An observed statement. | OBSERVED | R1 | - |",
                '| S2 | An observed statement. | READ | R1 | "three quoted words" |',
                None,
                None,
            ),
            ("runs-removed", "### Runs\n\n", "", None, None),
        ]
        for name, old, new, _missing, _unknown in plants:
            with self.subTest(name=name):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                if name == "pages-no-table":
                    sup.edit_in(
                        root,
                        WEB,
                        lib,
                        "### Pages read\n\n| Id | Address | Page title | Date read |\n|---|---|---|---|\n| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |\n\n",
                        "### Pages read\n\n",
                    )
                elif name == "repeat-statements":
                    extra = (
                        "\n### Statements\n\n| Id | Statement | Kind | Source | Quote |\n"
                        '|---|---|---|---|---|\n| S9 | extra | READ | P1 | "three quoted words" |\n'
                    )
                    sup.edit_in(
                        root,
                        WEB,
                        lib,
                        "\n### Slice S1 confirmation\n",
                        extra + "\n### Slice S1 confirmation\n",
                    )
                elif name == "runs-removed":
                    text = sup.read(root, WEB)
                    start, stop = sup.section_span(text, lib)
                    block = "\n".join(text.splitlines()[start:stop])
                    block = block.replace(
                        "### Runs\n\n| Id | Package and version | Date | Command | Output |\n|---|---|---|---|---|\n| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |\n\n",
                        "",
                    )
                    lines = text.splitlines()
                    lines[start:stop] = block.splitlines()
                    sup.write(root, WEB, "\n".join(lines) + "\n")
                elif name in ("statements-rename", "extra-sub"):
                    sup.edit_in(root, WEB, lib, old, new)
                elif name not in (
                    "pages-no-table",
                    "repeat-statements",
                    "runs-removed",
                ):
                    sup.edit_in(root, WEB, lib, old, new)
                lines = sup.run(root)
                fails = sup.fails(lines)
                if name == "statements-rename":
                    h = sup.heading_line(root, WEB, lib)
                    n = sup.line_of(root, WEB, "### Notes")
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB, "subsection", h, 'missing subsection "Statements"'
                            ),
                            sup.fail_line(
                                WEB, "subsection", n, 'unknown subsection "Notes"'
                            ),
                        ],
                    )
                elif name == "extra-sub":
                    n = sup.line_of(root, WEB, "### Extra")
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB, "subsection", n, 'unknown subsection "Extra"'
                            )
                        ],
                    )
                elif name == "repeat-statements":
                    n = sup.line_of(root, WEB, "### Statements", index=1)
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB, "subsection", n, 'repeated subsection "Statements"'
                            )
                        ],
                    )
                elif name == "pages-no-table":
                    n = sup.line_of(root, WEB, "### Pages read")
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB,
                                "subsection",
                                n,
                                'subsection "Pages read" has no table',
                            )
                        ],
                    )
                elif name == "observed-to-read":
                    n = sup.line_of(root, WEB, "### Runs")
                    m = sup.line_of(root, WEB, "| R1 | pkg 1.0.0 |")
                    s2 = sup.line_of(
                        root, WEB, "| S2 | An observed statement. | READ | R1 |"
                    )
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB,
                                "subsection",
                                n,
                                'section has a "Runs" subsection but no OBSERVED row',
                            ),
                            sup.fail_line(
                                WEB, "unused", m, "run R1 is cited by no row"
                            ),
                            sup.fail_line(
                                WEB,
                                "source",
                                s2,
                                'S2: READ source "R1" is not a page id of this section',
                            ),
                        ],
                    )
                elif name == "runs-removed":
                    h = sup.heading_line(root, WEB, lib)
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB,
                                "subsection",
                                h,
                                'section has OBSERVED rows but no "Runs" subsection',
                            ),
                        ],
                    )

    def test_table_shape(self) -> None:
        def identity(header: str) -> str:
            return header

        lib = FIRST_WEB
        table_heads: dict[str, Callable[[str], str]] = {
            "Pages read": identity,
            "Runs": identity,
            "Idioms that changed": identity,
            "Statements": identity,
            "Slice S1 confirmation": identity,
            sup.COVERAGE: identity,
        }
        for head, tweak in table_heads.items():
            with self.subTest(header=head):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                want = tables.ALL_TABLES[head]
                old = "| " + " | ".join(want) + " |"
                if head == "Slice S1 confirmation":
                    new = tweak(old.replace("| Field |", "| Field | Extra |", 1))
                elif head == sup.COVERAGE:
                    new = tweak(
                        old.replace("| Pack claim |", "| Pack claim | Extra |", 1)
                    )
                else:
                    new = tweak(old.replace("| Id |", "| Id | Extra |", 1))
                if head == sup.COVERAGE:
                    sup.edit_in(root, WEB, sup.COVERAGE, old, new)
                else:
                    sup.edit_in(root, WEB, lib, old, new)
                lines = sup.run(root)
                want_header = new.strip()

                def matches_header(line: str, want: str = want_header) -> bool:
                    return line.strip() == want

                t = sup.line_matching(root, WEB, matches_header)
                self.assertEqual(
                    sup.fails(lines),
                    [
                        sup.fail_line(
                            WEB,
                            "table",
                            t,
                            'header is not "| ' + " | ".join(want) + ' |"',
                        )
                    ],
                )
        with self.subTest(name="sep-missing"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit_in(
                root,
                WEB,
                lib,
                "| Id | Address | Page title | Date read |\n|---|---|---|---|\n",
                "| Id | Address | Page title | Date read |\n",
            )
            lines = sup.run(root)
            t = sup.line_of(root, WEB, "| Id | Address | Page title | Date read |")
            self.assertEqual(
                sup.fails(lines),
                [sup.fail_line(WEB, "table", t + 1, "separator row missing")],
            )
        with self.subTest(name="row-extra"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit_in(
                root,
                WEB,
                lib,
                "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
                "| P1 | extra | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
            )
            n = sup.line_of(root, WEB, "| P1 | extra |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "table", n, "row has 5 cells, expected 4")],
            )
        with self.subTest(name="row-fewer"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit_in(
                root,
                WEB,
                lib,
                "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
                "| P1 | https://deck.gl/docs/whats-new | 2026-11-12 |",
            )
            n = sup.line_of(
                root, WEB, "| P1 | https://deck.gl/docs/whats-new | 2026-11-12 |"
            )
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "table", n, "row has 3 cells, expected 4")],
            )
        with self.subTest(name="idioms-empty"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit_in(
                root,
                WEB,
                lib,
                '| I1 | old form | new form | READ | P1 | "three quoted words" |\n',
                "",
            )
            t = sup.line_of(
                root,
                WEB,
                "| Id | Earlier form | Current form | Kind | Source | Quote |",
            )
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "table", t, '"Idioms that changed" has no row')],
            )
        with self.subTest(name="coverage-empty"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit(
                root,
                WEB,
                "| A claim | docs/stub.md line 5 | MapLibre GL JS 6 S1; deck.gl 9.4 I1 |\n| Another claim | AGENTS.md line 2 | not covered: no row for it |\n",
                "",
            )
            t = sup.line_of(root, WEB, "| Pack claim | Pack source | Where |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "table", t, f'"{sup.COVERAGE}" has no row')],
            )

    def test_ids(self) -> None:
        lib = FIRST_WEB
        plants = [
            ("X1", "| S1 | A read", "| X1 | A read"),
            ("S01", "| S1 | A read", "| S01 | A read"),
            ("S0", "| S1 | A read", "| S0 | A read"),
            ("dup", "| S2 | An observed", "| S1 | An observed"),
            ("Q1", "| P1 | https", "| Q1 | https"),
            ("Run-S1", "| R1 | pkg", "| S1 | pkg"),
            ("I-num", "| I1 | old", "| 1 | old"),
        ]
        prefixes = {
            "X1": "S",
            "S01": "S",
            "S0": "S",
            "Q1": "P",
            "Run-S1": "R",
            "I-num": "I",
        }
        for name, old, new in plants:
            with self.subTest(name=name):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                sup.edit_in(root, WEB, lib, old, new)
                lines = sup.run(root)
                fails = sup.fails(lines)
                ident = new.split("|", 2)[1].strip()
                if name == "dup":
                    n = sup.line_of(root, WEB, "| S1 | An observed")
                    m = sup.line_of(root, WEB, "| S1 | A read")
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB, "id", n, f'"S1" repeated (first at line {m})'
                            )
                        ],
                    )
                else:
                    n = sup.line_of(root, WEB, f"| {ident} |")
                    prefix = prefixes[name]
                    self.assertEqual(
                        fails,
                        [
                            sup.fail_line(
                                WEB, "id", n, f'"{ident}" is not {prefix} and a number'
                            )
                        ],
                    )

    def test_addresses(self) -> None:
        user = "https://user" + "@" + "host.example/docs/x"
        cell_cases = [
            ("http", "http://deck.gl/docs/x", "not https"),
            (
                "lookalike",
                "https://deck.gl.example.org/docs/x",
                "not on the list of official addresses",
            ),
            ("user", user, "has user information or a port"),
            ("8443", "https://deck.gl:8443/docs/x", "has user information or a port"),
            ("abc", "https://deck.gl:abc/docs/x", "has user information or a port"),
            ("65536", "https://deck.gl:65536/docs/x", "has user information or a port"),
            ("bracket", "https://[::1/docs/x", "not on the list of official addresses"),
            ("query", "https://deck.gl/docs/x?a=b", "has a query or a fragment"),
            ("frag", "https://deck.gl/docs/x#a", "has a query or a fragment"),
            ("dotdot", "https://deck.gl/docs/../x", "has an unsafe path"),
            ("pct", "https://deck.gl/docs/%2e%2e/x", "has an unsafe path"),
            ("dslash", "https://deck.gl/docs//x", "has an unsafe path"),
            (
                "duck15",
                "https://duckdb.org/docs/1.5/x",
                "not on the list of official addresses",
            ),
            (
                "gh-other",
                "https://github.com/other/x",
                "not on the list of official addresses",
            ),
            (
                "carbon",
                "https://github.com/carbon-design-system",
                "not on the list of official addresses",
            ),
            (
                "example",
                "https://example.org/x",
                "not on the list of official addresses",
            ),
            ("words", "see the page", "see the page"),
            ("HTTPS", "HTTPS://deck.gl/docs/x", "not https"),
            ("dslash-scheme", "//deck.gl/docs/x", "not https"),
            ("ftp", "ftp://deck.gl/docs/x", "not https"),
        ]
        old_addr = "https://deck.gl/docs/whats-new"
        for name, url, reason in cell_cases:
            with self.subTest(name=name, where="cell"):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                sup.edit_in(root, WEB, FIRST_WEB, old_addr, url)
                lines = sup.run(root)
                n = sup.line_of(root, WEB, url)
                detail = (
                    f'"{url}" is not an address'
                    if reason == "see the page"
                    else f"{url}: {reason}"
                )
                self.assertEqual(
                    sup.fails(lines), [sup.fail_line(WEB, "address", n, detail)]
                )
        prose_urls = [
            "https://example.org/x",
            "HTTPS://evil.example/x",
            "//evil.example/y",
            "ftp://evil.example/z",
            "https://deck.gl:abc/docs/x",
            "https://deck.gl:65536/docs/x",
            "https://[::1/docs/x",
        ]
        for url in prose_urls:
            with self.subTest(url=url, where="prose"):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                link = f"[other notes]({LINKS[WEB]})"
                sup.edit(root, WEB, link, link + f"\nSee {url}")
                lines = sup.run(root)
                n = sup.line_of(root, WEB, url)
                if url.startswith("see"):
                    pass
                reason = (
                    "not https"
                    if url.startswith(("HTTPS", "//", "ftp"))
                    else (
                        "has user information or a port"
                        if ":abc" in url or ":65536" in url
                        else "not on the list of official addresses"
                    )
                )
                self.assertEqual(
                    sup.fails(lines),
                    [sup.fail_line(WEB, "address", n, f"{url}: {reason}")],
                )
        control_addresses = (
            "https://maplibre.org/maplibre-gl-js/docs/x",
            "https://github.com/maplibre/x",
            "https://raw.githubusercontent.com/maplibre/x",
            "https://deck.gl/docs/x",
            "https://github.com/visgl/x",
            "https://duckdb.org/docs/2.0/x",
            "https://duckdb.org/2026/10/21/announcing-duckdb-200x",
            "https://www.postgresql.org/docs/18/x",
            "https://www.postgresql.org/support/versioning/x",
            "https://hub.docker.com/_/postgresx",
            "https://github.com/carbon-design-system/x",
            "https://raw.githubusercontent.com/carbon-design-system/x",
            "https://platform.claude.com/docs/en/x",
        )
        for url in control_addresses:
            with self.subTest(control=url):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                sup.edit_in(root, WEB, FIRST_WEB, old_addr, url)
                lines = sup.run(root)
                self.assertEqual(sup.fails(lines), [])
        with self.subTest(control="prose-official"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            official = "https://deck.gl/docs/x."
            sup.edit(
                root,
                WEB,
                "[other notes]",
                f"[other notes]({LINKS[WEB]}) See {official}",
            )
            lines = sup.run(root)
            self.assertEqual(sup.fails(lines), [])

    def test_dates(self) -> None:
        bad_values = [
            "2026-13-45",
            "2026" + "1112",
            "2026-1-2",
            "12 November 2026",
            "",
            "2099-01-01",
            "1999-01-01",
            "2026-02-29",
        ]
        for value in bad_values:
            with self.subTest(value=value, where="pages"):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                sup.edit_in(
                    root,
                    WEB,
                    FIRST_WEB,
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
                    f"| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | {value} |",
                )
                lines = sup.run(root)
                n = sup.line_of(root, WEB, f"| {value} |")
                if value in ("2099-01-01", "1999-01-01"):
                    detail = f'"{value}" is outside 2026-01-01 to 2026-11-12'
                elif value == "":
                    detail = f'"{value}" is not a calendar date YYYY-MM-DD'
                else:
                    detail = f'"{value}" is not a calendar date YYYY-MM-DD'
                self.assertEqual(
                    sup.fails(lines), [sup.fail_line(WEB, "date", n, detail)]
                )
        for value in ("2026-13-45", "2026" + "1112", "2099-01-01"):
            with self.subTest(value=value, where="runs"):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                sup.edit_in(
                    root,
                    WEB,
                    FIRST_WEB,
                    "| R1 | pkg 1.0.0 | 2026-11-12 |",
                    f"| R1 | pkg 1.0.0 | {value} |",
                )
                lines = sup.run(root)
                n = sup.line_of(root, WEB, value)
                detail = (
                    f'"{value}" is outside 2026-01-01 to 2026-11-12'
                    if value == "2099-01-01"
                    else f'"{value}" is not a calendar date YYYY-MM-DD'
                )
                self.assertEqual(
                    sup.fails(lines), [sup.fail_line(WEB, "date", n, detail)]
                )
        with self.subTest(name="header-missing"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit(root, WEB, "| Date | 2026-11-12 |", "")
            lines = sup.run(root)
            self.assertEqual(
                sup.fails(lines),
                [
                    sup.fail_line(
                        WEB, "date", 1, 'no valid "| Date |" row in the header table'
                    )
                ],
            )
        with self.subTest(name="header-bad"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit(root, WEB, "| Date | 2026-11-12 |", "| Date | 2026-13-45 |")
            lines = sup.run(root)
            self.assertEqual(
                sup.fails(lines),
                [
                    sup.fail_line(
                        WEB, "date", 1, 'no valid "| Date |" row in the header table'
                    )
                ],
            )
        for good in ("2026-02-28", "2026-01-01", "2026-11-12"):
            with self.subTest(control=good):
                folder, root = _root()
                self.addCleanup(folder.cleanup)
                sup.edit_in(
                    root,
                    WEB,
                    FIRST_WEB,
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
                    f"| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | {good} |",
                )
                self.assertEqual(sup.fails(sup.run(root)), [])

    def test_fences(self) -> None:
        lib = SECOND_WEB
        with self.subTest("fence-before-heading"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit(root, WEB, f"## {lib}", "```\n## " + lib)
            fails = sup.fails(sup.run(root))
            self.assertEqual(len(fails), 2)
            self.assertTrue(all("fence" in line or "prose" in line for line in fails))
        with self.subTest("section-fenced"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            text = sup.read(root, WEB)
            old = f"## {lib}\n"
            inner = text.split(old, 1)[1].split("\n## ", 1)[0]
            sup.edit(root, WEB, old + inner, "```\n" + old + inner + "\n```\n")
            lines = sup.run(root)
            self.assertGreaterEqual(len(sup.fails(lines)), 2)
        with self.subTest("html-comment"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            text = sup.read(root, WEB)
            old = f"## {lib}\n"
            inner = text.split(old, 1)[1].split("\n## ", 1)[0]
            sup.edit(root, WEB, old + inner, "<!--\n" + old + inner + "\n-->\n")
            lines = sup.run(root)
            fails = sup.fails(lines)
            self.assertTrue(any("HTML comment" in line for line in fails))
        with self.subTest("tilde-how"):
            folder, root = _root()
            self.addCleanup(folder.cleanup)
            sup.edit_in(root, WEB, sup.HOW, "Fixture.", "~~~\nFixture.")
            lines = sup.run(root)
            self.assertEqual(len(sup.fails(lines)), 1)
            self.assertIn("code fence", sup.fails(lines)[0])
