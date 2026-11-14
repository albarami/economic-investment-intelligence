"""S1-T10: planted boundary, documentation, and file-scan regressions."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_boundary_cases as cases
import import_boundary_guard as boundary
import test_check_docs_exceptions as doc_cases

import check_docs


class Followup(unittest.TestCase):
    def test_earthdata_product_and_core(self) -> None:
        for package in ("eii_product", "eii_core"):
            with self.subTest(package=package), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                cases.write_planted(root, package, "# EARTHDATA_API_KEY\n")
                failures, notes = boundary.check_imports(root)
                self.assertEqual(
                    failures,
                    [
                        cases.expected_env_name_line(
                            cases.planted_rel_path(package), 1, "EARTHDATA_API_KEY"
                        )
                    ],
                )
                self.assertEqual(notes, [])

    def test_earthdata_custodian_and_tooling_tomtom_product_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            cases.write_planted(root, "eii_custodian", "# EARTHDATA_API_KEY\n")
            cases.write_planted(root, "eii_product", "# TOMTOM_API_KEY\n")
            (root / "scripts").mkdir()
            (root / "scripts" / "fetch.py").write_text(
                "# EARTHDATA_API_KEY\n", encoding="utf-8"
            )
            self.assertEqual(boundary.check_imports(root), ([], []))

    def test_hardening_file_required(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in check_docs.REQUIRED_FILES:
                if name != "docs/17_DEPLOYMENT_HARDENING.md":
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            (root / "docs" / "decisions").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "decisions" / "0001-example.md").touch()
            failures: list[str] = []
            with patch.object(check_docs, "ROOT", root):
                check_docs.check_required(failures)
            self.assertEqual(
                failures,
                ["FAIL required-file: docs/17_DEPLOYMENT_HARDENING.md: missing"],
            )

    def test_duplicate_hardening_identifier(self) -> None:
        failures: list[str] = []
        check_docs.check_requirement_ids(
            {
                check_docs.ROOT / "docs/17_DEPLOYMENT_HARDENING.md": [
                    "| DHA-01 | first |",
                    "| DHA-01 | duplicate |",
                ]
            },
            failures,
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("DHA-01 is already defined", failures[0])

    def test_unknown_hardening_identifier(self) -> None:
        failures: list[str] = []
        check_docs.check_requirement_ids(
            {
                check_docs.ROOT / "docs/17_DEPLOYMENT_HARDENING.md": [
                    "| DHA-01 | defined |",
                    "See DHA-9999 for details.",
                ]
            },
            failures,
        )
        self.assertEqual(
            failures,
            [
                "FAIL requirement-id: docs/17_DEPLOYMENT_HARDENING.md:2: "
                "DHA-9999 is referenced but defined nowhere"
            ],
        )


class AllListedRegularFilesScan(doc_cases.InProcess):
    def test_eight_digit_run_in_mjs_and_private_pattern_in_non_utf8(self) -> None:
        files = doc_cases.base()
        digits = "1234" + "5678"
        other = doc_cases.OTHER
        files["tables/probe.s1unlisted"] = f"{digits}\n"
        files["web/scripts/probe.mjs"] = f"export const sample = '{digits}';\n"
        files["tables/latin1.bin"] = (
            b"header\xff\n" + other.lower().encode("ascii") + b"\n"
        )
        files["tables/utf16.bin"] = f"id\n{other.lower()}\n".encode("utf-16")
        code, stdout, stderr, _ = self.run_main(
            files, [doc_cases.NAME.lower(), other.lower()]
        )
        self.assertEqual(stderr, "")
        self.assertEqual(code, 1)
        why = "identifier-shaped number (exactly 8 or 11 digits)"
        expected = sorted(
            [
                f"FAIL identifier-number: web/scripts/probe.mjs:1: {why}: {digits}",
                f"FAIL identifier-number: tables/probe.s1unlisted:1: {why}: {digits}",
                "FAIL extra-2: tables/latin1.bin:2: extra forbidden pattern: "
                "(matched text not shown)",
                "FAIL extra-2: tables/utf16.bin:2: extra forbidden pattern: "
                "(matched text not shown)",
            ]
        )
        self.assertEqual(doc_cases.fail_lines(stdout), expected)

    def test_missing_private_pattern_file_fails_closed(self) -> None:
        self.assert_unreadable_private_patterns(directory=False)

    def test_directory_private_pattern_file_fails_closed(self) -> None:
        self.assert_unreadable_private_patterns(directory=True)

    def assert_unreadable_private_patterns(self, *, directory: bool) -> None:
        files = doc_cases.base()
        with tempfile.TemporaryDirectory() as tmp:
            secret_dir = Path(tmp) / f"private-{doc_cases.OTHER.lower()}"
            secret_dir.mkdir()
            pattern_file = secret_dir / "patterns.txt"
            if directory:
                pattern_file.mkdir()
            code, stdout, stderr, _ = self.run_main(
                files,
                None,
                patches=lambda _root, _outside: [
                    patch.dict(
                        os.environ,
                        {"EII_FORBIDDEN_PATTERNS_FILE": str(pattern_file)},
                    )
                ],
            )
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertEqual(
                doc_cases.fail_lines(stdout),
                [
                    "FAIL extra-patterns: EII_FORBIDDEN_PATTERNS_FILE names no "
                    "readable file"
                ],
            )
            both = (stdout + stderr).casefold()
            self.assertNotIn(str(pattern_file).casefold(), both)
            for part in pattern_file.parts:
                if part != pattern_file.anchor:
                    self.assertNotIn(part.casefold(), both)


if __name__ == "__main__":
    unittest.main()
