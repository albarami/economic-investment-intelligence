"""Planted transport and dispatch refusals for S1-T20."""

import copy
import importlib
import unittest

pilot = importlib.import_module("scripts.mutation_pilot")


class PilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = pilot.manifest(
            {
                "commit": "a" * 40,
                "module": pilot.MODULE,
                "hashes": {"source": "b" * 64},
            },
            [
                {"name": f"toy.x_value__mutmut_{n}", "diff_sha256": "c" * 64}
                for n in range(8)
            ],
        )
        self.parts = [
            pilot.report(
                self.manifest,
                n,
                [
                    dict(row, raw_exit=1, status="killed")
                    for row in pilot.assigned(self.manifest, n)
                ],
                0,
            )
            for n in range(4)
        ]

    def refuses(self, reason: str) -> None:
        with self.assertRaisesRegex(pilot.Refusal, reason):
            pilot.merge(self.manifest, self.parts, ["success"] * 4)

    def test_partition_and_five_counts(self) -> None:
        merged = pilot.merge(self.manifest, self.parts, ["success"] * 4)
        self.assertEqual(
            merged["counts"],
            dict(
                killed=8, survived=0, timeout=0, not_covered=0, infrastructure_failure=0
            ),
        )

    def test_injection(self) -> None:
        for value in ("$(touch sentinel)", "a" * 40 + "\n", "--help", "../main"):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(pilot.Refusal, "wrong-ref"),
            ):
                pilot.validate_inputs(pilot.MODULE, value, "refs/heads/main")

    def test_wrong_ref(self) -> None:
        with self.assertRaisesRegex(pilot.Refusal, "workflow-ref"):
            pilot.validate_inputs(pilot.MODULE, "a" * 40, "refs/heads/other")

    def test_wrong_module(self) -> None:
        with self.assertRaisesRegex(pilot.Refusal, "wrong-module"):
            pilot.validate_inputs("custodian/src/other.py", "a" * 40, "refs/heads/main")

    def test_shard_index(self) -> None:
        self.parts[0]["shard_index"] = 1
        self.refuses("shard-index")

    def test_manifest_hash(self) -> None:
        self.parts[0]["manifest_sha256"] = "d" * 64
        self.refuses("manifest-hash")

    def test_assignment_names(self) -> None:
        self.parts[0]["names"] = self.parts[1]["names"]
        self.refuses("assigned-names")

    def test_empty_output(self) -> None:
        self.parts[0] = None
        self.refuses("missing-shard")

    def test_missing_shard(self) -> None:
        self.parts.pop()
        self.refuses("missing-shard")

    def test_failed_shard(self) -> None:
        with self.assertRaisesRegex(pilot.Refusal, "failed-shard"):
            pilot.merge(
                self.manifest, self.parts, ["success", "failure", "success", "success"]
            )

    def test_duplicate(self) -> None:
        self.parts[0]["records"].append(copy.deepcopy(self.parts[0]["records"][0]))
        self.refuses("duplicate-mutant")

    def test_missing_mutant(self) -> None:
        self.parts[0]["records"].pop()
        self.refuses("missing-mutant")

    def test_foreign_mutant(self) -> None:
        self.parts[0]["records"][0]["name"] = "toy.x_foreign__mutmut_9"
        self.refuses("foreign-mutant")

    def test_status_confusion(self) -> None:
        self.parts[0]["records"][0]["status"] = "timeout"
        self.refuses("status-confusion")

    def test_wrong_hash(self) -> None:
        self.parts[0]["records"][0]["diff_sha256"] = "e" * 64
        self.refuses("diff-hash")

    def test_overflow(self) -> None:
        with self.assertRaisesRegex(pilot.Refusal, "payload-overflow"):
            pilot.encode({"x": "a" * pilot.CAP})

    def test_nonzero_propagation(self) -> None:
        self.parts[0]["command_exit"] = 7
        self.refuses("command-failed")

    def test_unknown_outcome_is_infrastructure(self) -> None:
        self.assertEqual(pilot.status(None), "infrastructure_failure")
        self.assertEqual(pilot.status(36), "timeout")
        self.assertEqual(pilot.status(0), "survived")
        self.assertEqual(pilot.status(33), "not_covered")

    def test_comparison_refuses_different_status(self) -> None:
        merged = pilot.merge(self.manifest, self.parts, ["success"] * 4)
        other = copy.deepcopy(merged)
        other["records"][0]["status"] = "timeout"
        other["records"][0]["raw_exit"] = 36
        other = pilot.summary(self.manifest, other["records"])
        self.assertNotEqual(pilot.compare(merged, other), [])

    def test_glob_and_duplicate_manifest(self) -> None:
        for names in (["toy.*"], ["toy.x__mutmut_1"] * 2):
            with self.subTest(names=names), self.assertRaises(pilot.Refusal):
                pilot.manifest(
                    self.manifest["context"],
                    [{"name": n, "diff_sha256": "c" * 64} for n in names],
                )

    def test_survivor_count_difference(self) -> None:
        left = pilot.merge(self.manifest, self.parts, ["success"] * 4)
        right = copy.deepcopy(left)
        right["counts"]["survived"] = 1
        with self.assertRaisesRegex(pilot.Refusal, "summary-mismatch"):
            pilot.compare(left, right)

    def test_wrong_commit_ancestry(self) -> None:
        from pathlib import Path
        from unittest.mock import patch

        with (
            patch.object(
                pilot,
                "git",
                side_effect=[b"commit\n", pilot.Refusal("git-verification-failed")],
            ),
            self.assertRaisesRegex(pilot.Refusal, "git-verification-failed"),
        ):
            pilot.validate_ref(Path.cwd(), pilot.MODULE, "a" * 40, "refs/heads/main")

    def test_unreviewed_implementation(self) -> None:
        from pathlib import Path
        from unittest.mock import patch

        with (
            patch.object(pilot, "git", side_effect=[b"commit\n", b"", b"changed"]),
            self.assertRaisesRegex(pilot.Refusal, "unreviewed-implementation"),
        ):
            pilot.validate_ref(Path.cwd(), pilot.MODULE, "a" * 40, "refs/heads/main")

    def test_duplicate_json_property(self) -> None:
        with self.assertRaisesRegex(pilot.Refusal, "duplicate-property"):
            pilot.decode('{"names":[],"names":[]}')

    def test_symlink_evidence(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            target = folder / "target.json"
            target.write_text("{}")
            link = folder / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(pilot.Refusal, "symlink"):
                pilot.read(link)
            with self.assertRaisesRegex(pilot.Refusal, "symlink"):
                pilot.write(link, {})

    def test_workflow_security_contract(self) -> None:
        import re
        from pathlib import Path

        import yaml

        root = Path(__file__).resolve().parents[2]
        text = (root / ".github/workflows/mutation-pilot.yml").read_text()
        workflow = yaml.safe_load(text)
        ci = (root / ".github/workflows/ci.yml").read_text()
        self.assertEqual(set(workflow[True]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        self.assertEqual(workflow["jobs"]["merge"]["if"], "always()")
        self.assertEqual(workflow["jobs"]["shards"]["strategy"]["max-parallel"], 2)
        self.assertEqual(
            set(workflow["jobs"]["shards"]["outputs"]), {f"shard_{n}" for n in range(4)}
        )
        for job in workflow["jobs"].values():
            self.assertNotIn("permissions", job)
            self.assertNotIn("environment", job)
            for step in job["steps"]:
                self.assertNotIn("continue-on-error", step)
                if "run" in step:
                    self.assertIn("set -euo pipefail", step["run"])
                    self.assertNotIn("${{", step["run"])
                if "uses" in step:
                    self.assertIn(step["uses"], ci)
                    self.assertRegex(step["uses"], r"@[a-f0-9]{40}$")
                    if step["uses"].startswith("actions/checkout"):
                        self.assertFalse(step["with"]["persist-credentials"])
        self.assertNotRegex(text, re.compile(r"secrets[.]"))

    def test_comparison_rejects_incomplete_equal_reports(self) -> None:
        merged = pilot.merge(self.manifest, self.parts, ["success"] * 4)
        records = merged["records"]
        records[0]["raw_exit"] = None
        records[0]["status"] = "infrastructure_failure"
        left = pilot.summary(self.manifest, records)
        right = pilot.summary(self.manifest, copy.deepcopy(records))
        with self.assertRaisesRegex(pilot.Refusal, "incomplete-campaign"):
            pilot.compare(left, right)

    def test_comparison_rejects_different_manifest_commits(self) -> None:
        merged = pilot.merge(self.manifest, self.parts, ["success"] * 4)
        context = dict(self.manifest["context"], commit="b" * 40)
        other_manifest = pilot.manifest(context, self.manifest["mutants"])
        left = pilot.summary(self.manifest, merged["records"])
        right = pilot.summary(other_manifest, copy.deepcopy(merged["records"]))
        with self.assertRaisesRegex(pilot.Refusal, "comparison-manifest"):
            pilot.compare(left, right)
