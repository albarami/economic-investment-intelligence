#!/usr/bin/env python3
"""Real-repository and wiring checks for import-boundary guards."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import import_boundary_cases as cases
import import_boundary_child as child
import import_boundary_guard as guard

NOTES: list[str] = []


def tearDownModule() -> None:
    """Print collected NOTE lines from the real tree after the last test."""
    if NOTES:
        for line in NOTES:
            print(line, file=sys.stderr)


def _source_tree_paths(root: Path) -> list[Path]:
    """Return the three package source trees under ``root``."""
    return [root / rel for _pkg, rel in guard.PACKAGES]


def _tree_fingerprint(root: Path) -> list[tuple[str, str]]:
    """Return a sorted (relative path, sha256) listing of files under source trees."""
    entries: list[tuple[str, str]] = []
    for tree in _source_tree_paths(root):
        if not tree.is_dir():
            continue
        for path in sorted(tree.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_dir():
                entries.append((rel + "/", ""))
            elif path.is_file() and not path.is_symlink():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append((rel, digest))
    entries.sort(key=lambda row: row[0])
    return entries


class ImportBoundaryRealTest(unittest.TestCase):
    """Checks against the working tree and metadata wiring."""

    def test_real_tree_static_passes(self) -> None:
        """The real repository passes the static import-boundary guard."""
        failures, note_lines = guard.check_imports(cases.ROOT)
        self.assertEqual(
            failures,
            [],
            "\n".join(failures),
        )
        NOTES.extend(note_lines)

    def test_real_tree_fresh_interpreters_pass(self) -> None:
        """The real repository passes the fresh-interpreter guard."""
        failures = child.check_fresh(cases.ROOT)
        self.assertEqual(failures, [], "\n".join(failures))

    def test_clean_boundary_fixture_passes(self) -> None:
        """The synthetic clean fixture passes both guards."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root, gateway=True)
            self.assertEqual(guard.check_imports(root), ([], []))
            self.assertEqual(child.check_fresh(root), [])

    def test_guard_changes_nothing(self) -> None:
        """Guards do not mutate the trees they scan."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root, gateway=True)
            before_fixture = _tree_fingerprint(root)
            guard.check_imports(root)
            child.check_fresh(root)
            after_fixture = _tree_fingerprint(root)
            self.assertEqual(before_fixture, after_fixture)
            self.assertFalse(any("__pycache__" in row[0] for row in after_fixture))

        before_real = _tree_fingerprint(cases.ROOT)
        guard.check_imports(cases.ROOT)
        child.check_fresh(cases.ROOT)
        after_real = _tree_fingerprint(cases.ROOT)
        self.assertEqual(before_real, after_real)

    def test_metadata_guard_is_wired(self) -> None:
        """Workspace metadata guard is reachable from this suite."""
        import test_workspace_metadata as meta
        import workspace_guard as workspace

        count = 0
        with self.subTest(case="real_workspace"):
            self.assertEqual(workspace.check_workspace(cases.ROOT), [])
            count += 1
        with self.subTest(case="forbidden_dependency"):
            with tempfile.TemporaryDirectory() as folder:
                fixture = meta.make_fixture(Path(folder))
                product_toml = fixture / "product/pyproject.toml"
                data = tomllib.loads(product_toml.read_text(encoding="utf-8"))
                deps = list(data.get("project", {}).get("dependencies", []))
                deps.append("eii-custodian")
                project = dict(data.get("project", {}))
                project["dependencies"] = deps
                data["project"] = project
                product_toml.write_text(
                    workspace.dump_toml(data),
                    encoding="utf-8",
                )
                self.assertEqual(
                    workspace.check_workspace(fixture),
                    [
                        "FAIL dependency-edge: product/pyproject.toml: "
                        "project.dependencies names eii-custodian"
                    ],
                )
            count += 1
        self.assertEqual(count, 2)

    def test_tables_have_their_sizes(self) -> None:
        """Shared tables and guard constants have their documented sizes."""
        self.assertEqual(len(cases.MECHANISMS), 30)
        self.assertEqual(len(cases.EDGES), 7)
        self.assertEqual(len(cases.ALLOWED), 5)
        self.assertEqual(len(cases.NOTE_CASES), 21)
        self.assertEqual(len(cases.NOT_JUDGED), 30)
        self.assertEqual(len(cases.CHILD_CASES), 10)
        self.assertEqual(len(guard.PACKAGES), 3)
        self.assertEqual(
            tuple(guard.FORBIDDEN),
            tuple(pkg for pkg, _rel in guard.PACKAGES),
        )


if __name__ == "__main__":
    unittest.main()
