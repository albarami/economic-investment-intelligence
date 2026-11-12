"""Row-level tests for reference notes (kinds, cites, coverage, order)."""

from __future__ import annotations

import os
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_notes_support as sup

import reference_notes_tables as tables
from reference_notes_report import PROSE

WEB = sup.WEB
DOCS = sup.DOCS
WEB_LIB = sup.WEB_LIB
DOCS_LIB = sup.DOCS_LIB
PACK_LINE = "docs/stub.md ARC-01"
AGENTS_CITE = 'AGENTS.md section "Rules"'
DUCK_FIELD0 = tables.LIBRARIES[DOCS][0].fields[0]
DUCK_FIELD1 = tables.LIBRARIES[DOCS][0].fields[1]
WEB_LIB0 = tables.LIBRARIES[WEB][0].name
WEB_LIB1 = tables.LIBRARIES[WEB][1].name
COVERAGE_ROW1 = f"| A claim | {PACK_LINE} | {WEB_LIB0} S1; {WEB_LIB1} I1 |"
COVERAGE_ROW2 = f"| Another claim | {AGENTS_CITE} | {tables.NOT_COVERED}no row for it |"


class NotesRows(unittest.TestCase):
    def _plant(self, plant: Callable[[Path], None]) -> Path:
        folder, root = sup.fresh_root()
        self.addCleanup(folder.cleanup)
        plant(root)
        return root

    def test_kinds_and_sources(self) -> None:
        lib = WEB_LIB
        s1 = '| S1 | A read statement. | READ | P1 | "three quoted words" |'
        with self.subTest(name="kind-read"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    s1,
                    '| S1 | A read statement. | read | P1 | "three quoted words" |',
                )
            )
            n = sup.line_of(root, WEB, "| read |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "kind", n, '"read" is not READ, OBSERVED or PACK')],
            )
        with self.subTest(name="kind-unknown"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r, WEB, lib, s1, s1.replace("| READ |", "| UNKNOWN |")
                )
            )
            n = sup.line_of(root, WEB, "| UNKNOWN |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB, "kind", n, '"UNKNOWN" is not READ, OBSERVED or PACK'
                    )
                ],
            )
        with self.subTest(name="kind-empty"):
            root = self._plant(
                lambda r: sup.edit_in(r, WEB, lib, s1, s1.replace("| READ |", "|  |"))
            )
            n = sup.line_of(root, WEB, "|  | P1 |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "kind", n, '"" is not READ, OBSERVED or PACK')],
            )
        with self.subTest(name="read-p99"):
            root = self._plant(
                lambda r: sup.edit_in(r, WEB, lib, s1, s1.replace("| P1 |", "| P99 |"))
            )
            n = sup.line_of(root, WEB, "| P99 |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "source",
                        n,
                        'S1: READ source "P99" is not a page id of this section',
                    )
                ],
            )
        with self.subTest(name="read-r1"):
            root = self._plant(
                lambda r: sup.edit_in(r, WEB, lib, s1, s1.replace("| P1 |", "| R1 |"))
            )
            n = sup.line_of(root, WEB, '| R1 | "three')
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "source",
                        n,
                        'S1: READ source "R1" is not a page id of this section',
                    )
                ],
            )
        s2 = "| S2 | An observed statement. | OBSERVED | R1 | - |"
        for name, src, detail in (
            (
                "obs-p1",
                "P1",
                'S2: OBSERVED source "P1" is not a run id of this section',
            ),
            (
                "obs-r99",
                "R99",
                'S2: OBSERVED source "R99" is not a run id of this section',
            ),
        ):
            with self.subTest(name=name):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, s=src: sup.edit_in(
                            r,
                            WEB,
                            lib,
                            s2,
                            f"| S2 | An observed statement. | OBSERVED | {s} | - |",
                        ),
                    )
                )
                m = sup.line_of(root, WEB, "| R1 | pkg 1.0.0 |")
                n = sup.line_of(root, WEB, f"| {src} | - |")
                self.assertEqual(
                    sup.fails(sup.run(root)),
                    [
                        sup.fail_line(WEB, "unused", m, "run R1 is cited by no row"),
                        sup.fail_line(WEB, "source", n, detail),
                    ],
                )
        with self.subTest(name="pack-p1"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |",
                    f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | P1 | - |",
                )
            )
            n = sup.line_of(root, WEB, "| PACK | P1 |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        'S3: cite item "P1" is not an anchor',
                    )
                ],
            )

        with self.subTest(name="idiom-kind"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| I1 | old form | new form | READ |",
                    "| I1 | old form | new form | read |",
                )
            )
            n = sup.line_of(root, WEB, "| I1 | old form | new form | read |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "kind", n, '"read" is not READ, OBSERVED or PACK')],
            )
        with self.subTest(name="idiom-p99"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| I1 | old form | new form | READ | P1 |",
                    "| I1 | old form | new form | READ | P99 |",
                )
            )
            n = sup.line_of(root, WEB, "| I1 | old form | new form | READ | P99 |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "source",
                        n,
                        'I1: READ source "P99" is not a page id of this section',
                    )
                ],
            )

    def test_quotes(self) -> None:
        lib = WEB_LIB
        cases = [
            ("no-quotes", '"three quoted words"', "three quoted words", "S1"),
            ("two-words", '"three quoted words"', '"two words"', "S1"),
            (
                "41-words",
                '"three quoted words"',
                '"' + " ".join(f"w{i}" for i in range(41)) + '"',
                "S1",
            ),
            ("empty-quote", '"three quoted words"', '""', "S1"),
            ("single-quotes", '"three quoted words"', "'three quoted words'", "S1"),
            ("read-dash", '"three quoted words"', "-", "S1"),
            ("obs-quote", "-", '"nope"', "S2"),
            ("pack-quote", "-", '"nope"', "S3"),
        ]
        controls = [
            ("backtick", '"three quoted words"', '`"three quoted words"`', "S1"),
            ("three", '"three quoted words"', '"one two three"', "S1"),
            (
                "forty",
                '"three quoted words"',
                '"' + " ".join(f"w{i}" for i in range(40)) + '"',
                "S1",
            ),
        ]
        for name, old_q, new_q, ident in cases:
            with self.subTest(name=name):
                if ident == "S3":
                    root = self._plant(
                        cast(
                            Callable[[Path], None],
                            lambda r, nq=new_q: sup.edit_in(
                                r,
                                WEB,
                                lib,
                                f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |",
                                f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | {nq} |",
                            ),
                        )
                    )
                elif ident == "S2":
                    root = self._plant(
                        cast(
                            Callable[[Path], None],
                            lambda r, nq=new_q: sup.edit_in(
                                r,
                                WEB,
                                lib,
                                "| S2 | An observed statement. | OBSERVED | R1 | - |",
                                f"| S2 | An observed statement. | OBSERVED | R1 | {nq} |",
                            ),
                        )
                    )
                else:
                    root = self._plant(
                        cast(
                            Callable[[Path], None],
                            lambda r, o=old_q, n=new_q: sup.edit_in(
                                r,
                                WEB,
                                lib,
                                f"| S1 | A read statement. | READ | P1 | {o} |",
                                f"| S1 | A read statement. | READ | P1 | {n} |",
                            ),
                        )
                    )
                lines = sup.run(root)
                if ident == "S1":
                    n = sup.line_of(root, WEB, "| S1 | A read statement. | READ |")
                    detail = (
                        "S1: READ quote must be a double-quoted phrase of 3 to 40 words"
                    )
                elif ident == "S2":
                    n = sup.line_of(root, WEB, "| S2 | An observed")
                    detail = 'S2: OBSERVED quote must be "-"'
                else:
                    n = sup.line_of(root, WEB, "| S3 | A pack")
                    detail = 'S3: PACK quote must be "-"'
                self.assertEqual(
                    sup.fails(lines), [sup.fail_line(WEB, "quote", n, detail)]
                )
        for name, old_q, new_q, _ident in controls:
            with self.subTest(control=name):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, o=old_q, n=new_q: sup.edit_in(
                            r,
                            WEB,
                            lib,
                            f"| S1 | A read statement. | READ | P1 | {o} |",
                            f"| S1 | A read statement. | READ | P1 | {n} |",
                        ),
                    )
                )
                self.assertEqual(sup.fails(sup.run(root)), [])

    def test_pack_cites(self) -> None:
        lib = WEB_LIB
        old = f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} |"

        def one(cite: str) -> tuple[Path, int]:
            root = self._plant(
                cast(
                    Callable[[Path], None],
                    lambda r, c=cite: sup.edit_in(
                        r,
                        WEB,
                        lib,
                        old,
                        f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {c} |",
                    ),
                )
            )
            return root, sup.line_of(root, WEB, "| S3 | A pack")

        with self.subTest(name="a1-not-an-anchor"):
            root, n = one("docs/stub.md line 5")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        'S3: cite item "docs/stub.md line 5" is not an anchor',
                    )
                ],
            )
        with self.subTest(name="a2-not-a-regular-file"):
            root, n = one("docs/link.md ARC-01")
            os.symlink(root / "docs/stub.md", root / "docs/link.md")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "pack-cite", n, "S3: docs/link.md is not a file")],
            )
        with self.subTest(name="a3-requirement-count"):
            root, n = one("docs/stub.md ARC-99")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        'S3: requirement "ARC-99" found 0 times',
                    )
                ],
            )
        with self.subTest(name="a4-heading-count"):
            root, n = one('docs/stub.md section "Absent"')
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        'S3: heading "Absent" found 0 times',
                    )
                ],
            )
        with self.subTest(name="a5-row-label"):
            root, n = one('docs/stub.md section "Tables" row "Absent"')
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        'S3: row "Absent" is not in that section',
                    )
                ],
            )
        with self.subTest(name="a6-item-number"):
            root, n = one('docs/stub.md section "Items" item 2')
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        "S3: item 2 is not in that section",
                    )
                ],
            )
        with self.subTest(name="a7-task-heading"):
            root, n = one("TASKS.md S0-T99")
            sup.write(root, "TASKS.md", "# Tasks\n\n### S0-T01 \u2014 Present\n")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "pack-cite",
                        n,
                        'S3: task "S0-T99" has no heading',
                    )
                ],
            )
        with self.subTest(label="control-agents-section"):
            root, _n = one(AGENTS_CITE)
            self.assertEqual(sup.fails(sup.run(root)), [])
        with self.subTest(label="control-stub-and-agents"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    DOCS,
                    DOCS_LIB,
                    f"| {DUCK_FIELD1} | {tables.CONFIRMED} | - | {PACK_LINE} |",
                    f"| {DUCK_FIELD1} | {tables.CONFIRMED} | - | {PACK_LINE}; {AGENTS_CITE} |",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])

    def test_unverified(self) -> None:
        lib = WEB_LIB
        with self.subTest("pack-missing"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |",
                    f"| S3 | A pack statement. | PACK | {PACK_LINE} | - |",
                )
            )
            n = sup.line_of(root, WEB, "| S3 | A pack statement. | PACK |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "unverified",
                        n,
                        f'S3: PACK row lacks "{tables.UNVERIFIED}"',
                    )
                ],
            )
        for name, old, new, needle, detail in (
            (
                "read-tail",
                "| S1 | A read statement. | READ |",
                f"| S1 | A read statement {tables.UNVERIFIED}. | READ |",
                "| S1 | A read statement not",
                'S1: READ row says "not verified"',
            ),
            (
                "obs-tail",
                "| S2 | An observed statement. | OBSERVED |",
                f"| S2 | An observed statement {tables.UNVERIFIED}. | OBSERVED |",
                "| S2 | An observed statement not",
                'S2: OBSERVED row says "not verified"',
            ),
            (
                "idiom-tail",
                "| I1 | old form | new form | READ |",
                f"| I1 | old form | new form {tables.UNVERIFIED}. | READ |",
                "| I1 | old form | new form not",
                'I1: READ row says "not verified"',
            ),
        ):
            with self.subTest(name=name):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, o=old, n=new: sup.edit_in(r, WEB, lib, o, n),
                    )
                )
                n = sup.line_of(root, WEB, needle)
                self.assertEqual(
                    sup.fails(sup.run(root)),
                    [sup.fail_line(WEB, "unverified", n, detail)],
                )
        with self.subTest(label="pack-idiom-control"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    WEB_LIB,
                    '| I1 | old form | new form | READ | P1 | "three quoted words" |',
                    f"| I1 | old form | new form {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])

    def test_runs_and_pages_declared_and_used(self) -> None:
        lib = WEB_LIB
        with self.subTest("unused-r2"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |\n",
                    "| R1 | pkg 1.0.0 | 2026-11-12 | `echo ok` | ok |\n| R2 | pkg 2.0.0 | 2026-11-12 | `echo ok` | ok |\n",
                )
            )
            n = sup.line_of(root, WEB, "| R2 |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "unused", n, "run R2 is cited by no row")],
            )
        with self.subTest(label="runs-no-obs"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| S2 | An observed statement. | OBSERVED | R1 | - |",
                    '| S2 | An observed statement. | READ | P1 | "three quoted words" |',
                )
            )
            m = sup.line_of(root, WEB, "| R1 | pkg 1.0.0 |")
            runs_sub = sup.line_of(root, WEB, "### Runs")
            # Plan list (no READ-on-R1 source line).
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "subsection",
                        runs_sub,
                        'section has a "Runs" subsection but no OBSERVED row',
                    ),
                    sup.fail_line(WEB, "unused", m, "run R1 is cited by no row"),
                ],
            )
        with self.subTest(label="obs-row-removed"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| S2 | An observed statement. | OBSERVED | R1 | - |\n",
                    "",
                )
            )
            m = sup.line_of(root, WEB, "| R1 | pkg 1.0.0 |")
            runs_sub = sup.line_of(root, WEB, "### Runs")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "subsection",
                        runs_sub,
                        'section has a "Runs" subsection but no OBSERVED row',
                    ),
                    sup.fail_line(WEB, "unused", m, "run R1 is cited by no row"),
                ],
            )
        with self.subTest(label="p2-pack-control"):

            def plant_p2_pack(r: Path) -> None:
                sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |\n"
                    "| P2 | https://deck.gl/docs/whats-new | Other page | 2026-11-12 |",
                )
                sup.edit_in(
                    r,
                    WEB,
                    lib,
                    f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |",
                    f"| S3 | A pack statement on page P2: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |",
                )

            root = self._plant(plant_p2_pack)
            self.assertEqual(sup.fails(sup.run(root)), [])
        with self.subTest("unused-p2"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |",
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |\n| P2 | https://deck.gl/docs/whats-new | Other page | 2026-11-12 |",
                )
            )
            n = sup.line_of(root, WEB, "| P2 |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "unused", n, "page P2 is cited by no row")],
            )

    def test_claim_words(self) -> None:
        lib = WEB_LIB
        for word in tables.CLAIM_WORDS:
            with self.subTest(word=word):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, w=word: sup.edit_in(
                            r,
                            WEB,
                            lib,
                            "| S1 | A read statement. | READ |",
                            f"| S1 | Statement with {w} here. | READ |",
                        ),
                    )
                )
                n = sup.line_of(root, WEB, f"| S1 | Statement with {word}")
                self.assertEqual(
                    sup.fails(sup.run(root)),
                    [sup.fail_line(WEB, "claim-word", n, f'S1: word "{word.lower()}"')],
                )
        with self.subTest(label="idiom-fast-earlier"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| I1 | old form | new form | READ |",
                    "| I1 | The code is fast. | new form | READ |",
                )
            )
            n = sup.line_of(root, WEB, "| I1 | The code is fast.")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "claim-word", n, 'I1: word "fast"')],
            )
        with self.subTest(label="works-capitalized"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| S1 | A read statement. | READ |",
                    "| S1 | It Works well. | READ |",
                )
            )
            n = sup.line_of(root, WEB, "| S1 | It Works well.")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "claim-word", n, 'S1: word "works"')],
            )
        with self.subTest(label="idiom-fast-current"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| I1 | old form | new form | READ |",
                    "| I1 | old form | The code is fast. | READ |",
                )
            )
            n = sup.line_of(root, WEB, "| I1 | old form | The code is fast.")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "claim-word", n, 'I1: word "fast"')],
            )
        with self.subTest(label="control-word-in-quote"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    '| S1 | A read statement. | READ | P1 | "three quoted words" |',
                    '| S1 | A read statement. | READ | P1 | "works well here today" |',
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])
        with self.subTest(label="control-fastest-in-statement"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| S1 | A read statement. | READ |",
                    "| S1 | The fastest path wins. | READ |",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])
        with self.subTest(label="control-fast-inside-verified-anchor"):

            def plant_anchor(r: Path) -> None:
                sup.edit(
                    r,
                    "docs/stub.md",
                    "| First row | a value |",
                    "| First row | a value |\n| Fast mode | a value |",
                )
                sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| S1 | A read statement. | READ |",
                    "| S1 | The pack names the row "
                    '(docs/stub.md section "Tables" row "Fast mode"). | READ |',
                )

            root = self._plant(plant_anchor)
            self.assertEqual(sup.fails(sup.run(root)), [])
        with self.subTest(label="control-best-in-pages-title"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl |",
                    "| P1 | https://deck.gl/docs/whats-new | The best page title |",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])

    def test_confirmation(self) -> None:
        lib = DOCS_LIB
        field = DUCK_FIELD1
        confirm_header = "| Field | Value | Rows in pins.toml | Pack source |"
        with self.subTest(label="remove-field"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    DOCS,
                    lib,
                    f"| {field} | {tables.CONFIRMED} | - | {PACK_LINE} |\n",
                    "",
                )
            )
            t = sup.line_of(root, DOCS, confirm_header)
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(DOCS, "confirmation", t, f'missing field "{field}"')],
            )
        with self.subTest(label="rename-field"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    DOCS,
                    lib,
                    f"| {field} | {tables.CONFIRMED} | - | {PACK_LINE} |",
                    f"| Renamed field | not yet confirmed | - | {PACK_LINE} |",
                )
            )
            t = sup.line_of(root, DOCS, confirm_header)
            n = sup.line_of(root, DOCS, "| Renamed field |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(DOCS, "confirmation", t, f'missing field "{field}"'),
                    sup.fail_line(
                        DOCS, "confirmation", n, 'unknown field "Renamed field"'
                    ),
                ],
            )
        with self.subTest(label="duplicate-field"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    DOCS,
                    lib,
                    f"| {field} | {tables.CONFIRMED} | - | {PACK_LINE} |\n",
                    f"| {field} | {tables.CONFIRMED} | - | {PACK_LINE} |\n"
                    f"| {field} | {tables.CONFIRMED} | - | {PACK_LINE} |\n",
                )
            )
            n = sup.line_of(root, DOCS, f"| {field} |", index=1)
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(DOCS, "confirmation", n, f'repeated field "{field}"')],
            )
        for label, value in (
            ("confirmed-value", "confirmed"),
            ("not-yet-confirmed-value", "Not yet confirmed"),
            ("empty-value", ""),
        ):
            with self.subTest(label=label):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, v=value: sup.edit_in(
                            r,
                            DOCS,
                            lib,
                            f"| {field} | {tables.CONFIRMED} | - | {PACK_LINE} |",
                            f"| {field} | {v} | - | {PACK_LINE} |",
                        ),
                    )
                )
                n = sup.line_of(root, DOCS, f"| {field} |")
                self.assertEqual(
                    sup.fails(sup.run(root)),
                    [
                        sup.fail_line(
                            DOCS,
                            "confirmation",
                            n,
                            f'field "{field}": value "{value}" is not "{tables.CONFIRMED}"',
                        )
                    ],
                )

    def test_pins_rows(self) -> None:
        lib = DOCS_LIB
        row_line = f"| {DUCK_FIELD0} | {tables.CONFIRMED} | duckdb | {PACK_LINE} |"
        pins_cases = (
            ("claude-modle", "claude-modle"),
            ("a,b", "a,b"),
            ("duckdb-comma", "duckdb,"),
            ("dash", "-"),
        )
        for label, cell in pins_cases:
            with self.subTest(label=label):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, c=cell: sup.edit_in(
                            r,
                            DOCS,
                            lib,
                            row_line,
                            f"| {DUCK_FIELD0} | {tables.CONFIRMED} | {c} | {PACK_LINE} |",
                        ),
                    )
                )
                t = sup.line_of(
                    root, DOCS, "| Field | Value | Rows in pins.toml | Pack source |"
                )
                n = sup.line_of(root, DOCS, f"| {DUCK_FIELD0} |")
                if cell == "-":
                    self.assertEqual(
                        sup.fails(sup.run(root)),
                        [
                            sup.fail_line(
                                DOCS,
                                "pins-row",
                                t,
                                'section cites no row "duckdb"',
                            )
                        ],
                    )
                else:
                    self.assertEqual(
                        sup.fails(sup.run(root)),
                        [
                            sup.fail_line(
                                DOCS,
                                "pins-row",
                                t,
                                'section cites no row "duckdb"',
                            ),
                            sup.fail_line(
                                DOCS,
                                "pins-row",
                                n,
                                f'field "{DUCK_FIELD0}": "{cell}" is not a component of pins.toml',
                            ),
                        ],
                    )
        with self.subTest(label="missing-duckdb-row"):
            folder, root = sup.fresh_root()
            self.addCleanup(folder.cleanup)
            text = (
                (root / tables.PINS)
                .read_text()
                .replace('name = "duckdb"', 'name = "duckdb-removed"')
            )
            (root / tables.PINS).write_text(text)
            n = sup.line_of(root, DOCS, f"| {DUCK_FIELD0} |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        DOCS,
                        "pins-row",
                        n,
                        f'field "{DUCK_FIELD0}": "duckdb" is not a component of pins.toml',
                    )
                ],
            )
        with self.subTest(label="control-missing-other-row"):
            folder, root = sup.fresh_root()
            self.addCleanup(folder.cleanup)
            text = (
                (root / tables.PINS)
                .read_text()
                .replace('name = "other"', 'name = "other-removed"')
            )
            (root / tables.PINS).write_text(text)
            self.assertEqual(sup.fails(sup.run(root)), [])

    def test_output_order_and_summary(self) -> None:
        with self.subTest(label="multi-failures-ordered"):
            folder, root = sup.fresh_root()
            self.addCleanup(folder.cleanup)
            (root / tables.PINS).unlink()
            sup.edit(root, WEB, tables.LINKS[WEB], "../docs/10_FRONTEND.md")
            sup.edit_in(
                root,
                WEB,
                WEB_LIB,
                "| S1 | A read statement. | READ | P1 |",
                "| S1 | A read statement. | READ | P99 |",
            )
            sup.edit(
                root,
                WEB,
                f"| A claim | {PACK_LINE} |",
                f"| https://example.org/x | {PACK_LINE} |",
            )
            sup.edit_in(
                root,
                DOCS,
                "Claude API",
                "| S1 | A read statement. | READ | P1 |",
                "| S1 | A read statement. | READ | P97 |",
            )
            lines = sup.run(root)
            n_p99 = sup.line_of(root, WEB, "| P99 |")
            n_addr = sup.line_of(root, WEB, "https://example.org/x |")
            n_p97 = sup.line_of(root, DOCS, "| P97 |")
            link = tables.LINKS[WEB]
            self.assertEqual(
                lines,
                [
                    sup.fail_line(tables.PINS, "input", None, "missing"),
                    sup.fail_line(WEB, "cross-link", 1, f"no link to {link}"),
                    sup.fail_line(
                        WEB,
                        "source",
                        n_p99,
                        'S1: READ source "P99" is not a page id of this section',
                    ),
                    sup.fail_line(
                        WEB,
                        "address",
                        n_addr,
                        "https://example.org/x: not on the list of official addresses",
                    ),
                    sup.fail_line(
                        DOCS,
                        "source",
                        n_p97,
                        'S1: READ source "P97" is not a page id of this section',
                    ),
                    "checked 2 files, 6 libraries, 81 rows: 5 failure(s)",
                ],
            )
        with self.subTest(label="docs-p97-only"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    DOCS,
                    "Claude API",
                    "| S1 | A read statement. | READ | P1 |",
                    "| S1 | A read statement. | READ | P97 |",
                )
            )
            n = sup.line_of(root, DOCS, "| P97 |")
            lines = sup.run(root)
            self.assertEqual(
                lines,
                [
                    sup.fail_line(
                        DOCS,
                        "source",
                        n,
                        'S1: READ source "P97" is not a page id of this section',
                    ),
                    "checked 2 files, 6 libraries, 81 rows: 1 failure(s)",
                ],
            )
        with self.subTest(label="cross-link-before-date-header"):
            folder, root = sup.fresh_root()
            self.addCleanup(folder.cleanup)
            sup.edit(root, WEB, tables.LINKS[WEB], "../docs/10_FRONTEND.md")
            sup.edit(root, WEB, "| Date | 2026-11-12 |", "| Bad | x |")
            lines = sup.run(root)
            link = tables.LINKS[WEB]
            self.assertEqual(
                sup.fails(lines),
                [
                    sup.fail_line(WEB, "cross-link", 1, f"no link to {link}"),
                    sup.fail_line(
                        WEB, "date", 1, 'no valid "| Date |" row in the header table'
                    ),
                ],
            )
            cross = lines.index(
                sup.fail_line(WEB, "cross-link", 1, f"no link to {link}")
            )
            date = lines.index(
                sup.fail_line(
                    WEB, "date", 1, 'no valid "| Date |" row in the header table'
                )
            )
            self.assertLess(cross, date)

    def test_prose(self) -> None:
        lib = WEB_LIB

        def prose_fail(root: Path, needle: str, index: int = 0) -> list[str]:
            n = sup.line_of(root, WEB, needle, index=index)
            return [sup.fail_line(WEB, "prose", n, PROSE)]

        with self.subTest(label="sentence-after-opening"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "Used here: a fixture.\n",
                    "Used here: a fixture.\nExtra sentence.\n",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "Extra sentence.")
            )
        with self.subTest(label="second-opening-line"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "Used here: a fixture.\n",
                    "Used here: a fixture.\nUsed here: again.\n",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "Used here: again.")
            )
        with self.subTest(label="claims-here-opening"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "Used here: a fixture.\n",
                    "Claims here: none.\n",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), prose_fail(root, "Claims here:"))
        with self.subTest(label="setup-in-statements"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "### Statements\n\n",
                    "### Statements\n\nSetup of a claim.\n\n",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "Setup of a claim.")
            )
        with self.subTest(label="control-setup-in-runs"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "### Runs\n\n",
                    "### Runs\n\nSetup, in an empty folder: none.\n\n",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])
        with self.subTest(label="setup-line-twice"):
            setup = "Setup, in an empty folder: none.\n"
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "### Runs\n\n",
                    f"### Runs\n\n{setup}{setup}",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)),
                prose_fail(root, "Setup, in an empty folder: none.", index=1),
            )
        with self.subTest(label="table-after-statements"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |\n\n### Slice",
                    f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |\n\n"
                    "| Extra | Col |\n|---|---|\n| a | b |\n\n### Slice",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "| Extra | Col |")
            )
        with self.subTest(label="table-before-first-heading"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "Used here: a fixture.\n\n### Pages",
                    "Used here: a fixture.\n\n| Extra | Col |\n|---|---|\n| a | b |\n\n### Pages",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "| Extra | Col |")
            )
        with self.subTest(label="indented-table-row"):
            s3 = f"| S3 | A pack statement: {tables.UNVERIFIED}. | PACK | {PACK_LINE} | - |"
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    s3,
                    "  " + s3,
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)),
                prose_fail(root, "  | S3 | A pack statement:"),
            )
        with self.subTest(label="level-four-heading"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    lib,
                    "Used here: a fixture.\n",
                    "Used here: a fixture.\n\n#### Hidden claim here\n",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "#### Hidden claim here")
            )
        with self.subTest(label="paragraph-in-coverage"):
            root = self._plant(
                lambda r: sup.edit(
                    r,
                    WEB,
                    f"## {tables.COVERAGE}\n\n| Pack claim",
                    f"## {tables.COVERAGE}\n\nA paragraph here.\n\n| Pack claim",
                )
            )
            self.assertEqual(
                sup.fails(sup.run(root)), prose_fail(root, "A paragraph here.")
            )
        with self.subTest(label="control-second-how-paragraph"):
            root = self._plant(
                lambda r: sup.edit(
                    r,
                    WEB,
                    f"## {tables.HOW}\n\nFixture.",
                    f"## {tables.HOW}\n\nFixture.\n\nSecond paragraph.\n",
                )
            )
            self.assertEqual(sup.fails(sup.run(root)), [])

    def test_coverage(self) -> None:
        with self.subTest(label="empty-claim"):
            root = self._plant(
                lambda r: sup.edit(
                    r,
                    WEB,
                    COVERAGE_ROW1,
                    f"|  | {PACK_LINE} | {WEB_LIB0} S1; {WEB_LIB1} I1 |",
                )
            )
            n = sup.line_of(root, WEB, f"|  | {PACK_LINE} |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "coverage", n, "row 1: claim is empty")],
            )
        where_cases = (
            (
                "other-lib-s1",
                "Other lib S1",
                'row 1: "Other lib S1" is not a row of this file',
            ),
            (
                "maplibre-s9",
                f"{WEB_LIB0} S9",
                f'row 1: "{WEB_LIB0} S9" is not a row of this file',
            ),
            (
                "maplibre-x1",
                f"{WEB_LIB0} X1",
                f'row 1: "{WEB_LIB0} X1" is not a row of this file',
            ),
            (
                "duckdb-other-file",
                "DuckDB 2.0 S1",
                'row 1: "DuckDB 2.0 S1" is not a row of this file',
            ),
            (
                "comma-joined-items",
                f"{WEB_LIB0} S1, {WEB_LIB1} I1",
                f'row 1: "{WEB_LIB0} S1, {WEB_LIB1} I1" is not a row of this file',
            ),
        )
        for label, where, detail in where_cases:
            with self.subTest(label=label):
                root = self._plant(
                    cast(
                        Callable[[Path], None],
                        lambda r, w=where: sup.edit(
                            r,
                            WEB,
                            COVERAGE_ROW1,
                            f"| A claim | {PACK_LINE} | {w} |",
                        ),
                    )
                )
                n = sup.line_of(root, WEB, f"| A claim | {PACK_LINE} | {where}")
                self.assertEqual(
                    sup.fails(sup.run(root)),
                    [sup.fail_line(WEB, "coverage", n, detail)],
                )
        with self.subTest(label="row2-not-covered-short"):
            root = self._plant(
                lambda r: sup.edit(
                    r,
                    WEB,
                    COVERAGE_ROW2,
                    f"| Another claim | {AGENTS_CITE} | not covered: no |",
                )
            )
            n = sup.line_of(root, WEB, "not covered: no |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "coverage",
                        n,
                        'row 2: reason of "not covered:" has under 3 words',
                    )
                ],
            )
        with self.subTest(label="row2-nothing"):
            root = self._plant(
                lambda r: sup.edit(
                    r,
                    WEB,
                    COVERAGE_ROW2,
                    f"| Another claim | {AGENTS_CITE} | nothing |",
                )
            )
            n = sup.line_of(root, WEB, f"| Another claim | {AGENTS_CITE} | nothing |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "coverage",
                        n,
                        'row 2: "nothing" is not a row of this file',
                    )
                ],
            )
        with self.subTest(label="table-no-rows"):
            root = self._plant(
                lambda r: sup.edit(
                    r,
                    WEB,
                    f"{COVERAGE_ROW1}\n{COVERAGE_ROW2}\n",
                    "",
                )
            )
            t = sup.line_of(root, WEB, "| Pack claim | Pack source | Where |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "table",
                        t,
                        f'"{tables.COVERAGE}" has no row',
                    )
                ],
            )
        cov_block = (
            f"## {tables.COVERAGE}\n\n"
            "| Pack claim | Pack source | Where |\n"
            "|---|---|---|\n"
            f"{COVERAGE_ROW1}\n"
            f"{COVERAGE_ROW2}\n"
        )
        with self.subTest(label="section-no-table"):
            root = self._plant(
                lambda r: sup.edit(r, WEB, cov_block, f"## {tables.COVERAGE}\n\n")
            )
            h = sup.heading_line(root, WEB, tables.COVERAGE)
            self.assertEqual(
                sup.fails(sup.run(root)),
                [sup.fail_line(WEB, "coverage", h, "section has no table")],
            )
        with self.subTest(label="statements-header-changed"):
            root = self._plant(
                lambda r: sup.edit_in(
                    r,
                    WEB,
                    WEB_LIB,
                    "| Id | Statement | Kind | Source | Quote |",
                    "| Id | Claim | Kind | Source | Quote |",
                )
            )
            t = sup.line_of(root, WEB, "| Id | Claim | Kind | Source | Quote |")
            self.assertEqual(
                sup.fails(sup.run(root)),
                [
                    sup.fail_line(
                        WEB,
                        "table",
                        t,
                        'header is not "| Id | Statement | Kind | Source | Quote |"',
                    )
                ],
            )
