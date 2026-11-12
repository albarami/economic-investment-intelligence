"""Shape checks and fields the version-pin check does not judge."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base

S1 = base.summary(1)


class InputRules(unittest.TestCase):
    def test_wrong_shapes(self) -> None:
        cases = (
            (
                "pyproject.toml",
                'requires-python = ">=3.14"\n',
                'requires-python = ">=3.14"\ndependencies = "alpha==1.2.3"\n',
                "project.dependencies is not a list of strings",
            ),
            (
                "pyproject.toml",
                'requires-python = ">=3.14"\n',
                'requires-python = ">=3.14"\ndependencies = [1]\n',
                "project.dependencies is not a list of strings",
            ),
            (
                "pyproject.toml",
                'requires-python = ">=3.14"\n',
                'requires-python = ">=3.14"\noptional-dependencies = []\n',
                "project.optional-dependencies is not a table",
            ),
            (
                "pyproject.toml",
                "[dependency-groups]",
                '[project.optional-dependencies]\nextra = "x"\n\n[dependency-groups]',
                "project.optional-dependencies.extra is not a list of strings",
            ),
            (
                "pyproject.toml",
                "[project]\n"
                'name = "eii-workspace"\n'
                'requires-python = ">=3.14"\n\n'
                "[dependency-groups]\n"
                'dev = ["alpha==1.2.3"]\n',
                "dependency-groups = []\n\n"
                "[project]\n"
                'name = "eii-workspace"\n'
                'requires-python = ">=3.14"\n',
                "dependency-groups is not a table",
            ),
            (
                "pyproject.toml",
                'dev = ["alpha==1.2.3"]',
                'dev = "alpha==1.2.3"',
                "dependency-groups.dev is not a list of strings and tables",
            ),
            (
                "pyproject.toml",
                'dev = ["alpha==1.2.3"]',
                "dev = [1]",
                "dependency-groups.dev is not a list of strings and tables",
            ),
            (
                "pyproject.toml",
                '[tool.uv]\nrequired-version = "==0.11.31"\n\n'
                '[tool.uv.workspace]\nmembers = ["core", "custodian"]\n',
                "[tool]\nuv = 5\n",
                "tool.uv is not a table",
            ),
            (
                "custodian/pyproject.toml",
                '[project]\nname = "eii-custodian"\nrequires-python = ">=3.14"\n'
                'dependencies = ["eii-core"]\n\n',
                'project = "x"\n\n',
                "project is not a table",
            ),
            (
                "uv.lock",
                'name = "alpha"\n',
                "",
                "package[3].name is not a string",
            ),
            (
                "uv.lock",
                'version = "1.2.3"\n',
                "version = 5\n",
                "package[3].version is not a string",
            ),
            (
                "uv.lock",
                'source = { registry = "https://pypi.org/simple" }',
                'source = "x"',
                "package[3].source is not a table",
            ),
        )
        for rel, old, new, detail in cases:
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                base.edit(root, rel, old, new)
                self.assertEqual(
                    base.run(root, path=path), [f"FAIL input: {rel}: {detail}", S1]
                )
        for text, detail in (
            ("version = 1\npackage = 5\n", "package is not an array of tables"),
            ("version = 1\npackage = [1]\n", "package[0] is not a table"),
        ):
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                base.write(root, "uv.lock", text)
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL input: uv.lock: {detail}", S1],
                )
        root, path = base.ready(self)
        base.edit(root, "uv.lock", 'version = "1.2.3"\n', "")
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL lock-version: uv.lock: alpha: entry has no version", S1],
        )
        web = (
            (
                '"dependencies": {"left": "4.5.6"}',
                '"dependencies": []',
                "dependencies is not an object",
            ),
            (
                '"devDependencies": {"@scope/pkg": "1.0.0"}',
                '"devDependencies": "x"',
                "devDependencies is not an object",
            ),
            ('"left": "4.5.6"', '"left": 5', "dependencies.left is not a string"),
            (
                '"engines": {"node": ">=22.12.0 <23"}',
                '"engines": "x"',
                "engines is not an object",
            ),
        )
        for old, new, detail in web:
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                doc_path = root / "web" / "package.json"
                doc_path.write_text(
                    doc_path.read_text(encoding="utf-8").replace(old, new, 1),
                    encoding="utf-8",
                )
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL input: web/package.json: {detail}", S1],
                )
        lock_cases = (
            ("missing", "packages is missing"),
            ("array", "packages is not an object"),
            ("scalar", 'packages["node_modules/left"] is not an object'),
            ("version", 'packages["node_modules/left"].version is not a string'),
        )
        for kind, detail in lock_cases:
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                self._plant_lock(root, kind)
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL input: web/package-lock.json: {detail}", S1],
                )
        root, path = base.ready(self)
        self._plant_lock(root, "link")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-version: web/package-lock.json: node_modules/left: entry has no version",
                S1,
            ],
        )

    def test_fields_not_judged(self) -> None:
        root, path = base.ready(self)
        base.edit(
            root,
            "pyproject.toml",
            "[tool.uv]\n",
            '[tool.uv]\nconstraint-dependencies = ["zzz==9.9.9"]\n',
        )
        base.edit(
            root,
            "pyproject.toml",
            "[tool.uv.workspace]\n",
            '[tool.uv.sources]\nzzz = { path = "vendor/zzz" }\n\n[tool.uv.workspace]\n',
        )
        base.edit(
            root,
            "pyproject.toml",
            "[tool.uv]\n",
            '[build-system]\nrequires = ["uv_build>=0.11.31,<0.12", "setuptools"]\n'
            'build-backend = "uv_build"\n\n[tool.uv]\n',
        )
        doc = json.loads((root / "web" / "package.json").read_text(encoding="utf-8"))
        doc["overrides"] = {"left": "9.9.9"}
        doc["scripts"] = {"build": "vite build"}
        doc["engines"]["npm"] = ">=99"
        base.write(root, "web/package.json", json.dumps(doc) + "\n")
        base.edit(
            root,
            "web/package-lock.json",
            '"lockfileVersion": 3',
            '"lockfileVersion": 99',
        )
        base.edit(
            root,
            "uv.lock",
            'registry = "https://pypi.org/simple"',
            'registry = "https://example.invalid/simple"',
        )
        base.edit(
            root,
            "web/package-lock.json",
            '"node_modules/left": {"version": "4.5.6"}',
            '"node_modules/left": {"version": "4.5.6", "resolved": '
            '"https://example.invalid/left.tgz", "integrity": "sha512-aaaa"}',
        )
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def _plant_lock(self, root: Path, kind: str) -> None:
        path = root / "web" / "package-lock.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if kind == "missing":
            del doc["packages"]
        elif kind == "array":
            doc["packages"] = []
        elif kind == "scalar":
            doc["packages"]["node_modules/left"] = 5
        elif kind == "version":
            doc["packages"]["node_modules/left"] = {"version": 5}
        elif kind == "link":
            doc["packages"]["node_modules/left"] = {"link": True}
        else:
            raise AssertionError(kind)
        path.write_text(json.dumps(doc) + "\n", encoding="utf-8")
