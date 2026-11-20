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
S3_T12_HEADING = "### S3-T12 — The living map's Public layers"
OI_162_AMENDMENT = "register-company task re-plan, OI-162"
SYNTHETIC_GUARD = (
    "a planted Simulated figure, or a Synthetic figure other than the permitted "
    "`employee_count`, on a register company fails"
)
DAT_83_TABLES = (
    "outside `register_company_list`, `pub_register_company` and "
    "`pub_register_snapshot`"
)
DAT_83_FIXTURES = (
    "with a positive allowed-key fixture for each table and a planted registration "
    "number in any other table failing"
)


def _task_block(text: str, heading: str) -> str:
    pattern = re.escape(heading) + r"\n(?:(?!^### ).*\n)*"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        return ""
    return match.group(0)


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

    def test_s2_t49_dat_83_criterion(self) -> None:
        text = TASKS.read_text(encoding="utf-8")
        block = _task_block(text, TASK_HEADING)
        self.assertIn(TASK_HEADING, block)
        self.assertNotIn("two key tables", block)
        self.assertIn(DAT_83_TABLES, block)
        self.assertIn(DAT_83_FIXTURES, block)

    def test_s3_t12_oi_162_amendment(self) -> None:
        text = TASKS.read_text(encoding="utf-8")
        block = _task_block(text, S3_T12_HEADING)
        self.assertIn(S3_T12_HEADING, block)
        amendment_lines = [
            line for line in block.splitlines() if OI_162_AMENDMENT in line
        ]
        self.assertEqual(
            len(amendment_lines), 1, "S3-T12 OI-162 amendment line missing"
        )
        amendment = amendment_lines[0]
        for snippet in (
            "company_points",
            "pub_register_company",
            "register_company_list",
        ):
            self.assertIn(snippet, amendment)
        self.assertIn(SYNTHETIC_GUARD, amendment)

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
