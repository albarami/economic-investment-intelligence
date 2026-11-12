"""Python manifest, lock, version-file and state rules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base

S1 = base.summary(1)
BOUND = "['uv_build>=0.11.31,<0.12']"


class ManifestRules(unittest.TestCase):
    def test_python_version_file(self) -> None:
        root, path = base.ready(self)
        base.write(root, ".python-version", "3.14")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        plants = (
            "3.13\n",
            "3.14.6\n",
            "3.14\r\n",
            "3.14\n\n",
            " 3.14\n",
            "python-3.14\n",
            "",
        )
        for text in plants:
            with self.subTest(text=text):
                root, path = base.ready(self)
                base.write(root, ".python-version", text)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL version-file: .python-version: holds {text!r} expected '3.14'",
                        S1,
                    ],
                )

    def test_node_version_file(self) -> None:
        plants = ("v22\n", "22.12.0\n", "20\n", "lts/*\n", "22\r\n")
        for text in plants:
            with self.subTest(text=text):
                root, path = base.ready(self)
                base.write(root, ".nvmrc", text)
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL version-file: .nvmrc: holds {text!r} expected '22'", S1],
                )

    def test_version_fields(self) -> None:
        good = (
            (
                "pyproject.toml",
                'requires-python = ">=3.14"',
                'requires-python = ">=3.14"',
            ),
            (
                "core/pyproject.toml",
                'requires-python = ">=3.14"',
                'requires-python = ">=3.14"',
            ),
            (
                "custodian/pyproject.toml",
                'requires-python = ">=3.14"',
                'requires-python = ">=3.14"',
            ),
            (
                "pyproject.toml",
                'required-version = "==0.11.31"',
                'required-version = "==0.11.31"',
            ),
            ("web/package.json", '">=22.12.0 <23"', '">=22.12.0 <23"'),
        )
        for rel, old, new in good:
            with self.subTest(rel=rel, new=new):
                root, path = base.ready(self)
                if old != new:
                    base.edit(root, rel, old, new)
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        python_files = (
            "pyproject.toml",
            "core/pyproject.toml",
            "custodian/pyproject.toml",
        )
        bad_python = (">=3.12", ">=3.14,<3.15", "==3.14.*")
        for rel in python_files:
            for value in bad_python:
                with self.subTest(rel=rel, value=value):
                    root, path = base.ready(self)
                    base.edit(
                        root,
                        rel,
                        'requires-python = ">=3.14"',
                        f'requires-python = "{value}"',
                    )
                    self.assertEqual(
                        base.run(root, path=path),
                        [
                            "FAIL version-field: "
                            f"{rel}: project.requires-python is '{value}' expected '>=3.14'",
                            S1,
                        ],
                    )
            with self.subTest(rel=rel, value="removed"):
                root, path = base.ready(self)
                base.edit(root, rel, 'requires-python = ">=3.14"\n', "")
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL version-field: {rel}: project.requires-python is missing",
                        S1,
                    ],
                )
        for value in ("==0.11.30", ">=0.11.31"):
            with self.subTest(field="required-version", value=value):
                root, path = base.ready(self)
                base.edit(
                    root,
                    "pyproject.toml",
                    'required-version = "==0.11.31"',
                    f'required-version = "{value}"',
                )
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL version-field: pyproject.toml: "
                        f"tool.uv.required-version is '{value}' expected '==0.11.31'",
                        S1,
                    ],
                )
        root, path = base.ready(self)
        base.edit(root, "pyproject.toml", 'required-version = "==0.11.31"\n', "")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL version-field: pyproject.toml: tool.uv.required-version is missing",
                S1,
            ],
        )
        for value in (">=22.12.0 <24", ">=22.0.0 <23", "22.x"):
            with self.subTest(field="engines", value=value):
                root, path = base.ready(self)
                base.edit(root, "web/package.json", ">=22.12.0 <23", value)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL version-field: web/package.json: "
                        f"engines.node is '{value}' expected '>=22.12.0 <23'",
                        S1,
                    ],
                )
        root, path = base.ready(self)
        base.edit(
            root, "web/package.json", '"engines": {"node": ">=22.12.0 <23"},\n', ""
        )
        self.assertEqual(
            base.run(root, path=path),
            ["FAIL version-field: web/package.json: engines.node is missing", S1],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "web/package.json",
            "{\n",
            '{\n  "packageManager": "npm 10.9.8",\n',
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL version-field: web/package.json: packageManager is present expected absent",
                S1,
            ],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "web/package.json",
            "{\n",
            '{\n  "devEngines": {"runtime": {}},\n',
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL version-field: web/package.json: devEngines is present expected absent",
                S1,
            ],
        )

    def test_build_backend(self) -> None:
        plants = (
            (
                "core/pyproject.toml",
                'requires = ["uv_build>=0.11.31,<0.12"]',
                'requires = ["uv_build>=0.11.31,<0.13"]',
                "['uv_build>=0.11.31,<0.13']",
            ),
            (
                "custodian/pyproject.toml",
                'requires = ["uv_build>=0.11.31,<0.12"]',
                'requires = ["uv_build>=0.11.30,<0.12"]',
                "['uv_build>=0.11.30,<0.12']",
            ),
            (
                "core/pyproject.toml",
                'requires = ["uv_build>=0.11.31,<0.12"]',
                'requires = ["uv_build>=0.11.31,<0.12", "other"]',
                "['uv_build>=0.11.31,<0.12', 'other']",
            ),
        )
        for rel, old, new, shown in plants:
            with self.subTest(rel=rel, new=new):
                root, path = base.ready(self)
                base.edit(root, rel, old, new)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL build-backend: {rel}: build-system.requires is {shown} expected {BOUND}",
                        S1,
                    ],
                )
        root, path = base.ready(self)
        base.edit(
            root,
            "core/pyproject.toml",
            '[build-system]\nrequires = ["uv_build>=0.11.31,<0.12"]\nbuild-backend = "uv_build"\n',
            "",
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL build-backend: core/pyproject.toml: build-system.requires is missing",
                S1,
            ],
        )

    def test_manifest_forms_python(self) -> None:
        bad = (
            "alpha>=1.2.3",
            "alpha~=1.2",
            "alpha==1.2.*",
            "alpha===1.2.3",
            "alpha @ https://example.invalid/a.whl",
            "alpha==1.2.3; python_version > '3.0'",
            "alpha",
            "==1.2.3",
        )
        places = (
            (
                "custodian/pyproject.toml",
                'dependencies = ["eii-core"]',
                'dependencies = ["eii-core", "{req}"]',
                "project.dependencies",
            ),
            (
                "custodian/pyproject.toml",
                "[build-system]\n",
                '[project.optional-dependencies]\nextra = ["{req}"]\n\n[build-system]\n',
                "project.optional-dependencies.extra",
            ),
            (
                "pyproject.toml",
                'dev = ["alpha==1.2.3"]',
                'dev = ["alpha==1.2.3", "{req}"]',
                "dependency-groups.dev",
            ),
        )
        for req in bad:
            for rel, old, new, field in places:
                with self.subTest(req=req, field=field):
                    root, path = base.ready(self)
                    if "optional-dependencies" in new:
                        base.edit(root, rel, old, new.format(req=req))
                    else:
                        base.edit(root, rel, old, new.format(req=req))
                    shown = base.escaped(req)
                    self.assertEqual(
                        base.run(root, path=path),
                        [
                            f"FAIL manifest-form: {rel}: {field}: {shown}: not name==exact version",
                            S1,
                        ],
                    )
        for req in ("alpha[extra]==1.2.3", "Alpha == 1.2.3"):
            with self.subTest(req=req):
                root, path = base.ready(self)
                base.edit(
                    root,
                    "pyproject.toml",
                    'dev = ["alpha==1.2.3"]',
                    f'dev = ["alpha==1.2.3", "{req}"]',
                )
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_workspace_members_extras_and_groups(self) -> None:
        root, path = base.ready(self)
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        base.edit(
            root,
            "pyproject.toml",
            'dev = ["alpha==1.2.3"]',
            'dev = ["alpha==1.2.3", { include-group = "dev" }]',
        )
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        base.edit(root, "pyproject.toml", "alpha==1.2.3", "alpha[x]==1.2.3")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        for spelled in ("ALPHA==1.2.3", "Alpha_==1.2.3", "Alpha==1.2.3"):
            with self.subTest(spelled=spelled):
                root, path = base.ready(self)
                base.edit(
                    root,
                    "pyproject.toml",
                    'dev = ["alpha==1.2.3"]',
                    f'dev = ["alpha==1.2.3", "{spelled}"]',
                )
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_manifest_unrecorded_python(self) -> None:
        places = (
            (
                "custodian/pyproject.toml",
                'dependencies = ["eii-core"]',
                'dependencies = ["eii-core", "zeta==1.0.0"]',
                "project.dependencies",
            ),
            (
                "custodian/pyproject.toml",
                "[build-system]\n",
                '[project.optional-dependencies]\nextra = ["zeta==1.0.0"]\n\n[build-system]\n',
                "project.optional-dependencies.extra",
            ),
            (
                "pyproject.toml",
                'dev = ["alpha==1.2.3"]',
                'dev = ["alpha==1.2.3", "zeta==1.0.0"]',
                "dependency-groups.dev",
            ),
        )
        for rel, old, new, field in places:
            with self.subTest(field=field):
                root, path = base.ready(self)
                base.edit(root, rel, old, new)
                self._lock_package(root, "zeta", "1.0.0")
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL manifest-unrecorded: {rel}: {field}: zeta: no component in pins.toml",
                        S1,
                    ],
                )

    def test_manifest_version_python(self) -> None:
        allowed = (
            ("beta==2.0.7", "2.0.7", "beta"),
            ("beta==1.5.3", "1.5.3", "beta"),
            ("delta==3.1.0", "3.1.0", "delta"),
        )
        for req, version, name in allowed:
            with self.subTest(req=req):
                root, path = base.ready(self)
                self._install(root, name, req, version)
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        refused = (
            (
                "alpha==1.2.4",
                "alpha",
                "1.2.3",
                "none recorded",
                "dependency-groups.dev",
            ),
            ("beta==2.1.0", "beta", "2.0.x", "1.5.x", "dependency-groups.dev"),
            ("beta==1.6.0", "beta", "2.0.x", "1.5.x", "dependency-groups.dev"),
            (
                "gamma==3.0.1",
                "gamma",
                "3.0.0",
                "replace:delta",
                "dependency-groups.dev",
            ),
        )
        for req, name, pin, retreat, field in refused:
            with self.subTest(req=req):
                root, path = base.ready(self)
                if name == "alpha":
                    base.edit(root, "pyproject.toml", "alpha==1.2.3", req)
                else:
                    base.edit_row(
                        root,
                        f'name = "{name}"',
                        'state = "recorded"',
                        'state = "installed"',
                    )
                    base.edit(
                        root,
                        "pyproject.toml",
                        'dev = ["alpha==1.2.3"]',
                        f'dev = ["alpha==1.2.3", "{req}"]',
                    )
                    self._lock_package(root, name, pin if name != "beta" else "2.0.0")
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL manifest-version: pyproject.toml: "
                        f"{field}: {req}: neither pin {pin} nor retreat {retreat}",
                        S1,
                    ],
                )

    def test_lock_source(self) -> None:
        sources = (
            '{ git = "https://example.invalid/alpha.git" }',
            '{ url = "https://example.invalid/alpha.whl" }',
            '{ path = "vendor/alpha" }',
            '{ editable = "vendor/alpha" }',
            '{ virtual = "." }',
            None,
        )
        for source in sources:
            with self.subTest(source=source):
                root, path = base.ready(self)
                if source is None:
                    base.edit(
                        root,
                        "uv.lock",
                        '\nsource = { registry = "https://pypi.org/simple" }',
                        "",
                    )
                else:
                    base.edit(
                        root,
                        "uv.lock",
                        'source = { registry = "https://pypi.org/simple" }',
                        f"source = {source}",
                    )
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL lock-source: uv.lock: alpha 1.2.3: not locked from a registry",
                        "FAIL lock-entry: uv.lock: alpha: named by a manifest, no package entry",
                        base.summary(2),
                    ],
                )

    def test_lock_entry_python(self) -> None:
        root, path = base.ready(self)
        base.edit(
            root,
            "uv.lock",
            '\n[[package]]\nname = "alpha"\nversion = "1.2.3"\n'
            'source = { registry = "https://pypi.org/simple" }\n',
            "\n",
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-entry: uv.lock: alpha: named by a manifest, no package entry",
                S1,
            ],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "uv.lock",
            'source = { registry = "https://pypi.org/simple" }',
            'source = { editable = "vendor/alpha" }',
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-source: uv.lock: alpha 1.2.3: not locked from a registry",
                "FAIL lock-entry: uv.lock: alpha: named by a manifest, no package entry",
                base.summary(2),
            ],
        )

    def test_lock_version_python(self) -> None:
        root, path = base.ready(self)
        base.edit(root, "uv.lock", 'version = "1.2.3"', 'version = "1.2.4"')
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-version: uv.lock: alpha 1.2.4: neither pin 1.2.3 nor retreat none recorded",
                S1,
            ],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "uv.lock",
            'name = "alpha"\nversion = "1.2.3"\n'
            'source = { registry = "https://pypi.org/simple" }\n',
            'name = "alpha"\nversion = "1.2.3"\n'
            'source = { registry = "https://pypi.org/simple" }\n\n'
            "[[package]]\n"
            'name = "alpha"\nversion = "1.2.4"\n'
            'source = { registry = "https://pypi.org/simple" }\n',
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-version: uv.lock: alpha 1.2.4: neither pin 1.2.3 nor retreat none recorded",
                S1,
            ],
        )
        root, path = base.ready(self)
        base.edit_row(
            root, 'name = "beta"', 'state = "recorded"', 'state = "installed"'
        )
        base.edit(
            root,
            "pyproject.toml",
            'dev = ["alpha==1.2.3"]',
            'dev = ["alpha==1.2.3", "beta==2.0.7"]',
        )
        self._lock_package(root, "beta", "2.1.0")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-version: uv.lock: beta 2.1.0: neither pin 2.0.x nor retreat 1.5.x",
                S1,
            ],
        )
        root, path = base.ready(self)
        self._lock_package(root, "zzz", "9.9.9")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_state_rule_python(self) -> None:
        root, path = base.ready(self)
        base.edit(root, "pyproject.toml", 'dev = ["alpha==1.2.3"]', "dev = []")
        base.edit(
            root,
            "uv.lock",
            '\n[[package]]\nname = "alpha"\nversion = "1.2.3"\n'
            'source = { registry = "https://pypi.org/simple" }\n',
            "\n",
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL state: pins.toml: component[4] alpha: installed but named by no manifest or lock",
                S1,
            ],
        )
        root, path = base.ready(self)
        base.edit(root, "pyproject.toml", 'dev = ["alpha==1.2.3"]', "dev = []")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        base.edit(
            root,
            "pyproject.toml",
            'dev = ["alpha==1.2.3"]',
            'dev = ["alpha==1.2.3", "beta==2.0.0"]',
        )
        self._lock_package(root, "beta", "2.0.0")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL state: pins.toml: component[5] beta: recorded but a manifest names it",
                S1,
            ],
        )
        root, path = base.ready(self)
        self._lock_package(root, "beta", "2.0.0")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        base.edit_row(
            root, 'name = "gamma"', 'state = "recorded"', 'state = "installed"'
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL state: pins.toml: component[6] gamma: installed but named by no manifest or lock",
                S1,
            ],
        )

    def _lock_package(self, root: Path, name: str, version: str) -> None:
        addition = (
            "\n[[package]]\n"
            f'name = "{name}"\n'
            f'version = "{version}"\n'
            'source = { registry = "https://pypi.org/simple" }\n'
        )
        path = root / "uv.lock"
        path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")

    def _install(self, root: Path, name: str, requirement: str, version: str) -> None:
        base.edit_row(
            root, f'name = "{name}"', 'state = "recorded"', 'state = "installed"'
        )
        base.edit(
            root,
            "pyproject.toml",
            'dev = ["alpha==1.2.3"]',
            f'dev = ["alpha==1.2.3", "{requirement}"]',
        )
        self._lock_package(root, name, version)
