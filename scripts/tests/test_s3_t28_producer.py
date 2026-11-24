"""Command-to-producer wiring without store drivers or a real Public cache."""

from __future__ import annotations

import hashlib
import json
import unittest
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from public_assembly_fixture import approve, dump, inputs
from s3_t28_support import IDENTITY, WorkspaceCase
from test_s3_t28_controls import without_call

from commands.main import main
from eii_core.manifest import canonical_json
from eii_custodian.release.assembly import read_assembly
from operations.build import build_release
from operations.common import Refusal


class ProducerCommand(WorkspaceCase):
    def prepare(self) -> Path:
        cache = self.root / "data/public_cache"
        inputs(cache)
        approve(cache)
        return cache

    def sandbox(self, profile: str, layout: Any, command: Any) -> Any:
        self.assertEqual(profile, "build-release")
        self.assertIn("public_release.py", command[3])
        read_assembly(layout.cache)
        (layout.staging / "manifest.json").write_text(
            json.dumps(
                dict(
                    release_id=IDENTITY,
                    release_kind="public_only",
                )
            )
        )
        return SimpleNamespace(returncode=0)

    def test_command_materialises_reviewed_outputs_before_readonly_sandbox(
        self,
    ) -> None:
        cache = self.prepare()
        self.assertFalse((cache / "assembly/release.json").exists())
        with patch(
            "commands.build_release.build_release",
            partial(build_release, sandbox=self.sandbox, validate=Mock()),
        ):
            self.assertEqual(main(["build-release"], {}, self.root), 0)
        self.assertTrue((cache / "assembly/release_review.json").is_file())
        self.assertTrue((self.root / "data/releases" / IDENTITY).is_dir())

    def test_dangling_spec_refuses_before_valid_legacy_envelope_can_build(self) -> None:
        cache = self.prepare()
        candidate = json.loads((cache / "assembly/release_candidate.json").read_bytes())
        legacy = dict(
            candidate,
            files={
                "assembly/final_audit.json": candidate["files"][
                    "assembly/final_audit.json"
                ]
            },
        )
        review = json.loads((cache / "review/release_approval.json").read_bytes())
        review["input_sha256"] = hashlib.sha256(
            canonical_json(legacy).encode()
        ).hexdigest()
        dump(cache / "assembly/release.json", legacy)
        dump(cache / "assembly/release_review.json", review)
        spec = cache / "review/release_spec.json"
        spec.unlink()
        spec.symlink_to(cache / "INVENTED-missing-spec.json")
        self.assertEqual(read_assembly(cache), legacy)
        sandbox = Mock(side_effect=self.sandbox)
        with self.assertRaisesRegex(Refusal, "^assembly_path_invalid$"):
            build_release(self.root, cache=cache, sandbox=sandbox, validate=Mock())
        sandbox.assert_not_called()
        self.assertEqual(list((self.root / ".operations/build").iterdir()), [])
        self.assertFalse((self.root / "data/releases").exists())

    def test_omitted_adapter_invocation_makes_same_command_assertion_red(self) -> None:
        self.prepare()
        without_producer = without_call(build_release, "produce")
        with patch(
            "commands.build_release.build_release",
            partial(without_producer, sandbox=self.sandbox, validate=Mock()),
        ):
            result = main(["build-release"], {}, self.root)
        outcome = unittest.TestResult()
        unittest.FunctionTestCase(lambda: self.assertEqual(result, 0)).run(outcome)
        self.assertEqual(len(outcome.failures), 1)
        self.assertEqual(outcome.errors, [])
        self.assertFalse((self.root / "data/releases").exists())

    def test_each_bad_input_blocks_sandbox_and_cleans_owned_vault(self) -> None:
        for plant in ("missing_receipt", "hash", "kind", "table", "chain", "review"):
            with self.subTest(plant=plant):
                cache = self.root / plant / "data/public_cache"
                spec = inputs(cache)
                approve(cache)
                source = spec["sources"]["INVENTED-source"]
                if plant == "missing_receipt":
                    (cache / source["receipt"]["path"]).unlink()
                elif plant == "hash":
                    (cache / source["body"]["path"]).write_bytes(b"{}")
                elif plant == "review":
                    (cache / "review/release_approval.json").unlink()
                else:
                    receipt_path = cache / source["receipt"]["path"]
                    receipt = json.loads(receipt_path.read_bytes())
                    if plant == "kind":
                        receipt["kind"] = "synthetic_feed"
                    elif plant == "chain":
                        receipt.pop("publisher")
                    else:
                        spec["tables"][0]["name"] = "INVENTED-unknown"
                    receipt_path.write_text(json.dumps(receipt))
                    source["receipt"]["sha256"] = hashlib.sha256(
                        receipt_path.read_bytes()
                    ).hexdigest()
                    (cache / "review/release_spec.json").write_text(json.dumps(spec))
                sandbox = Mock(
                    side_effect=AssertionError("INVENTED-sandbox-must-not-run")
                )
                with patch(
                    "commands.build_release.build_release",
                    partial(build_release, sandbox=sandbox, validate=Mock()),
                ):
                    self.assertEqual(
                        main(["build-release"], {}, cache.parents[1]),
                        8 if plant == "review" else 4,
                    )
                sandbox.assert_not_called()
                self.assertEqual(
                    list((cache.parents[1] / ".operations/build").iterdir()), []
                )
                self.assertFalse((cache.parents[1] / "data/releases").exists())

    def test_each_refusal_is_deciding_with_valid_legacy_consumer_input(self) -> None:
        without_producer = without_call(build_release, "produce")
        for plant in ("missing_receipt", "hash", "kind", "table", "chain", "review"):
            with self.subTest(plant=plant):
                for name, implementation in (
                    ("checked", build_release),
                    ("unchecked", without_producer),
                ):
                    root = self.root / (plant + "-" + name)
                    cache = root / "data/public_cache"
                    spec = inputs(cache)
                    candidate = approve(cache)
                    # The original consumer contract bound the reviewed data
                    # and final audit, without knowing the new S2 input spec.
                    legacy = dict(
                        candidate,
                        files={
                            "assembly/final_audit.json": candidate["files"][
                                "assembly/final_audit.json"
                            ]
                        },
                    )
                    review = json.loads(
                        (cache / "review/release_approval.json").read_bytes()
                    )
                    review["input_sha256"] = hashlib.sha256(
                        canonical_json(legacy).encode()
                    ).hexdigest()
                    dump(cache / "assembly/release.json", legacy)
                    dump(cache / "assembly/release_review.json", review)
                    source = spec["sources"]["INVENTED-source"]
                    receipt_path = cache / source["receipt"]["path"]
                    if plant == "missing_receipt":
                        receipt_path.unlink()
                    elif plant == "hash":
                        (cache / source["body"]["path"]).write_bytes(b"{}")
                    elif plant == "review":
                        (cache / "review/release_approval.json").unlink()
                    else:
                        if plant == "table":
                            spec["tables"][0]["name"] = "INVENTED-unknown"
                        else:
                            receipt = json.loads(receipt_path.read_bytes())
                            if plant == "kind":
                                receipt["kind"] = "synthetic_feed"
                            else:
                                receipt.pop("publisher")
                            source["receipt"]["sha256"] = dump(receipt_path, receipt)
                        dump(cache / "review/release_spec.json", spec)
                    self.assertEqual(read_assembly(cache), legacy)
                    sandbox = Mock(side_effect=self.sandbox)
                    with patch(
                        "commands.build_release.build_release",
                        partial(implementation, sandbox=sandbox, validate=Mock()),
                    ):
                        result = main(["build-release"], {}, root)
                    if name == "checked":
                        self.assertEqual(result, 8 if plant == "review" else 4)
                        sandbox.assert_not_called()
                        self.assertFalse((root / "data/releases").exists())
                    else:
                        self.assertEqual(result, 0)
                        sandbox.assert_called_once()
                        self.assertTrue((root / "data/releases" / IDENTITY).is_dir())
                        outcome = unittest.TestResult()

                        def still_refuses(
                            result: int = result,
                            expected: int = 8 if plant == "review" else 4,
                        ) -> None:
                            self.assertEqual(result, expected)

                        unittest.FunctionTestCase(still_refuses).run(outcome)
                        self.assertEqual(len(outcome.failures), 1)
                        self.assertEqual(outcome.errors, [])
