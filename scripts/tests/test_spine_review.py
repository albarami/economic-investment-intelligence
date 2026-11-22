"""S2-P60 offline workflow; invented receipts and classifications only."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from spine_triage_fixtures import invented_cache

from eii_custodian.publicdata.review.activity import (
    read_review_csv,
    write_review_csv,
)


class SpineReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        invented_cache(self.root)
        self.cache = self.root / "data/public_cache"
        self.review = self.cache / "review.csv"
        self.preparer = "invented_preparer"
        # Empty reviewed baskets are valid membership, never a mapping approval.
        self.baskets = self.cache / "baskets.yaml"
        self.baskets.write_text(
            json.dumps(
                {
                    "status": "reviewed: INVENTED",
                    "activities": [
                        {"activity": code, "inputs": []}
                        for code in ("5510", "5610", "5630")
                    ],
                }
            )
        )
        for name in ("socket.socket", "socket.getaddrinfo"):
            guard = patch(name, side_effect=AssertionError("network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def prepare(self) -> Path:
        from spine_review import prepare_review_inputs

        return prepare_review_inputs(
            self.root, self.cache, self.review, "invented-prepare", self.preparer
        )

    def returns(self, prepared: Path) -> tuple[Path, Path, Path]:
        signer = "model review: invented_signer model, classification specialist"
        auditor = "model review: invented_auditor model, classification specialist"
        rows = []
        for row in read_review_csv(prepared / "queue.csv"):
            eligible = row.code_length == 7
            rows.append(
                replace(
                    row,
                    status="mapped" if eligible else row.status,
                    reason="reviewer_approved" if eligible else row.reason,
                    isic_class=row.code[:4] if eligible else "",
                    reviewed_by_role=signer if eligible else "INVENTED acknowledgement",
                    reviewed_on="2026-11-21",
                )
            )
        signed = self.cache / "signed.csv"
        audited = self.cache / "audited.csv"
        record = self.cache / "makers.json"
        write_review_csv(signed, rows)
        write_review_csv(
            audited,
            [
                replace(row, reviewed_by_role=auditor, reviewed_on="2026-11-22")
                for row in rows
                if row.code_length == 7
            ],
        )
        record.write_text(
            json.dumps(
                dict(
                    preparer_maker=self.preparer,
                    signer_role=signer,
                    auditor_role=auditor,
                    batch_id="invented-batch",
                    seed=3141592653,
                    audit_date="2026-11-22",
                )
            )
        )
        return signed, audited, record

    def assemble(
        self,
        prepared: Path,
        paths: tuple[Path, Path, Path],
        run_id: str = "invented-assembled",
    ) -> Path:
        from spine_review import assemble_audited_review

        return assemble_audited_review(
            self.root, prepared / "manifest.json", *paths, run_id
        )

    def test_prepare_assemble_finalise_roundtrip(self) -> None:
        from spine_review import finalise_check
        from spine_triage_io import file_hash

        prepared = self.prepare()
        manifest = json.loads((prepared / "manifest.json").read_text())
        self.assertEqual(
            manifest["counts"],
            dict(eligible_codes=2, acknowledgement_rows=1, excluded_groups=0),
        )
        packet = json.loads((prepared / "signer_packet.json").read_text())
        self.assertEqual(len(packet), 2)
        self.assertEqual(packet[0]["class_title_ar"], "")
        paths = self.returns(prepared)
        assembled = self.assemble(prepared, paths)
        binding = json.loads((assembled / "activity_spine.binding.json").read_text())
        self.assertEqual(
            binding["audit_sha256"], file_hash(assembled / "activity_spine_audits.json")
        )
        result = finalise_check(
            self.root,
            prepared / "manifest.json",
            assembled / "activity_spine.csv",
            "invented-final",
        )
        self.assertEqual(
            json.loads((result / "result.json").read_text())["state"], "complete"
        )
        self.assertEqual(read_review_csv(self.review), ())

    def test_unsigned_finalise_refuses_without_output(self) -> None:
        from spine_review import finalise_check
        from spine_triage_io import Refusal

        prepared = self.prepare()
        with self.assertRaisesRegex(Refusal, "^mandatory_review_missing$"):
            finalise_check(
                self.root, prepared / "manifest.json", self.review, "invented-final"
            )
        self.assertFalse((self.cache / "spine_review/invented-final").exists())

    def test_prepare_refusals(self) -> None:
        from spine_review import prepare_review_inputs
        from spine_triage_io import Refusal

        for run in (
            "../escape",
            "Upper",
            "a" * 65,
            "run-" + "1" * 8,
            "run-" + "1" * 11,
        ):
            with (
                self.subTest(run=run),
                self.assertRaisesRegex(Refusal, "^output refused$"),
            ):
                prepare_review_inputs(
                    self.root, self.cache, self.review, run, "invented"
                )
        with self.assertRaisesRegex(Refusal, "^preparer_maker_invalid$"):
            prepare_review_inputs(
                self.root, self.cache, self.review, "invented", "two makers"
            )
        with self.assertRaisesRegex(Refusal, "^cache_location_invalid$"):
            prepare_review_inputs(
                self.root, self.root / "other", self.review, "invented", "invented"
            )
        with self.assertRaisesRegex(Refusal, "^input refused$"):
            prepare_review_inputs(
                self.root,
                self.cache / "../public_cache",
                self.review,
                "invented",
                "invented",
            )
        alias = self.root / "alias"
        alias.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaisesRegex(Refusal, "^input refused$"):
            prepare_review_inputs(self.root, alias, self.review, "invented", "invented")
        self.prepare()
        with self.assertRaisesRegex(Refusal, "^output refused$"):
            self.prepare()

    def test_prepare_unreceipted_and_unreviewed_refusals(self) -> None:
        from eii_custodian.publicdata.review.activity import SpineError
        from eii_custodian.publicdata.review.cache_fixture import CacheError
        from spine_review import prepare_review_inputs

        self.baskets.write_text(
            self.baskets.read_text().replace("reviewed: INVENTED", "pending")
        )
        with self.assertRaisesRegex(SpineError, "^basket file is not reviewed$"):
            self.prepare()
        self.baskets.write_text(
            self.baskets.read_text().replace("pending", "reviewed: INVENTED")
        )
        receipt = next((self.cache / "lic_active").glob("????-??-??/*.meta.json"))
        receipt.unlink()
        with self.assertRaisesRegex(CacheError, "^lic_active: snapshot_missing$"):
            prepare_review_inputs(
                self.root, self.cache, self.review, "invented", "invented"
            )
        self.assertFalse((self.cache / "spine_review").exists())

    def test_cli_modes_are_offline_and_print_closed_output(self) -> None:
        from spine_triage import main

        with patch(
            "spine_triage.Gateway", side_effect=AssertionError("gateway forbidden")
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(
                    [
                        "--mode",
                        "prepare",
                        "--cache",
                        str(self.cache),
                        "--review",
                        str(self.review),
                        "--run-id",
                        "invented-prepare",
                        "--preparer-maker",
                        "invented_preparer",
                    ],
                    root=self.root,
                )
            self.assertEqual(result, 0)
            self.assertEqual(
                output.getvalue(),
                "acknowledgement_rows=1 eligible_codes=2 excluded_groups=0\n",
            )
            prepared = self.cache / "spine_review/invented-prepare"
            signed, audited, makers = self.returns(prepared)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "--mode=assemble",
                            "--manifest",
                            str(prepared / "manifest.json"),
                            "--signer-rows",
                            str(signed),
                            "--auditor-rows",
                            str(audited),
                            "--maker-record",
                            str(makers),
                            "--run-id",
                            "invented-assembled",
                        ],
                        root=self.root,
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "--mode",
                            "finalise-check",
                            "--manifest",
                            str(prepared / "manifest.json"),
                            "--review",
                            str(
                                self.cache
                                / "spine_review/invented-assembled/activity_spine.csv"
                            ),
                            "--run-id",
                            "invented-final",
                        ],
                        root=self.root,
                    ),
                    0,
                )
            for args, reason in (
                (["--mode", "prepare", "--run-id", "invented"], "arguments refused"),
                (
                    [
                        "--mode",
                        "prepare",
                        "--cache",
                        str(self.cache),
                        "--review",
                        "missing",
                        "--preparer-maker",
                        "invented",
                        "--run-id",
                        "invented",
                    ],
                    "review_input_invalid",
                ),
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(args, root=self.root), 3)
                self.assertEqual(output.getvalue(), "REFUSED " + reason + "\n")

    def test_preserves_earlier_signed_rows_and_audits(self) -> None:
        from spine_review import prepare_review_inputs

        first = self.prepare()
        signed, audited, makers = self.returns(first)
        # First candidate contains a person-signed acknowledgement and audited decisions.
        candidate = self.assemble(first, (signed, audited, makers))
        earlier = read_review_csv(candidate / "activity_spine.csv")
        self.review.write_bytes((candidate / "activity_spine.csv").read_bytes())
        for name in ("activity_spine_audits.json",):
            (self.cache / name).write_bytes((candidate / name).read_bytes())
        (self.cache / "review.binding.json").write_bytes(
            (candidate / "activity_spine.binding.json").read_bytes()
        )
        prepared = prepare_review_inputs(
            self.root, self.cache, self.review, "invented-second", "invented_preparer"
        )
        self.assertEqual(read_review_csv(prepared / "queue.csv"), ())
        paths = self.returns(prepared)
        second = self.assemble(prepared, paths, "invented-second-assembled")
        self.assertEqual(read_review_csv(second / "activity_spine.csv"), earlier)
        self.assertEqual(
            (second / "activity_spine_audits.json").read_bytes(),
            (candidate / "activity_spine_audits.json").read_bytes(),
        )

    def test_rejected_row_is_bound_and_audit_disagreement_is_not_accepted(self) -> None:
        prepared = self.prepare()
        paths = self.returns(prepared)
        signed = list(read_review_csv(paths[0]))
        audited = list(read_review_csv(paths[1]))
        signed[0] = replace(
            signed[0],
            status="not_mappable_rejected",
            isic_class="",
            reason="reviewer_rejected",
        )
        audited[0] = replace(
            audited[0],
            status="not_mappable_rejected",
            isic_class="",
            reason="reviewer_rejected",
        )
        write_review_csv(paths[0], signed)
        write_review_csv(paths[1], audited)
        result = self.assemble(prepared, paths)
        self.assertEqual(
            read_review_csv(result / "activity_spine.csv")[0].status,
            "not_mappable_rejected",
        )
        binding = json.loads((result / "activity_spine.binding.json").read_text())
        self.assertEqual(binding["inputs"][0]["code"], "5610")

    def test_cancelled_supplier_is_in_prepared_membership(self) -> None:
        from importlib import import_module

        from eii_custodian.publicdata.fetch.registry import load_registry
        from eii_custodian.publicdata.review.cache_fixture import (
            class_csv,
            real_feed_body,
            write_cached,
        )

        baskets = import_module("custodian.tests.test_baskets").invented_review()
        baskets["status"] = "reviewed: invented"
        self.baskets.write_text(json.dumps(baskets))
        entries = {entry.key: entry for entry in load_registry()}
        write_cached(
            self.cache,
            entries["lic_cancelled"],
            real_feed_body(
                "lic_cancelled",
                [
                    dict(
                        activity_code="4630901",
                        activity_name_ar="مورد مخترع",
                        cancelled_count=1,
                    )
                ],
            ),
        )
        write_cached(
            self.cache,
            entries["cls_isic4"],
            class_csv(
                [("5610", "Invented test class"), ("4630", "Invented supplier class")]
            ),
        )
        prepared = self.prepare()
        membership = json.loads((prepared / "membership.json").read_text())
        self.assertEqual(membership["supplier_codes"], ["4630901"])
        self.assertEqual(membership["playbook_codes"], ["5610901", "5610902"])
        self.assertIn(
            "4630901", {row.code for row in read_review_csv(prepared / "queue.csv")}
        )

    def test_symlink_in_cache_is_refused_before_reader(self) -> None:
        from spine_triage_io import Refusal

        (self.cache / "invented-link").symlink_to(self.baskets)
        with patch(
            "spine_review.reviewed_selections",
            side_effect=AssertionError("reader reached"),
        ):
            with self.assertRaisesRegex(Refusal, "^input refused$"):
                self.prepare()

    def test_each_prepared_output_is_bound(self) -> None:
        from spine_review import frozen_context
        from spine_triage_io import Refusal

        prepared = self.prepare()
        for name in (
            "queue.csv",
            "membership.json",
            "queue.binding.json",
            "signer_packet.json",
        ):
            path = prepared / name
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(Refusal, "^prepared_output_changed$"),
            ):
                frozen_context(self.root, prepared / "manifest.json")
            path.write_bytes(original)

    def test_duplicate_return_code_refuses_specifically(self) -> None:
        from eii_custodian.publicdata.review.activity import SpineError

        prepared = self.prepare()
        paths = self.returns(prepared)
        rows = read_review_csv(paths[0])
        write_review_csv(paths[0], (*rows, rows[0]))
        with self.assertRaisesRegex(SpineError, "^duplicate review code$"):
            self.assemble(prepared, paths)
        self.assertFalse((self.cache / "spine_review/invented-assembled").exists())

    def test_fused_split_and_unicode_judgement_text_refuse(self) -> None:
        from spine_triage_io import Refusal

        prepared = self.prepare()
        paths = self.returns(prepared)
        rows = read_review_csv(paths[0])
        name = rows[0].name_ar
        for changed in (
            name.replace(" ", ""),
            name.replace(" ", "  "),
            name + "\u064e",
        ):
            write_review_csv(paths[0], (replace(rows[0], name_ar=changed), *rows[1:]))
            with (
                self.subTest(changed=changed),
                self.assertRaisesRegex(Refusal, "^judgement_identity_differs$"),
            ):
                self.assemble(prepared, paths)
            self.assertFalse((self.cache / "spine_review/invented-assembled").exists())

    def test_seed_types_bounds_and_role_format(self) -> None:
        from eii_custodian.publicdata.review.activity import SpineError
        from spine_review import read_makers
        from spine_triage_io import Refusal

        prepared = self.prepare()
        paths = self.returns(prepared)
        record = json.loads(paths[2].read_text())
        for seed in (True, 1.5, "3141592653", 999999999, 4294967296):
            paths[2].write_text(json.dumps({**record, "seed": seed}))
            with (
                self.subTest(seed=seed),
                self.assertRaisesRegex(Refusal, "^audit_seed_invalid$"),
            ):
                read_makers(self.root, paths[2], self.preparer)
        for seed in (1000000000, 4294967295):
            paths[2].write_text(json.dumps({**record, "seed": seed}))
            self.assertEqual(
                read_makers(self.root, paths[2], self.preparer)["seed"], seed
            )
        paths[2].write_text(json.dumps({**record, "signer_role": "invalid"}))
        with self.assertRaisesRegex(SpineError, "^model audit role is malformed$"):
            read_makers(self.root, paths[2], self.preparer)

    def test_changed_return_during_validation_refuses(self) -> None:
        import spine_review
        from spine_triage_io import Refusal

        prepared = self.prepare()
        paths = self.returns(prepared)
        original = spine_review.verify_candidate

        def change(*args: Any) -> Any:
            result = original(*args)
            paths[0].write_bytes(paths[0].read_bytes() + b"\n")
            return result

        with patch("spine_review.verify_candidate", side_effect=change):
            with self.assertRaisesRegex(Refusal, "^returned_inputs_changed$"):
                self.assemble(prepared, paths)
        self.assertFalse((self.cache / "spine_review/invented-assembled").exists())


# Each row changes one frozen file or one returned field; all other inputs stay valid.
REFUSALS = {
    "manifest_contract": "manifest_contract_invalid",
    "duplicate_json_key": "json_input_invalid",
    "frozen_baskets": "frozen_inputs_changed",
    "manifest_outputs": "manifest_outputs_invalid",
    "prepared_queue": "prepared_output_changed",
    "maker_fields": "maker_record_invalid",
    "preparer_changed": "preparer_maker_changed",
    "same_preparer": "signer_maker_conflict",
    "same_auditor": "signer_maker_conflict",
    "seed": "audit_seed_invalid",
    "signer_coverage": "signer_coverage_differs",
    "judgement_name": "judgement_identity_differs",
    "signer_decision": "signer_decision_invalid",
    "signer_role": "signer_role_differs",
    "acknowledgement_decision": "acknowledgement_decision_invalid",
    "auditor_coverage": "auditor_coverage_differs",
    "auditor_identity": "auditor_identity_differs",
    "audit_disagreement": "audit_decision_differs",
    "previous_audits": "previous_audits_invalid",
}


def refusal_case(plant: str, reason: str) -> Callable[[SpineReviewTest], None]:
    def test(self: SpineReviewTest) -> None:
        from spine_triage_io import Refusal

        if plant == "same_preparer":
            self.preparer = "invented_signer"
        if plant == "previous_audits":
            (self.cache / "activity_spine_audits.json").write_text("{}")
        prepared = self.prepare()
        paths = self.returns(prepared)
        manifest_path = prepared / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        record = json.loads(paths[2].read_text())
        signed = list(read_review_csv(paths[0]))
        audited = list(read_review_csv(paths[1]))
        if plant == "manifest_contract":
            manifest["method"] = "invented-other"
        elif plant == "frozen_baskets":
            self.baskets.write_bytes(self.baskets.read_bytes() + b"\n")
        elif plant == "manifest_outputs":
            del manifest["outputs"]["queue.csv"]
        elif plant == "prepared_queue":
            (prepared / "queue.csv").write_bytes(
                (prepared / "queue.csv").read_bytes() + b"\n"
            )
        elif plant == "maker_fields":
            del record["batch_id"]
        elif plant == "preparer_changed":
            record["preparer_maker"] = "invented_other"
        elif plant == "same_auditor":
            record["auditor_role"] = record["signer_role"].replace(
                "invented_signer", "INVENTED_SIGNER"
            )
            audited = [
                replace(row, reviewed_by_role=record["auditor_role"]) for row in audited
            ]
        elif plant == "seed":
            record["seed"] = 999999999
        elif plant == "signer_coverage":
            signed.pop()
        elif plant == "judgement_name":
            signed[0] = replace(signed[0], name_ar="اسم مخترع معدل")
        elif plant == "signer_decision":
            signed[0] = replace(signed[0], reason="reviewer_rejected")
        elif plant == "signer_role":
            signed[0] = replace(signed[0], reviewed_by_role="INVENTED other role")
        elif plant == "acknowledgement_decision":
            signed[-1] = replace(signed[-1], status="unreviewed")
        elif plant == "auditor_coverage":
            audited.pop()
        elif plant == "auditor_identity":
            audited[0] = replace(audited[0], reviewed_on="2026-11-21")
        elif plant == "audit_disagreement":
            audited[0] = replace(
                audited[0],
                status="not_mappable_rejected",
                isic_class="",
                reason="reviewer_rejected",
            )
        manifest_path.write_text(json.dumps(manifest))
        if plant == "duplicate_json_key":
            manifest_path.write_text(
                manifest_path.read_text().replace(
                    '"method":', '"method": "invented", "method":', 1
                )
            )
        paths[2].write_text(json.dumps(record))
        write_review_csv(paths[0], signed)
        write_review_csv(paths[1], audited)
        with self.assertRaisesRegex(Refusal, "^" + reason + "$"):
            self.assemble(prepared, paths)
        self.assertFalse((self.cache / "spine_review/invented-assembled").exists())

    return test


for _plant, _reason in REFUSALS.items():
    setattr(SpineReviewTest, "test_refuses_" + _plant, refusal_case(_plant, _reason))
