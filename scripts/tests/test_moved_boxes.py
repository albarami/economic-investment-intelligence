"""Guard the word-for-word acceptance transfers of S2-P32 (lead ruling L-1320)."""

from __future__ import annotations

import argparse
import re
import unittest
from pathlib import Path

TASKS = Path(__file__).resolve().parents[2] / "TASKS.md"
FDI_BOX = (
    "FDI projects are shown in full, with every field available on cards, lists and "
    "the map; each card, list and map legend carries collapsed credits naming the "
    "agency as publisher, the data gatherer as the page names it, the date read and "
    "a link to the dashboard, with the page's caveat that the data \"includes "
    'estimates of publicly announced projects" and "does not capture all investment '
    'projects"; capital and jobs are labelled as announced estimates, never added '
    "to measured figures or shown beside them without that label; no field is "
    "dropped at loading; the footer's reproduction notice is recorded in document "
    "04 in the publisher's own words, read 2026-11-14 from the fetch of 2026-11-13 "
    "(PUB-12; decision 0026)"
)
RESTRICTED_BOX = (
    "each expected value or numeric finding of a source without an open licence "
    "that no committed test pins (the findings of PUB-71 among them; OI-195, "
    "OI-276) is checked by a test under `custodian/data_tests/` that reads the "
    "uncommitted public cache"
)


def task_section(text: str, task: str) -> str:
    match = re.search(
        rf"^### {re.escape(task)} —[^\n]*\n.*?(?=^#{{1,3}} |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing task section: {task}")
    return match.group(0)


class MovedBoxesTests(unittest.TestCase):
    def assert_moved_box(
        self,
        source: str,
        target: str,
        box: str,
        *,
        tasks_path: Path = TASKS,
        prefix: str = "",
    ) -> None:
        text = tasks_path.read_text(encoding="utf-8")
        source_section = task_section(text, source)
        target_section = task_section(text, target)
        self.assertIn(box, target_section, f"{target}: moved wording changed")
        self.assertIn(
            f"[ ] {prefix}{box}",
            target_section,
            f"{target}: moved criterion must stay unticked with its scope",
        )
        source_boxes = re.findall(
            r"\[[ xX]\] (.*?)(?=; \[[ xX]\] |\n|\Z)", source_section
        )
        for source_box in source_boxes:
            self.assertNotIn(box, source_box, f"{source}: criterion not moved")
        self.assertIn(
            f"Moved to task {target}, unticked and word for word, by the owner's "
            "decision of 2026-11-21 05:34 (S2 gate items 14 and 15; lead ruling "
            "L-1320)",
            source_section,
        )

    def test_s2_t12_box_moved_to_s3_t12(self) -> None:
        self.assert_moved_box("S2-T12", "S3-T12", FDI_BOX, tasks_path=TASKS)

    def test_s2_t35_box_retained_and_c12_part_moved_to_s6_t13(self) -> None:
        text = TASKS.read_text(encoding="utf-8")
        source_section = task_section(text, "S2-T35")
        target_section = task_section(text, "S6-T13")
        self.assertIn(
            f"- Acceptance criteria: [ ] {RESTRICTED_BOX}; [",
            source_section,
            "S2-T35: original first criterion must stay unticked in its place",
        )
        self.assertIn(RESTRICTED_BOX, target_section, "S6-T13: moved wording changed")
        self.assertIn(
            f"[ ] for card C12, MTH-46, {RESTRICTED_BOX}",
            target_section,
            "S6-T13: moved criterion must stay unticked with its C12 scope",
        )
        self.assertIn(
            "The card C12 part (MTH-46) of the first box moved to task S6-T13, "
            "unticked and word for word, by the owner's decision of 2026-11-21 "
            "05:34 (S2 gate item 15; lead ruling L-1320); the rest of that box "
            "stays here.",
            source_section,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-path", type=Path, default=TASKS)
    arguments, remaining = parser.parse_known_args()
    TASKS = arguments.tasks_path
    unittest.main(argv=[__file__, *remaining])
