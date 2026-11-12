"""npm manifest, lock and state rules."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base

S1 = base.summary(1)
SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


class NpmRules(unittest.TestCase):
    def test_manifest_unrecorded_npm(self) -> None:
        for section in SECTIONS:
            with self.subTest(section=section):
                root, path = base.ready(self)
                self._set_spec(root, section, "zeta", "1.0.0")
                self._lock(root, "node_modules/zeta", "1.0.0")
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL manifest-unrecorded: web/package.json: "
                        f"{section}.zeta: no component in pins.toml",
                        S1,
                    ],
                )

    def test_manifest_version_npm(self) -> None:
        left_bad = (
            "^4.5.6",
            "~4.5.6",
            "4.5.7",
            "4.5",
            "latest",
            ">=4",
            "4.5.6 ",
            "npm:other 1.0.0",
            "https://example.invalid/left.tgz",
            "4.5.6\n",
            "\uff14.5.6",
        )
        for spec in left_bad:
            for section in SECTIONS:
                with self.subTest(name="left", spec=spec, section=section):
                    root, path = base.ready(self)
                    self._set_spec(root, section, "left", spec)
                    self.assertEqual(
                        base.run(root, path=path),
                        [
                            "FAIL manifest-version: web/package.json: "
                            f"{section}.left: {base.escaped(spec)}: "
                            "neither pin 4.5.6 nor retreat none recorded",
                            S1,
                        ],
                    )
        right_bad = ("7.1", "6.0.1", "7.2.0", "7.1.9\n")
        for spec in right_bad:
            for section in SECTIONS:
                with self.subTest(name="right", spec=spec, section=section):
                    root, path = base.ready(self)
                    base.edit_row(
                        root,
                        'name = "right"',
                        'state = "recorded"',
                        'state = "installed"',
                    )
                    self._lock(root, "node_modules/right", "7.1.9")
                    self._set_spec(root, section, "right", spec)
                    self.assertEqual(
                        base.run(root, path=path),
                        [
                            "FAIL manifest-version: web/package.json: "
                            f"{section}.right: {base.escaped(spec)}: "
                            "neither pin 7.1.x nor retreat 6.0.0",
                            S1,
                        ],
                    )
        for spec, locked in (("7.1.9", "7.1.9"), ("6.0.0", "6.0.0")):
            for section in SECTIONS:
                with self.subTest(name="right", spec=spec, section=section):
                    root, path = base.ready(self)
                    base.edit_row(
                        root,
                        'name = "right"',
                        'state = "recorded"',
                        'state = "installed"',
                    )
                    self._lock(root, "node_modules/right", locked)
                    self._set_spec(root, section, "right", spec)
                    self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_lock_entry_npm(self) -> None:
        root, path = base.ready(self)
        self._drop_key(root, "node_modules/left")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-entry: web/package-lock.json: left: "
                "named by web/package.json, no top-level entry",
                S1,
            ],
        )
        root, path = base.ready(self)
        self._drop_key(root, "node_modules/left")
        self._lock(root, "node_modules/other/node_modules/left", "4.5.6")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL lock-entry: web/package-lock.json: left: "
                "named by web/package.json, no top-level entry",
                S1,
            ],
        )
        root, path = base.ready(self)
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_lock_version_npm(self) -> None:
        plants = (
            ("node_modules/left", "4.5.7", "4.5.6", "none recorded"),
            ("node_modules/foo/node_modules/left", "4.5.0", "4.5.6", "none recorded"),
            ("node_modules/@scope/pkg", "1.0.1", "1.0.0", "none recorded"),
            ("node_modules/right", "7.0.9", "7.1.x", "6.0.0"),
            ("node_modules/right", "6.0.1", "7.1.x", "6.0.0"),
        )
        for key, version, pin, retreat in plants:
            with self.subTest(key=key, version=version):
                root, path = base.ready(self)
                if key == "node_modules/@scope/pkg":
                    self._set_version(root, key, version)
                elif key.startswith("node_modules/right"):
                    self._lock(root, key, version)
                elif key == "node_modules/left":
                    self._set_version(root, key, version)
                else:
                    self._lock(root, key, version)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        "FAIL lock-version: web/package-lock.json: "
                        f"{key}: {version}: neither pin {pin} nor retreat {retreat}",
                        S1,
                    ],
                )
        root, path = base.ready(self)
        self._lock(root, "node_modules/right", "6.0.0")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        self._lock(root, "node_modules/zzz", "9.9.9")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def test_state_rule_npm(self) -> None:
        root, path = base.ready(self)
        self._drop_name(root, "dependencies", "left")
        self._drop_key(root, "node_modules/left")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL state: pins.toml: component[8] left: "
                "installed but named by no manifest or lock",
                S1,
            ],
        )
        root, path = base.ready(self)
        self._drop_name(root, "dependencies", "left")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        root, path = base.ready(self)
        self._set_spec(root, "dependencies", "right", "7.1.0")
        self._lock(root, "node_modules/right", "7.1.0")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL state: pins.toml: component[9] right: recorded but a manifest names it",
                S1,
            ],
        )
        root, path = base.ready(self)
        self._lock(root, "node_modules/right", "7.1.0")
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])

    def _load(self, root: Path, rel: str) -> dict[str, object]:
        parsed = json.loads((root / rel).read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise AssertionError(f"{rel} is not an object")
        loaded: dict[str, object] = {}
        for key, value in parsed.items():
            loaded[str(key)] = value
        return loaded

    def _dump(self, root: Path, rel: str, doc: dict[str, object]) -> None:
        base.write(root, rel, json.dumps(doc, indent=2) + "\n")

    def _set_spec(self, root: Path, section: str, name: str, spec: str) -> None:
        doc = self._load(root, "web/package.json")
        existing = doc.get(section)
        if not isinstance(existing, dict):
            existing = {}
        existing[name] = spec
        doc[section] = existing
        self._dump(root, "web/package.json", doc)

    def _drop_name(self, root: Path, section: str, name: str) -> None:
        doc = self._load(root, "web/package.json")
        section_doc = doc[section]
        if isinstance(section_doc, dict):
            del section_doc[name]
        self._dump(root, "web/package.json", doc)

    def _lock(self, root: Path, key: str, version: str) -> None:
        doc = self._load(root, "web/package-lock.json")
        packages = doc["packages"]
        if isinstance(packages, dict):
            packages[key] = {"version": version}
        self._dump(root, "web/package-lock.json", doc)

    def _set_version(self, root: Path, key: str, version: str) -> None:
        doc = self._load(root, "web/package-lock.json")
        packages = doc["packages"]
        if isinstance(packages, dict):
            entry = packages[key]
            if isinstance(entry, dict):
                entry["version"] = version
        self._dump(root, "web/package-lock.json", doc)

    def _drop_key(self, root: Path, key: str) -> None:
        doc = self._load(root, "web/package-lock.json")
        packages = doc["packages"]
        if isinstance(packages, dict):
            del packages[key]
        self._dump(root, "web/package-lock.json", doc)
