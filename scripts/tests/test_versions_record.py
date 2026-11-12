"""Record rules for the version-pin check."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import versions_support as base


class RecordRules(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        root, path = base.ready(self)
        self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        proc = base.cli(["--root", str(root)], {"PATH": path})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [base.SUMMARY_OK])
        self.assertEqual(proc.stderr, "")

    def test_inputs_missing_and_malformed(self) -> None:
        files = (
            "pins.toml",
            ".python-version",
            ".nvmrc",
            "pyproject.toml",
            "custodian/pyproject.toml",
            "uv.lock",
            "web/package.json",
            "web/package-lock.json",
        )
        parsed = {
            "pins.toml",
            "pyproject.toml",
            "custodian/pyproject.toml",
            "uv.lock",
            "web/package.json",
            "web/package-lock.json",
        }
        json_files = {"web/package.json", "web/package-lock.json"}
        for rel in files:
            plants: list[tuple[str, str]] = [
                ("missing", "missing"),
                ("directory", "not a regular file"),
                ("link", "not a regular file"),
                ("bytes", "not valid UTF-8"),
            ]
            if rel in parsed:
                plants.append(
                    (
                        "unterminated",
                        "not valid TOML"
                        if rel.endswith(".toml") or rel == "uv.lock"
                        else "not valid JSON",
                    )
                )
            if rel in json_files:
                plants.append(("duplicate", "duplicate key"))
                plants.append(("array", "top level is not an object"))
            for kind, detail in plants:
                with self.subTest(rel=rel, kind=kind):
                    root, path = base.ready(self)
                    self._plant_input(root, rel, kind)
                    lines = base.run(root, path=path)
                    if rel == "pins.toml":
                        summary = "checked 0 components: 1 failure(s)"
                    else:
                        summary = base.summary(1)
                    self.assertEqual(
                        lines,
                        [f"FAIL input: {rel}: {detail}", summary],
                    )
        root, path = base.ready(self)
        with patch.object(Path, "read_bytes", side_effect=PermissionError):
            lines = base.run(root, path=path)
        self.assertEqual(
            lines,
            [
                "FAIL input: pins.toml: unreadable",
                "checked 0 components: 1 failure(s)",
            ],
        )

    def test_members_value(self) -> None:
        plants = (
            ("members = ", ""),
            ('members = ["core", "custodian"]', 'members = "core"'),
            ('members = ["core", "custodian"]', "members = [1]"),
        )
        expected = [
            "FAIL input: pyproject.toml: tool.uv.workspace.members is not a list of strings",
            base.summary(1),
        ]
        for old, new in plants:
            with self.subTest(new=new):
                root, path = base.ready(self)
                if old == "members = ":
                    base.edit(
                        root,
                        "pyproject.toml",
                        '[tool.uv.workspace]\nmembers = ["core", "custodian"]\n',
                        "",
                    )
                else:
                    base.edit(root, "pyproject.toml", old, new)
                self.assertEqual(base.run(root, path=path), expected)

    def test_top_level_keys(self) -> None:
        plants = (
            ("schema = 1", "schema = true", "schema is not 1", 12),
            ("schema = 1", "schema = 2", "schema is not 1", 12),
            ("schema = 1", 'schema = "1"', "schema is not 1", 12),
            ("schema = 1\n", "", "schema is not 1", 12),
            (
                'confirm_at = "slice S1"',
                'confirm_at = "slice S2"',
                'confirm_at is not "slice S1"',
                12,
            ),
            (
                'spike_result = "not yet run"\n',
                "",
                "spike_result is missing or empty",
                12,
            ),
            (
                'spike_result = "not yet run"',
                'spike_result = " "',
                "spike_result is missing or empty",
                12,
            ),
            ("schema = 1\n", "extra = 1\nschema = 1\n", "unknown key extra", 12),
            ("component = [", "component = []\ncomponent = [", "unused", 12),
        )
        # The empty-array and non-array plants are written below; this table
        # keeps the header plants that leave the component array intact.
        for old, new, detail, count in plants:
            if detail == "unused":
                continue
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                base.edit(root, "pins.toml", old, new)
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL record-row: pins.toml: {detail}",
                        f"checked {count} components: 1 failure(s)",
                    ],
                )
        with self.subTest(detail="empty array"):
            root, path = base.ready(self)
            text = (root / "pins.toml").read_text(encoding="utf-8")
            start = text.index("component = [")
            base.write(root, "pins.toml", text[:start] + "component = []\n")
            self.assertEqual(
                base.run(root, path=path),
                [
                    "FAIL record-row: pins.toml: component is not a non-empty array of tables",
                    "checked 0 components: 1 failure(s)",
                ],
            )
        with self.subTest(detail="not an array"):
            root, path = base.ready(self)
            text = (root / "pins.toml").read_text(encoding="utf-8")
            start = text.index("component = [")
            base.write(root, "pins.toml", text[:start] + "component = 5\n")
            self.assertEqual(
                base.run(root, path=path),
                [
                    "FAIL record-row: pins.toml: component is not a non-empty array of tables",
                    "checked 0 components: 1 failure(s)",
                ],
            )

    def test_required_fields_types_and_unknown_fields(self) -> None:
        alpha = 'name = "alpha", '
        plants = (
            (alpha, "", "component[4]: name is missing"),
            ('kind = "python", ', "", "component[4] alpha: kind is missing"),
            ('pin = "1.2.3", ', "", "component[4] alpha: pin is missing"),
            (
                'retreat = "none recorded", ',
                "",
                "component[4] alpha: retreat is missing",
            ),
            ('state = "installed", ', "", "component[4] alpha: state is missing"),
            ('first_use = "S0-T12", ', "", "component[4] alpha: first_use is missing"),
            (
                'pin = "1.2.3"',
                "pin = 5",
                "component[4] alpha: pin is not a single-line non-empty string",
            ),
            (
                'pin = "1.2.3"',
                'pin = ""',
                "component[4] alpha: pin is not a single-line non-empty string",
            ),
            (
                'pin = "1.2.3"',
                'pin = "a\\nb"',
                "component[4] alpha: pin is not a single-line non-empty string",
            ),
            (
                'pin = "1.2.3"',
                "pin = true",
                "component[4] alpha: pin is not a single-line non-empty string",
            ),
            (
                'source = "fixture" }',
                'source = "fixture", x = "1" }',
                "component[4] alpha: unknown field x",
            ),
        )
        for old, new, detail in plants:
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                base.edit_row(root, 'name = "alpha"', old, new)
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL record-row: pins.toml: {detail}", base.summary(1)],
                )

    def test_pin_and_retreat_grammar(self) -> None:
        valid_pins = ("1.2", "1.2.3", "1.2.3.4", "1.x", "1.2.x")
        for pin in valid_pins:
            with self.subTest(pin=pin):
                root, path = base.ready(self)
                base.edit(
                    root,
                    "pins.toml",
                    'name = "alpha", kind = "python", pin = "1.2.3"',
                    f'name = "alpha", kind = "python", pin = "{pin}"',
                )
                if pin not in {"1.2.3", "1.x", "1.2.x"}:
                    version = pin
                    base.edit(
                        root, "pyproject.toml", "alpha==1.2.3", f"alpha=={version}"
                    )
                    base.edit(
                        root, "uv.lock", 'version = "1.2.3"', f'version = "{version}"'
                    )
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        invalid_pins = (
            "^1.2.3",
            ">=1",
            "1",
            "1.2.x.x",
            "1.2.3.x",
            "latest",
            "1.2.3-rc1",
            "1.2.3 ",
            "x",
            ".x",
            "\uff11.2.3",
        )
        for pin in invalid_pins:
            with self.subTest(pin=pin):
                root, path = base.ready(self)
                shown = base.escaped(pin)
                base.edit(
                    root,
                    "pins.toml",
                    'pin = "1.2.3"',
                    'pin = "' + pin + '"',
                )
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL record-row: pins.toml: component[4] alpha: pin {shown} is not an exact version or a series",
                        base.summary(1),
                    ],
                )
        with self.subTest(pin="newline"):
            root, path = base.ready(self)
            base.edit(root, "pins.toml", 'pin = "1.2.3"', 'pin = """1.2.3\\n"""')
            self.assertEqual(
                base.run(root, path=path),
                [
                    "FAIL record-row: pins.toml: component[4] alpha: pin is not a single-line non-empty string",
                    base.summary(1),
                ],
            )
        valid_retreats = (
            ("none recorded", "none recorded"),
            ("1.5.x", "1.5.x"),
            ("2.0.0", "2.0.0"),
            ("replace:delta", "replace:delta"),
            ("replace:Delta", "replace:Delta"),
        )
        for retreat, _label in valid_retreats:
            with self.subTest(retreat=retreat):
                root, path = base.ready(self)
                base.edit(
                    root,
                    "pins.toml",
                    'name = "alpha", kind = "python", pin = "1.2.3", retreat = "none recorded"',
                    f'name = "alpha", kind = "python", pin = "1.2.3", retreat = "{retreat}"',
                )
                self.assertEqual(base.run(root, path=path), [base.SUMMARY_OK])
        invalid_retreats = (
            (
                "None recorded",
                "retreat None recorded is not none recorded, a version, a series or replace:<name>",
            ),
            (
                "replace:",
                "retreat replace: is not none recorded, a version, a series or replace:<name>",
            ),
            (
                "replace:missing",
                "replace target missing is not a component of the same kind",
            ),
            ("replace:left", "replace target left is not a component of the same kind"),
        )
        for retreat, detail in invalid_retreats:
            with self.subTest(retreat=retreat):
                root, path = base.ready(self)
                base.edit(
                    root,
                    "pins.toml",
                    'name = "alpha", kind = "python", pin = "1.2.3", retreat = "none recorded"',
                    f'name = "alpha", kind = "python", pin = "1.2.3", retreat = "{retreat}"',
                )
                self.assertEqual(
                    base.run(root, path=path),
                    [
                        f"FAIL record-row: pins.toml: component[4] alpha: {detail}",
                        base.summary(1),
                    ],
                )

    def test_kind_state_and_toolchain_rules(self) -> None:
        plants = (
            (
                'kind = "python"',
                'kind = "gcc"',
                "component[4] alpha: unknown kind gcc",
                "alpha",
            ),
            (
                'state = "installed"',
                'state = "pending"',
                "component[4] alpha: unknown state pending",
                "alpha",
            ),
            (
                'first_use = "S0-T12"',
                'first_use = "T01"',
                "component[4] alpha: first_use T01 is not a task id or a slice",
                "alpha",
            ),
            (
                'first_use = "S0-T12"',
                'first_use = "S0-T1"',
                "component[4] alpha: first_use S0-T1 is not a task id or a slice",
                "alpha",
            ),
            (
                'first_use = "S0-T12"',
                'first_use = "slice 1"',
                "component[4] alpha: first_use slice 1 is not a task id or a slice",
                "alpha",
            ),
            (
                'first_use = "S0-T12"',
                'first_use = "S0-T01 "',
                "component[4] alpha: first_use S0-T01  is not a task id or a slice",
                "alpha",
            ),
            (
                'name = "python", kind = "toolchain", pin = "3.14.x", retreat = "none recorded", label = "'
                + base.PACK
                + '", cite = "'
                + base.CITE
                + '", state = "installed"',
                'name = "python", kind = "toolchain", pin = "3.14.x", retreat = "none recorded", label = "'
                + base.PACK
                + '", cite = "'
                + base.CITE
                + '", state = "recorded"',
                "component[0] python: a toolchain row must be installed",
            ),
            (
                'name = "service", kind = "external"',
                'name = "gcc", kind = "toolchain"',
                "component[11] gcc: no probe for toolchain gcc",
            ),
            (
                'name = "service", kind = "external", pin = "18", retreat = "none recorded", label = "'
                + base.PACK
                + '", cite = "'
                + base.CITE
                + '", state = "recorded"',
                'name = "service", kind = "external", pin = "18", retreat = "none recorded", label = "'
                + base.PACK
                + '", cite = "'
                + base.CITE
                + '", state = "installed"',
                "component[11] service: an external row must be recorded",
            ),
            (
                'name = "uv", kind = "toolchain", pin = "0.11.31"',
                'name = "uv", kind = "toolchain", pin = "0.11.x"',
                "component[1] uv: uv needs an exact three-part pin",
            ),
            (
                'name = "uv", kind = "toolchain", pin = "0.11.31"',
                'name = "uv", kind = "toolchain", pin = "0.11"',
                "component[1] uv: uv needs an exact three-part pin",
            ),
            (
                'name = "node", kind = "toolchain", pin = "22.x"',
                'name = "node", kind = "toolchain", pin = "22.12.0"',
                "component[2] node: node needs a pin such as 22.x",
            ),
            (
                'floor = "22.12.0", ',
                "",
                "component[2] node: node needs a floor such as 22.12.0",
            ),
            (
                'floor = "22.12.0"',
                'floor = "22.12"',
                "component[2] node: node needs a floor such as 22.12.0",
            ),
            (
                'source = "fixture" }',
                'source = "fixture", floor = "1.2.3" }',
                "component[4] alpha: floor is only for node",
                "alpha",
            ),
        )
        for item in plants:
            old, new, detail = item[0], item[1], item[2]
            marker = item[3] if len(item) == 4 else ""
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                if marker:
                    base.edit_row(root, f'name = "{marker}"', old, new)
                else:
                    base.edit(root, "pins.toml", old, new)
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL record-row: pins.toml: {detail}", base.summary(1)],
                )

    def test_four_toolchain_rows_required(self) -> None:
        root, path = base.ready(self)
        text = (root / "pins.toml").read_text(encoding="utf-8")
        kept = [
            line
            for line in text.splitlines(keepends=True)
            if 'name = "npm"' not in line
        ]
        base.write(root, "pins.toml", "".join(kept))
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL record-row: pins.toml: toolchain npm is missing",
                "checked 11 components: 1 failure(s)",
            ],
        )

    def test_label_rule(self) -> None:
        plants: list[tuple[str, str, list[str]]] = [
            (
                'label = "ASSUMPTION", ',
                "",
                ["FAIL record-label: pins.toml: component[4] alpha: label is missing"],
            ),
            (
                'label = "ASSUMPTION"',
                'label = "pack"',
                [
                    'FAIL record-label: pins.toml: component[4] alpha: label \'pack\' is not "pack, confirm at slice S1" or "ASSUMPTION"'
                ],
            ),
            (
                'label = "ASSUMPTION"',
                'label = "assumption"',
                [
                    'FAIL record-label: pins.toml: component[4] alpha: label \'assumption\' is not "pack, confirm at slice S1" or "ASSUMPTION"'
                ],
            ),
            (
                'label = "ASSUMPTION"',
                'label = ""',
                [
                    "FAIL record-row: pins.toml: component[4] alpha: label is not a single-line non-empty string",
                    'FAIL record-label: pins.toml: component[4] alpha: label \'\' is not "pack, confirm at slice S1" or "ASSUMPTION"',
                ],
            ),
            (
                ', source = "fixture"',
                "",
                [
                    "FAIL record-label: pins.toml: component[4] alpha: ASSUMPTION needs a source"
                ],
            ),
            (
                'source = "fixture"',
                'source = ""',
                [
                    "FAIL record-row: pins.toml: component[4] alpha: source is not a single-line non-empty string",
                    "FAIL record-label: pins.toml: component[4] alpha: ASSUMPTION needs a source",
                ],
            ),
        ]
        for old, new, details in plants:
            with self.subTest(details=details[0]):
                root, path = base.ready(self)
                base.edit_row(root, 'name = "alpha"', old, new)
                self.assertEqual(
                    base.run(root, path=path),
                    [*details, base.summary(len(details))],
                )

    def test_cite_rule(self) -> None:
        plants = (
            (
                f'cite = "{base.CITE}", ',
                "",
                "component[4] alpha: cite is missing",
            ),
            (
                base.CITE,
                "docs/a.md 5",
                'component[4] alpha: cite item "docs/a.md 5" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "docs/a.md line 0",
                'component[4] alpha: cite item "docs/a.md line 0" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "docs/a.md line -1",
                'component[4] alpha: cite item "docs/a.md line -1" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "docs/a.md line 5x",
                'component[4] alpha: cite item "docs/a.md line 5x" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "docs/a.md line  5",
                'component[4] alpha: cite item "docs/a.md line  5" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "/etc/passwd line 1",
                'component[4] alpha: cite item "/etc/passwd line 1" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "../x.md line 1",
                'component[4] alpha: cite item "../x.md line 1" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "docs\\\\a.md line 1",
                'component[4] alpha: cite item "docs\\a.md line 1" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                f"{base.CITE}; ",
                'component[4] alpha: cite item "" is not "<path> line <n>"',
            ),
            (
                base.CITE,
                "docs/none.md line 1",
                "component[4] alpha: docs/none.md is not a file",
            ),
            (
                base.CITE,
                "docs line 1",
                "component[4] alpha: docs is not a file",
            ),
            (
                base.CITE,
                "docs/a.md line 41",
                "component[4] alpha: docs/a.md has 40 lines, line 41 does not exist",
            ),
            (
                base.CITE,
                f"{base.CITE}; docs/none.md line 1",
                "component[4] alpha: docs/none.md is not a file",
            ),
        )
        for old, new, detail in plants:
            with self.subTest(detail=detail):
                root, path = base.ready(self)
                base.edit_row(root, 'name = "alpha"', old, new)
                self.assertEqual(
                    base.run(root, path=path),
                    [f"FAIL record-cite: pins.toml: {detail}", base.summary(1)],
                )

    def test_duplicates(self) -> None:
        addition = (
            '{ name = "Alpha", kind = "python", pin = "1.2.3", retreat = "none recorded", '
            f'label = "{base.PACK}", cite = "{base.CITE}", state = "recorded", '
            'first_use = "S0-T12" },'
        )
        root, path = base.ready(self)
        base.edit(root, "pins.toml", "]\n", addition + "\n]\n")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL record-duplicate: pins.toml: component[12] Alpha: same component as component[4] alpha",
                "checked 13 components: 1 failure(s)",
            ],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "pins.toml",
            "]\n",
            '{ name = "left", kind = "npm", pin = "4.5.6", retreat = "none recorded", '
            f'label = "{base.PACK}", cite = "{base.CITE}", state = "recorded", '
            'first_use = "S0-T12" },\n]\n',
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL record-duplicate: pins.toml: component[12] left: same component as component[8] left",
                "checked 13 components: 1 failure(s)",
            ],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "pins.toml",
            "]\n",
            '{ name = "uv", kind = "toolchain", pin = "0.11.31", retreat = "none recorded", '
            f'label = "ASSUMPTION", cite = "{base.CITE}", state = "installed", '
            'first_use = "S0-T12", source = "fixture" },\n]\n',
        )
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL record-duplicate: pins.toml: component[12] uv: same component as component[1] uv",
                "checked 13 components: 1 failure(s)",
            ],
        )
        root, path = base.ready(self)
        base.edit(
            root,
            "pins.toml",
            "]\n",
            '{ name = "left", kind = "python", pin = "1.0.0", retreat = "none recorded", '
            f'label = "{base.PACK}", cite = "{base.CITE}", state = "recorded", '
            'first_use = "S0-T12" },\n]\n',
        )
        self.assertEqual(base.run(root, path=path), ["checked 13 components: OK"])

    def test_record_failure_stops_other_rules(self) -> None:
        root, path = base.ready(self)
        (root / "custodian" / "pyproject.toml").unlink()
        base.write(root, "web/package.json", "{")
        base.edit_row(root, 'name = "alpha"', base.CITE, "docs/none.md line 1")
        self.assertEqual(
            base.run(root, path=path),
            [
                "FAIL record-cite: pins.toml: component[4] alpha: docs/none.md is not a file",
                base.summary(1),
            ],
        )

    def test_version_matches_table(self) -> None:
        import versions_record

        newline = "2.0.0\n"
        wide = "\uff12.0.0"
        cases = (
            ("1.2.3", "1.2.3", True),
            ("1.2.3", "1.2.30", False),
            ("1.2.3", "1.2", False),
            ("2.0.x", "2.0.0", True),
            ("2.0.x", "2.0.9", True),
            ("2.0.x", "2.0", True),
            ("2.0.x", "2.1.0", False),
            ("2.0.x", "1.9.9", False),
            ("2.0.x", "2.00.0", False),
            ("1.5.x", "1.50.0", False),
            ("22.x", "22.0.0", True),
            ("22.x", "22.23.5", True),
            ("22.x", "220.1.0", False),
            ("22.x", "2.2.0", False),
            ("0.162.x", "0.162.5", True),
            ("2.0.x", "2.0.1.dev3", False),
            ("2.0.x", "2.0.0rc1", False),
            ("2.0.x", "v2.0.0", False),
            ("2.0.x", "", False),
            ("2.0.0", newline, False),
            ("2.0.x", newline, False),
            ("22.x", "22.0.0\n", False),
            ("2.0.x", wide, False),
            ("none recorded", "1.2.3", False),
            ("replace:x", "1.2.3", False),
            # non-series: dropping the series guard would match 1.2.3ab against 1.2.3.4
            ("1.2.3ab", "1.2.3.4", False),
        )
        for entry, version, expected in cases:
            with self.subTest(entry=entry, version=version):
                self.assertEqual(
                    versions_record.version_matches(entry, version), expected
                )

    def _plant_input(self, root: Path, rel: str, kind: str) -> None:
        path = root / rel
        if kind == "missing":
            path.unlink()
            return
        if kind == "directory":
            path.unlink()
            path.mkdir()
            return
        if kind == "link":
            path.unlink()
            path.symlink_to("missing-target")
            return
        if kind == "bytes":
            path.write_bytes(b"\xff")
            return
        if kind == "unterminated":
            path.write_text("{", encoding="utf-8")
            return
        if kind == "duplicate":
            path.write_text('{"a": 1, "a": 2}\n', encoding="utf-8")
            return
        if kind == "array":
            path.write_text("[]\n", encoding="utf-8")
            return
        raise AssertionError(kind)
