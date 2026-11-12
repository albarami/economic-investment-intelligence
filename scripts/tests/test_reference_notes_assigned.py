"""Tests for the Confirmations assigned to this task section."""

from __future__ import annotations

import re
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_notes_support as sup

import reference_notes_tables as tables

WEB = sup.WEB
DOCS = sup.DOCS
ASSIGNED = sup.ASSIGNED
SENTENCE = sup.SENTENCE
COVERAGE = sup.COVERAGE

F1 = "| F1 | IBM Plex Sans | latin | 400 | ibm-plex-sans-latin-400-normal.woff2, ibm-plex-sans-latin-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |"
F2 = "| F2 | IBM Plex Sans | latin | 500 | ibm-plex-sans-latin-500-normal.woff2, ibm-plex-sans-latin-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |"
F3 = "| F3 | IBM Plex Sans | latin | 600 | ibm-plex-sans-latin-600-normal.woff2, ibm-plex-sans-latin-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |"
F4 = "| F4 | IBM Plex Sans Arabic | arabic | 400 | ibm-plex-sans-arabic-arabic-400-normal.woff2, ibm-plex-sans-arabic-arabic-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R1 |"
F5 = "| F5 | IBM Plex Sans Arabic | arabic | 500 | ibm-plex-sans-arabic-arabic-500-normal.woff2, ibm-plex-sans-arabic-arabic-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R1 |"
F6 = "| F6 | IBM Plex Sans Arabic | arabic | 600 | ibm-plex-sans-arabic-arabic-600-normal.woff2, ibm-plex-sans-arabic-arabic-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R1 |"
C1 = "| C1 | icons 1.0.0 | Apache-2.0 | LICENSE in the package | OBSERVED | R1 | - | 2026-11-12 |"
C2 = '| C2 | icons | Apache 2.0 License | LICENSE in the repository root | READ | P1 | "three quoted words" | 2026-11-12 |'
P1_ROW = "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |"
R1_ROW = "| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |"
FONT_HDR = (
    "| Id | Family | Subset | Weight | Files found in the package | Kind | "
    "Package and version | Date | Source |"
)
ICON_HDR = (
    "| Id | Package and version | Licence identifier | Licence file | Kind | "
    "Source | Quote | Date |"
)
PAGES_HDR = "| Id | Address | Page title | Date read |"
RUNS_BLOCK = (
    "### Runs\n\n| Id | Package and version | Date | Command | Output |\n"
    "|---|---|---|---|---|\n| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |\n\n"
)
FONT_FILES = "ibm-plex-sans-latin-400-normal.woff2, ibm-plex-sans-latin-400-normal.woff"
PKG_F1 = "@fontsource/ibm-plex-sans 5.3.0"

Plant = Callable[[Path], None]
Expect = Callable[[Path], list[str]]


def _summary(rows: int, failures: int | str) -> str:
    if failures == "OK":
        return f"checked 2 files, 6 libraries, {rows} rows: OK"
    return f"checked 2 files, 6 libraries, {rows} rows: {failures} failure(s)"


def _font_table(root: Path) -> int:
    return sup.assigned_font_table_line(root)


def _icon_table(root: Path) -> int:
    return sup.assigned_icon_table_line(root)


def _strip_font_table(root: Path) -> None:
    text = sup.read(root, WEB)
    start, stop = sup.section_span(text, ASSIGNED)
    block = "\n".join(text.splitlines()[start:stop])
    block = re.sub(
        r"(### Font weights\n\n)\| Id \| Family.*?(?=\n### Icon package licence)",
        r"\1",
        block,
        count=1,
        flags=re.DOTALL,
    )
    lines = text.splitlines()
    lines[start:stop] = block.splitlines()
    sup.write(root, WEB, "\n".join(lines) + "\n")


class NotesAssigned(unittest.TestCase):
    def _plant(self, plant: Plant) -> Path:
        folder, root = sup.fresh_root()
        self.addCleanup(folder.cleanup)
        plant(root)
        return root

    def _assert_run(
        self,
        root: Path,
        expect: Expect,
        *,
        rows: int = 81,
        failures: int | str = "OK",
    ) -> None:
        lines = sup.run(root)
        self.assertEqual(sup.fails(lines), expect(root))
        self.assertEqual(sup.summary(lines), _summary(rows, failures))

    def test_assigned_section_and_opening(self) -> None:
        with self.subTest("a"):
            root = self._plant(sup.drop_assigned)
            self._assert_run(
                root,
                lambda _r: [
                    sup.fail_line(
                        WEB,
                        "section",
                        1,
                        f'section "{ASSIGNED}" found 0 times, expected once',
                    )
                ],
                rows=36,
                failures=1,
            )
        with self.subTest("b"):
            root = self._plant(
                lambda r: sup.edit(
                    r, WEB, f"## {ASSIGNED}", "## Confirmations assigned to this tasks"
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "section",
                        1,
                        f'section "{ASSIGNED}" found 0 times, expected once',
                    ),
                    sup.fail_line(
                        WEB,
                        "section",
                        sup.heading_line(
                            r, WEB, "Confirmations assigned to this tasks"
                        ),
                        'unknown section "Confirmations assigned to this tasks"',
                    ),
                ],
                rows=36,
                failures=2,
            )
        with self.subTest("c"):

            def plant_c(r: Path) -> None:
                block = sup.read(r, WEB)
                start, stop = sup.section_span(block, ASSIGNED)
                section = "\n".join(block.splitlines()[start:stop]) + "\n"
                sup.edit(r, DOCS, f"## {COVERAGE}\n", section + f"## {COVERAGE}\n")

            root = self._plant(plant_c)
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        DOCS,
                        "section",
                        sup.heading_line(r, DOCS, ASSIGNED),
                        f'unknown section "{ASSIGNED}"',
                    )
                ],
                rows=45,
                failures=1,
            )
        with self.subTest("d"):
            root = self._plant(
                lambda r: sup.edit_in(r, WEB, ASSIGNED, "nearest", "next")
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "assigned",
                        sup.line_of(r, WEB, "next"),
                        "the opening line is not the sentence of the assignment",
                    )
                ],
                failures=1,
            )
        with self.subTest("e"):
            root = self._plant(lambda r: sup.edit_in(r, WEB, ASSIGNED, SENTENCE, ""))
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "assigned",
                        sup.heading_line(r, WEB, ASSIGNED),
                        "the opening sentence is missing",
                    )
                ],
                failures=1,
            )
        with self.subTest("f"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, SENTENCE + "\n", SENTENCE + "\n\nMore words.\n"
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "prose",
                        sup.line_of(r, WEB, "More words."),
                        "line is not a heading, a table row or the one opening or setup paragraph",
                    ),
                    sup.fail_line(
                        WEB,
                        "assigned",
                        sup.line_of(r, WEB, "More words."),
                        "the opening line is not the sentence of the assignment",
                    ),
                ],
                failures=2,
            )
        with self.subTest("g"):
            root = self._plant(
                lambda r: sup.edit_in(r, WEB, ASSIGNED, SENTENCE, "Claims here: none.")
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "prose",
                        sup.line_of(r, WEB, "Claims here: none."),
                        "line is not a heading, a table row or the one opening or setup paragraph",
                    ),
                    sup.fail_line(
                        WEB,
                        "assigned",
                        sup.line_of(r, WEB, "Claims here: none."),
                        "the opening line is not the sentence of the assignment",
                    ),
                ],
                failures=2,
            )
        with self.subTest("h"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    SENTENCE + "\n",
                    SENTENCE + "\n" + SENTENCE + "\n",
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "prose",
                        sup.line_of(r, WEB, SENTENCE, index=1),
                        "line is not a heading, a table row or the one opening or setup paragraph",
                    )
                ],
                failures=1,
            )
        for label, sub in (
            ("i-pages", "Pages read"),
            ("i-runs", "Runs"),
            ("i-font", "Font weights"),
            ("i-icon", "Icon package licence"),
        ):
            with self.subTest(label):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, name=sub: sup.edit_in(
                            r, WEB, ASSIGNED, f"### {name}", "### Notes"
                        ),
                    )
                )
                rows = {
                    "Pages read": 80,
                    "Runs": 80,
                    "Font weights": 75,
                    "Icon package licence": 79,
                }[sub]

                def expect_rename(r: Path, name: str = sub) -> list[str]:
                    return [
                        sup.fail_line(
                            WEB,
                            "subsection",
                            sup.heading_line(r, WEB, ASSIGNED),
                            f'missing subsection "{name}"',
                        ),
                        sup.fail_line(
                            WEB,
                            "subsection",
                            sup.line_of(r, WEB, "### Notes"),
                            'unknown subsection "Notes"',
                        ),
                    ]

                self._assert_run(root, expect_rename, rows=rows, failures=2)
        with self.subTest("j"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    "### Font weights",
                    "### Extra\n\n| x |\n|---|\n| y |\n\n### Font weights",
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "subsection",
                        sup.line_of(r, WEB, "### Extra"),
                        'unknown subsection "Extra"',
                    )
                ],
                failures=1,
            )
        with self.subTest("k"):

            def plant_k(r: Path) -> None:
                extra = (
                    "\n### Font weights\n\n"
                    + FONT_HDR
                    + "\n|---|---|---|---|---|---|---|---|---|\n"
                    + F1
                    + "\n\n"
                )
                sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    "\n### Icon package licence",
                    extra + "\n### Icon package licence",
                )

            root = self._plant(plant_k)
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "subsection",
                        sup.line_of(r, WEB, "### Font weights", index=1),
                        'repeated subsection "Font weights"',
                    )
                ],
                failures=1,
            )
        with self.subTest("l"):
            root = self._plant(_strip_font_table)
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "subsection",
                        sup.line_of(r, WEB, "### Font weights"),
                        'subsection "Font weights" has no table',
                    )
                ],
                rows=75,
                failures=1,
            )
        with self.subTest("m"):
            root = self._plant(lambda r: sup.edit_in(r, WEB, ASSIGNED, RUNS_BLOCK, ""))
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "subsection",
                        sup.heading_line(r, WEB, ASSIGNED),
                        'missing subsection "Runs"',
                    )
                ],
                rows=80,
                failures=1,
            )
        with self.subTest("n"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    RUNS_BLOCK,
                    "### Runs\n\nSetup, in an empty folder: none.\n\n"
                    "| Id | Package and version | Date | Command | Output |\n"
                    "|---|---|---|---|---|\n| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |\n\n",
                )
            )
            self._assert_run(root, lambda _r: [])
        with self.subTest("o"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    SENTENCE + "\n\n### Pages read",
                    SENTENCE + "\n\n| x |\n|---|\n| y |\n\n### Pages read",
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "prose",
                        sup.line_of(r, WEB, "| x |"),
                        "line is not a heading, a table row or the one opening or setup paragraph",
                    )
                ],
                failures=1,
            )
        with self.subTest("p"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    "### Runs\n\n",
                    "### Runs\n\nSetup, line one.\nSetup, line two.\n\n",
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "prose",
                        sup.line_of(r, WEB, "Setup, line two."),
                        "line is not a heading, a table row or the one opening or setup paragraph",
                    )
                ],
                failures=1,
            )
        with self.subTest("q"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    "### Font weights\n\n",
                    "### Font weights\n\nSetup of a claim.\n\n",
                )
            )
            self._assert_run(
                root,
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "prose",
                        sup.line_of(r, WEB, "Setup of a claim."),
                        "line is not a heading, a table row or the one opening or setup paragraph",
                    )
                ],
                failures=1,
            )

    def test_assigned_rows(self) -> None:
        quote_msg = (
            "C2: READ quote must be a double-quoted phrase of "
            f"{tables.QUOTE_WORDS[0]} to {tables.QUOTE_WORDS[1]} words"
        )

        def pages_p1_line(root: Path) -> int:
            return sup.assigned_pages_p1_line(root)

        cases: list[tuple[str, Plant, Expect, int, int | str]] = [
            (
                "f2-read",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("| OBSERVED |", "| READ |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "kind",
                        sup.line_of(
                            r, WEB, "| READ | @fontsource/ibm-plex-sans 5.3.0 |"
                        ),
                        '"READ" is not OBSERVED',
                    ),
                ],
                81,
                2,
            ),
            (
                "f2-observed",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("| OBSERVED |", "| observed |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "kind",
                        sup.line_of(r, WEB, "| observed | @fontsource"),
                        '"observed" is not OBSERVED',
                    ),
                ],
                81,
                2,
            ),
            (
                "f2-r9",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("| R1 |", "| R9 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "source",
                        sup.line_of(r, WEB, "| R9 |"),
                        'F2: OBSERVED source "R9" is not a run id of this section',
                    )
                ],
                81,
                1,
            ),
            (
                "f2-p1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("| R1 |", "| P1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "source",
                        sup.line_of(r, WEB, F2.split("| R1 |")[0] + "| P1 |"),
                        'F2: OBSERVED source "P1" is not a run id of this section',
                    )
                ],
                81,
                1,
            ),
            (
                "f2-date2099",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("2026-11-12", "2099-01-01")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "date",
                        sup.line_of(r, WEB, "2099-01-01"),
                        '"2099-01-01" is outside 2026-01-01 to 2026-11-12',
                    )
                ],
                81,
                1,
            ),
            (
                "f2-baddate",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("2026-11-12", "2026-13-45")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "date",
                        sup.line_of(r, WEB, "2026-13-45"),
                        '"2026-13-45" is not a calendar date YYYY-MM-DD',
                    )
                ],
                81,
                1,
            ),
            (
                "c2-pack",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C2, C2.replace("| READ |", "| PACK |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB, "unused", pages_p1_line(r), "page P1 is cited by no row"
                    ),
                    sup.fail_line(
                        WEB,
                        "kind",
                        sup.line_of(
                            r,
                            WEB,
                            "| C2 | icons | Apache 2.0 License | LICENSE in the repository root | PACK |",
                        ),
                        '"PACK" is not READ or OBSERVED',
                    ),
                ],
                81,
                2,
            ),
            (
                "c2-p9",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C2, C2.replace("| P1 |", "| P9 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB, "unused", pages_p1_line(r), "page P1 is cited by no row"
                    ),
                    sup.fail_line(
                        WEB,
                        "source",
                        sup.line_of(r, WEB, "| P9 |"),
                        'C2: READ source "P9" is not a page id of this section',
                    ),
                ],
                81,
                2,
            ),
            (
                "c2-r1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C2, C2.replace("| P1 |", "| R1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB, "unused", pages_p1_line(r), "page P1 is cited by no row"
                    ),
                    sup.fail_line(
                        WEB,
                        "source",
                        sup.line_of(r, WEB, '| R1 | "three quoted words"'),
                        'C2: READ source "R1" is not a page id of this section',
                    ),
                ],
                81,
                2,
            ),
            (
                "c2-quote-two",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    C2,
                    C2.replace('"three quoted words"', '"two words"'),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB, "quote", sup.line_of(r, WEB, '"two words"'), quote_msg
                    )
                ],
                81,
                1,
            ),
            (
                "c2-quote-dash",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C2, C2.replace('"three quoted words"', "-")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "quote",
                        sup.line_of(r, WEB, C2.replace('"three quoted words"', "-")),
                        quote_msg,
                    )
                ],
                81,
                1,
            ),
            (
                "c1-quote",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C1, C1.replace("| - |", '| "quoted" |')
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "quote",
                        sup.line_of(r, WEB, '| "quoted" |'),
                        'C1: OBSERVED quote must be "-"',
                    )
                ],
                81,
                1,
            ),
            (
                "c1-p1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C1, C1.replace("| R1 |", "| P1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "source",
                        sup.line_of(r, WEB, "| P1 | - |"),
                        'C1: OBSERVED source "P1" is not a run id of this section',
                    )
                ],
                81,
                1,
            ),
            (
                "c1-baddate",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C1, C1.replace("2026-11-12", "12 November 2026")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "date",
                        sup.line_of(r, WEB, "12 November 2026"),
                        '"12 November 2026" is not a calendar date YYYY-MM-DD',
                    )
                ],
                81,
                1,
            ),
            (
                "f1-x1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace("| F1 |", "| X1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "id",
                        sup.line_of(r, WEB, "| X1 |"),
                        '"X1" is not F and a number',
                    )
                ],
                81,
                1,
            ),
            (
                "f2-as-f1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F2, F2.replace("| F2 |", "| F1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "id",
                        sup.line_of(r, WEB, "| F1 |", index=1),
                        f'"F1" repeated (first at line {sup.line_of(r, WEB, "| F1 |")})',
                    )
                ],
                81,
                1,
            ),
            (
                "c1-as-f1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C1, C1.replace("| C1 |", "| F1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "id",
                        sup.line_of(r, WEB, "| F1 |", index=1),
                        '"F1" is not C and a number',
                    )
                ],
                81,
                1,
            ),
            (
                "c2-as-c1",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C2, C2.replace("| C2 |", "| C1 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "id",
                        sup.line_of(r, WEB, "| C1 |", index=1),
                        f'"C1" repeated (first at line {sup.line_of(r, WEB, "| C1 |")})',
                    )
                ],
                81,
                1,
            ),
            (
                "r2-unused",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    R1_ROW + "\n\n",
                    R1_ROW + "\n| R2 | pkg 2.0.0 | 2026-11-12 | `echo x` | x |\n\n",
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "unused",
                        sup.line_of(r, WEB, "| R2 |"),
                        "run R2 is cited by no row",
                    )
                ],
                82,
                1,
            ),
            (
                "p2-unused",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    P1_ROW + "\n\n",
                    P1_ROW
                    + "\n| P2 | https://deck.gl/docs/whats-new | Other | 2026-11-12 |\n\n",
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "unused",
                        sup.line_of(r, WEB, "| P2 |"),
                        "page P2 is cited by no row",
                    )
                ],
                82,
                1,
            ),
            (
                "c2-observed",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    C2,
                    "| C2 | icons | Apache 2.0 License | LICENSE in the repository root | OBSERVED | R1 | - | 2026-11-12 |",
                ),
                lambda r: [
                    sup.fail_line(
                        WEB, "unused", pages_p1_line(r), "page P1 is cited by no row"
                    )
                ],
                81,
                1,
            ),
            (
                "font-subset-col",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, FONT_HDR, FONT_HDR.replace("Subset", "Group")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "table",
                        sup.line_of(r, WEB, FONT_HDR.replace("Subset", "Group")),
                        f'header is not "{FONT_HDR}"',
                    )
                ],
                75,
                1,
            ),
            (
                "icon-lic-col",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    ICON_HDR,
                    ICON_HDR.replace("Licence identifier", "Licence"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "table",
                        sup.line_of(
                            r, WEB, ICON_HDR.replace("Licence identifier", "Licence")
                        ),
                        f'header is not "{ICON_HDR}"',
                    )
                ],
                79,
                1,
            ),
            (
                "pages-title-col",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    PAGES_HDR,
                    PAGES_HDR.replace("Page title", "Title"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "table",
                        sup.line_of(r, WEB, PAGES_HDR.replace("Page title", "Title")),
                        f'header is not "{PAGES_HDR}"',
                    )
                ],
                80,
                1,
            ),
            (
                "see-page",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, "https://deck.gl/docs/whats-new", "see the page"
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "address",
                        sup.line_of(r, WEB, "see the page"),
                        '"see the page" is not an address',
                    )
                ],
                81,
                1,
            ),
            (
                "example-url",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    "https://deck.gl/docs/whats-new",
                    "https://example.org/x",
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "address",
                        sup.line_of(r, WEB, "https://example.org/x"),
                        "https://example.org/x: not on the list of official addresses",
                    )
                ],
                81,
                1,
            ),
            (
                "f1-fewer-cells",
                lambda r: sup.edit_in(r, WEB, ASSIGNED, F1, F1.rsplit("|", 2)[0] + "|"),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "table",
                        sup.line_of(r, WEB, F1.rsplit("|", 2)[0] + "|"),
                        "row has 8 cells, expected 9",
                    ),
                ],
                81,
                2,
            ),
            (
                "c1-more-cells",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    C1,
                    C1.replace("| 2026-11-12 |", "| extra | 2026-11-12 |"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        _icon_table(r),
                        "no OBSERVED row with a licence identifier",
                    ),
                    sup.fail_line(
                        WEB,
                        "table",
                        sup.line_of(r, WEB, "| extra | 2026-11-12 |"),
                        "row has 9 cells, expected 8",
                    ),
                ],
                81,
                2,
            ),
            (
                "runs-date2099",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, R1_ROW, R1_ROW.replace("2026-11-12", "2099-01-01")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "date",
                        sup.line_of(r, WEB, "2099-01-01"),
                        '"2099-01-01" is outside 2026-01-01 to 2026-11-12',
                    )
                ],
                81,
                1,
            ),
        ]
        self.assertEqual(len(cases), 29)
        for name, plant, expect, rows, failures in cases:
            with self.subTest(name=name):
                root = self._plant(plant)
                self._assert_run(root, expect, rows=rows, failures=failures)

    def test_font_weights(self) -> None:
        pkg_fail = 'F1: package "{pkg}" is not "@fontsource/ibm-plex-sans <version>"'
        files_fail = '{id}: files "{files}" are not the woff2 or woff file of the subset and weight'

        def expect_missing(family: str, weight: str) -> Expect:
            return lambda r: [
                sup.fail_line(
                    WEB,
                    "weights",
                    _font_table(r),
                    f"{family} {weight}: no OBSERVED row",
                )
            ]

        cases: list[tuple[str, Plant, Expect, int, int | str]] = [
            (
                "rm-f1",
                lambda r: sup.remove_in_assigned(r, F1),
                expect_missing("IBM Plex Sans", "400"),
                80,
                1,
            ),
            (
                "rm-f2",
                lambda r: sup.remove_in_assigned(r, F2),
                expect_missing("IBM Plex Sans", "500"),
                80,
                1,
            ),
            (
                "rm-f3",
                lambda r: sup.remove_in_assigned(r, F3),
                expect_missing("IBM Plex Sans", "600"),
                80,
                1,
            ),
            (
                "rm-f4",
                lambda r: sup.remove_in_assigned(r, F4),
                expect_missing("IBM Plex Sans Arabic", "400"),
                80,
                1,
            ),
            (
                "rm-f5",
                lambda r: sup.remove_in_assigned(r, F5),
                expect_missing("IBM Plex Sans Arabic", "500"),
                80,
                1,
            ),
            (
                "rm-f6",
                lambda r: sup.remove_in_assigned(r, F6),
                expect_missing("IBM Plex Sans Arabic", "600"),
                80,
                1,
            ),
            (
                "rm-f456",
                lambda r: sup.remove_in_assigned(r, F4, F5, F6),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 600: no OBSERVED row",
                    ),
                ],
                78,
                3,
            ),
            (
                "rm-f2to6",
                lambda r: sup.remove_in_assigned(r, F2, F3, F4, F5, F6),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 600: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 600: no OBSERVED row",
                    ),
                ],
                76,
                5,
            ),
            (
                "rm-all",
                lambda r: sup.remove_in_assigned(r, F1, F2, F3, F4, F5, F6),
                lambda r: [
                    sup.fail_line(
                        WEB, "table", _font_table(r), '"Font weights" has no row'
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 600: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 500: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans Arabic 600: no OBSERVED row",
                    ),
                ],
                75,
                7,
            ),
            (
                "f1-mono",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace("IBM Plex Sans", "IBM Plex Mono")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "IBM Plex Mono"),
                        'F1: family "IBM Plex Mono" is not a known family',
                    ),
                ],
                81,
                2,
            ),
            (
                "f1-lower",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace("IBM Plex Sans", "ibm plex sans")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "ibm plex sans"),
                        'F1: family "ibm plex sans" is not a known family',
                    ),
                ],
                81,
                2,
            ),
            (
                "f1-w700",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace("| 400 |", "| 700 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "| 700 |"),
                        'F1: weight "700" is not one of 400, 500, 600',
                    ),
                ],
                81,
                2,
            ),
            (
                "f1-w4",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace("| 400 |", "| 4 |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "| 4 |"),
                        'F1: weight "4" is not one of 400, 500, 600',
                    ),
                ],
                81,
                2,
            ),
            (
                "f1-read",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace("| OBSERVED |", "| READ |")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        _font_table(r),
                        "IBM Plex Sans 400: no OBSERVED row",
                    ),
                    sup.fail_line(
                        WEB,
                        "kind",
                        sup.line_of(r, WEB, "| READ | @fontsource/ibm-plex-sans"),
                        '"READ" is not OBSERVED',
                    ),
                ],
                81,
                2,
            ),
            (
                "f1-files-empty",
                lambda r: sup.edit_in(r, WEB, ASSIGNED, F1, F1.replace(FONT_FILES, "")),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, F1.replace(FONT_FILES, "")),
                        files_fail.format(id="F1", files=""),
                    )
                ],
                81,
                1,
            ),
            (
                "f1-files-dash",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace(FONT_FILES, "-")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, F1.replace(FONT_FILES, "-")),
                        files_fail.format(id="F1", files="-"),
                    )
                ],
                81,
                1,
            ),
            (
                "f1-greek",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace("latin", "greek").replace(
                        FONT_FILES,
                        "ibm-plex-sans-greek-400-normal.woff2, ibm-plex-sans-greek-400-normal.woff",
                    ),
                ),
                lambda _r: [],
                81,
                "OK",
            ),
            (
                "f1-w500-names",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(
                        FONT_FILES,
                        "ibm-plex-sans-latin-500-normal.woff2, ibm-plex-sans-latin-500-normal.woff",
                    ),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "latin-500-normal"),
                        files_fail.format(
                            id="F1",
                            files="ibm-plex-sans-latin-500-normal.woff2, ibm-plex-sans-latin-500-normal.woff",
                        ),
                    )
                ],
                81,
                1,
            ),
            (
                "f1-italic",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(
                        FONT_FILES,
                        "ibm-plex-sans-latin-400-italic.woff2, ibm-plex-sans-latin-400-italic.woff",
                    ),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "italic"),
                        files_fail.format(
                            id="F1",
                            files="ibm-plex-sans-latin-400-italic.woff2, ibm-plex-sans-latin-400-italic.woff",
                        ),
                    )
                ],
                81,
                1,
            ),
            (
                "f4-wrong-stem",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F4,
                    F4.replace(
                        "ibm-plex-sans-arabic-arabic-400-normal",
                        "ibm-plex-sans-arabic-400-normal",
                    ),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "ibm-plex-sans-arabic-400-normal"),
                        files_fail.format(
                            id="F4",
                            files="ibm-plex-sans-arabic-400-normal.woff2, ibm-plex-sans-arabic-400-normal.woff",
                        ),
                    )
                ],
                81,
                1,
            ),
            (
                "f1-woff-first",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(
                        FONT_FILES,
                        "ibm-plex-sans-latin-400-normal.woff, ibm-plex-sans-latin-400-normal.woff2",
                    ),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, ".woff, ibm-plex"),
                        files_fail.format(
                            id="F1",
                            files="ibm-plex-sans-latin-400-normal.woff, ibm-plex-sans-latin-400-normal.woff2",
                        ),
                    )
                ],
                81,
                1,
            ),
            (
                "f1-nospace",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(
                        FONT_FILES,
                        "ibm-plex-sans-latin-400-normal.woff2,ibm-plex-sans-latin-400-normal.woff",
                    ),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "woff2,ibm-plex"),
                        files_fail.format(
                            id="F1",
                            files="ibm-plex-sans-latin-400-normal.woff2,ibm-plex-sans-latin-400-normal.woff",
                        ),
                    )
                ],
                81,
                1,
            ),
            (
                "f1-woff2-only",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(FONT_FILES, "ibm-plex-sans-latin-400-normal.woff2"),
                ),
                lambda _r: [],
                81,
                "OK",
            ),
            (
                "f1-woff-only",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(FONT_FILES, "ibm-plex-sans-latin-400-normal.woff"),
                ),
                lambda _r: [],
                81,
                "OK",
            ),
            (
                "pkg-other",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, F1, F1.replace(PKG_F1, "@fontsource/other 5.3.0")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "@fontsource/other"),
                        pkg_fail.format(pkg="@fontsource/other 5.3.0"),
                    )
                ],
                81,
                1,
            ),
            (
                "pkg-arabic",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(PKG_F1, "@fontsource/ibm-plex-sans-arabic 5.3.0"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "@fontsource/ibm-plex-sans-arabic"),
                        pkg_fail.format(pkg="@fontsource/ibm-plex-sans-arabic 5.3.0"),
                    )
                ],
                81,
                1,
            ),
            (
                "pkg-no-ver",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(PKG_F1, "@fontsource/ibm-plex-sans"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "@fontsource/ibm-plex-sans | 2026"),
                        pkg_fail.format(pkg="@fontsource/ibm-plex-sans"),
                    )
                ],
                81,
                1,
            ),
            (
                "pkg-short-ver",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(PKG_F1, "@fontsource/ibm-plex-sans 5.3"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "@fontsource/ibm-plex-sans 5.3 |"),
                        pkg_fail.format(pkg="@fontsource/ibm-plex-sans 5.3"),
                    )
                ],
                81,
                1,
            ),
            (
                "pkg-latest",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(PKG_F1, "@fontsource/ibm-plex-sans latest"),
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "weights",
                        sup.line_of(r, WEB, "@fontsource/ibm-plex-sans latest"),
                        pkg_fail.format(pkg="@fontsource/ibm-plex-sans latest"),
                    )
                ],
                81,
                1,
            ),
            (
                "pkg-ok-ver",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F1,
                    F1.replace(PKG_F1, "@fontsource/ibm-plex-sans 10.20.30"),
                ),
                lambda _r: [],
                81,
                "OK",
            ),
            (
                "f7-control",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    F6 + "\n",
                    F6
                    + "\n"
                    + "| F7 | IBM Plex Sans | latin-ext | 400 | ibm-plex-sans-latin-ext-400-normal.woff2 | OBSERVED | @fontsource/ibm-plex-sans 10.20.30 | 2026-11-12 | R1 |\n",
                ),
                lambda _r: [],
                82,
                "OK",
            ),
        ]
        self.assertEqual(len(cases), 31)
        for name, plant, expect, rows, failures in cases:
            with self.subTest(name=name):
                root = self._plant(plant)
                self._assert_run(root, expect, rows=rows, failures=failures)

    def test_icon_licence(self) -> None:
        def pages_p1(root: Path) -> int:
            return sup.assigned_pages_p1_line(root)

        cases: list[tuple[str, Plant, Expect, int, int | str]] = [
            (
                "c1-empty",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C1, C1.replace("Apache-2.0", "")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        _icon_table(r),
                        "no OBSERVED row with a licence identifier",
                    ),
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        sup.line_of(r, WEB, C1.replace("Apache-2.0", "")),
                        "C1: licence identifier is empty",
                    ),
                ],
                81,
                2,
            ),
            (
                "c1-dash",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C1, C1.replace("Apache-2.0", "-")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        _icon_table(r),
                        "no OBSERVED row with a licence identifier",
                    ),
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        sup.line_of(r, WEB, C1.replace("Apache-2.0", "-")),
                        "C1: licence identifier is empty",
                    ),
                ],
                81,
                2,
            ),
            (
                "c2-empty",
                lambda r: sup.edit_in(
                    r, WEB, ASSIGNED, C2, C2.replace("Apache 2.0 License", "")
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        sup.line_of(r, WEB, C2.replace("Apache 2.0 License", "")),
                        "C2: licence identifier is empty",
                    )
                ],
                81,
                1,
            ),
            (
                "c1-read",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    C1,
                    '| C1 | icons 1.0.0 | Apache-2.0 | LICENSE in the package | READ | P1 | "three quoted words" | 2026-11-12 |',
                ),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        _icon_table(r),
                        "no OBSERVED row with a licence identifier",
                    )
                ],
                81,
                1,
            ),
            (
                "c1-removed",
                lambda r: sup.remove_in_assigned(r, C1),
                lambda r: [
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        _icon_table(r),
                        "no OBSERVED row with a licence identifier",
                    )
                ],
                80,
                1,
            ),
            (
                "c2-removed",
                lambda r: sup.remove_in_assigned(r, C2),
                lambda r: [
                    sup.fail_line(
                        WEB, "unused", pages_p1(r), "page P1 is cited by no row"
                    )
                ],
                80,
                1,
            ),
            (
                "both-removed",
                lambda r: sup.remove_in_assigned(r, C1, C2),
                lambda r: [
                    sup.fail_line(
                        WEB, "unused", pages_p1(r), "page P1 is cited by no row"
                    ),
                    sup.fail_line(
                        WEB,
                        "table",
                        _icon_table(r),
                        '"Icon package licence" has no row',
                    ),
                    sup.fail_line(
                        WEB,
                        "icon-licence",
                        _icon_table(r),
                        "no OBSERVED row with a licence identifier",
                    ),
                ],
                79,
                3,
            ),
            (
                "c3-control",
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    ASSIGNED,
                    C2 + "\n",
                    C2
                    + "\n"
                    + "| C3 | icons 2.0.0 | MIT | LICENSE in the package | OBSERVED | R1 | - | 2026-11-12 |\n",
                ),
                lambda _r: [],
                82,
                "OK",
            ),
        ]
        self.assertEqual(len(cases), 8)
        for name, plant, expect, rows, failures in cases:
            with self.subTest(name=name):
                root = self._plant(plant)
                self._assert_run(root, expect, rows=rows, failures=failures)


if __name__ == "__main__":
    unittest.main()
