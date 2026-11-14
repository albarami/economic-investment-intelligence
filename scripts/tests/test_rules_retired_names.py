#!/usr/bin/env python3
"""Repository scan for the retired rules names.

The package suite runs from the package folder alone, so this scan of the
seven roots lives with the cross-plane guards. The spellings stay in the
check's tests. This file reads that tuple and does not repeat it, so the
allow-list remains the check and that test file.
"""

from __future__ import annotations

import ast
import os
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_PATH = (
    REPO_ROOT / "custodian" / "src" / "eii_custodian" / "privacy" / "rules_config.py"
)
SCAN_ROOTS = ("core", "custodian", "product", "gateway", "scripts", "infra", "web")
SKIP_DIRECTORIES = {
    "node_modules",
    "__pycache__",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
}
DOCUMENT_SUFFIXES = {".md", ".rst", ".adoc"}
CODE_SUFFIXES = {
    ".py",
    ".pyi",
    ".toml",
    ".json",
    ".jsonl",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".conf",
    ".mjs",
    ".cjs",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".html",
    ".sql",
    ".sh",
    ".bash",
    ".txt",
    ".xml",
    ".svg",
    ".lock",
}


def _retired_names(repo: Path) -> tuple[str, ...]:
    """Return the retired-name tuple defined by the check's tests."""
    path = repo / "custodian" / "tests" / "test_rules_config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        names = _assigned_retired_names(node)
        if names is not None:
            return names
    raise AssertionError("RETIRED_NAMES missing from the check tests")


def _assigned_retired_names(node: ast.AST) -> tuple[str, ...] | None:
    if not isinstance(node, ast.Assign):
        return None
    if not any(
        isinstance(target, ast.Name) and target.id == "RETIRED_NAMES"
        for target in node.targets
    ):
        return None
    evaluated = ast.literal_eval(node.value)
    if not isinstance(evaluated, tuple):
        raise AssertionError("RETIRED_NAMES is not a tuple")
    names: list[str] = []
    for item in evaluated:
        if not isinstance(item, str) or item == "":
            raise AssertionError("RETIRED_NAMES holds only non-blank text")
        names.append(item)
    if not names:
        raise AssertionError("RETIRED_NAMES is empty")
    return tuple(names)


RETIRED_NAMES = _retired_names(REPO_ROOT)


def _walk_code(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRECTORIES]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() in DOCUMENT_SUFFIXES:
                continue
            if path.suffix.lower() not in CODE_SUFFIXES and path.suffix != "":
                continue
            yield path


def _retired_hits(repo: Path) -> tuple[dict[Path, set[str]], dict[str, int]]:
    hits: dict[Path, set[str]] = {}
    files_read = dict.fromkeys(SCAN_ROOTS, 0)
    for root_name in SCAN_ROOTS:
        root = repo / root_name
        if not root.is_dir():
            continue
        for path in _walk_code(root):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            files_read[root_name] += 1
            present = {name for name in RETIRED_NAMES if name in text}
            if present:
                hits[path.resolve()] = present
    return hits, files_read


def _allowed_retired_path(path: Path, repo: Path) -> bool:
    allowed = {
        CHECK_PATH.resolve(),
        (repo / "custodian" / "tests" / "test_rules_config.py").resolve(),
    }
    return path.resolve() in allowed


class RetiredNameScanTests(unittest.TestCase):
    def test_retired_names_appear_only_in_the_check_and_its_tests(self) -> None:
        """The three retired names occur in the check, and in no other code or configuration."""
        repo = REPO_ROOT
        for root_name in SCAN_ROOTS:
            self.assertTrue((repo / root_name).is_dir())
        hits, files_read = _retired_hits(repo)
        for root_name in SCAN_ROOTS:
            self.assertGreaterEqual(files_read[root_name], 1)
        unexpected = {
            str(path.relative_to(repo)): sorted(names)
            for path, names in hits.items()
            if not _allowed_retired_path(path, repo)
        }
        self.assertEqual(unexpected, {})
        check = CHECK_PATH.resolve()
        for name in RETIRED_NAMES:
            self.assertIn(name, hits[check])
            self.assertIn(name, check.read_text(encoding="utf-8"))

    def test_retired_allow_list_rejects_a_neighbour_and_a_nested_namesake(
        self,
    ) -> None:
        """The three names are allowed only in the check and in the check's tests."""
        repo = REPO_ROOT
        neighbour = repo / "custodian" / "tests" / "test_rules_other.py"
        nested = repo / "custodian" / "tests" / "sub" / "test_rules_config.py"
        designated = repo / "custodian" / "tests" / "test_rules_config.py"
        self.assertIs(_allowed_retired_path(neighbour, repo), False)
        self.assertIs(_allowed_retired_path(nested, repo), False)
        self.assertIs(_allowed_retired_path(designated, repo), True)
        self.assertIs(_allowed_retired_path(CHECK_PATH, repo), True)

    def test_retired_scan_reports_a_plant_in_each_of_the_seven_roots(self) -> None:
        """A retired name planted in one file of each root is reported."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for root_name in SCAN_ROOTS:
                planted_dir = root / root_name
                planted_dir.mkdir()
                (planted_dir / "plant.py").write_text(
                    f"{RETIRED_NAMES[0]}\n",
                    encoding="utf-8",
                )
            hits, files_read = _retired_hits(root)
            reported = {path.relative_to(root).parts[0] for path in hits}
            self.assertEqual(reported, set(SCAN_ROOTS))
            for root_name in SCAN_ROOTS:
                self.assertGreaterEqual(files_read[root_name], 1)
                planted = root / root_name / "plant.py"
                self.assertIn(RETIRED_NAMES[0], hits[planted.resolve()])


if __name__ == "__main__":
    unittest.main()
