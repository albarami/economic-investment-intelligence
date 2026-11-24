"""The manifest catalogue matches section 7.2 of the data contracts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import eii_core.manifest as manifest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "docs" / "03_DATA_CONTRACTS.md"
HEADING = "### 7.2 Table catalogue"


def section_rows(text: str) -> list[tuple[str, str, tuple[str, ...]]]:
    """Return name, class label and key columns from one copy of section 7.2."""
    start = text.index(HEADING)
    end = text.index("### 7.3 Columns", start)
    rows: list[tuple[str, str, tuple[str, ...]]] = []
    for line in text[start:end].splitlines():
        if not line.startswith("| `"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        name = parts[0].strip("`")
        label = parts[1]
        key = tuple(re.findall(r"`([^`]+)`", parts[3]))
        rows.append((name, label, key))
    return rows


class Catalogue(unittest.TestCase):
    def test_catalogue_equals_section_7_2(self) -> None:
        """Names, class labels and keys equal the document table."""
        text = CONTRACTS.read_text(encoding="utf-8")
        parsed = section_rows(text)
        stored = [(row.name, row.label, row.key) for row in manifest.CATALOGUE]
        self.assertEqual(stored, parsed)
        self.assertEqual(len(parsed), 96)
        removed = text.replace(
            "| `district` | Frame (Public geometry) |",
            "| `removed_district` | Frame (Public geometry) |",
            1,
        )
        self.assertNotIn(
            ("district", "Frame (Public geometry)", ("district_key",)),
            section_rows(removed),
        )
        changed = text.replace(
            "| `pub_place` | Public |",
            "| `pub_place` | Simulated |",
            1,
        )
        self.assertIn(("pub_place", "Simulated", ("place_id",)), section_rows(changed))
        self.assertNotEqual(section_rows(changed), stored)
