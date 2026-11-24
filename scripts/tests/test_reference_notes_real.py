"""Real-tree and CLI tests for scripts/check_reference_notes.py."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_notes_support as sup

import reference_notes_tables as tables

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_reference_notes.py"

REAL_NOTE_PATHS = (
    tables.WEB,
    tables.DOCS,
    tables.PINS,
    "scripts/check_reference_notes.py",
    "scripts/reference_notes_assigned.py",
    "scripts/reference_notes_parse.py",
    "scripts/reference_notes_report.py",
    "scripts/reference_notes_tables.py",
)


class RealNotes(unittest.TestCase):
    def test_p24_summary_rows_match_local_reading_closures(self) -> None:
        text = (REPO / "OPEN_ITEMS.md").read_text()
        expected = (
            "| OI-200 | **CLOSED LOCALLY 2026-11-20 (P24)**. DuckDB P13/P14 and S29\u2013S32 of docs/REFERENCE_NOTES.md record the two official Parquet-page readings with publisher, quotations, date and fetched-body hashes; R10/S28 stay OBSERVED. Independent another-maker confirmation remains with the lead. Source: OI-200 P24 closure block. |",
            "| OI-224 | **CLOSED LOCALLY 2026-11-20 (P24)**. The `_GEOPARQUET` comment in read.py names publisher, page URL and retrieval date; DuckDB P15/S33 record the quotation and fetched-body hash. Supplies the P2 reading only; OI-202 and the real-file check stay open. Independent another-maker confirmation remains with the lead. Source: OI-224 P24 closure block. |",
        )
        for row in expected:
            with self.subTest(item=row.split(" | ")[0]):
                self.assertEqual(
                    [line for line in text.splitlines() if line.startswith(row[:10])],
                    [row],
                )

    def test_p24_terms_cell_preserves_only_remaining_attribution_hold(self) -> None:
        text = (REPO / "docs/04_PUBLIC_DATA_PACK.md").read_text()
        rows = [
            line
            for line in text.splitlines()
            if line.startswith("| `satellite_cdse_backup` |")
            and "Owner-requested Sentinel-2 L2A" in line
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].split(" | ")[-1],
            "Imagery notice and interface terms read 2026-11-20 (CDSE README D15/D12, fetched-body hashes recorded); complete attribution pending: the read pages supply no complete service-specific display line; `provider_terms`, empty decision_record, commit false; proposed decision 0066 |",
        )

    def test_configuration_repeat_reading_is_explicit(self) -> None:
        text = (REPO / tables.DOCS).read_text()
        start, stop = sup.section_span(text, "DuckDB 2.0")
        block = "\n".join(text.splitlines()[start:stop])
        self.assertIn("P15 intentionally records a separate dated reading of P9", block)
        self.assertIn("both addresses resolve to the same Configuration page", block)

    def test_parquet_official_readings(self) -> None:
        """OI-200: observations cannot stand in for the four owed READ rows."""
        text = (REPO / tables.DOCS).read_text()
        start, stop = sup.section_span(text, "DuckDB 2.0")
        block = "\n".join(text.splitlines()[start:stop])
        for ident, source, subject in (
            ("S29", "P13", "reading and writing Parquet"),
            ("S30", "P14", "parquet_metadata"),
            ("S31", "P14", "parquet_kv_metadata"),
            ("S32", "P14", "geo key"),
        ):
            with self.subTest(ident=ident):
                rows = [
                    line
                    for line in block.splitlines()
                    if line.startswith(f"| {ident} |")
                ]
                self.assertEqual(len(rows), 1, ident)
                self.assertIn(f"| READ | {source} |", rows[0])
                self.assertIn(subject, rows[0])
        for digest in (
            "86eb8f97b400242d4a7682cf5a8f9d5cbdaafb0da18a117319a7cf86a805a51e",
            "931be889d0d0c0e9305e172246bb68bfbb4e56e3a5630fa0f9bd0c59abe11c11",
        ):
            self.assertIn(digest, block)

    def test_geoparquet_setting_official_reading(self) -> None:
        """OI-224: require attributable setting evidence, separate from R10."""
        text = (REPO / tables.DOCS).read_text()
        start, stop = sup.section_span(text, "DuckDB 2.0")
        block = "\n".join(text.splitlines()[start:stop])
        self.assertRegex(
            block,
            r"\| S33 \| [^\n]*enable_geoparquet_conversion[^\n]*\| READ \| P15 \|",
        )
        self.assertIn(
            "50e69320eb7def5d284ba29b92b2082c679d97c1532a7c7413c2663012b8f86f",
            block,
        )
        code = (
            REPO / "custodian/src/eii_custodian/publicdata/places/read.py"
        ).read_text()
        comment = code.split('_GEOPARQUET = "enable_geoparquet_conversion"')[
            0
        ].splitlines()[-4:]
        for attribution in (
            "DuckDB Foundation",
            "https://duckdb.org/docs/2.0/configuration/overview.html",
            "2026-11-20",
        ):
            self.assertIn(attribution, "\n".join(comment))

    def test_real_notes_pass(self) -> None:
        lines = sup.run(REPO)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("checked 2 files, 6 libraries, "))
        self.assertTrue(lines[0].endswith(" rows: OK"))
        count = int(lines[0].split(", ")[2].split()[0])
        self.assertGreater(count, 0)
        self.assertEqual(sup.fails(lines), [])

    def test_cli_exit_codes_and_streams(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = sup.make_root(Path(folder.name) / "tree")
        link = tables.LINKS[tables.WEB]
        usage = "usage: check_reference_notes.py [--root DIR]\n"
        with self.subTest("clean"):
            proc = sup.cli(["--root", str(root)], Path.cwd(), {"PATH": ""})
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(proc.stdout, "checked 2 files, 6 libraries, 81 rows: OK\n")
            self.assertEqual(proc.stderr, "")
        sup.edit(root, tables.WEB, link, "../docs/10_FRONTEND.md")
        with self.subTest("failure"):
            proc = sup.cli(["--root", str(root)], Path.cwd(), {"PATH": ""})
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(
                proc.stdout,
                f"FAIL cross-link: {tables.WEB}:1: no link to {link}\n"
                "checked 2 files, 6 libraries, 81 rows: 1 failure(s)\n",
            )
            self.assertEqual(proc.stderr, "")
        with self.subTest("bogus"):
            proc = sup.cli(["--bogus"], Path.cwd(), {"PATH": ""})
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(proc.stderr, usage)
        with self.subTest("root-alone"):
            proc = sup.cli(["--root"], Path.cwd(), {"PATH": ""})
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(proc.stderr, usage)

    def test_cli_independent_of_working_folder(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        hostile = Path(folder.name) / "hostile"
        hostile.mkdir()
        sup.write(hostile, tables.PINS, "component = [\n")
        sup.write(hostile, tables.WEB, " \n")
        sup.write(
            hostile,
            "tomllib.py",
            "raise ImportError('hostile tomllib')\n",
        )
        good = Path(folder.name) / "tree"
        sup.make_root(good)
        with self.subTest("empty-env"):
            proc = sup.cli(["--root", str(good)], hostile, {})
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(proc.stdout.startswith("checked 2 files, 6 libraries, "))
            self.assertTrue(proc.stdout.endswith(" rows: OK\n"))
            self.assertEqual(proc.stderr, "")
        with self.subTest("hostile-pythonpath"):
            control = sup.cli(
                ["--root", str(good)], hostile, {"PYTHONPATH": str(hostile)}
            )
            if control.returncode == 0 and "tomllib" not in control.stderr:
                self.fail(
                    "control ineffective: the hostile folder did not reach the interpreter"
                )
            self.assertNotEqual(control.returncode, 0)

    def test_no_side_effects(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = sup.make_root(Path(folder.name) / "tree")
        before_tree = sup.tree_digest(root)
        before_real = {rel: sup.file_digest(REPO / rel) for rel in REAL_NOTE_PATHS}
        listing = set(before_tree)
        _ = sup.run(root)
        after_tree = sup.tree_digest(root)
        after_real = {rel: sup.file_digest(REPO / rel) for rel in REAL_NOTE_PATHS}
        self.assertEqual(before_tree, after_tree)
        self.assertEqual(before_real, after_real)
        self.assertEqual(set(after_tree), listing)

    def test_tables_have_their_sizes(self) -> None:
        self.assertEqual(len(tables.LIBRARIES[tables.WEB]), 3)
        self.assertEqual(len(tables.LIBRARIES[tables.DOCS]), 3)
        fields = [len(lib.fields) for lib in tables.LIBRARIES[tables.WEB]] + [
            len(lib.fields) for lib in tables.LIBRARIES[tables.DOCS]
        ]
        self.assertEqual(fields, [6, 6, 3, 7, 4, 5])
        pin_rows = [len(lib.rows) for lib in tables.LIBRARIES[tables.WEB]] + [
            len(lib.rows) for lib in tables.LIBRARIES[tables.DOCS]
        ]
        self.assertEqual(pin_rows, [2, 4, 2, 1, 3, 2])
        self.assertEqual(len(tables.OFFICIAL), 15)
        self.assertEqual(len(tables.CLAIM_WORDS), 13)
        self.assertEqual(len(tables.RULES), 23)
        self.assertEqual(len(tables.TABLES), 5)
        self.assertEqual(len(tables.ASSIGNED_TABLES), 2)
        self.assertEqual(len(tables.ALL_TABLES), 8)
        self.assertEqual(
            tables.ASSIGNED_SUBS,
            ("Pages read", "Runs", "Font weights", "Icon package licence"),
        )
        self.assertEqual(tables.WEIGHTS, ("400", "500", "600"))
        self.assertEqual(
            tuple(tables.FAMILIES), ("IBM Plex Sans", "IBM Plex Sans Arabic")
        )
        self.assertEqual(
            tables.EXTRA_SECTIONS,
            {tables.WEB: (tables.ASSIGNED,), tables.DOCS: ()},
        )
        self.assertEqual(
            tables.ASSIGNED_SENTENCE,
            (
                "The owner decided on 2026-11-11 that the lead assigns each slice S0 "
                "requirement that no task owned to the nearest task; the lead assigned "
                "DES-25 and DES-45 to S0-T13."
            ),
        )
        self.assertEqual(tables.QUOTE_WORDS, (3, 40))
        self.assertEqual(tables.KINDS, ("READ", "OBSERVED", "PACK"))
        self.assertEqual(len(tables.OPENING), 2)
        self.assertEqual(len(tables.SETUP), 2)
        self.assertEqual(len(tables.ASSIGNED_OPENING), 1)
        for libs in tables.LIBRARIES.values():
            for lib in libs:
                self.assertEqual(len(lib.fields), len(set(lib.fields)))
