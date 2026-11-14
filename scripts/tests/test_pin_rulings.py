"""S1-T08 requires a ruling and a written retreat or reason for every pin."""

from __future__ import annotations

import re
import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pack_anchors import _heading_text

ROOT = Path(__file__).resolve().parents[2]
RULING = re.compile(r"\b(confirmed:|confirmed by use:|not installed:) ")
PROGRESS = re.compile(r'PROGRESS\.md heading (?:"([^"\n]+)"|([^;\n]+))')
TASK = re.compile(r"\bS[0-9]+-T[0-9]+\b")
NO_RETREAT = "retreat ruling S1-T08: none exists: "


def faults(rows: list[dict[str, str]]) -> list[str]:
    headings = {
        heading.split(" (pull request ", 1)[0]
        for line in (ROOT / "PROGRESS.md").read_text(encoding="utf-8").splitlines()
        if (heading := _heading_text(line)) is not None
    }
    completed = set()
    for section in re.split(
        r"(?m)(?=^### S[0-9]+-T[0-9]+ )",
        (ROOT / "TASKS.md").read_text(encoding="utf-8"),
    ):
        ident = TASK.match(section.removeprefix("### "))
        if ident and re.search(
            r"(?m)^- Delivery:.*; status (?:done|merged)\b", section
        ):
            completed.add(ident.group())
    failures = []
    for row in rows:
        note = row.get("note", "")
        rulings = list(RULING.finditer(note))
        if len(rulings) != 1:
            failures.append(f"{row['name']}: expected exactly one pin ruling")
        else:
            ruling = rulings[0]
            body = note[ruling.end() :].split(";", 1)[0].strip()
            if not body:
                failures.append(f"{row['name']}: empty pin ruling")
            if ruling.group(1) != "not installed:":
                citations = [a or b.strip() for a, b in PROGRESS.findall(note)]
                if not citations or any(cite not in headings for cite in citations):
                    failures.append(
                        f"{row['name']}: missing or unknown PROGRESS.md heading"
                    )
            elif completed.intersection(TASK.findall(note)):
                failures.append(
                    f"{row['name']}: not-installed ruling names a completed task"
                )
        if row["retreat"] == "none recorded" and (
            NO_RETREAT not in note
            or not note.split(NO_RETREAT, 1)[1].split(";", 1)[0].strip()
        ):
            failures.append(f"{row['name']}: missing no-retreat registry ruling")
    return failures


class PinRulings(unittest.TestCase):
    def test_every_pin_has_a_ruling_and_retreat(self) -> None:
        root = Path(__file__).resolve().parents[2]
        record = tomllib.loads((root / "pins.toml").read_text(encoding="utf-8"))
        self.assertEqual(faults(record["component"]), [])

    def test_planted_missing_ruling_and_retreat(self) -> None:
        table = tomllib.loads(
            """
            [[component]]
            name = "synthetic-missing-ruling"
            retreat = "1.0.0"
            [[component]]
            name = "synthetic-missing-retreat"
            retreat = "none recorded"
            note = "not installed: slice S3 installs it and confirms it"
            """
        )
        self.assertEqual(
            faults(table["component"]),
            [
                "synthetic-missing-ruling: expected exactly one pin ruling",
                "synthetic-missing-retreat: missing no-retreat registry ruling",
            ],
        )


class PlantedRulings(unittest.TestCase):
    def row(self, note: str, retreat: str = "1.0.0") -> dict[str, str]:
        return {"name": "synthetic-ruling", "retreat": retreat, "note": note}

    def test_a_bare_ruling(self) -> None:
        for words in ("confirmed: ", "confirmed by use: ", "not installed: "):
            with self.subTest(words=words):
                self.assertTrue(faults([self.row(words)]))

    def test_a_empty_none_exists(self) -> None:
        self.assertTrue(
            faults(
                [
                    self.row(
                        "retreat ruling S1-T08: none exists: ; not installed: no task needs it",
                        "none recorded",
                    )
                ]
            )
        )

    def test_a_bare_none_exists(self) -> None:
        self.assertTrue(
            faults(
                [
                    self.row(
                        "not installed: no task needs it; retreat ruling S1-T08: none exists: ",
                        "none recorded",
                    )
                ]
            )
        )

    def test_b_two_rulings(self) -> None:
        self.assertTrue(
            faults(
                [
                    self.row(
                        "not installed: no task needs it and confirmed: a measured run"
                    )
                ]
            )
        )

    def test_c_missing_progress_citation(self) -> None:
        for words in ("confirmed: ", "confirmed by use: "):
            with self.subTest(words=words):
                self.assertTrue(faults([self.row(words + "a measured run")]))

    def test_c_nonexistent_progress_heading(self) -> None:
        self.assertTrue(
            faults(
                [
                    self.row(
                        "confirmed: a measured run; PROGRESS.md heading synthetic-missing-heading"
                    )
                ]
            )
        )

    def test_d_completed_task(self) -> None:
        self.assertTrue(
            faults([self.row("not installed: S0-T06 installs it and confirms it")])
        )

    def test_pending_task_remains_valid(self) -> None:
        self.assertEqual(
            faults([self.row("not installed: S8-T02 installs it and confirms it")]), []
        )
