"""The joined database proofs stay confined to the guards matrix leg."""

from __future__ import annotations

import copy
import unittest

import ci_support
import ci_workflow_rules as rules

import ci_aggregate

NAMES = (
    "Start the database service",
    "Create the owner role",
    "Load the public release",
    "Load the public release with a planted difference",
)
CONDITION = "${{ matrix.suite == 'python-guards' }}"


class DatabaseMatrix(unittest.TestCase):
    def test_database_steps_are_declared_and_workflow_passes(self) -> None:
        text = (ci_support.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        document = rules._parse_workflow(text)
        self.assertEqual(ci_aggregate.shape_problems(document), [])
        self.assertEqual(rules.check_no_weakeners({"ci.yml": text}), [])
        steps = document["jobs"]["suite"]["steps"]
        database = [step for step in steps if step["name"] in NAMES]
        self.assertEqual(tuple(step["name"] for step in database), NAMES)
        for step in database:
            self.assertEqual(step["if"], CONDITION)

    def test_each_database_condition_is_required_exactly(self) -> None:
        text = (ci_support.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        document = rules._parse_workflow(text)
        for name in NAMES:
            for condition in (
                None,
                "${{ false }}",
                "${{ matrix.suite == 'python-core' }}",
            ):
                with self.subTest(name=name, condition=condition):
                    planted = copy.deepcopy(document)
                    step = next(
                        s
                        for s in planted["jobs"]["suite"]["steps"]
                        if s["name"] == name
                    )
                    if condition is None:
                        del step["if"]
                    else:
                        step["if"] = condition
                    self.assertIn(
                        f"FAIL step-missing: suite: {name}",
                        ci_aggregate.shape_problems(planted),
                    )

    def test_condition_is_not_admitted_on_other_steps_or_workflows(self) -> None:
        text = (ci_support.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        planted = text.replace(
            "      - name: Run one suite\n",
            f"      - name: Run one suite\n        if: {CONDITION}\n",
            1,
        )
        self.assertIn(
            "ci.yml: step or job condition",
            rules.check_no_weakeners({"ci.yml": planted}),
        )
        self.assertIn(
            "FAIL step-key: suite: Run one suite: if",
            ci_aggregate.shape_problems(rules._parse_workflow(planted)),
        )
        docs = (ci_support.WORKFLOW_DIR / "docs.yml").read_text(encoding="utf-8")
        self.assertEqual(rules.check_no_weakeners({"docs.yml": docs}), [])
        planted_docs = docs.replace(
            "      - name: Check out\n",
            f"      - name: Check out\n        if: {CONDITION}\n",
            1,
        )
        self.assertNotEqual(planted_docs, docs)
        self.assertIn(
            "docs.yml: step or job condition",
            rules.check_no_weakeners({"docs.yml": planted_docs}),
        )

    def test_duplicate_database_condition_is_refused(self) -> None:
        text = (ci_support.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        for name in NAMES:
            with self.subTest(name=name):
                header = f"      - name: {name}\n        if: {CONDITION}\n"
                planted = text.replace(header, header + f"        if: {CONDITION}\n", 1)
                self.assertNotEqual(planted, text)
                self.assertIn(
                    "ci.yml: step or job condition",
                    rules.check_no_weakeners({"ci.yml": planted}),
                )

    def test_duplicate_database_step_condition_is_refused(self) -> None:
        text = (ci_support.WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
        for name in NAMES:
            with self.subTest(name=name):
                header = f"      - name: {name}\n"
                start = text.index(header)
                end = min(
                    text.index("      - name:", start + len(header)),
                    text.index("\n  web-spikes:", start),
                )
                planted = text[:end] + text[start:end] + text[end:]
                self.assertIn(
                    "ci.yml: step or job condition",
                    rules.check_no_weakeners({"ci.yml": planted}),
                )
                self.assertIn(
                    f"FAIL step-extra: suite: {name}",
                    ci_aggregate.shape_problems(rules._parse_workflow(planted)),
                )
