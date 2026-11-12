"""Workflow contract tests for S0-T07."""

from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import ci_support as support
import ci_workflow_rules as rules


class WorkflowRules(unittest.TestCase):
    def test_pinned_text_of_the_three_workflows(self) -> None:
        self.assertEqual(set(rules.PINNED_SHA256), rules.WORKFLOW_NAMES)
        for name in rules.WORKFLOW_NAMES:
            with self.subTest(name=name):
                digest = hashlib.sha256(
                    (support.WORKFLOW_DIR / name).read_bytes()
                ).hexdigest()
                self.assertEqual(rules.PINNED_SHA256[name], digest)

    def test_removed_test_command_is_refused_even_as_its_own_reference(self) -> None:
        home, _env = support.temp_home(self)
        folder = support.workflow_fixture(home)
        path = folder / "ci.yml"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [line for line in lines if "./eii test" not in line]
        self.assertEqual(len(lines) - len(kept), 1)
        path.write_text("".join(kept), encoding="utf-8")
        with patch.object(rules, "WORKFLOW_DIR", folder):
            problems = rules.validate(folder)
        self.assertTrue(
            any(
                item.startswith("required-steps:") and "ci.yml" in item
                for item in problems
            ),
            problems,
        )

    def test_action_pin_must_be_exact(self) -> None:
        for mutation in ("trailing-character", "local-action"):
            with self.subTest(mutation=mutation):
                home, _env = support.temp_home(self)
                folder = support.workflow_fixture(home)
                path = folder / "ci.yml"
                text = path.read_text(encoding="utf-8")
                if mutation == "trailing-character":
                    planted, count = re.subn(
                        r"(uses:\s*\S+@[0-9a-f]{40})",
                        r"\g<1>x",
                        text,
                        count=1,
                    )
                else:
                    planted, count = re.subn(
                        r"(uses:\s*)\S+", r"\g<1>./local-action", text, count=1
                    )
                self.assertEqual(count, 1)
                path.write_text(planted, encoding="utf-8")
                self.assertTrue(rules.rule_problems("no-weakeners", folder))

    def test_real_files_pass(self) -> None:
        self.assertEqual(rules.validate(support.WORKFLOW_DIR), [])

    def test_exact_six_check_names(self) -> None:
        self.assertEqual(
            rules.required_check_names(),
            [
                "check-docs",
                "static-checks",
                "tests",
                "secret-scan",
                "planted-failures",
                "sandbox proof",
            ],
        )

    def test_exact_action_pins(self) -> None:
        self.assertEqual(
            rules.pin_commit_hashes(),
            frozenset(
                {
                    "3d3c42e5aac5ba805825da76410c181273ba90b1",
                    "68559e99cc807c1eb7e9238fd43a15bba460eec2",
                    "949feb2413d6458794dcd2491c4babbbce0c15c1",
                }
            ),
        )

    def test_exact_scanner_ordering(self) -> None:
        problems = rules.rule_problems("required-steps", support.WORKFLOW_DIR)
        weakened = [
            item
            for item in problems
            if "fetch the scanner" in item or "before fetching" in item
        ]
        self.assertEqual(weakened, [])

    def test_unchanged_sandbox_file(self) -> None:
        self.assertEqual(rules.sandbox_unchanged(support.WORKFLOW_DIR), [])
        home, _env = support.temp_home(self)
        folder = support.workflow_fixture(home)
        path = folder / "sandbox.yml"
        path.write_text(
            path.read_text(encoding="utf-8") + "# planted comment\n",
            encoding="utf-8",
        )
        self.assertTrue(rules.sandbox_unchanged(folder))

    def test_one_plant_per_rule(self) -> None:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        base = support.workflow_fixture(home)

        def plant_extra(folder: Path) -> None:
            (folder / "extra.yml").write_text("name: x\n", encoding="utf-8")

        def plant_events(folder: Path) -> None:
            text = (folder / "ci.yml").read_text(encoding="utf-8")
            (folder / "ci.yml").write_text(
                text.replace("pull_request:", "workflow_dispatch:", 1),
                encoding="utf-8",
            )

        def plant_jobs(folder: Path) -> None:
            text = (folder / "ci.yml").read_text(encoding="utf-8")
            (folder / "ci.yml").write_text(
                text.replace("\n  secret-scan:\n", "\n", 1),
                encoding="utf-8",
            )

        def plant_steps(folder: Path) -> None:
            text = (folder / "ci.yml").read_text(encoding="utf-8")
            (folder / "ci.yml").write_text(
                text.replace("fetch-depth: 0\n", "", 1),
                encoding="utf-8",
            )

        def plant_weakeners(folder: Path) -> None:
            text = (folder / "ci.yml").read_text(encoding="utf-8")
            (folder / "ci.yml").write_text(
                text.replace(
                    "timeout-minutes: 25\n",
                    "timeout-minutes: 25\n        continue-on-error: true\n",
                    1,
                ),
                encoding="utf-8",
            )

        plants: list[tuple[str, Callable[[Path], None]]] = [
            ("workflow-files", plant_extra),
            ("events-and-permissions", plant_events),
            ("required-jobs", plant_jobs),
            ("required-steps", plant_steps),
            ("no-weakeners", plant_weakeners),
        ]
        for rule, plant in plants:
            with self.subTest(rule=rule):
                folder = home / rule
                shutil.copytree(base, folder)
                plant(folder)
                problems = rules.rule_problems(rule, folder)
                self.assertTrue(problems, rule)

    def test_malformed_workflow_refuses(self) -> None:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        folder = support.workflow_fixture(home)
        (folder / "ci.yml").write_text("jobs: [", encoding="utf-8")
        problems = rules.validate(folder)
        self.assertTrue(any("not valid YAML" in item for item in problems))
