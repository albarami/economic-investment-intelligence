"""The version-pin check against the real repository."""

from __future__ import annotations

import json
import os
import sys
import tomllib
import unittest
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base

REPO = Path(__file__).resolve().parents[2]


class RealTree(unittest.TestCase):
    def test_real_repository_passes(self) -> None:
        proc = base.cli([], {"PATH": os.environ.get("PATH", "")})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertTrue(lines)
        self.assertFalse(any(line.startswith("FAIL") for line in lines))
        last = lines[-1]
        self.assertTrue(last.startswith("checked "))
        self.assertTrue(last.endswith("components: OK"))

    def test_planted_drift_in_a_copy_of_the_real_tree(self) -> None:
        import versions_record

        self.assertTrue((REPO / "pins.toml").is_file())
        components, failures, _count = versions_record.load_record(REPO)
        self.assertEqual(failures, [])
        rows = {item.name: item for item in components}
        rels = self._closed_set(rows)
        before = base.closed_set_digest(REPO, rels)
        folder = __import__("tempfile").TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        copy = Path(folder.name) / "tree"
        copy.mkdir()
        for rel in rels:
            source = REPO / rel
            target = copy / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            __import__("shutil").copy2(source, target)
        base.git_init(copy)
        pins = {name: rows[name].pin for name in ("react", "pytest", "typescript")}
        retreats = {name: rows[name].retreat for name in pins}
        for name, row in rows.items():
            if name in pins and (row.state != "installed" or not _exact(row.pin)):
                self.fail(f"row {name} is not an installed exact pin")
        bumped = {name: _bump(pin) for name, pin in pins.items()}
        package = json.loads(
            (copy / "web" / "package.json").read_text(encoding="utf-8")
        )
        section = ""
        for key in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        ):
            block = package.get(key)
            if isinstance(block, dict) and "react" in block:
                section = key
                block["react"] = "^" + pins["react"]
        if not section:
            self.fail("react section missing")
        base.write(copy, "web/package.json", json.dumps(package) + "\n")
        lock = (copy / "uv.lock").read_text(encoding="utf-8")
        needle = 'name = "pytest"\nversion = "' + pins["pytest"] + '"'
        if lock.count(needle) != 1:
            self.fail("pytest lock entry is not unique")
        lock = lock.replace(
            needle, 'name = "pytest"\nversion = "' + bumped["pytest"] + '"', 1
        )
        base.write(copy, "uv.lock", lock)
        base.edit_row(
            copy,
            'name = "typescript"',
            'pin = "' + pins["typescript"] + '"',
            'pin = "' + bumped["typescript"] + '"',
        )
        proc = base.cli(["--root", str(copy)], {"PATH": os.environ.get("PATH", "")})
        self.assertEqual(proc.returncode, 1, proc.stdout)
        lines = proc.stdout.splitlines()
        typescript_section = ""
        fresh = json.loads((REPO / "web" / "package.json").read_text(encoding="utf-8"))
        for key in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        ):
            block = fresh.get(key)
            if isinstance(block, dict) and "typescript" in block:
                typescript_section = key
        expected = [
            "FAIL manifest-version: web/package.json: "
            f"{section}.react: ^{pins['react']}: neither pin {pins['react']} "
            f"nor retreat {retreats['react']}",
            "FAIL manifest-version: web/package.json: "
            f"{typescript_section}.typescript: {pins['typescript']}: "
            f"neither pin {bumped['typescript']} nor retreat {retreats['typescript']}",
            "FAIL lock-version: uv.lock: pytest "
            f"{bumped['pytest']}: neither pin {pins['pytest']} nor retreat {retreats['pytest']}",
            "FAIL lock-version: web/package-lock.json: node_modules/typescript: "
            f"{pins['typescript']}: neither pin {bumped['typescript']} "
            f"nor retreat {retreats['typescript']}",
        ]
        self.assertEqual(lines[: len(expected)], expected)
        for extra in lines[len(expected) : -1]:
            self.assertTrue(
                extra.startswith("FAIL lock-version: web/package-lock.json:")
            )
            self.assertIn("typescript", extra)
        self.assertEqual(base.closed_set_digest(REPO, rels), before)

    def _closed_set(self, rows: Mapping[str, object]) -> list[str]:
        root_doc = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
        workspace = root_doc["tool"]["uv"]["workspace"]["members"]
        rels = [
            "pins.toml",
            ".python-version",
            ".nvmrc",
            "pyproject.toml",
            "uv.lock",
            "web/package.json",
            "web/package-lock.json",
        ]
        rels.extend(f"{member}/pyproject.toml" for member in workspace)
        for row in rows.values():
            cite = getattr(row, "cite", "")
            for item in str(cite).split("; "):
                path = item.split(" line ", 1)[0]
                if path and path not in rels:
                    rels.append(path)
        return rels


def _exact(pin: str) -> bool:
    import versions_record

    return versions_record.version_matches(pin, pin)


def _bump(pin: str) -> str:
    parts = pin.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)
