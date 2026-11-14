"""Compare document 13's headed tables with their executable inventories."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_tree
import commit_guard
import preflight

ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = ROOT / "docs/13_DEPLOYMENT_AND_OPERATIONS.md"
PREFLIGHT_NAMES = {
    "Python 3.14 managed by `uv`": "python",
    "Node 22 and npm": "node-npm",
    "Locked dependencies": "locked-dependencies",
    "DuckDB with `spatial` and `h3` extensions installed locally": "duckdb-extensions",
    "PostgreSQL 18 with PostGIS 3.6": "postgresql",
    "Release present and intact": "release",
    "Load receipt": "load-receipt",
    "Embedded reader file": "embedded-reader",
    "Tiles, glyphs and interface fonts": "tiles-glyphs-fonts",
    "Recorded assistant replays": "recorded-replays",
    "bubblewrap sandbox (build machine only)": "bubblewrap-sandbox",
    "API port free": "api-port",
    "Model key": "model-key",
    "Traffic provider key": "traffic-provider-key",
    "Night-lights key": "night-lights-key",
    "Imagery provider key": "imagery-provider-key",
    "Photorealistic 3D key": "photorealistic-3d-key",
    "`.env` not tracked": "env-not-tracked",
    "WSL interoperability (warning only)": "wsl-interop",
}


def table(text: str, heading: str, column: str) -> list[dict[str, str]]:
    """Read the named table in a headed section, without positional anchors."""
    section = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    lines = section.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"| {column} |"))
    headers = [cell.strip() for cell in lines[start].strip("|").split("|")]
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            raise AssertionError("table column count differs")
        rows.append(dict(zip(headers, cells, strict=True)))
    if not rows:
        raise AssertionError("empty operations table")
    return rows


def documented(text: str, kind: str) -> set[str]:
    if kind == "preflight":
        rows = table(text, "3. Prerequisites and how each is checked", "Prerequisite")
        labels = [row["Prerequisite"] for row in rows]
        if len(labels) != len(set(labels)) or set(labels) != set(PREFLIGHT_NAMES):
            raise AssertionError(
                "preflight table has unmapped, duplicate or missing rows"
            )
        return {PREFLIGHT_NAMES[label] for label in labels}
    rows = table(text, "2. Environments", "Variable")
    if kind == "secrets":
        # OPS-07 also forbids printing the model key; its table row says key or absent.
        rows = [
            row
            for row in rows
            if "never printed" in row["Operational note"].lower()
            or row["Values"] == "key or absent"
        ]
    return {row["Variable"].strip("`") for row in rows}


def assert_parity(text: str, kind: str, actual: set[str]) -> None:
    expected = documented(text, kind)
    if expected != actual:
        raise AssertionError(
            f"{kind} inventory differs: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


class OperationsParity(unittest.TestCase):
    def test_document_and_code_inventories(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        examples = set(
            re.findall(
                r"^([A-Z][A-Z0-9_]*)=",
                (ROOT / ".env.example").read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
        inventories = {
            "preflight": set(preflight.CHECKS),
            "example": examples,
            "tree": set(check_tree.ENV_EXAMPLE_NAMES),
            "secrets": set(commit_guard.SECRET_NAMES),
        }
        for kind, actual in inventories.items():
            with self.subTest(kind=kind):
                assert_parity(text, kind, actual)
        preflight_rows = table(
            text, "3. Prerequisites and how each is checked", "Prerequisite"
        )
        self.assertEqual(
            list(preflight.CHECKS),
            [PREFLIGHT_NAMES[row["Prerequisite"]] for row in preflight_rows],
        )

    def test_added_table_row_is_refused(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        for kind in ("preflight", "example", "tree", "secrets"):
            with self.subTest(kind=kind):
                original = documented(text, kind)
                if kind == "preflight":
                    needle = "| Python 3.14 managed by `uv` |"
                    row = (
                        "| Planted prerequisite | synthetic | synthetic | synthetic |\n"
                    )
                else:
                    needle = "| `ANTHROPIC_API_KEY` |"
                    row = "| `PLANTED_KEY` | key or absent | synthetic | never printed |\n"
                changed = text.replace(needle, row + needle, 1)
                with self.assertRaises(AssertionError):
                    assert_parity(changed, kind, original)

    def test_removed_code_name_is_refused(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        for kind in ("preflight", "example", "tree", "secrets"):
            with self.subTest(kind=kind):
                actual = documented(text, kind)
                actual.remove(sorted(actual)[0])
                with self.assertRaisesRegex(AssertionError, "inventory differs"):
                    assert_parity(text, kind, actual)


if __name__ == "__main__":
    unittest.main()
