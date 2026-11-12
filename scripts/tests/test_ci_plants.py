"""Plant-harness tests for S0-T07."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_support as support

import ci_plant_cases as cases
import ci_plants as plants


class PlantHarness(unittest.TestCase):
    def test_exact_twelve_cases(self) -> None:
        self.assertEqual(len(cases.CASES), 12)
        self.assertEqual(len(cases.CLASSES), 12)
        self.assertEqual(len({case.check for case in cases.CASES}), 12)
        self.assertEqual(len({case.name for case in cases.CASES}), 12)
        self.assertEqual(tuple(case.check for case in cases.CASES), cases.CLASSES)

    def test_one_case_per_guard(self) -> None:
        guards = [case.check for case in cases.CASES]
        self.assertEqual(len(guards), len(set(guards)))
        planted = [*guards, guards[0]]
        self.assertNotEqual(len(planted), len(set(planted)))

    def test_clean_before_plant(self) -> None:
        home, env = support.temp_home(self)
        controls: dict[tuple[str, str], tuple[int, str]] = {}
        case = cases.CASES[0]
        with patch.object(plants, "make_copy", return_value=home / "copy"):
            with patch.object(plants, "prepare"):
                with patch.object(
                    plants, "run_check", return_value=(1, "failed control")
                ):
                    reason = plants.run_case(
                        case, support.ROOT, home / "scratch", env, controls
                    )
        self.assertIsNotNone(reason)
        self.assertIn("clean copy failed", reason or "")

    def test_scratch_only_writes(self) -> None:
        home, env = support.temp_home(self)
        case = cases.CASES[0]
        controls: dict[tuple[str, str], tuple[int, str]] = {}
        destinations: list[Path] = []

        def _copy(root: Path, destination: Path, environment: dict[str, str]) -> Path:
            if destination == support.ROOT or destination.is_relative_to(
                support.ROOT / ".git"
            ):
                raise AssertionError("wrote to the real checkout")
            destinations.append(destination)
            destination.mkdir(parents=True, exist_ok=True)
            return destination

        with patch.object(plants, "make_copy", side_effect=_copy):
            with patch.object(plants, "prepare"):
                with patch.object(
                    plants,
                    "run_check",
                    side_effect=[(0, "clean"), (1, case.expect)],
                ):
                    with patch.object(cases, "git"):
                        with patch.dict(
                            cases.PLANTS, {case.plant: lambda *_a, **_k: None}
                        ):
                            reason = plants.run_case(
                                case, support.ROOT, home / "scratch", env, controls
                            )
        self.assertIsNone(reason)
        self.assertEqual(len(destinations), 2)

    def test_blocked_evidence_judgement(self) -> None:
        case = cases.CASES[0]

        def judge(status: int, output: str) -> str | None:
            if status == 0:
                return f"the planted copy passed: {output}"
            if case.expect not in output:
                return (
                    f"status {status} but the line {case.expect!r} was not printed: "
                    f"{output}"
                )
            return None

        missing = judge(1, "failed without evidence")
        self.assertIsNotNone(missing)
        self.assertIn("was not printed", missing or "")
        self.assertIsNone(judge(1, case.expect))

    def test_totals_and_exit(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with patch.object(
            plants,
            "run_case",
            side_effect=[None] * len(cases.CASES),
        ):
            status = plants.run_all(support.ROOT, {}, out, err)
        self.assertEqual(status, 0)
        text = out.getvalue()
        self.assertIn("plants: 12 cases, 12 blocked, 0 failed", text)
        self.assertIn("RESULT: PASSED", text)
        with patch.object(plants, "run_case", return_value="planted copy passed"):
            status_fail = plants.run_all(support.ROOT, {}, io.StringIO(), io.StringIO())
        self.assertEqual(status_fail, 1)

    def test_usage(self) -> None:
        status, _stdout, stderr = support.run_module("ci_plants.py", ["wrong"])
        self.assertEqual(status, 2)
        self.assertIn("usage: ci_plants.py run", stderr)
