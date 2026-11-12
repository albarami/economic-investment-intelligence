"""Plant-harness tests for S0-T07."""

from __future__ import annotations

import io
import sys
import unittest
from dataclasses import replace
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
        plants.validate_cases(cases.CASES)
        planted = (
            *cases.CASES[:-1],
            replace(cases.CASES[-1], check=cases.CASES[0].check),
        )
        with self.assertRaises(plants.PlantError):
            plants.validate_cases(planted)

    def test_broken_case_table_stops_the_run_before_any_case(self) -> None:
        planted = (
            *cases.CASES[:-1],
            replace(cases.CASES[-1], check=cases.CASES[0].check),
        )
        with patch.object(cases, "CASES", planted):
            with patch.object(plants, "run_case") as run_case:
                with self.assertRaises(plants.PlantError):
                    plants.run_all(support.ROOT, {}, io.StringIO(), io.StringIO())
        run_case.assert_not_called()

    def test_copy_destination_that_resolves_to_the_root_is_refused(self) -> None:
        for destination_kind in ("root", "symlink", "parent"):
            with self.subTest(destination_kind=destination_kind):
                home, env = support.temp_home(self)
                root = support.history_repo(home, env, shallow=False)
                link = home / "root-link"
                link.symlink_to(root, target_is_directory=True)
                destination = {
                    "root": root,
                    "symlink": link,
                    "parent": root.parent,
                }[destination_kind]
                with self.assertRaises(plants.PlantError):
                    plants.make_copy(root, destination, env)

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

    def test_planted_copy_that_passes_is_reported(self) -> None:
        home, env = support.temp_home(self)
        case = cases.CASES[0]
        controls: dict[tuple[str, str], tuple[int, str]] = {}
        with patch.object(plants, "make_copy", return_value=home / "copy"):
            with patch.object(plants, "prepare"):
                with patch.object(
                    plants,
                    "run_check",
                    side_effect=[(0, "clean"), (0, "planted ok")],
                ):
                    with patch.object(cases, "git"):
                        with patch.dict(
                            cases.PLANTS, {case.plant: lambda *_a, **_k: None}
                        ):
                            reason = plants.run_case(
                                case, support.ROOT, home / "scratch", env, controls
                            )
        self.assertIsNotNone(reason)
        self.assertIn("the planted copy passed", reason or "")

    def test_failure_without_the_evidence_line_is_reported(self) -> None:
        home, env = support.temp_home(self)
        case = cases.CASES[0]
        controls: dict[tuple[str, str], tuple[int, str]] = {}
        with patch.object(plants, "make_copy", return_value=home / "copy"):
            with patch.object(plants, "prepare"):
                with patch.object(
                    plants,
                    "run_check",
                    side_effect=[(0, "clean"), (1, "failed without evidence")],
                ):
                    with patch.object(cases, "git"):
                        with patch.dict(
                            cases.PLANTS, {case.plant: lambda *_a, **_k: None}
                        ):
                            reason = plants.run_case(
                                case, support.ROOT, home / "scratch", env, controls
                            )
        self.assertIsNotNone(reason)
        self.assertIn("was not printed", reason or "")

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
        out_fail = io.StringIO()
        err_fail = io.StringIO()
        with patch.object(
            plants,
            "run_case",
            side_effect=[None] * (len(cases.CASES) - 1) + ["planted copy passed"],
        ):
            status_fail = plants.run_all(support.ROOT, {}, out_fail, err_fail)
        self.assertEqual(status_fail, 1)
        self.assertIn("plants: 12 cases, 11 blocked, 1 failed", out_fail.getvalue())
        self.assertIn("RESULT: FAILED", out_fail.getvalue())
        self.assertIn("FAIL plant", err_fail.getvalue())
        self.assertIn(cases.CASES[-1].name, err_fail.getvalue())

    def test_usage(self) -> None:
        status, _stdout, stderr = support.run_module("ci_plants.py", ["wrong"])
        self.assertEqual(status, 2)
        self.assertIn("usage: ci_plants.py run", stderr)
