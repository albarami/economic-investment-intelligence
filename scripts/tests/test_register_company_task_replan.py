"""Planted guard for OI-162 register-company task ownership (package S2-P17, TST-263 style).

Fails while document 14 keeps the OPEN line without a CLOSED owner sentence and while
OI-162 stays OPEN in its item heading.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs" / "14_IMPLEMENTATION_PLAN.md"
OPEN_ITEMS = ROOT / "OPEN_ITEMS.md"
TASKS = ROOT / "TASKS.md"

OPEN_LINE = (
    "OPEN (decision 0022): which slice and task build the Public table "
    "`pub_register_company`, the company card and the map's establishment points"
)
CLOSED_MARKER = "CLOSED by register-company task re-plan (OI-162"
OWNER_SNIPPET = "task S3-T12"
TABLE_OWNER_SNIPPET = "task S2-T49"
TASK_HEADING = "### S2-T49 — Commerce and financial-centre register Public tables"


class RegisterCompanyTaskReplanTests(unittest.TestCase):
    def test_document_14_names_register_company_owners(self) -> None:
        text = PLAN.read_text(encoding="utf-8")
        self.assertNotIn(OPEN_LINE, text)
        self.assertIn(CLOSED_MARKER, text)
        self.assertIn(OWNER_SNIPPET, text)
        self.assertIn(TABLE_OWNER_SNIPPET, text)

    def test_tasks_md_lists_s2_t49(self) -> None:
        text = TASKS.read_text(encoding="utf-8")
        self.assertIn(TASK_HEADING, text)

    def test_oi_162_closure_names_s2_t49(self) -> None:
        text = OPEN_ITEMS.read_text(encoding="utf-8")
        block = re.search(
            r"## OI-162 —[^\n]*\n(?:.*\n)*?- CLOSED:.*",
            text,
        )
        self.assertIsNotNone(block, "OI-162 CLOSED line missing")
        assert block is not None
        self.assertIn(TABLE_OWNER_SNIPPET, block.group(0))

    def test_oi_162_item_is_closed(self) -> None:
        text = OPEN_ITEMS.read_text(encoding="utf-8")
        match = re.search(
            r"## OI-162 —[^\n]*\n\n- ID: OI-162\n- TYPE: (\w+)",
            text,
        )
        self.assertIsNotNone(match, "OI-162 item block missing")
        assert match is not None
        self.assertEqual(match.group(1), "CLOSED")


if __name__ == "__main__":
    unittest.main()
