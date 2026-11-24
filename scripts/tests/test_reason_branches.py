"""Each refined refusal changes one input and asserts its exact closed code."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from public_assembly_fixture import approve, dump, inputs
from s3_t28_support import WorkspaceCase

from eii_core.manifest import canonical_json
from eii_core.source_chain import SourceChainRefusal
from eii_custodian.release import assembly, producer
from eii_custodian.release.approval import approval_reason
from operations.common import Refusal

APPROVALS: tuple[tuple[str, object, str], ...] = (
    ("extra", "INVENTED", "approval_fields_invalid"),
    ("verdict", "PENDING", "approval_verdict_invalid"),
    ("builder", " ", "approval_builder_invalid"),
    ("reviewer", [], "approval_reviewer_invalid"),
    ("reviewer", " INVENTED-BUILDER ", "approval_same_maker"),
    ("code_version", "ab" * 20, "approval_code_mismatch"),
    ("input_sha256", "ab" * 32, "approval_hash_mismatch"),
)


class RefinedBranches(WorkspaceCase):
    def test_each_approval_condition_refuses_before_materialisation(self) -> None:
        inputs(self.root)
        approve(self.root)
        path = self.root / producer.APPROVAL
        original = json.loads(path.read_bytes())
        self.assertIsNone(
            approval_reason(
                original, original["code_version"], original["input_sha256"]
            )
        )
        for field, value, expected in APPROVALS:
            with self.subTest(field=field, expected=expected):
                review = {**original, field: value}
                dump(path, review)
                with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                    producer.produce(self.root)
                self.assertFalse((self.root / "assembly/release.json").exists())
                self.assertFalse((self.root / "assembly/release_review.json").exists())
        self.assertEqual(
            approval_reason([], original["code_version"], original["input_sha256"]),
            "approval_fields_invalid",
        )

    def test_candidate_missing_approval_has_own_exit_and_no_release(self) -> None:
        from commands import build_release
        from operations.build import build_release as build

        cache = self.root / "cache"
        inputs(cache)
        output = io.StringIO()
        sandbox = Mock()
        with (
            patch.object(
                build_release,
                "build_release",
                side_effect=lambda root: build(root, cache=cache, sandbox=sandbox),
            ),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(build_release.run(self.root, {}, []), 8)
        self.assertEqual(
            output.getvalue().splitlines()[0],
            "FAIL build-release: candidate_written_approval_missing",
        )
        self.assertTrue((cache / "assembly/release_candidate.json").is_file())
        self.assertFalse((cache / "assembly/release.json").exists())
        sandbox.assert_not_called()

    def test_receipt_fields_have_individual_reasons(self) -> None:
        spec = inputs(self.root)
        ref = spec["sources"]["INVENTED-source"]
        original = json.loads((self.root / ref["receipt"]["path"]).read_bytes())
        cases: list[tuple[str, object, str]] = [
            (field, None, "producer_receipt_" + field + "_invalid")
            for field in (
                "source_id",
                "publisher",
                "retrieved_utc",
                "sha256",
                "fetch_url",
                "title_en",
                "key",
                "licence_id",
                "licence_basis",
            )
        ]
        cases.extend(
            [
                ("key", "INVENTED-other", "producer_receipt_key_mismatch"),
                ("switched_off", True, "producer_receipt_switched_off"),
                ("sha256", "ab" * 32, "producer_receipt_body_hash_mismatch"),
                ("fetch_url", "INVENTED-invalid", "producer_receipt_url_invalid"),
                ("retrieved_utc", "INVENTED-invalid", "producer_receipt_date_invalid"),
                ("kind", "synthetic_feed", "producer_non_public"),
            ]
        )
        for field, value, expected in cases:
            with self.subTest(field=field, expected=expected):
                receipt = {**original, field: value}
                changed = copy.deepcopy(ref)
                changed["receipt"]["sha256"] = dump(
                    self.root / ref["receipt"]["path"], receipt
                )
                with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                    producer._source(self.root, "INVENTED-source", changed, {})
        receipt = {**original, "licence_id": ""}
        changed = copy.deepcopy(ref)
        changed["receipt"]["sha256"] = dump(self.root / ref["receipt"]["path"], receipt)
        producer._source(self.root, "INVENTED-source", changed, {})
        # One change from the valid basis-only citation removes its sole licence.
        receipt["licence_basis"] = ""
        changed["receipt"]["sha256"] = dump(self.root / ref["receipt"]["path"], receipt)
        with self.assertRaisesRegex(ValueError, "^producer_receipt_licence_missing$"):
            producer._source(self.root, "INVENTED-source", changed, {})

    def test_receipt_and_reference_shapes_each_change_one_valid_input(self) -> None:
        ref = inputs(self.root)["sources"]["INVENTED-source"]
        producer._source(self.root, "INVENTED-source", ref, {})
        with self.assertRaisesRegex(ValueError, "^producer_schema_refused$"):
            producer._source(self.root, "INVENTED-source", {**ref, "extra": None}, {})
        ref["receipt"]["sha256"] = dump(self.root / ref["receipt"]["path"], [])
        with self.assertRaisesRegex(ValueError, "^producer_receipt_shape_invalid$"):
            producer._source(self.root, "INVENTED-source", ref, {})

    def test_assembly_path_hash_and_review_have_distinct_reasons(self) -> None:
        inputs(self.root)
        candidate = approve(self.root)
        review = json.loads((self.root / producer.APPROVAL).read_bytes())
        for plant, expected in (
            ("shape", "assembly_input_refused"),
            ("review", "approval_hash_mismatch"),
            ("hash", "assembly_file_hash_mismatch"),
            ("path", "assembly_path_refused"),
        ):
            with self.subTest(plant=plant):
                document = copy.deepcopy(candidate)
                approval = dict(review)
                if plant == "review":
                    approval["input_sha256"] = "ab" * 32
                elif plant == "shape":
                    document["version"] = 2
                    approval["input_sha256"] = hashlib.sha256(
                        canonical_json(document).encode()
                    ).hexdigest()
                else:
                    document["files"][
                        "../INVENTED"
                        if plant == "path"
                        else "assembly/final_audit.json"
                    ] = "ab" * 32
                    approval["input_sha256"] = hashlib.sha256(
                        canonical_json(document).encode()
                    ).hexdigest()
                dump(self.root / "assembly/release.json", document)
                dump(self.root / "assembly/release_review.json", approval)
                with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                    assembly.read_assembly(self.root)

    def test_prepare_preserves_chain_and_structural_faults(self) -> None:
        for error, expected in (
            (SourceChainRefusal("source_link_unknown"), "source_link_unknown"),
            (KeyError("INVENTED"), "input_key_missing"),
            (TypeError("INVENTED"), "input_type_invalid"),
            (AttributeError("INVENTED"), "input_attribute_missing"),
        ):
            with (
                self.subTest(expected=expected),
                patch.object(producer, "_candidate", side_effect=error),
            ):
                with self.assertRaisesRegex(ValueError, "^" + expected + "$"):
                    producer.prepare(self.root)

    def test_web_build_launch_and_nonzero_refuse_without_child_text(self) -> None:
        from operations.package import prepare_archive

        for result, error, expected in (
            (None, OSError("INVENTED/private"), "application_web_build_unavailable"),
            (
                SimpleNamespace(returncode=1, stderr="INVENTED/private SQL"),
                None,
                "application_web_build_nonzero",
            ),
        ):
            with (
                self.subTest(expected=expected),
                patch("operations.package.source_files", return_value={"uv.lock": b""}),
                patch("operations.package.dependency_files", return_value={}),
                patch(
                    "operations.package.subprocess.run",
                    return_value=result,
                    side_effect=error,
                ),
            ):
                with self.assertRaisesRegex(Refusal, "^" + expected + "$"):
                    prepare_archive(self.root, "ab" * 20, self.root / "out", {})

    def test_missing_catalogue_target_is_a_named_refusal(self) -> None:
        import export_web_catalogue

        output = io.StringIO()
        with (
            patch.object(export_web_catalogue, "render_catalogue", return_value="{}"),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(
                export_web_catalogue.run(self.root, self.root / "absent", True), 1
            )
        self.assertEqual(output.getvalue(), "catalogue_target_missing\n")

    def test_each_asset_reason_and_priority(self) -> None:
        from eii_product.api.health import asset_reason

        self.assertEqual(asset_reason(("ok", "ok", "ok")), "installed_local_assets")
        self.assertEqual(asset_reason(("missing", "ok", "ok")), "basemap_missing")
        self.assertEqual(asset_reason(("ok", "missing", "ok")), "fonts_missing")
        self.assertEqual(asset_reason(("ok", "ok", "missing")), "replays_missing")
        self.assertEqual(
            asset_reason(("missing", "missing", "missing")),
            "basemap_missing_fonts_missing_replays_missing",
        )
        self.assertEqual(
            asset_reason(("ok", "invalid", "missing")), "fonts_invalid_replays_missing"
        )

    def test_entire_asset_status_domain_retains_exact_failed_slots(self) -> None:
        from itertools import product
        from typing import cast

        from eii_product.api.health import AssetStatus, asset_reason

        for statuses in product(("ok", "missing", "invalid"), repeat=3):
            assets = cast(tuple[AssetStatus, AssetStatus, AssetStatus], statuses)
            with self.subTest(assets=assets):
                expected = [
                    (name, state)
                    for name, state in zip(
                        ("basemap", "fonts", "replays"), assets, strict=True
                    )
                    if state != "ok"
                ]
                code = asset_reason(assets)
                if not expected:
                    self.assertEqual(code, "installed_local_assets")
                else:
                    tokens = code.split("_")
                    self.assertEqual(
                        list(zip(tokens[::2], tokens[1::2], strict=True)), expected
                    )

    def test_packaging_inventory_and_source_drift_still_refuse(self) -> None:
        from operations.package import prepare_archive

        original = {"uv.lock": b""}
        with (
            patch("operations.package.source_files", return_value=original) as sources,
            patch("operations.package.dependency_files", return_value={}),
            patch(
                "operations.package.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ),
            patch(
                "operations.package.write_archive", return_value=self.root / "archive"
            ),
        ):
            self.assertEqual(
                prepare_archive(self.root, "ab" * 20, self.root / "out", {}),
                self.root / "archive",
            )
            sources.side_effect = [original, {**original, "INVENTED.py": b"changed"}]
            with self.assertRaisesRegex(Refusal, "^application_commit_mismatch$"):
                prepare_archive(self.root, "ab" * 20, self.root / "out", {})

            sources.side_effect = None
            dist = self.root / "web/dist"
            dist.mkdir(parents=True)
            target = self.root / "INVENTED-file"
            target.write_bytes(b"INVENTED")
            (dist / "linked").symlink_to(target)
            with self.assertRaisesRegex(Refusal, "^application_inventory_invalid$"):
                prepare_archive(self.root, "ab" * 20, self.root / "out", {})

    def test_live_receipt_error_preserves_its_inner_code(self) -> None:
        import live_public_release_load as live

        from eii_product.store.receipt import ReceiptRefusal

        dump(self.root / "manifest.json", {"artefacts": []})
        with patch(
            "eii_product.store.receipt.read_receipt",
            side_effect=ReceiptRefusal("receipt_unreadable"),
        ):
            with self.assertRaisesRegex(live._Stop, "^receipt_unreadable$"):
                live.receipt_complete_not_artefact(self.root, "ab" * 32)


if __name__ == "__main__":
    unittest.main()
