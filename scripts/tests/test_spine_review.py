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
        from spine_review import derived_audit_seed

        history = self.review.with_name("activity_spine_audits.json")
        audits = json.loads(history.read_bytes()) if history.exists() else []
        seed = derived_audit_seed(
            tuple(row for row in rows if row.code_length == 7), audits
        )
        record.write_text(
            json.dumps(
                dict(
                    preparer_maker=self.preparer,
                    signer_role=signer,
                    auditor_role=auditor,
                    batch_id="invented-batch",
                    seed=seed,
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
        draw: Path | None = None,
    ) -> Path:
        from spine_review import assemble_audited_review

        draw = self.draw(prepared, paths) if draw is None else draw
        return assemble_audited_review(
            self.root, prepared / "manifest.json", *paths, run_id, draw
        )

    def draw(self, prepared: Path, paths: tuple[Path, Path, Path]) -> Path:
        from spine_review import draw_audit

        target = draw_audit(
            self.root,
            prepared / "manifest.json",
            paths[0],
            paths[2],
            prepared.name + "-draw",
        )
        return target / "draw.json"

    def install_candidate(self, candidate: Path) -> bytes:
        from eii_custodian.publicdata.review.activity import binding_path
        from spine_triage_io import file_hash

        self.review.write_bytes((candidate / "activity_spine.csv").read_bytes())
        audit_path = self.review.with_name("activity_spine_audits.json")
        # Noncanonical whitespace must survive every later pass exactly.
        old_bytes = b" \n" + (candidate / audit_path.name).read_bytes().replace(
            b"{", b"{\n "
        )
        audit_path.write_bytes(old_bytes)
        binding = json.loads((candidate / "activity_spine.binding.json").read_bytes())
        binding["audit_sha256"] = file_hash(audit_path)
        binding_path(self.review).write_text(json.dumps(binding))
        return old_bytes

    def next_batch(
        self, seed: int | None = None
    ) -> tuple[Path, tuple[Path, Path, Path], bytes]:
        from eii_custodian.publicdata.fetch.registry import load_registry
        from eii_custodian.publicdata.review.cache_fixture import (
            real_feed_body,
            write_cached,
        )
        from spine_review import prepare_review_inputs

        first = self.prepare()
        old_bytes = self.install_candidate(self.assemble(first, self.returns(first)))
        entry = next(e for e in load_registry() if e.key == "lic_active")
        write_cached(
            self.cache,
            entry,
            real_feed_body(
                "lic_active",
                [
                    dict(
                        activity_code=code,
                        activity_name_ar="نشاط اصطناعي للاختبار",
                        active_count=1,
                    )
                    for code in ("5610901", "5610902", "561099", "5610903")
                ],
            ),
        )
        prepared = prepare_review_inputs(
            self.root,
            self.cache,
            self.review,
            "invented-second",
            self.preparer,
        )
        paths = self.returns(prepared)
        makers = json.loads(paths[2].read_bytes())
        paths[2].write_text(
            json.dumps(
                {
                    **makers,
                    "seed": makers["seed"] if seed is None else seed,
                    "batch_id": "invented-second-batch",
                }
            )
        )
        return prepared, paths, old_bytes

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

    def cli(self, mode: str, **values: str | Path) -> tuple[int, str]:
        from spine_triage import main

        args = ["--mode", mode]
        for key, value in values.items():
            args.extend(("--" + key.replace("_", "-"), str(value)))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(args, root=self.root)
        return result, output.getvalue()

    def test_cli_modes_are_offline_and_print_closed_output(self) -> None:
        with patch(
            "spine_triage.Gateway", side_effect=AssertionError("gateway forbidden")
        ):
            self.assertEqual(
                self.cli(
                    "prepare",
                    cache=self.cache,
                    review=self.review,
                    run_id="invented-prepare",
                    preparer_maker=self.preparer,
                ),
                (0, "acknowledgement_rows=1 eligible_codes=2 excluded_groups=0\n"),
            )
            prepared = self.cache / "spine_review/invented-prepare"
            signed, audited, makers = self.returns(prepared)
            arguments = dict(
                manifest=prepared / "manifest.json",
                signer_rows=signed,
                maker_record=makers,
            )
            self.assertEqual(
                self.cli("draw", **arguments, run_id="invented-draw"),
                (0, "OK audit draw\n"),
            )
            for missing in arguments:
                partial = {
                    key: value for key, value in arguments.items() if key != missing
                }
                self.assertEqual(
                    self.cli("draw", **partial, run_id="invented-new-draw"),
                    (3, "REFUSED arguments refused\n"),
                )
            self.assertEqual(
                self.cli(
                    "assemble",
                    **arguments,
                    auditor_rows=audited,
                    draw=self.cache / "spine_review/invented-draw/draw.json",
                    run_id="invented-assembled",
                ),
                (0, "OK audited candidate\n"),
            )
            self.assertEqual(
                self.cli(
                    "finalise-check",
                    manifest=prepared / "manifest.json",
                    review=self.cache
                    / "spine_review/invented-assembled/activity_spine.csv",
                    run_id="invented-final",
                ),
                (0, "OK finalised spine\n"),
            )
            for mode, values in (
                ("prepare", {}),
                ("draw", {}),
                ("assemble", {**arguments, "auditor_rows": audited}),
            ):
                self.assertEqual(
                    self.cli(mode, **values, run_id="invented"),
                    (3, "REFUSED arguments refused\n"),
                )
            self.assertEqual(
                self.cli(
                    "prepare",
                    cache=self.cache,
                    review="missing",
                    preparer_maker="invented",
                    run_id="invented",
                ),
                (3, "REFUSED review_input_invalid\n"),
            )

    def test_preserves_earlier_signed_rows_and_audits(self) -> None:
        from spine_review import prepare_review_inputs

        # Real procedure keeps review evidence beside the review, outside the cache.
        folder = self.root / "review"
        folder.mkdir()
        self.review.rename(folder / "activity_spine.csv")
        self.baskets.rename(folder / "baskets.yaml")
        self.review = folder / "activity_spine.csv"
        self.baskets = folder / "baskets.yaml"
        first = self.prepare()
        signed, audited, makers = self.returns(first)
        # First candidate contains a person-signed acknowledgement and audited decisions.
        candidate = self.assemble(first, (signed, audited, makers))
        earlier = read_review_csv(candidate / "activity_spine.csv")
        old_bytes = self.install_candidate(candidate)
        from spine_triage_io import file_hash

        audit_path = self.review.with_name("activity_spine_audits.json")
        prepared = prepare_review_inputs(
            self.root, self.cache, self.review, "invented-second", "invented_preparer"
        )
        self.assertEqual(read_review_csv(prepared / "queue.csv"), ())
        paths = self.returns(prepared)
        second = self.assemble(prepared, paths, "invented-second-assembled")
        self.assertEqual(read_review_csv(second / "activity_spine.csv"), earlier)
        self.assertEqual(
            (second / "activity_spine_audits.json").read_bytes(),
            old_bytes,
        )
        manifest = json.loads((prepared / "manifest.json").read_bytes())
        self.assertEqual(
            manifest["snapshot"]["inputs"]["audits"], file_hash(audit_path)
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
        from spine_review import derived_audit_seed

        makers = json.loads(paths[2].read_bytes())
        makers["seed"] = derived_audit_seed(
            tuple(row for row in signed if row.code_length == 7), []
        )
        paths[2].write_text(json.dumps(makers))
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
        from spine_review import frozen_context, read_makers
        from spine_triage_io import Refusal

        prepared = self.prepare()
        paths = self.returns(prepared)
        record = json.loads(paths[2].read_text())
        context, _ = frozen_context(self.root, prepared / "manifest.json")
        signed = read_review_csv(paths[0])
        for seed in (True, 1.5, "3141592653", 999999999, 4294967296):
            paths[2].write_text(json.dumps({**record, "seed": seed}))
            with (
                self.subTest(seed=seed),
                self.assertRaisesRegex(Refusal, "^audit_seed_invalid$"),
            ):
                read_makers(self.root, paths[2], self.preparer, context, signed, [])
        for seed in (1000000000, 4294967295):
            paths[2].write_text(json.dumps({**record, "seed": seed}))
            with patch("spine_review.derived_audit_seed", return_value=seed):
                self.assertEqual(
                    read_makers(
                        self.root, paths[2], self.preparer, context, signed, []
                    )[0]["seed"],
                    seed,
                )
        paths[2].write_text(json.dumps({**record, "signer_role": "invalid"}))
        with self.assertRaisesRegex(SpineError, "^model audit role is malformed$"):
            read_makers(self.root, paths[2], self.preparer, context, signed, [])

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

    def test_draw_packet_is_blind_and_bound_before_auditor_return(self) -> None:
        from spine_triage_io import file_hash

        prepared = self.prepare()
        paths = self.returns(prepared)
        paths[1].unlink()  # Drawing cannot require or read an auditor return.
        drawn = self.draw(prepared, paths)
        record = json.loads(drawn.read_bytes())
        self.assertEqual(
            record,
            dict(
                manifest_sha256=file_hash(prepared / "manifest.json"),
                signer_rows_sha256=file_hash(paths[0]),
                maker_record_sha256=file_hash(paths[2]),
                seed=json.loads(paths[2].read_bytes())["seed"],
                batch_id="invented-batch",
                sampled_codes=["5610901", "5610902"],
            ),
        )
        packet = json.loads(drawn.with_name("audit_packet.json").read_bytes())
        self.assertEqual(
            packet, json.loads((prepared / "signer_packet.json").read_bytes())
        )
        self.assertTrue(
            all(
                set(row)
                == {"code", "name_ar", "prefix", "class_title_en", "class_title_ar"}
                for row in packet
            )
        )

    def test_draw_input_change_during_validation_refuses(self) -> None:
        import spine_review
        from spine_triage_io import Refusal

        prepared = self.prepare()
        paths = self.returns(prepared)
        original = spine_review.decision_rows

        def change(*args: Any) -> Any:
            result = original(*args)
            paths[0].write_bytes(paths[0].read_bytes() + b"\n")
            return result

        with patch("spine_review.decision_rows", side_effect=change):
            with self.assertRaisesRegex(Refusal, "^returned_inputs_changed$"):
                self.draw(prepared, paths)
        self.assertFalse((prepared.parent / (prepared.name + "-draw")).exists())

    def test_finalise_input_change_during_validation_refuses(self) -> None:
        import spine_review
        from spine_triage_io import Refusal

        prepared = self.prepare()
        candidate = self.assemble(prepared, self.returns(prepared))
        original = spine_review.verify_candidate

        def change(*args: Any) -> Any:
            result = original(*args)
            review = candidate / "activity_spine.csv"
            review.write_bytes(review.read_bytes() + b"\n")
            return result

        with patch("spine_review.verify_candidate", side_effect=change):
            with self.assertRaisesRegex(Refusal, "^returned_inputs_changed$"):
                spine_review.finalise_check(
                    self.root,
                    prepared / "manifest.json",
                    candidate / "activity_spine.csv",
                    "invented-final",
                )
        self.assertFalse((prepared.parent / "invented-final").exists())

    def test_finalise_manifest_change_during_context_refuses(self) -> None:
        import spine_review
        from spine_triage_io import Refusal

        prepared = self.prepare()
        candidate = self.assemble(prepared, self.returns(prepared))
        manifest = prepared / "manifest.json"
        original = spine_review.frozen_context
        calls = 0

        def change(*args: Any) -> Any:
            nonlocal calls
            result = original(*args)
            calls += 1
            if calls == 1:
                manifest.write_bytes(manifest.read_bytes() + b"\n")
            return result

        with patch("spine_review.frozen_context", side_effect=change):
            with self.assertRaisesRegex(Refusal, "^returned_inputs_changed$"):
                spine_review.finalise_check(
                    self.root,
                    manifest,
                    candidate / "activity_spine.csv",
                    "invented-final",
                )
        self.assertFalse((prepared.parent / "invented-final").exists())

    def test_baskets_symlink_refuses_before_reader(self) -> None:
        from spine_triage_io import Refusal

        folder = self.root / "review"
        folder.mkdir()
        self.review.rename(folder / "activity_spine.csv")
        self.review = folder / "activity_spine.csv"
        (folder / "baskets.yaml").symlink_to(self.baskets)
        with patch(
            "spine_review.parse_yaml", side_effect=AssertionError("reader reached")
        ):
            with self.assertRaisesRegex(Refusal, "^input refused$"):
                self.prepare()
        self.assertFalse((self.cache / "spine_review").exists())

    def test_review_audit_symlink_refuses_before_reader(self) -> None:
        from spine_triage_io import Refusal

        folder = self.root / "review"
        folder.mkdir()
        self.review.rename(folder / "activity_spine.csv")
        self.baskets.rename(folder / "baskets.yaml")
        self.review = folder / "activity_spine.csv"
        self.baskets = folder / "baskets.yaml"
        (folder / "activity_spine_audits.json").symlink_to(self.cache / "queue.csv")
        with patch(
            "spine_review.reviewed_selections",
            side_effect=AssertionError("reader reached"),
        ):
            with self.assertRaisesRegex(Refusal, "^input refused$"):
                self.prepare()
        self.assertFalse((self.cache / "spine_review").exists())

    def test_draw_only_samples_thirty_blind_packets(self) -> None:
        from test_spine_review_seed import many_returns

        from eii_custodian.publicdata.review.activity import audit_sample

        prepared, paths = many_returns(self)
        drawn = self.draw(prepared, paths)
        sample = audit_sample(
            [r.code for r in read_review_csv(paths[0])],
            json.loads(paths[2].read_bytes())["seed"],
        )
        packet = json.loads(drawn.with_name("audit_packet.json").read_bytes())
        self.assertEqual(len(packet), 30)
        self.assertEqual([row["code"] for row in packet], list(sample))
        write_review_csv(
            paths[1], [row for row in read_review_csv(paths[1]) if row.code in sample]
        )
        self.assemble(prepared, paths, draw=drawn)

    def test_previous_audits_strict_json(self) -> None:
        from spine_review import previous_audits
        from spine_triage_io import Refusal

        path = self.review.with_name("activity_spine_audits.json")
        for body in (b'[{"seed": 1, "seed": 2}]', b"[{", b"\xff", b"{}"):
            path.write_bytes(body)
            with (
                self.subTest(body=body),
                self.assertRaisesRegex(Refusal, "^previous_audits_invalid$"),
            ):
                previous_audits(self.root, self.review)

    def test_audit_seed_reuse_refuses(self) -> None:
        from spine_review import require_fresh_seed
        from spine_triage_io import Refusal

        with self.assertRaisesRegex(Refusal, "^audit_seed_reused$"):
            require_fresh_seed([{"seed": 3141592653}], 3141592653)
        require_fresh_seed([{"seed": 3141592653}], 3141592654)

    def test_draw_refuses_chosen_seed_for_later_batch(self) -> None:
        from spine_triage_io import Refusal

        prepared, paths, _ = self.next_batch(3141592653)
        with self.assertRaisesRegex(Refusal, "^audit_seed_not_derived$"):
            self.draw(prepared, paths)
        self.assertFalse((prepared.parent / (prepared.name + "-draw")).exists())

    def test_empty_batch_refuses_seed_reuse(self) -> None:
        from spine_review import prepare_review_inputs
        from spine_triage_io import Refusal

        first = self.prepare()
        self.install_candidate(self.assemble(first, self.returns(first)))
        prepared = prepare_review_inputs(
            self.root, self.cache, self.review, "invented-empty", self.preparer
        )
        paths = self.returns(prepared)
        self.assertEqual(read_review_csv(prepared / "queue.csv"), ())
        makers = json.loads(paths[2].read_bytes())
        history = json.loads(
            self.review.with_name("activity_spine_audits.json").read_bytes()
        )
        paths[2].write_text(json.dumps({**makers, "seed": history[0]["seed"]}))
        with self.assertRaisesRegex(Refusal, "^audit_seed_not_derived$"):
            self.draw(prepared, paths)
        self.assertFalse((prepared.parent / "invented-empty-draw").exists())

    def test_assemble_rechecks_seed_from_earlier_valid_batch(self) -> None:
        from spine_triage_io import Refusal

        prepared, paths, old_bytes = self.next_batch()
        seed = json.loads(old_bytes)[0]["seed"]
        makers = json.loads(paths[2].read_bytes())
        paths[2].write_text(json.dumps({**makers, "seed": seed}))
        # Force a hash collision to isolate the unchanged freshness guard.
        with patch("spine_review.derived_audit_seed", return_value=seed):
            with patch("spine_review.require_fresh_seed"):
                drawn = self.draw(prepared, paths)
            with self.assertRaisesRegex(Refusal, "^audit_seed_reused$"):
                self.assemble(prepared, paths, "invented-second-assembled", draw=drawn)
        self.assertFalse((prepared.parent / "invented-second-assembled").exists())

    def test_fresh_second_batch_preserves_prior_record_bytes(self) -> None:
        prepared, paths, old_bytes = self.next_batch()
        candidate = self.assemble(prepared, paths, "invented-second-assembled")
        body = (candidate / "activity_spine_audits.json").read_bytes()
        self.assertTrue(body.startswith(old_bytes[: old_bytes.rfind(b"]")]))
        audits = json.loads(body)
        self.assertEqual(len(audits), 2)
        self.assertEqual(audits[0], json.loads(old_bytes)[0])
        self.assertEqual(audits[1]["codes"], ["5610903"])

    def test_append_preserves_earlier_audit_record_bytes(self) -> None:
        from spine_review import append_audit

        body = b' \n[ { "seed" : 3141592653 }  ]\t\n'
        result = append_audit(body, [{"seed": 3141592653}], {"seed": 3141592654})
        self.assertIn(b'{ "seed" : 3141592653 }', result)
        self.assertEqual(
            json.loads(result), [{"seed": 3141592653}, {"seed": 3141592654}]
        )
        self.assertEqual(append_audit(body, [{"seed": 3141592653}], None), body)


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
    "signer_other_class": "signer_decision_invalid",
    "signer_role": "signer_role_differs",
    "acknowledgement_decision": "acknowledgement_decision_invalid",
    "acknowledgement_role": "acknowledgement_role_invalid",
    "auditor_coverage": "auditor_coverage_differs",
    "auditor_identity": "auditor_identity_differs",
    "audit_disagreement": "audit_decision_differs",
    "previous_audits": "previous_audits_invalid",
}


def refusal_case(plant: str, reason: str) -> Callable[[SpineReviewTest], None]:
    def test(self: SpineReviewTest) -> None:
        from spine_triage_io import Refusal

        if plant == "signer_other_class":
            from eii_custodian.publicdata.fetch.registry import load_registry
            from eii_custodian.publicdata.review.cache_fixture import (
                class_csv,
                write_cached,
            )

            entry = next(e for e in load_registry() if e.key == "cls_isic4")
            write_cached(
                self.cache,
                entry,
                class_csv(
                    [
                        ("5610", "Invented test class"),
                        ("5630", "Another invented class"),
                    ]
                ),
            )
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
        elif plant == "signer_other_class":
            signed[0] = replace(signed[0], isic_class="5630")
        elif plant == "signer_role":
            signed[0] = replace(signed[0], reviewed_by_role="INVENTED other role")
        elif plant == "acknowledgement_decision":
            signed[-1] = replace(signed[-1], status="unreviewed")
        elif plant == "acknowledgement_role":
            signed[-1] = replace(signed[-1], reviewed_by_role=record["signer_role"])
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


def draw_change_case(field: str) -> Callable[[SpineReviewTest], None]:
    def test(self: SpineReviewTest) -> None:
        from spine_triage_io import Refusal

        prepared = self.prepare()
        paths = self.returns(prepared)
        drawn = self.draw(prepared, paths)
        if field in ("manifest", "signer", "makers"):
            path = {
                "manifest": prepared / "manifest.json",
                "signer": paths[0],
                "makers": paths[2],
            }[field]
            path.write_bytes(path.read_bytes() + b"\n")
        else:
            record = json.loads(drawn.read_bytes())
            record[field] = {
                "seed": 3141592654,
                "batch_id": "invented-other",
                "sampled_codes": ["5610901"],
                "manifest_sha256": "0" * 64,
                "signer_rows_sha256": "0" * 64,
                "maker_record_sha256": "0" * 64,
            }[field]
            drawn.write_text(json.dumps(record))
        reason = "audit_seed_not_derived" if field == "seed" else "draw_changed"
        with self.assertRaisesRegex(Refusal, "^" + reason + "$"):
            self.assemble(prepared, paths, draw=drawn)
        self.assertFalse((prepared.parent / "invented-assembled").exists())

    return test


for _field in (
    "manifest",
    "signer",
    "makers",
    "seed",
    "batch_id",
    "sampled_codes",
    "manifest_sha256",
    "signer_rows_sha256",
    "maker_record_sha256",
):
    setattr(SpineReviewTest, "test_refuses_draw_" + _field, draw_change_case(_field))
