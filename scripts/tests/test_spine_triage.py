"""S2-T05 acceptance: offline triage never signs a mapping."""

import builtins
import contextlib
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from spine_triage_fixtures import invented_cache, recorded_answers

from eii_custodian.publicdata.review.activity import (
    CODE_SYSTEM_VERSION,
    ReviewRow,
    SpineError,
    SupplierMembership,
    binding_path,
    build_spine,
    finalise_spine,
    read_review_csv,
    review_binding,
)
from eii_gateway import Gateway
from eii_gateway.memo import digest
from eii_gateway.records import RUNS
from eii_gateway.schema import validate_record


class SpineTriageTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.args = invented_cache(self.root)
        self.cache = self.root / "data/public_cache"
        for name in ("socket.socket", "socket.getaddrinfo"):
            guard = patch(name, side_effect=AssertionError("network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def test_retains_reviewed_older_snapshot_and_refuses_tamper(self) -> None:
        from eii_custodian.publicdata.fetch.registry import load_registry
        from eii_custodian.publicdata.fetch.snapshots import (
            read_snapshot,
            reviewed_selections,
        )
        from eii_custodian.publicdata.review.cache_fixture import (
            CacheError,
            write_cached,
        )

        entry = next(row for row in load_registry() if row.key == "lic_active")
        older = read_snapshot(
            self.cache / entry.key, reviewed_selections(self.cache)[entry.key]
        )
        write_cached(self.cache, entry, b"syn-newer-invalid-rows", select=False)
        self.assertTrue(self.context().receipts)
        older.path.write_bytes(b"syn-tamper")
        with self.assertRaisesRegex(CacheError, "snapshot_hash_mismatch"):
            self.context()

    def test_orphan_body_reuse_hashes_verified_receipt(self) -> None:
        from eii_custodian.publicdata.fetch.registry import load_registry
        from eii_custodian.publicdata.fetch.snapshots import (
            read_snapshot,
            reviewed_selections,
        )
        from eii_custodian.publicdata.review.cache_fixture import write_cached
        from spine_triage_io import file_hash

        entry = next(row for row in load_registry() if row.key == "lic_active")
        identity = reviewed_selections(self.cache)[entry.key]
        directory = self.cache / entry.key
        older = read_snapshot(directory, identity)
        body = older.body
        receipt = older.path.with_name(f"{identity}.meta.json")
        receipt.unlink()
        (directory / f"{identity}.meta.json").unlink()
        (directory / "index" / f"{identity}.json").unlink()
        self.assertTrue(older.path.exists())
        reused = write_cached(
            self.cache, entry, body, retrieved_utc="2026-11-02T00:00:00Z"
        )
        self.assertEqual(reused, older.path)
        self.assertFalse(receipt.exists())
        actual_receipt = directory / "2026-11-02" / f"{identity}.meta.json"
        self.assertTrue(actual_receipt.is_file())
        self.assertEqual(
            self.context().hashes["lic_active_receipt"], file_hash(actual_receipt)
        )

    def context(self) -> Any:
        from spine_triage_io import load_context

        return load_context(
            self.root,
            self.cache,
            self.cache / "review.csv",
            self.cache / "queue.csv",
            self.cache / "membership.json",
        )

    def invoke(self, provider: str = "none", extra: list[str] | None = None) -> int:
        from spine_triage import main, requests

        def invented_requests(context: Any) -> Any:
            return {
                code: replace(request, input_class="synthetic")
                for code, request in requests(context).items()
            }

        with (
            patch("spine_triage.requests", side_effect=invented_requests),
            patch.dict(os.environ, {"EII_DECISION_PROVIDER": provider}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return main(self.args + (extra or []), root=self.root)

    def replay(self) -> Path:
        from spine_triage import requests

        return recorded_answers(self.root, dict(requests(self.context())))

    def test_requests_have_exact_closed_contract(self) -> None:
        from spine_triage import requests

        # INVENTED cache only; inspect the boundary without selecting a provider.
        context = self.context()
        pairs = requests(context)
        self.assertEqual(list(pairs), ["5610901", "5610902"])
        title = context.inputs.classes[0]
        for code, request in pairs.items():
            with self.subTest(code=code):
                self.assertEqual(
                    asdict(request),
                    {
                        "decision_class": "spine_match",
                        "kind": "yes_no",
                        "input_class": "public",
                        "input_text": request.input_text,
                        "language": "ar",
                        "rubric_id": "spine-triage-v1",
                        "rubric_text": "Does the Arabic activity name fit the supplied "
                        "ISIC class title? Answer yes or no.",
                        "route": "offline-spine-triage-v1",
                        "options": (),
                        "case_id": "spine-" + code,
                    },
                )
                row = next(
                    row for row in context.inputs.spine.queue if row.code == code
                )
                self.assertEqual(
                    json.loads(request.input_text),
                    {
                        "activity_name_ar": row.name_ar,
                        "class_code": "5610",
                        "class_title_en": title.label_en,
                        "class_title_ar": title.label_ar,
                        "code_system_version": CODE_SYSTEM_VERSION,
                    },
                )

    def test_all_priority_groups_are_stable_and_accounted(self) -> None:
        from spine_triage import triage

        context = self.context()
        row, _, legacy = context.inputs.spine.queue
        queue = tuple(replace(row, code="561090" + str(n)) for n in range(1, 7))
        queue = (*queue[:3], legacy, *queue[3:])
        context = replace(
            context,
            inputs=replace(
                context.inputs, spine=replace(context.inputs.spine, queue=queue)
            ),
        )
        # INVENTED in-memory replies; no adapter is constructed or configured.
        gateway = Mock(spec=Gateway, configured="recorded", endpoint=None, remaining=20)
        answers = iter(("yes", "no", None, "yes", "no", None))

        def decide(request: object) -> dict[str, object]:
            answer = next(answers)
            gateway.remaining -= 1
            return {
                "threshold_outcome": "DECIDED" if answer else "BELOW_THRESHOLD",
                "returned_label": answer,
                "memo_key": "invented-memo-" + str(gateway.remaining),
            }

        gateway.decide.side_effect = decide
        result = triage(context, cast(Gateway, gateway))
        self.assertEqual(
            result.queue,
            (queue[1], queue[5], queue[2], legacy, queue[6], queue[0], queue[4]),
        )
        self.assertFalse(result.fallback)
        self.assertEqual(
            [item.suggestion for item in result.suggestions],
            [
                "match",
                "mismatch",
                "unresolved",
                "ineligible",
                "match",
                "mismatch",
                "unresolved",
            ],
        )
        self.assertEqual(
            result.evidence,
            {
                "provider": "recorded",
                "rubric_id": "spine-triage-v1",
                "rubric_sha256": digest(
                    "Does the Arabic activity name fit the supplied "
                    "ISIC class title? Answer yes or no."
                ),
                "language": "ar",
                "route": "offline-spine-triage-v1",
                "calls": 6,
                "returned_tokens": 6,
                "model": "synthetic-recorded",
            },
        )
        self.assertEqual(gateway.decide.call_count, 6)
        self.assertEqual(
            [item.memo_key for item in result.suggestions],
            [
                "invented-memo-19",
                "invented-memo-18",
                "invented-memo-17",
                "",
                "invented-memo-16",
                "invented-memo-15",
                "invented-memo-14",
            ],
        )

    def test_each_failure_outcome_restores_prior_decisions_and_stops_calls(
        self,
    ) -> None:
        from spine_triage import MODEL, triage

        original = self.context()
        first, second, legacy = original.inputs.spine.queue
        queue = (first, second, replace(first, code="5610903"), legacy)
        context = replace(
            original,
            inputs=replace(
                original.inputs, spine=replace(original.inputs.spine, queue=queue)
            ),
        )
        for failure in ("ERROR", "UNAVAILABLE"):
            with self.subTest(outcome=failure):
                # INVENTED stand-in exercises the keyed branch without an adapter.
                gateway = Mock(
                    spec=Gateway,
                    configured="jev",
                    endpoint="https://invented.invalid",
                    remaining=7,
                )
                gateway.decide.side_effect = [
                    {
                        "threshold_outcome": "DECIDED",
                        "returned_label": "yes",
                        "memo_key": "a" * 64,
                    },
                    {"threshold_outcome": failure, "memo_key": "b" * 64},
                ]
                result = triage(context, cast(Gateway, gateway))
                self.assertTrue(result.fallback)
                self.assertEqual(result.queue, queue)
                self.assertEqual(gateway.decide.call_count, 2)
                self.assertEqual(
                    [item.suggestion for item in result.suggestions],
                    ["unresolved", "unresolved", "unresolved", "ineligible"],
                )
                self.assertEqual(
                    [item.memo_key for item in result.suggestions],
                    ["a" * 64, "b" * 64, "", ""],
                )
                self.assertEqual(result.evidence["calls"], 2)
                self.assertEqual(result.evidence["model"], MODEL)
                self.assertEqual(
                    result.evidence["route"],
                    "offline-spine-triage-v1-" + digest("https://invented.invalid"),
                )

    def test_each_provider_exception_has_closed_refusal_or_fallback(self) -> None:
        from spine_triage import triage
        from spine_triage_io import Refusal

        for configured in ("none", "jev"):
            for error in (OSError, ValueError, KeyError, TypeError):
                with self.subTest(configured=configured, error=error):
                    # INVENTED stand-in only; the environment stays provider none.
                    gateway = Mock(
                        spec=Gateway,
                        configured=configured,
                        endpoint="https://invented.invalid",
                        remaining=0,
                    )
                    gateway.decide.side_effect = error("invented private body")
                    if configured == "none":
                        with self.assertRaisesRegex(Refusal, "^provider refused$"):
                            triage(self.context(), cast(Gateway, gateway))
                    else:
                        result = triage(self.context(), cast(Gateway, gateway))
                        self.assertTrue(result.fallback)
                        self.assertEqual(
                            result.queue, self.context().inputs.spine.queue
                        )
                        self.assertNotIn("invented private body", str(result))
                    self.assertEqual(gateway.decide.call_count, 1)

    def test_context_and_output_preserve_exact_lineage_and_columns(self) -> None:
        from spine_triage_io import Result, Suggestion, write_outputs

        context = self.context()
        expected_hashes = {
            name: hashlib.sha256(
                (self.cache / (name + "." + suffix)).read_bytes()
            ).hexdigest()
            for name, suffix in (
                ("review", "csv"),
                ("queue", "csv"),
                ("membership", "json"),
            )
        }
        receipts = {}
        for key in ("lic_active", "lic_cancelled", "cls_isic4"):
            path = next((self.cache / key).glob("????-??-??/*.meta.json"))
            expected_hashes[key + "_receipt"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            body = json.loads(path.read_text())
            receipts[body["source_id"]] = {
                name: body[name]
                for name in (
                    "source_id",
                    "publisher",
                    "landing_url",
                    "licence_id",
                    "licence_basis",
                    "retrieved_utc",
                    "sha256",
                )
            }
        self.assertEqual(context.hashes, expected_hashes)
        self.assertEqual({row["source_id"]: row for row in context.receipts}, receipts)
        self.assertEqual(len(context.receipts), 3)
        # INVENTED dotted-code row proves the reversible code path in suggestions.
        result = Result(
            context.inputs.spine.queue,
            (Suggestion("5610" + "0000", "5610", "unresolved", "invented-memo"),),
            False,
            {"invented": "evidence"},
        )
        target = write_outputs(context, "invented-lineage", result)
        self.assertEqual(target, self.cache / "spine_triage/invented-lineage")
        with (target / "suggestions.csv").open(newline="") as handle:
            self.assertEqual(
                list(csv.reader(handle)),
                [
                    ["code", "candidate_isic_class", "suggestion", "memo_key"],
                    ["5610.0000", "5610", "unresolved", "invented-memo"],
                ],
            )
        binding = review_binding(CODE_SYSTEM_VERSION, context.inputs.classes)
        self.assertEqual(
            json.loads((target / "queue.binding.json").read_text()),
            {
                "code_system_version": CODE_SYSTEM_VERSION,
                "inputs": [
                    {"name": name, "code": code, "sha256": sha}
                    for name, code, sha in binding.input_sha256
                ],
            },
        )
        manifest = json.loads((target / "manifest.json").read_text())
        self.assertEqual(
            manifest,
            {
                "method": "spine_triage.v1",
                "inputs": expected_hashes,
                "sources": list(context.receipts),
                "spine": json.loads(json.dumps(asdict(context.inputs.manifest))),
                "state": "complete",
                "evidence": {"invented": "evidence"},
                "outputs": {
                    name: hashlib.sha256((target / name).read_bytes()).hexdigest()
                    for name in ("queue.csv", "suggestions.csv", "queue.binding.json")
                },
            },
        )
        without_manifest = replace(
            context, inputs=replace(context.inputs, manifest=None)
        )
        other = write_outputs(
            without_manifest, "invented-no-manifest", replace(result, fallback=True)
        )
        self.assertIsNone(json.loads((other / "manifest.json").read_text())["spine"])
        self.assertEqual(
            json.loads((other / "manifest.json").read_text())["state"], "fallback"
        )

    def test_each_membership_key_is_required(self) -> None:
        from spine_triage_io import Refusal

        path = self.cache / "membership.json"
        original = json.loads(path.read_text())
        for key in ("playbook_codes", "supplier_codes", "supplier_complete"):
            with self.subTest(key=key):
                path.write_text(
                    json.dumps(
                        {name: value for name, value in original.items() if name != key}
                    )
                )
                with self.assertRaisesRegex(Refusal, "^input refused$"):
                    self.context()

    def test_path_and_code_returns_and_run_id_boundaries(self) -> None:
        from spine_triage_io import Refusal, codes, contained, output_path

        context = self.context()
        self.assertEqual(
            contained(self.root, Path("invented/child")), self.root / "invented/child"
        )
        self.assertEqual(contained(self.root, self.cache), self.cache)
        self.assertEqual(codes(["5610901", "5610.0000"]), ("5610901", "5610" + "0000"))
        self.assertEqual(codes([]), ())
        for run in (
            "a",
            "a" * 64,
            "run-" + "1" * 7,
            "run-" + "1" * 9,
            "run-" + "1" * 10,
            "run-" + "1" * 12,
        ):
            self.assertEqual(
                output_path(context, run), self.cache / "spine_triage" / run
            )
        for run in (
            "a" * 65,
            "run-" + "1" * 8,
            "run-" + "1" * 11,
            "bad/name",
            "Upper",
            "run_",
            "run-\n",
        ):
            with (
                self.subTest(run=run),
                self.assertRaisesRegex(Refusal, "^output refused$"),
            ):
                output_path(context, run)
        for path in (Path("../invented"), self.root.parent / "invented-outside"):
            with (
                self.subTest(path=path.name),
                self.assertRaisesRegex(Refusal, "^input refused$"),
            ):
                contained(self.root, path)
        alias = self.root / "invented-alias"
        alias.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaisesRegex(Refusal, "^input refused$"):
            contained(self.root, alias / "queue.csv")

    def test_script_entry_refuses_before_reading_inputs(self) -> None:
        import runpy

        # INVENTED missing arguments; the script must exit before any cache read.
        with (
            patch.object(sys, "argv", ["spine_triage.py"]),
            patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
            contextlib.redirect_stdout(io.StringIO()) as output,
            self.assertRaises(SystemExit) as stopped,
        ):
            runpy.run_path(
                str(Path(__file__).resolve().parents[1] / "spine_triage.py"),
                run_name="__main__",
            )
        self.assertEqual(stopped.exception.code, 3)
        self.assertEqual(
            output.getvalue(), "REFUSED spine triage input or authorisation\n"
        )

    def test_each_cli_input_is_required_before_context_or_gateway(self) -> None:
        from spine_triage import main

        for name in ("cache", "review", "queue", "membership"):
            arguments = list(self.args)
            index = arguments.index("--" + name)
            del arguments[index : index + 2]
            with (
                self.subTest(name=name),
                patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
                patch(
                    "spine_triage.load_context",
                    side_effect=AssertionError("context forbidden"),
                ),
                patch(
                    "spine_triage.Gateway",
                    side_effect=AssertionError("gateway forbidden"),
                ),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(main(arguments, root=self.root), 3)
                self.assertEqual(
                    output.getvalue(), "REFUSED spine triage input or authorisation\n"
                )

    def test_main_refuses_each_input_exception_without_echo(self) -> None:
        from eii_custodian.publicdata.review.cache_fixture import CacheError
        from spine_triage import main

        for error in (OSError, ValueError, TypeError, SpineError, CacheError):
            with (
                self.subTest(error=error),
                patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
                patch(
                    "spine_triage.load_context",
                    side_effect=error("invented private body"),
                ),
                patch(
                    "spine_triage.Gateway",
                    side_effect=AssertionError("gateway forbidden"),
                ),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(main(self.args, root=self.root), 3)
                self.assertEqual(
                    output.getvalue(), "REFUSED spine triage input or authorisation\n"
                )

    def test_both_binding_inputs_refuse_stale_identity(self) -> None:
        from spine_triage_io import Refusal

        inputs = self.context().inputs
        for name in ("review", "queue"):
            path = binding_path(self.cache / (name + ".csv"))
            original = path.read_bytes() if path.exists() else None
            try:
                path.write_text(
                    json.dumps({"code_system_version": "invented-stale", "inputs": []})
                )
                with (
                    self.subTest(name=name),
                    patch("spine_triage_io.load_activity_inputs", return_value=inputs),
                    self.assertRaisesRegex(Refusal, "^input refused$"),
                ):
                    self.context()
            finally:
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)

    def test_none_fixture_leaves_suite_stdout_clean(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.test_none_preserves_queue_without_network_or_key_access()
        self.assertEqual(output.getvalue(), "")

    def test_none_preserves_queue_without_network_or_key_access(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = invented_cache(root)
            original_import = builtins.__import__
            original_getitem = os._Environ.__getitem__

            def offline_import(name: str, *args: Any, **kwargs: Any) -> Any:
                if "jev_provider" in name:
                    raise AssertionError("configured adapter import forbidden")
                return original_import(name, *args, **kwargs)

            def no_key(env: os._Environ[str], key: str) -> str:
                if "KEY" in key:
                    raise AssertionError("key access forbidden")
                return original_getitem(env, key)

            with (
                contextlib.redirect_stdout(io.StringIO()),
                patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
                patch("socket.socket", side_effect=AssertionError("network forbidden")),
                patch(
                    "socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")
                ),
                patch("builtins.__import__", side_effect=offline_import),
                patch.object(os._Environ, "__getitem__", no_key),
            ):
                from spine_triage import main

                self.assertEqual(main(args, root=root), 0)
            cache = root / "data/public_cache"
            self.assertEqual(
                (cache / "queue.csv").read_bytes(),
                (cache / "spine_triage/invented-run/queue.csv").read_bytes(),
            )

    def test_recorded_orders_without_adopting_mapping(self) -> None:
        self.assertEqual(self.invoke("recorded", ["--fixtures", str(self.replay())]), 0)
        out = self.cache / "spine_triage/invented-run"
        rows = read_review_csv(out / "queue.csv")
        self.assertEqual([r.code for r in rows], ["5610902", "561099", "5610901"])
        self.assertTrue(all(not r.reviewed_by_role and not r.reviewed_on for r in rows))
        self.assertTrue(all(r.status != "mapped" for r in rows))
        ctx = self.context()
        with self.assertRaises(SpineError):
            build_spine(
                ctx.inputs.activities,
                ctx.inputs.classes,
                rows,
                (),
                supplier_membership=SupplierMembership((), True),
            )
        with self.assertRaises(SpineError):
            finalise_spine(ctx.inputs.spine)
        with self.assertRaises(SpineError):
            read_review_csv(out / "suggestions.csv")

    def test_individual_human_signoff_and_binding_required(self) -> None:
        ctx = self.context()
        row = ctx.inputs.spine.queue[0]
        signed = ReviewRow(
            **{
                **asdict(row),
                "status": "mapped",
                "reason": "reviewer_approved",
                "isic_class": "5610",
                "reviewed_by_role": "fixture_reviewer",
                "reviewed_on": "2026-11-01",
            }
        )
        binding = review_binding(CODE_SYSTEM_VERSION, ctx.inputs.classes)
        for invalid in (
            None,
            replace(binding, code_system_version="invented-new-version"),
            replace(binding, input_sha256=(("class_title", "5610", "a" * 64),)),
        ):
            with self.subTest(binding=invalid), self.assertRaises(SpineError):
                build_spine(
                    ctx.inputs.activities,
                    ctx.inputs.classes,
                    (signed,),
                    (),
                    supplier_membership=SupplierMembership((), True),
                    reviewed_binding=invalid,
                )
        for invalid_review in (
            replace(signed, reviewed_by_role=""),
            replace(signed, reviewed_on=""),
        ):
            with self.assertRaises(SpineError):
                build_spine(
                    ctx.inputs.activities,
                    ctx.inputs.classes,
                    (invalid_review,),
                    (),
                    supplier_membership=SupplierMembership((), True),
                    reviewed_binding=binding,
                )
        spine = build_spine(
            ctx.inputs.activities,
            ctx.inputs.classes,
            (signed,),
            (),
            supplier_membership=SupplierMembership((), True),
            reviewed_binding=binding,
        )
        self.assertEqual(sum(r.status == "mapped" for r in spine.rows), 1)
        self.assertEqual(len(spine.queue), 2)

    def test_records_only_in_runs_and_manifest_has_no_payload(self) -> None:
        self.assertEqual(self.invoke(), 0)
        paths = list((self.root / RUNS).glob("*.json"))
        self.assertEqual(len(paths), 2)
        for path in paths:
            record = validate_record(json.loads(path.read_text()))
            self.assertIsNone(record["human_disposition"])
            self.assertEqual(record["threshold_outcome"], "DISABLED")
        manifest = (self.cache / "spine_triage/invented-run/manifest.json").read_text()
        for forbidden in ("نشاط", "returned_scores", "decision_record", "input_text"):
            self.assertNotIn(forbidden, manifest)
        self.assertEqual(
            json.loads(manifest)["spine"]["code_system_version"], CODE_SYSTEM_VERSION
        )
        self.assertEqual(json.loads(manifest)["state"], "complete")
        self.assertEqual(
            json.loads(manifest)["evidence"],
            {
                "provider": "none",
                "rubric_id": "spine-triage-v1",
                "rubric_sha256": digest(
                    "Does the Arabic activity name fit the supplied "
                    "ISIC class title? Answer yes or no."
                ),
                "language": "ar",
                "route": "offline-spine-triage-v1",
                "calls": 2,
                "returned_tokens": 0,
                "model": "none",
            },
        )
        self.assertEqual(
            set(json.loads(manifest)["outputs"]),
            {"queue.csv", "suggestions.csv", "queue.binding.json"},
        )

    def test_queue_corruption_refused_before_gateway(self) -> None:
        path = self.cache / "queue.csv"
        original = path.read_text()
        lines = original.splitlines()
        variants = [
            "\n".join([*lines, lines[1]]) + "\n",
            "\n".join(lines[:-1]) + "\n",
            "\n".join([lines[0], *reversed(lines[1:])]) + "\n",
            original.replace("reviewed_on", "unknown"),
            original.replace(
                "awaiting_human_review,,", "awaiting_human_review,fixture_reviewer,"
            ),
            original.replace("5610901", "5610903"),
        ]
        with patch.object(
            Gateway, "decide", side_effect=AssertionError("call forbidden")
        ):
            for value in variants:
                with self.subTest(value=value):
                    path.write_text(value)
                    self.assertEqual(self.invoke(), 3)
        self.assertFalse((self.root / RUNS).exists())

    def test_membership_contract_refuses_unknown_incomplete_and_wrong_types(
        self,
    ) -> None:
        path = self.cache / "membership.json"
        original = json.loads(path.read_text())
        value: object
        for value in (
            {**original, "extra": True},
            {**original, "supplier_complete": False},
            {**original, "supplier_complete": 1},
            {**original, "playbook_codes": "5610901"},
            {**original, "playbook_codes": {}},
            [],
            {**original, "supplier_codes": ["1" * 8]},
        ):
            with self.subTest(value=value):
                path.write_text(json.dumps(value))
                self.assertEqual(self.invoke(), 3)

    def test_receipt_missing_or_conflicting_refused(self) -> None:
        path = next((self.cache / "lic_active").rglob("*.meta.json"))
        original = path.read_text()
        payload = json.loads(original)
        path.write_text(json.dumps({**payload, "sha256": "a" * 64}))
        self.assertEqual(self.invoke(), 3)
        path.unlink()
        self.assertEqual(self.invoke(), 3)

    def test_stale_queue_binding_refused(self) -> None:
        path = binding_path(self.cache / "queue.csv")
        path.write_text(json.dumps({"code_system_version": "stale", "inputs": []}))
        self.assertEqual(self.invoke(), 3)

    def test_provider_and_arbitrary_argument_refusals(self) -> None:
        self.assertEqual(self.invoke("invalid"), 3)
        self.assertEqual(self.invoke("recorded"), 3)
        for option in ("--prompt", "--input-class", "--decision-class"):
            self.assertEqual(self.invoke(extra=[option, "invented"]), 3)

    def test_output_reuse_traversal_and_symlinks_refused(self) -> None:
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(self.invoke(), 3)
        for run in ("../escape", "", "1bad", "run-" + "1" * 8):
            self.assertEqual(self.invoke(extra=["--run-id", run]), 3)
        link = self.cache / "alias.csv"
        link.symlink_to(self.cache / "queue.csv")
        self.assertEqual(
            self.invoke(extra=["--queue", str(link), "--run-id", "fresh"]), 3
        )
        self.assertEqual(
            self.invoke(extra=["--cache", str(self.root), "--run-id", "fresh"]), 3
        )

    def test_runs_symlink_refused_before_call(self) -> None:
        parent = self.root / "evals/typed_decisions"
        parent.mkdir(parents=True)
        (parent / "runs").symlink_to(self.cache, target_is_directory=True)
        with patch.object(
            Gateway, "decide", side_effect=AssertionError("call forbidden")
        ):
            self.assertEqual(self.invoke(), 3)

    def test_low_missing_and_malformed_answers_stay_unresolved(self) -> None:
        path = self.replay()
        rows = json.loads(path.read_text())
        rows[0]["scores"] = {"yes": 0.6, "no": 0.4}
        rows[1]["label"] = "invented-invalid"
        path.write_text(json.dumps(rows))
        self.assertEqual(self.invoke("recorded", ["--fixtures", str(path)]), 0)
        self.assertEqual(
            (self.cache / "queue.csv").read_bytes(),
            (self.cache / "spine_triage/invented-run/queue.csv").read_bytes(),
        )
        path.write_text("[]")
        self.assertEqual(
            self.invoke("recorded", ["--fixtures", str(path), "--run-id", "missing"]), 0
        )

    def test_memo_repeatability_and_changed_input_identity(self) -> None:
        from eii_gateway.memo import memo_key
        from spine_triage import requests

        path = self.replay()
        self.assertEqual(self.invoke("recorded", ["--fixtures", str(path)]), 0)
        self.assertEqual(
            self.invoke("recorded", ["--fixtures", str(path), "--run-id", "again"]), 0
        )
        records = [json.loads(p.read_text()) for p in (self.root / RUNS).glob("*.json")]
        self.assertEqual(len(records), 4)
        self.assertEqual(len({r["memo_key"] for r in records}), 2)
        request = next(iter(requests(self.context()).values()))
        self.assertNotEqual(
            memo_key(request, "synthetic-recorded"),
            memo_key(
                replace(request, input_text="invented changed name"),
                "synthetic-recorded",
            ),
        )

    def test_qualification_and_caps_refused_without_calls(self) -> None:
        from spine_triage import (
            LANGUAGE,
            MODEL,
            ROUTE,
            RUBRIC,
            RUBRIC_ID,
            keyed_cap,
        )
        from spine_triage_io import Refusal

        path = self.cache / "qualification.json"
        endpoint = "https://invented.invalid"
        identity = {
            "qualified": True,
            "model": MODEL,
            "rubric_id": RUBRIC_ID,
            "rubric_sha256": digest(RUBRIC),
            "language": LANGUAGE,
            "route": ROUTE + "-" + digest(endpoint),
        }
        with self.assertRaises(Refusal):
            keyed_cap(self.root, True, endpoint, "1", None)
        for field in ("model", "rubric_id", "rubric_sha256", "language", "route"):
            path.write_text(json.dumps({**identity, field: "wrong"}))
            with self.subTest(field=field), self.assertRaises(Refusal):
                keyed_cap(self.root, True, endpoint, "1", path)
        path.write_text(json.dumps(identity))
        for raw in (
            None,
            "0",
            "-1",
            "bad",
            "5000001",
            "1" * 9,
            "0" * 7 + "1",
            chr(0x661),
        ):
            with self.subTest(cap=raw), self.assertRaises(Refusal):
                keyed_cap(self.root, True, endpoint, raw, path)
        for authorised, route in ((False, endpoint), (True, None), (True, "")):
            with self.assertRaises(Refusal):
                keyed_cap(self.root, authorised, route, "1", path)
        self.assertEqual(keyed_cap(self.root, True, endpoint, "1", path), 1)
        self.assertEqual(
            keyed_cap(self.root, True, endpoint, "5000000", path), 5_000_000
        )

    def test_empty_queue(self) -> None:
        from spine_triage import triage

        ctx = self.context()
        ctx = replace(
            ctx, inputs=replace(ctx.inputs, spine=replace(ctx.inputs.spine, queue=()))
        )
        with patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}):
            result = triage(ctx, Gateway(self.root))
        self.assertEqual(result.queue, ())
        self.assertEqual(result.suggestions, ())

    def test_serving_import_plant_caught_by_existing_guard(self) -> None:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from import_boundary_guard import PACKAGES, check_imports

        for _, rel in PACKAGES:
            folder = self.root / rel
            folder.mkdir(parents=True)
            (folder / "__init__.py").write_text("")
        (self.root / "product/src/eii_product/planted.py").write_text(
            "import eii_gateway\n"
        )
        failures, _ = check_imports(self.root)
        self.assertTrue(any("forbidden-import" in failure for failure in failures))

    def test_ineligible_invalid_prefix_and_dotted_codes(self) -> None:
        from eii_custodian.publicdata.review.activity import (
            ActivityRow,
            write_queue_csv,
        )
        from spine_triage import triage

        ctx = self.context()
        activities = (
            *ctx.inputs.activities,
            ActivityRow("9999901", "نشاط اصطناعي", 1, 0),
            ActivityRow("5610" + "0000", "نشاط اصطناعي", 1, 0),
        )
        spine = build_spine(
            activities,
            ctx.inputs.classes,
            (),
            (),
            supplier_membership=SupplierMembership((), True),
        )
        ctx = replace(
            ctx, inputs=replace(ctx.inputs, activities=activities, spine=spine)
        )
        with patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}):
            result = triage(ctx, Gateway(self.root))
        self.assertEqual(
            sum(s.suggestion == "ineligible" for s in result.suggestions), 3
        )
        for suggestion in result.suggestions:
            if suggestion.suggestion == "ineligible":
                self.assertEqual(
                    (suggestion.candidate_isic_class, suggestion.memo_key), ("", "")
                )
        path = self.cache / "long.csv"
        write_queue_csv(path, result.queue)
        self.assertIn("5610.0000", path.read_text())
        self.assertEqual(
            [r.code for r in read_review_csv(path)], [r.code for r in result.queue]
        )
        path.write_text(path.read_text().replace("5610.0000", "5610" + "0000"))
        with self.assertRaises(SpineError):
            read_review_csv(path)

    def test_standin_failure_stops_calls_and_restores_baseline(self) -> None:
        from typing import cast

        from spine_triage import triage

        ctx = self.context()

        # No configured provider is selected; this is an in-memory stand-in.
        class Standin:
            configured = "jev"
            endpoint = "https://invented.invalid"
            remaining = 1
            calls = 0

            def decide(self, request: Any) -> dict[str, object]:
                self.calls += 1
                if request.route != "offline-spine-triage-v1-" + digest(self.endpoint):
                    raise AssertionError("route identity differs")
                raise ValueError("invented provider body must never be persisted")

        standin = Standin()
        result = triage(ctx, cast(Gateway, standin))
        self.assertEqual(standin.calls, 1)
        self.assertTrue(result.fallback)
        self.assertEqual(result.queue, ctx.inputs.spine.queue)
        self.assertEqual(
            [s.suggestion for s in result.suggestions],
            ["unresolved", "unresolved", "ineligible"],
        )
        self.assertNotIn("invented provider body", str(result))
        with patch("spine_triage.triage", return_value=result):
            self.assertEqual(self.invoke(), 4)
        manifest = json.loads(
            (self.cache / "spine_triage/invented-run/manifest.json").read_text()
        )
        self.assertEqual(manifest["state"], "fallback")

    def test_standin_error_record_stops_follow_on_calls(self) -> None:
        from typing import cast

        from spine_triage import triage

        class Standin:
            configured = "jev"
            endpoint = "https://invented.invalid"
            remaining = 1
            calls = 0

            def decide(self, request: object) -> dict[str, object]:
                self.calls += 1
                return {"threshold_outcome": "ERROR", "memo_key": "a" * 64}

        standin = Standin()
        result = triage(self.context(), cast(Gateway, standin))
        self.assertEqual(standin.calls, 1)
        self.assertTrue(result.fallback)

    def test_documented_relative_paths(self) -> None:
        self.args = [
            str(Path(arg).relative_to(self.root))
            if arg.startswith(str(self.root))
            else arg
            for arg in self.args
        ]
        self.assertEqual(self.invoke(), 0)

    def test_cli_diagnostics_fixture_shape_and_offline_endpoint(self) -> None:
        from spine_triage import main

        path = self.cache / "malformed.json"
        path.write_text("{}")
        self.assertEqual(self.invoke("recorded", ["--fixtures", str(path)]), 3)
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(main(self.args, root=self.root), 0)
        self.assertEqual(output.getvalue(), "OK unsigned queue\n")
        from spine_triage_io import Result

        result = Result(self.context().inputs.spine.queue, (), True, {})
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
            contextlib.redirect_stdout(output),
            patch("spine_triage.triage", return_value=result),
            patch("spine_triage.Gateway", wraps=Gateway) as factory,
        ):
            self.assertEqual(
                main(
                    [
                        *self.args,
                        "--run-id",
                        "diagnostic",
                        "--endpoint",
                        "invented-ignored",
                    ],
                    root=self.root,
                ),
                4,
            )
            self.assertIsNone(factory.call_args.kwargs["endpoint"])
        self.assertEqual(output.getvalue(), "FALLBACK unsigned queue\n")


if __name__ == "__main__":
    unittest.main()
