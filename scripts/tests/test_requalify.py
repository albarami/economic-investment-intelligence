"""Offline requalification; synthetic replay is never a measurement."""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.typed_decisions.interval import interval

ROOT = Path(__file__).resolve().parents[2]
ADMITTED = ROOT / "evals/typed_decisions/results_2026-11-11.json"


class IntervalTest(unittest.TestCase):
    def test_stated_bounds(self) -> None:
        admitted = json.loads(ADMITTED.read_text())["arms"][
            "jev-1.14.0 (typed-decision provider)"
        ]
        result = interval(admitted["correct"], admitted["answered"])
        self.assertEqual(result["ci95"], admitted["ci95"])


class HarnessSupport(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        from evals.typed_decisions import requalify

        self.harness = requalify
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.cases = json.loads(requalify.CASES.read_text())

    def invoke(self, *args: str) -> tuple[int, str]:
        import contextlib
        import io
        from unittest.mock import patch

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            patch("socket.socket", side_effect=AssertionError("network forbidden")),
            patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")),
        ):
            code = self.harness.main(list(args), root=self.root)
        return code, output.getvalue()

    def fixture(self) -> Path:
        from eii_gateway.memo import input_hash, option_orders

        rows = []
        for case in self.cases:
            request = self.harness.request_for(case, self.cases)
            label = self.harness.encode_label(case, case["expected"])
            for order in option_orders(request):
                rows.append(
                    dict(
                        case_id=case["id"],
                        input_sha256=input_hash(request),
                        order=list(order),
                        label=label,
                        scores={name: float(name == label) for name in request.labels},
                        tokens=0,
                    )
                )
        path = self.root / "synthetic-replay.json"
        path.write_text(json.dumps(rows))
        return path


class HarnessTest(HarnessSupport):
    def test_none_visits_full_set_without_key_or_network(self) -> None:
        import os
        import sys
        from unittest.mock import patch

        with patch.dict(os.environ, {"EII_DECISION_PROVIDER": "jev"}, clear=True):
            code, output = self.invoke("--provider", "none")
        self.assertEqual(code, 0)
        self.assertIn("DISABLED", output)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(
            {row["id"] for row in result["gateway_accepted"]["cases"]},
            {c["id"] for c in self.cases},
        )
        self.assertTrue(
            all(
                row["outcome"] == "DISABLED"
                for row in result["gateway_accepted"]["cases"]
            )
        )
        self.assertFalse(result["admitted_measurement_reproduced"])
        self.assertEqual(result["identity"]["provider"], "none")
        self.assertEqual(result["evidence"], "offline exercise; not a measurement")
        self.assertEqual(
            len(list(self.root.glob("evals/typed_decisions/runs/*.json"))),
            len(self.cases),
        )
        self.assertNotIn("eii_gateway.providers.jev_provider", sys.modules)

    def test_recorded_full_set_orders_and_counts(self) -> None:
        from eii_gateway.memo import option_orders

        fixture = self.fixture()
        code, output = self.invoke("--provider", "recorded", "--fixtures", str(fixture))
        self.assertEqual(code, 0)
        self.assertIn("synthetic replay; not a measurement", output)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(
            result["gateway_accepted"]["overall"]["correct"], len(self.cases)
        )
        self.assertEqual(
            result["gateway_accepted"]["overall"]["total"], len(self.cases)
        )
        self.assertEqual(
            set(result["gateway_accepted"]["by_test"]), {c["test"] for c in self.cases}
        )
        for name, summary in result["gateway_accepted"]["by_test"].items():
            total = sum(c["test"] == name for c in self.cases)
            self.assertEqual(summary["correct"], total)
            self.assertEqual(summary["total"], total)
        preamble = json.loads(output.splitlines()[0])
        self.assertEqual(preamble["case_count"], len(self.cases))
        self.assertEqual(
            preamble["planned_calls"], len(json.loads(fixture.read_text()))
        )
        from math import ceil

        mean = json.loads(ADMITTED.read_text())["arms"][
            "jev-1.14.0 (typed-decision provider)"
        ]["tokens_mean_per_call"]
        self.assertEqual(
            preamble["planned_tokens"], ceil(preamble["planned_calls"] * mean)
        )
        self.assertEqual(preamble["token_cap"], 0)
        self.assertEqual(
            {r["id"] for r in result["gateway_accepted"]["cases"]},
            {c["id"] for c in self.cases},
        )
        self.assertFalse(result["admitted_measurement_reproduced"])
        self.assertTrue(
            all(
                set(v) == {"current", "admitted"}
                for v in result["raw_answers"]["by_test"].values()
            )
        )
        for case, row in zip(
            self.cases, result["gateway_accepted"]["cases"], strict=True
        ):
            self.assertEqual(row["label"], case["expected"])
            self.assertEqual(
                row["orders"],
                [
                    list(o)
                    for o in option_orders(self.harness.request_for(case, self.cases))
                ],
            )
        self.assertEqual(result["identity"]["model"], "synthetic-recorded")
        self.assertEqual(result["evidence"], "offline exercise; not a measurement")

    def test_disagreeing_and_weak_second_choice_are_excluded(self) -> None:
        fixture = self.fixture()
        rows = json.loads(fixture.read_text())
        choices = [c for c in self.cases if c["question_type"] == "choice"][:2]
        for case, mode in zip(choices, ("disagree", "weak"), strict=True):
            pair = [r for r in rows if r["case_id"] == case["id"]]
            second = pair[1]
            if mode == "disagree":
                second["label"] = next(
                    label for label in second["order"] if label != second["label"]
                )
            second["scores"] = {
                label: (0.5 if mode == "weak" else float(label == second["label"]))
                for label in second["order"]
            }
        fixture.write_text(json.dumps(rows))
        code, _ = self.invoke("--provider", "recorded", "--fixtures", str(fixture))
        self.assertEqual(code, 0)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        for row in result["gateway_accepted"]["cases"]:
            if row["id"] in {c["id"] for c in choices}:
                self.assertFalse(row["accepted"])
                self.assertFalse(row["correct"])
        self.assertEqual(
            result["gateway_accepted"]["overall"]["correct"],
            len(self.cases) - len(choices),
        )

    def test_keyed_refusals_precede_provider_and_write_nothing(self) -> None:
        import os
        import sys
        from unittest.mock import patch

        for args, env, reason in (
            ([], {}, "authorisation required"),
            (["--authorised"], {}, "key variable required"),
            (
                ["--authorised"],
                {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"},
                "invalid token cap",
            ),
            *[
                (
                    ["--authorised", "--token-cap", cap],
                    {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"},
                    "invalid token cap",
                )
                for cap in ("0", "-1", "5000001", "1.5", "nan", "1e3")
            ],
            (
                ["--authorised", "--token-cap", "1"],
                {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"},
                "planned use exceeds cap",
            ),
            (
                ["--authorised", "--token-cap", "5000000"],
                {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"},
                "explicit endpoint required",
            ),
        ):
            with (
                self.subTest(args=args),
                patch.dict(os.environ, env, clear=True),
                patch.object(
                    self.harness,
                    "Gateway",
                    side_effect=AssertionError("provider constructed"),
                ),
            ):
                code, output = self.invoke("--provider", "jev", *args)
                self.assertEqual((code, output), (3, f"REFUSED: {reason}\n"))
                self.assertEqual(list(self.root.iterdir()), [])
                self.assertNotIn("eii_gateway.providers.jev_provider", sys.modules)

    def test_paths_and_provider_are_closed(self) -> None:
        for args, reason in (
            (["--provider", "unknown"], "invalid arguments"),
            (["--provider", "recorded"], "recorded fixture required"),
            (
                ["--provider", "none", "--output", str(self.root / ADMITTED.name)],
                "admitted result is immutable",
            ),
        ):
            with self.subTest(args=args):
                self.assertEqual(self.invoke(*args), (3, f"REFUSED: {reason}\n"))
                self.assertEqual(list(self.root.iterdir()), [])

    def test_cases_are_closed_and_labels_nonnumeric(self) -> None:
        from eii_gateway import Request
        from eii_gateway.policy import DataPolicyBlocked, check_policy

        with self.assertRaises(DataPolicyBlocked):
            check_policy("visitor_typed", "spine_match")
        with self.assertRaises(ValueError):
            self.harness.request_for(
                {**self.cases[0], "id": "synthetic-outside"}, self.cases
            )
        choice = next(c for c in self.cases if c["test"] == "A_choice")
        request = self.harness.request_for(choice, self.cases)
        self.assertTrue(all(label.startswith("isic-") for label in request.options))
        self.assertIn(choice["criteria"][0]["description"], request.rubric_text)
        with self.assertRaises(ValueError):
            Request(
                "spine_match",
                "choice",
                "public",
                "SYNTHETIC",
                "en",
                "synthetic",
                "synthetic",
                "synthetic",
                ("1234", "5678"),
            )

    def test_reported_provider_change_requires_requalification(self) -> None:
        from unittest.mock import patch

        with patch("eii_gateway.providers.none_provider.NoneProvider.name", "recorded"):
            code, output = self.invoke("--provider", "none")
        self.assertEqual(code, 2)
        self.assertIn("requalify", output)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(result["identity"]["provider"], "recorded")

    def test_reported_model_change_requires_requalification(self) -> None:
        from unittest.mock import patch

        with patch(
            "eii_gateway.providers.none_provider.NoneProvider.model", "synthetic-drift"
        ):
            code, output = self.invoke("--provider", "none")
        self.assertEqual(code, 2)
        self.assertIn("requalify", output)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(result["identity"]["model"], "synthetic-drift")
        self.assertEqual(result["route_status"], "requalify")

    def test_changed_cases_trigger_requalification(self) -> None:
        from unittest.mock import patch

        changed = self.root / "synthetic-cases.json"
        changed.write_bytes(self.harness.CASES.read_bytes() + b"\n")
        with patch.object(self.harness, "CASES", changed):
            code, output = self.invoke("--provider", "none")
        self.assertEqual(code, 2)
        self.assertIn("requalify", output)


class AggregateTest(HarnessSupport):
    fields: ClassVar[set[str]] = {
        "id",
        "test",
        "label",
        "accepted",
        "correct",
        "outcome",
        "orders",
    }

    def assert_public_fields(self, value: Any) -> None:
        if isinstance(value, dict):
            for name, child in value.items():
                self.assertFalse(
                    isinstance(child, str)
                    and any(
                        word in name.lower()
                        for word in (
                            "key",
                            "token",
                            "secret",
                            "password",
                            "credential",
                            "auth",
                        )
                    ),
                    name,
                )
                self.assert_public_fields(child)
        elif isinstance(value, list):
            for child in value:
                self.assert_public_fields(child)

    def test_written_gateway_cases_have_closed_fields(self) -> None:
        code, _ = self.invoke("--provider", "none")
        self.assertEqual(code, 0)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        for row in result["gateway_accepted"]["cases"]:
            self.assertEqual(set(row), self.fields)

    def test_conversion_preserves_other_values_and_input(self) -> None:
        from copy import deepcopy

        result = json.loads(
            (ADMITTED.parent / KeyedRunReadmeTest.result_name).read_text()
        )
        for row in result["gateway_accepted"]["cases"]:
            row["memo_key"] = "synthetic-digest"
        original = deepcopy(result)
        expected = deepcopy(result)
        for row in expected["gateway_accepted"]["cases"]:
            del row["memo_key"]
        converted = self.harness.committed_aggregate(result)
        self.assertEqual(converted, expected)
        self.assertEqual(result, original)
        self.assertEqual(self.harness.committed_aggregate(converted), expected)

    def test_aggregate_has_no_sensitive_text_fields_with_plants(self) -> None:
        result = json.loads(
            (ADMITTED.parent / KeyedRunReadmeTest.result_name).read_text()
        )
        self.assert_public_fields(self.harness.committed_aggregate(result))
        for word in ("key", "token", "secret", "password", "credential", "auth"):
            for plant in (
                {word: "synthetic-text"},
                {"nested": [{"prefix_" + word.upper() + "_suffix": "synthetic-text"}]},
            ):
                with self.subTest(word=word, plant=plant):
                    with self.assertRaises(AssertionError):
                        self.assert_public_fields(plant)

    def test_sensitive_field_names_allow_whole_number_counts(self) -> None:
        for word in ("key", "token", "secret", "password", "credential", "auth"):
            with self.subTest(word=word):
                self.assert_public_fields({"nested": [{word + "s_used": 1}]})

    def test_committed_file_has_closed_fields_and_canonical_bytes(self) -> None:
        from eii_gateway.memo import canonical

        raw = (ADMITTED.parent / KeyedRunReadmeTest.result_name).read_bytes()
        result = json.loads(raw)
        for row in result["gateway_accepted"]["cases"]:
            self.assertEqual(set(row), self.fields)
        self.assert_public_fields(result)
        self.assertEqual(raw, (canonical(result) + "\n").encode("utf-8"))


class ArithmeticTest(unittest.TestCase):
    def test_invalid_counts_keep_fixed_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "^invalid counts$"):
            interval(-1, 0)

    def test_interval_edges_and_invalid_counts(self) -> None:
        self.assertEqual(interval(0, 0), dict(correct=0, total=0, rate=None, ci95=None))
        self.assertEqual(interval(0, 1)["ci95"], [0.0, 79.3])
        self.assertEqual(interval(1, 1)["ci95"], [20.7, 100.0])
        for counts in ((-1, 1), (2, 1), (0, -1), (True, 1), (0, True), (0.5, 1)):
            with self.assertRaises(ValueError):
                interval(*counts)

    def test_each_side_of_stated_bounds(self) -> None:
        from evals.typed_decisions.interval import inside_stated, reserve

        bounds = json.loads(ADMITTED.read_text())["arms"][
            "jev-1.14.0 (typed-decision provider)"
        ]["ci95"]
        low, high = bounds
        for rate, expected in (
            (low - 0.01, False),
            (low, True),
            (low + 0.01, True),
            (high - 0.01, True),
            (high, True),
            (high + 0.01, False),
        ):
            self.assertEqual(inside_stated(rate, bounds), expected)
        self.assertIsNone(inside_stated(None, bounds))
        self.assertIsNone(inside_stated(low, None))
        self.assertEqual(reserve(3, 1.5), 5)


class IdentityTest(unittest.TestCase):
    def test_every_identity_dimension_requires_requalification(self) -> None:
        from evals.typed_decisions.route import compare, configured

        for provider in ("none", "recorded", "jev"):
            original = configured(provider)
            self.assertEqual(compare(original, dict(original)), "match")
            for field in original:
                altered = dict(original)
                altered[field] = (
                    {"high": 0.95, "low": 0.05}
                    if field == "thresholds"
                    else "synthetic-changed"
                )
                self.assertEqual(compare(altered, original), "requalify")

    def test_identity_hashes_inputs_and_copies_thresholds(self) -> None:
        from evals.typed_decisions.route import identity

        from eii_gateway.memo import digest

        thresholds = {"high": 0.90, "low": 0.10}
        actual = identity(
            "recorded",
            "synthetic-model",
            "synthetic rubric",
            b"synthetic cases",
            thresholds,
        )
        self.assertEqual(
            actual,
            dict(
                provider="recorded",
                model="synthetic-model",
                rubric_sha256=digest("synthetic rubric"),
                cases_sha256=digest("synthetic cases"),
                thresholds=thresholds,
                route_sha256=digest("recorded"),
            ),
        )
        thresholds["high"] = 0.95
        self.assertEqual(actual["thresholds"]["high"], 0.90)

    def test_cap_boundaries_and_output_guards(self) -> None:
        import os
        import tempfile
        from unittest.mock import patch

        from evals.typed_decisions.requalify import Refusal, output_path, token_cap

        with patch.dict(
            os.environ, {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"}, clear=True
        ):
            self.assertEqual(token_cap(True, "1", 1), 1)
            self.assertEqual(token_cap(True, "5000000", 5_000_000), 5_000_000)
            for raw in (chr(0x661), " 1", "1 ", "+1", "0" * 8):
                with self.assertRaisesRegex(Refusal, "invalid token cap"):
                    token_cap(True, raw, 0)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            existing = root / "synthetic-existing.json"
            existing.write_text("synthetic sentinel")
            with self.assertRaisesRegex(Refusal, "result already exists"):
                output_path(root, str(existing))
            with self.assertRaisesRegex(Refusal, "output outside run root"):
                output_path(root, str(root.parent / "synthetic-outside.json"))
            alias = root / "synthetic-alias.json"
            alias.symlink_to(ADMITTED)
            with self.assertRaisesRegex(Refusal, "admitted result is immutable"):
                output_path(root, str(alias))
            self.assertEqual(existing.read_text(), "synthetic sentinel")


class PinRulingTest(unittest.TestCase):
    def test_unchanged_primary_pins_and_planted_retreat(self) -> None:
        import tomllib

        pins = tomllib.loads((ROOT / "pins.toml").read_text())
        primary = {
            "duckdb": "2.0.x",
            "pyvalhalla": "3.9.1",
            "maplibre-gl": "6.17.0",
            "@deck.gl/core": "9.4.1",
            "@deck.gl/layers": "9.4.1",
            "@deck.gl/geo-layers": "9.4.1",
            "@deck.gl/extensions": "9.4.1",
            "@deck.gl/maplibre": "9.4.1",
        }
        actual = {
            row["name"]: row["pin"]
            for row in pins["component"]
            if row["name"] in primary
        }
        self.assertEqual(
            actual,
            primary,
            "No alternative is accepted by S1-T08; a future change needs a decision record and review of this assertion.",
        )
        for row in pins["component"]:
            if row["name"] in primary:
                changed = {**actual, row["name"]: row["retreat"]}
                with self.assertRaises(AssertionError):
                    self.assertEqual(changed, primary)
        self.assertEqual(pins["confirm_at"], "slice S1")
        for row in pins["component"]:
            if row["name"] in ("pmtiles", "@protomaps/basemaps"):
                self.assertEqual(row["first_use"], "slice S3")
            if row["name"] == "typed-decision-provider":
                self.assertEqual(row["state"], "recorded")


class EndpointIdentityTest(unittest.TestCase):
    def test_endpoint_change_is_drift(self) -> None:
        from evals.typed_decisions.route import compare, identity

        left = identity(
            "jev", "synthetic-model", "rubric", b"cases", {}, "synthetic-route-left"
        )
        right = identity(
            "jev", "synthetic-model", "rubric", b"cases", {}, "synthetic-route-right"
        )
        self.assertEqual(compare(left, right), "requalify")


class ContractTest(unittest.TestCase):
    def test_requests_preserve_closed_fields_and_strip_answers(self) -> None:
        from evals.typed_decisions.requalify import (
            CASES,
            Refusal,
            encode_label,
            request_for,
        )

        cases = json.loads(CASES.read_text())
        expected = {
            "A_match": ("spine_match", "public"),
            "A_choice": ("spine_match", "public"),
            "B_route": ("question_route", "team_question"),
            "C_qc": ("brief_second_reader", "synthetic"),
            "D_parity": ("string_parity", "project_text"),
        }
        for case in cases:
            request = request_for(case, cases)
            self.assertEqual(
                (request.decision_class, request.input_class), expected[case["test"]]
            )
            self.assertEqual(request.input_text, case["state"])
            self.assertEqual(request.language, case["lang"])
            self.assertEqual(request.rubric_id, "requalification-v1-" + case["id"])
            self.assertEqual(request.route, "offline-requalification-v1")
            self.assertEqual(request.case_id, case["id"])
            rubric = json.loads(request.rubric_text)
            self.assertEqual(
                rubric,
                dict(
                    instructions=case["instructions"],
                    criteria=[
                        dict(
                            label=encode_label(case, row["label"]),
                            description=row["description"],
                        )
                        for row in case["criteria"]
                    ],
                ),
            )
            self.assertEqual(
                request.kind,
                "choice" if case["question_type"] == "choice" else "yes_no",
            )
        for changed in (
            {**cases[0], "input_class": "visitor_typed"},
            {**cases[0], "expected": "synthetic-outside"},
        ):
            with self.assertRaises(Refusal):
                request_for(changed, [changed])


class BreakRegressionTest(unittest.TestCase):
    def test_configured_route_is_provider_specific_and_digest_only(self) -> None:
        from evals.typed_decisions.route import configured

        from eii_gateway.memo import digest

        for provider in ("none", "recorded", "jev"):
            self.assertEqual(
                configured(provider)["thresholds"], {"high": 0.90, "low": 0.10}
            )
            self.assertEqual(
                configured(provider)["model"],
                {"none": "none", "recorded": "synthetic-recorded", "jev": "jev-1.14.0"}[
                    provider
                ],
            )
            self.assertEqual(
                configured(provider)["route_sha256"],
                "d4207e9f26433022974df0ae94512b2846baccef21b1d9e2749bbeba8cc01159"
                if provider == "jev"
                else digest(provider),
            )

    def test_direct_offline_command(self) -> None:
        import os
        import subprocess
        import sys
        import tempfile

        aggregate_dir = ROOT / "evals/typed_decisions"
        before = set(aggregate_dir.glob("results_*.json")) | set(
            (aggregate_dir / "runs").glob("*.json")
        )

        def cleanup() -> None:
            after = set(aggregate_dir.glob("results_*.json")) | set(
                (aggregate_dir / "runs").glob("*.json")
            )
            for path in after - before:
                path.unlink()

        self.addCleanup(cleanup)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "evals/typed_decisions/requalify.py"),
                "--provider",
                "none",
            ],
            cwd=ROOT,
            env={"PATH": os.environ["PATH"], "TMPDIR": tempfile.gettempdir()},
            text=True,
            capture_output=True,
        )
        after = set(aggregate_dir.glob("results_*.json")) | set(
            (aggregate_dir / "runs").glob("*.json")
        )
        self.assertEqual(after, before)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.endswith("match\nDISABLED\n"))


class LiveDispatchWithoutProviderTest(unittest.TestCase):
    def test_live_root_dispatch_without_running_harness(self) -> None:
        from unittest.mock import patch

        from evals.typed_decisions import requalify

        with patch.object(requalify, "run", return_value=2) as runner:
            self.assertEqual(requalify.main(["--provider", "jev"]), 2)
        self.assertEqual(runner.call_args.args[1], ROOT)

    def test_live_preamble_and_memo_route_before_any_provider_call(self) -> None:
        import argparse
        import contextlib
        import io
        import os
        import tempfile
        from unittest.mock import patch

        from evals.typed_decisions import requalify

        from eii_gateway.memo import digest

        class StopBeforeProvider(Exception):
            pass

        args = argparse.Namespace(
            provider="jev",
            authorised=True,
            token_cap="5000000",
            endpoint="https://synthetic.invalid/qualification",
            fixtures=None,
            output=None,
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stdout = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"}, clear=True
                ),
                patch.object(requalify, "Gateway") as factory,
                patch("socket.socket", side_effect=AssertionError("network forbidden")),
                patch(
                    "socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")
                ),
                contextlib.redirect_stdout(stdout),
            ):
                factory.return_value.decide.side_effect = StopBeforeProvider
                with self.assertRaises(StopBeforeProvider):
                    requalify.run(args, root)
                request = factory.return_value.decide.call_args.args[0]
                self.assertEqual(
                    request.route, "offline-requalification-" + digest(args.endpoint)
                )
                self.assertNotIn("EII_DECISION_PROVIDER", os.environ)
            self.assertEqual(list(root.iterdir()), [])
            preamble = json.loads(stdout.getvalue())
            self.assertEqual(
                preamble["identity"]["route_sha256"], digest(args.endpoint)
            )
            self.assertEqual(preamble["token_cap"], int(args.token_cap))
            self.assertEqual(factory.call_args.kwargs["endpoint"], args.endpoint)
            self.assertEqual(factory.call_args.kwargs["token_cap"], int(args.token_cap))


class CapRepresentationTest(unittest.TestCase):
    def test_leading_zeroes_precede_integer_digit_limit(self) -> None:
        import os
        from unittest.mock import patch

        from evals.typed_decisions.requalify import token_cap

        previous = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(640)
            with patch.dict(
                os.environ, {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"}, clear=True
            ):
                self.assertEqual(token_cap(True, "0" * 641 + "1", 1), 1)
        finally:
            sys.set_int_max_str_digits(previous)

    def test_leading_zeroes_do_not_change_whole_number_value(self) -> None:
        import os
        from unittest.mock import patch

        from evals.typed_decisions.requalify import token_cap

        with patch.dict(
            os.environ, {"JEV_PRO_API_KEY": "SYNTHETIC_NOT_A_KEY"}, clear=True
        ):
            self.assertEqual(token_cap(True, "0" * 9 + "1", 1), 1)


class MutationCoverageTest(HarnessSupport):
    def test_request_refusals_keep_fixed_reasons(self) -> None:
        outside_label = {**self.cases[0], "expected": "synthetic-outside"}
        extra_field = {**self.cases[0], "synthetic_extra": "invented"}
        for case, cases, reason in (
            (self.cases[0], [], "case outside qualification set"),
            (extra_field, [extra_field], "case outside qualification set"),
            (outside_label, [outside_label], "expected label outside options"),
        ):
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(self.harness.Refusal, "^" + reason + "$"),
            ):
                self.harness.request_for(case, cases)

    def test_output_is_utf8_under_an_ascii_locale(self) -> None:
        import locale
        from unittest.mock import patch

        case_id = "synthetic-اختبار"
        cases = self.root / "synthetic-cases.json"
        cases.write_text(json.dumps([{**self.cases[0], "id": case_id}]))
        destination = self.root / "synthetic-result.json"
        previous = locale.setlocale(locale.LC_CTYPE)
        try:
            locale.setlocale(locale.LC_CTYPE, "C")
            with patch.object(self.harness, "CASES", cases):
                code, _ = self.invoke(
                    "--provider", "none", "--output", str(destination)
                )
            self.assertEqual(code, 2)
        finally:
            locale.setlocale(locale.LC_CTYPE, previous)
        result = json.loads(destination.read_bytes().decode("utf-8"))
        self.assertEqual(result["raw_answers"]["cases"][0]["id"], case_id)

    def test_output_creates_nested_parents(self) -> None:
        destination = self.root / "synthetic-reports/nested/result.json"
        code, output = self.invoke("--provider", "none", "--output", str(destination))
        self.assertEqual(code, 0)
        self.assertEqual(output.splitlines()[-2:], ["match", "DISABLED"])
        result = json.loads(destination.read_text())
        self.assertEqual(result["identity"]["provider"], "none")

    def test_report_preserves_the_admitted_comparison(self) -> None:
        fixture = self.fixture()
        code, output = self.invoke("--provider", "recorded", "--fixtures", str(fixture))
        self.assertEqual(code, 0)
        self.assertEqual(
            output.splitlines()[-2:], ["match", "synthetic replay; not a measurement"]
        )
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        admitted = json.loads(ADMITTED.read_text())["arms"][self.harness.ARM]
        self.assertEqual(result["stated_ci95"], admitted["ci95"])
        self.assertIs(result["inside_stated_interval"], False)
        self.assertIs(result["admitted_measurement_reproduced"], False)

    def test_reported_acceptance_is_boolean_and_matches_outcome(self) -> None:
        fixture = self.fixture()
        replies = json.loads(fixture.read_text())
        for reply in replies:
            if reply["case_id"] == self.cases[0]["id"]:
                reply["scores"] = {label: 0.5 for label in reply["scores"]}
        fixture.write_text(json.dumps(replies))
        code, _ = self.invoke("--provider", "recorded", "--fixtures", str(fixture))
        self.assertEqual(code, 0)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        rows = result["gateway_accepted"]["cases"]
        self.assertEqual({row["accepted"] for row in rows}, {False, True})
        for row in rows:
            self.assertIs(type(row["accepted"]), bool)
            self.assertEqual(row["accepted"], row["outcome"] == "DECIDED")

    def test_provider_environment_is_restored_on_success_and_failure(self) -> None:
        import os
        from unittest.mock import patch

        for previous in (None, "synthetic-previous"):
            environment = (
                {} if previous is None else {"EII_DECISION_PROVIDER": previous}
            )
            with (
                self.subTest(previous=previous),
                patch.dict(os.environ, environment, clear=True),
            ):
                code, _ = self.invoke("--provider", "none")
                self.assertEqual(code, 0)
                self.assertEqual(dict(os.environ), environment)
                with patch.object(
                    self.harness,
                    "Gateway",
                    side_effect=RuntimeError("synthetic failure"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "^synthetic failure$"):
                        self.invoke("--provider", "none")
                self.assertEqual(dict(os.environ), environment)

    def test_offline_endpoint_does_not_change_route(self) -> None:
        from eii_gateway.memo import digest

        code, _ = self.invoke(
            "--provider", "none", "--endpoint", "synthetic-unused-endpoint"
        )
        self.assertEqual(code, 0)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(result["identity"]["route_sha256"], digest("none"))

    def test_default_and_live_dispatch_preserve_arguments(self) -> None:
        from unittest.mock import patch

        for argv, expected in (([], "none"), (["--provider", "jev"], "jev")):
            with (
                self.subTest(provider=expected),
                patch.object(self.harness, "run", return_value=0) as run,
            ):
                self.assertEqual(self.harness.main(argv), 0)
                args, root = run.call_args.args
                self.assertEqual(args.provider, expected)
                self.assertFalse(args.authorised)
                self.assertIsNone(args.token_cap)
                if expected == "jev":
                    self.assertEqual(root, self.harness.FOLDER.parents[1])
                else:
                    self.assertFalse(root.exists())

    def test_help_keeps_description(self) -> None:
        import contextlib
        import io

        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            self.harness.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn(self.harness.__doc__, output.getvalue())

    def test_output_timestamp_is_utc_and_uses_the_recorded_format(self) -> None:
        from datetime import UTC, datetime
        from unittest.mock import patch

        with patch.object(self.harness, "datetime") as clock:
            clock.now.return_value = datetime(
                2026, 11, 13, 4, 19, 15, 123456, tzinfo=UTC
            )
            result = self.harness.output_path(self.root, None)
        clock.now.assert_called_once_with(UTC)
        self.assertEqual(
            result,
            self.root / "evals/typed_decisions/results_2026-11-13T04-19-15-123456.json",
        )

    def test_output_refusals_have_fixed_reasons(self) -> None:
        with self.assertRaisesRegex(self.harness.Refusal, "^output outside run root$"):
            self.harness.output_path(
                self.root, str(self.root.parent / "synthetic-output.json")
            )
        path = self.root / "synthetic-existing.json"
        path.write_text("synthetic sentinel")
        with self.assertRaisesRegex(self.harness.Refusal, "^result already exists$"):
            self.harness.output_path(self.root, str(path))
        self.assertEqual(path.read_text(), "synthetic sentinel")


class ReproductionTest(HarnessSupport):
    """C2 compares first answers, independently of gateway acceptance."""

    def replay(self, correct: int, *, missing: bool = False) -> dict[str, Any]:
        fixture = self.fixture()
        replies = json.loads(fixture.read_text())
        wrong_ids = {case["id"] for case in self.cases[correct:]}
        for reply in replies:
            if reply["case_id"] in wrong_ids:
                reply["label"] = next(
                    label for label in reply["scores"] if label != reply["label"]
                )
            reply["scores"] = {label: 0.5 for label in reply["scores"]}
        if missing:
            replies = [r for r in replies if r["case_id"] != self.cases[0]["id"]]
        fixture.write_text(json.dumps(replies))
        result_path = self.root / "synthetic-result.json"
        code, _ = self.invoke(
            "--provider",
            "recorded",
            "--fixtures",
            str(fixture),
            "--output",
            str(result_path),
        )
        self.assertEqual(code, 0)
        result: dict[str, Any] = json.loads(result_path.read_text())
        result_path.unlink()
        # Each replay is independent; do not reuse gateway memo records.
        for record in self.root.glob("evals/typed_decisions/runs/*.json"):
            record.unlink()
        return result

    def test_first_answer_bounds_with_replay(self) -> None:
        from math import ceil, floor

        from evals.typed_decisions.reproduction import reproduction

        admitted = json.loads(ADMITTED.read_text())["arms"][self.harness.ARM]
        low, high = admitted["ci95"]
        total = admitted["answered"]
        for correct, expected in (
            (ceil(low * total / 100) - 1, False),
            (ceil(low * total / 100), True),
            (floor(high * total / 100), True),
            (floor(high * total / 100) + 1, False),
        ):
            with self.subTest(correct=correct):
                result = self.replay(correct)
                raw = result["raw_answers"]
                self.assertEqual(raw["overall"], interval(correct, total))
                for case, row in zip(self.cases, raw["cases"], strict=True):
                    self.assertEqual(row["correct"], row["label"] == case["expected"])
                    self.assertIn(
                        self.harness.encode_label(case, row["label"]),
                        self.harness.request_for(case, self.cases).labels,
                    )
                self.assertEqual(result["gateway_accepted"]["overall"]["correct"], 0)
                self.assertFalse(result["admitted_measurement_reproduced"])
                self.assertEqual(result["reproduction_reason"], "not_keyed")
                keyed_rows = [
                    {
                        **row,
                        "response_models": ["jev-1.14.0"] * len(row["response_models"]),
                    }
                    for row in raw["cases"]
                ]
                verdict = reproduction("jev", keyed_rows, admitted)
                self.assertEqual(verdict["admitted_measurement_reproduced"], expected)
                self.assertEqual(
                    verdict["reproduction_reason"],
                    "reproduced" if expected else "outside_stated_interval",
                )
                wrong_family = [dict(row) for row in keyed_rows]
                wrong_family[0] = {
                    **wrong_family[0],
                    "response_models": ["synthetic-other"],
                }
                verdict = reproduction("jev", wrong_family, admitted)
                self.assertFalse(verdict["admitted_measurement_reproduced"])
                self.assertEqual(
                    verdict["reproduction_reason"], "model_family_mismatch"
                )
                self.assertEqual(verdict["route_status"], "requalify")
                self.assertEqual(
                    raw["by_test"]["A_match"]["admitted"],
                    admitted["by_test"]["A_match"],
                )
                self.assertEqual(len(result["protocol_differences"]), 4)
                for name in self.harness.CLASSES:
                    group = [row for row in raw["cases"] if row["test"] == name]
                    self.assertEqual(
                        raw["by_test"][name]["current"],
                        interval(sum(row["correct"] for row in group), len(group)),
                    )

    def test_incomplete_answer_set_does_not_reproduce(self) -> None:
        from evals.typed_decisions.reproduction import reproduction

        admitted = json.loads(ADMITTED.read_text())["arms"][self.harness.ARM]
        result = self.replay(admitted["correct"], missing=True)
        rows = [
            {**row, "response_models": ["jev-1.14.0"] * len(row["response_models"])}
            for row in result["raw_answers"]["cases"]
        ]
        verdict = reproduction("jev", rows, admitted)
        self.assertFalse(verdict["admitted_measurement_reproduced"])
        self.assertEqual(verdict["reproduction_reason"], "incomplete_answers")
        self.assertEqual(result["raw_answers"]["overall"]["total"], len(self.cases) - 1)
        name = self.cases[0]["test"]
        self.assertEqual(
            result["raw_answers"]["by_test"][name]["current"]["total"],
            sum(case["test"] == name for case in self.cases) - 1,
        )

    def test_missing_second_order_keeps_first_raw_answer(self) -> None:
        fixture = self.fixture()
        replies = json.loads(fixture.read_text())
        case = next(c for c in self.cases if c["question_type"] == "choice")
        pair = [r for r in replies if r["case_id"] == case["id"]]
        replies.remove(pair[1])
        fixture.write_text(json.dumps(replies))
        code, _ = self.invoke("--provider", "recorded", "--fixtures", str(fixture))
        self.assertEqual(code, 0)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(result["raw_answers"]["overall"]["correct"], len(self.cases))
        self.assertEqual(
            result["gateway_accepted"]["overall"]["correct"], len(self.cases) - 1
        )

    def test_second_response_model_drift_is_observed(self) -> None:
        from dataclasses import replace
        from unittest.mock import patch

        from eii_gateway.memo import option_orders
        from eii_gateway.providers.base import Reply
        from eii_gateway.providers.recorded_provider import RecordedProvider
        from eii_gateway.types import Request

        fixture = self.fixture()
        case = next(c for c in self.cases if c["question_type"] == "choice")
        second = option_orders(self.harness.request_for(case, self.cases))[1]
        original = RecordedProvider.answer

        def changed(
            provider: RecordedProvider,
            request: Request,
            order: tuple[str, ...],
            cap: int,
        ) -> Reply | None:
            reply = original(provider, request, order, cap)
            if reply is not None and request.case_id == case["id"] and order == second:
                return replace(reply, model="synthetic-other-family")
            return reply

        with patch.object(RecordedProvider, "answer", changed):
            code, output = self.invoke(
                "--provider", "recorded", "--fixtures", str(fixture)
            )
        self.assertEqual(code, 2)
        self.assertIn("requalify", output)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        row = next(
            row for row in result["raw_answers"]["cases"] if row["id"] == case["id"]
        )
        self.assertTrue(row["correct"])
        self.assertEqual(
            row["response_models"], ["synthetic-recorded", "synthetic-other-family"]
        )
        self.assertFalse(result["admitted_measurement_reproduced"])
        self.assertEqual(result["gateway_accepted"]["outcomes"]["ERROR"], 1)


class PinnedModelReportTest(HarnessSupport):
    def test_reply_counts_and_first_answer_selection_are_separate(self) -> None:
        from copy import deepcopy

        from evals.typed_decisions.reproduction import (
            answer_summary,
            model_reply_counts,
        )

        rows = [
            dict(response_models=models, label=label, correct=correct)
            for models, label, correct in (
                (["synthetic-pin", "synthetic-other"], "yes", True),
                (["synthetic-other", "synthetic-pin"], "yes", True),
                ([], None, False),
                ([None], "yes", True),
                ([""], "yes", True),
                (["synthetic-pin"], None, False),
                (["synthetic-pin"], "no", False),
            )
        ]
        original = deepcopy(rows)
        self.assertEqual(
            model_reply_counts(rows, "synthetic-pin"),
            {"pinned": 4, "other_or_missing": 4},
        )
        self.assertEqual(answer_summary(rows, "synthetic-pin"), interval(1, 2))
        self.assertEqual(
            model_reply_counts(rows[-1:], "synthetic-pin"),
            {"pinned": 1, "other_or_missing": 0},
        )
        self.assertEqual(answer_summary(rows[:1], "synthetic-pin"), interval(1, 1))
        self.assertEqual(rows, original)
        self.assertEqual(
            model_reply_counts([], "synthetic-pin"),
            {"pinned": 0, "other_or_missing": 0},
        )
        self.assertEqual(answer_summary([], "synthetic-pin"), interval(0, 0))

    def assert_excluded_reply(self, model: str) -> None:
        from dataclasses import replace
        from unittest.mock import patch

        from eii_gateway.providers.base import Reply
        from eii_gateway.providers.recorded_provider import RecordedProvider
        from eii_gateway.types import Request

        fixture = self.fixture()
        replies = json.loads(fixture.read_text())
        case = self.cases[0]
        original = RecordedProvider.answer

        def changed(
            provider: RecordedProvider,
            request: Request,
            order: tuple[str, ...],
            cap: int,
        ) -> Reply | None:
            reply = original(provider, request, order, cap)
            if reply is not None and request.case_id == case["id"]:
                return replace(reply, model=model)
            return reply

        with patch.object(RecordedProvider, "answer", changed):
            code, _ = self.invoke("--provider", "recorded", "--fixtures", str(fixture))
        self.assertEqual(code, 2)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(
            result["raw_answers"]["overall"],
            interval(len(self.cases) - 1, len(self.cases) - 1),
        )
        group_size = sum(c["test"] == case["test"] for c in self.cases) - 1
        self.assertEqual(
            result["raw_answers"]["by_test"][case["test"]]["current"],
            interval(group_size, group_size),
        )
        self.assertEqual(
            result["model_replies"], {"pinned": len(replies) - 1, "other_or_missing": 1}
        )
        self.assertEqual(result["raw_answers"]["cases"][0]["response_models"], [model])
        self.assertEqual(result["gateway_accepted"]["outcomes"]["ERROR"], 1)
        self.assertEqual(
            set(result["gateway_accepted"]["cases"][0]), AggregateTest.fields
        )

    def test_recorded_reply_naming_another_model_is_counted_and_excluded(self) -> None:
        self.assert_excluded_reply("synthetic-other-family")

    def test_recorded_reply_without_model_is_counted_and_excluded(self) -> None:
        self.assert_excluded_reply("")

    def test_keyed_run_reply_counts_come_from_recorded_models(self) -> None:
        from evals.typed_decisions.reproduction import model_reply_counts

        result = json.loads(
            (ADMITTED.parent / KeyedRunReadmeTest.result_name).read_text()
        )
        rows = result["raw_answers"]["cases"]
        self.assertEqual(
            model_reply_counts(rows, "jev-1.14.0"),
            {"pinned": result["calls_made"], "other_or_missing": 0},
        )


class ReproductionLogicTest(unittest.TestCase):
    def test_closed_verdicts_and_response_models(self) -> None:
        from copy import deepcopy

        from evals.typed_decisions.reproduction import reproduction

        admitted = json.loads(ADMITTED.read_text())["arms"][
            "jev-1.14.0 (typed-decision provider)"
        ]
        rows = [
            dict(
                label="synthetic-answer",
                correct=i < admitted["correct"],
                response_models=["jev-1.14.0"],
            )
            for i in range(admitted["answered"])
        ]
        result = reproduction("jev", rows, admitted)
        self.assertEqual(
            result,
            dict(
                overall=interval(admitted["correct"], admitted["answered"]),
                stated_ci95=admitted["ci95"],
                inside_stated_interval=True,
                admitted_measurement_reproduced=True,
                reproduction_reason="reproduced",
                route_status="match",
            ),
        )
        for provider in ("recorded", "none"):
            replay = reproduction(provider, rows, admitted)
            self.assertFalse(replay["admitted_measurement_reproduced"])
            self.assertEqual(replay["reproduction_reason"], "not_keyed")
        changed = deepcopy(rows)
        changed[0]["response_models"] = ["jev-1.14.0", "synthetic-other-family"]
        verdict = reproduction("jev", changed, admitted)
        self.assertEqual(verdict["route_status"], "requalify")
        self.assertEqual(verdict["reproduction_reason"], "model_family_mismatch")
        self.assertFalse(verdict["admitted_measurement_reproduced"])
        self.assertEqual(
            reproduction("jev", rows[1:], admitted)["reproduction_reason"],
            "incomplete_answers",
        )
        changed = [{**row, "correct": False} for row in rows]
        self.assertEqual(
            reproduction("jev", changed, admitted)["reproduction_reason"],
            "outside_stated_interval",
        )
        changed = [
            {**row, "label": None, "correct": False, "response_models": []}
            for row in rows
        ]
        verdict = reproduction("jev", changed, admitted)
        self.assertEqual(verdict["overall"], interval(0, 0))
        self.assertEqual(verdict["reproduction_reason"], "incomplete_answers")

    def test_observer_preserves_first_answer_and_all_models(self) -> None:
        from unittest.mock import Mock

        from evals.typed_decisions.reproduction import (
            PROTOCOL_DIFFERENCES,
            ObservedProvider,
        )
        from evals.typed_decisions.requalify import CASES, request_for

        from eii_gateway.providers.base import Reply

        cases = json.loads(CASES.read_text())
        request = request_for(cases[0], cases)
        first = Reply("yes", {"yes": 0.5, "no": 0.5}, "synthetic-first", 0)
        second = Reply("no", {"yes": 0.5, "no": 0.5}, "synthetic-second", 0)
        provider = Mock(name="synthetic-provider")
        provider.name = "recorded"
        provider.model = "synthetic-recorded"
        provider.answer.side_effect = [None, first, second]
        observed = ObservedProvider(provider)
        self.assertEqual(
            (observed.name, observed.model), ("recorded", "synthetic-recorded")
        )
        self.assertIsNone(observed.answer(request, (), 0))
        self.assertEqual((observed.first, observed.models), ({}, {}))
        self.assertIs(observed.answer(request, (), 0), first)
        self.assertIs(observed.answer(request, (), 0), second)
        self.assertEqual(observed.first, {request.case_id: "yes"})
        self.assertEqual(
            observed.models, {request.case_id: ["synthetic-first", "synthetic-second"]}
        )
        self.assertEqual(
            PROTOCOL_DIFFERENCES,
            (
                "Option orders are hash-derived, not the original order.",
                "Activity labels are sent with the isic- prefix.",
                "The admitted run was made before the gateway existed.",
                "The adapter cuts the yes/no label at a weight of 0.5.",
            ),
        )
        provider.answer.side_effect = [
            Reply("synthetic-invalid", {}, "synthetic-model", 0)
        ]
        with self.assertRaises(ValueError):
            observed.answer(request, (), 0)
        self.assertEqual(observed.first, {request.case_id: "yes"})


class WireSupport(unittest.TestCase):
    """Explicit loopback tests; restore the adapter import after each test."""

    def setUp(self) -> None:
        import importlib
        import os
        import tempfile
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from unittest.mock import patch

        from evals.typed_decisions import requalify

        importlib.import_module("urllib.request")
        modules = patch.dict(sys.modules)
        modules.start()
        self.addCleanup(modules.stop)
        jev_provider = importlib.import_module("eii_gateway.providers.jev_provider")

        self.adapter = jev_provider
        self.harness = requalify
        all_cases = json.loads(requalify.CASES.read_text())
        self.cases = [
            *all_cases[:3],
            next(c for c in all_cases if c["question_type"] == "choice"),
        ]
        self.request = requalify.request_for(self.cases[0], self.cases)
        self.received: list[dict[str, Any]] = []
        self.headers: list[dict[str, str]] = []
        self.status = 200
        self.fail_at = 0
        self.close_connection = False
        self.response: Any = None
        self.tokens_sent = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.received.append(body)
                owner.headers.append(dict(self.headers.items()))
                if owner.close_connection:
                    self.close_connection = True
                    return
                status = owner.status if len(owner.received) == owner.fail_at else 200
                if status != 200:
                    self.send_response(status)
                    if status == 302:
                        self.send_header("Location", owner.endpoint + "redirect")
                    self.end_headers()
                    self.wfile.write(b'{"error":"fixture-key"}')
                    return
                question = body.get("questions", {}).get("decision", {})
                if question.get("type") == "choice":
                    labels = list(question["criteria"])
                    label = min(labels)
                    answer = dict(
                        type="choice",
                        choice=label,
                        probabilities={v: float(v == label) for v in labels},
                        confidence=1.0,
                    )
                else:
                    answer = dict(type="noul", noul=0.9)
                response = (
                    owner.response
                    if owner.response is not None
                    else dict(
                        model="jev-1.14.0",
                        answers=dict(decision=answer),
                        usage=dict(input_tokens=3, output_tokens=2),
                        ignored="fixture-key",
                    )
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                owner.tokens_sent += 5

        server = HTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(server.shutdown)
        self.endpoint = f"http://127.0.0.1:{server.server_port}/"
        self.provider = jev_provider.JevProvider(self.endpoint)
        env = patch.dict(os.environ, {"JEV_PRO_API_KEY": "fixture-key"})
        env.start()
        self.addCleanup(env.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.case_path = self.root / "cases.json"
        self.case_path.write_text(json.dumps(self.cases))

    def answer(self, **changes: Any) -> Any:
        from dataclasses import replace

        request = replace(self.request, **changes)
        return self.provider.answer(request, request.labels, 2000000)

    def invoke(self, *, matching: bool = False) -> tuple[int, str]:
        import contextlib
        import io
        from unittest.mock import patch

        from evals.typed_decisions import route

        from eii_gateway.memo import canonical, digest

        requests = [self.harness.request_for(c, self.cases) for c in self.cases]
        output = io.StringIO()
        with (
            patch.object(self.harness, "CASES", self.case_path),
            patch.object(route, "CASE_SHA256", digest(self.case_path.read_text())),
            patch.object(
                route,
                "RUBRIC_SHA256",
                digest(canonical([r.rubric_text for r in requests])),
            ),
            contextlib.ExitStack() as stack,
            contextlib.redirect_stdout(output),
        ):
            if matching:
                stack.enter_context(
                    patch.object(route, "JEV_ROUTE_SHA256", digest(self.endpoint))
                )
            code = self.harness.main(
                [
                    "--provider",
                    "jev",
                    "--authorised",
                    "--token-cap",
                    "2000000",
                    "--endpoint",
                    self.endpoint,
                ],
                root=self.root,
            )
        printed = output.getvalue()
        self.assertNotIn("fixture-key", printed)
        self.assertNotIn(self.endpoint, printed)
        for path in self.root.rglob("*.json"):
            self.assertNotIn("fixture-key", path.read_text())
            self.assertNotIn(self.endpoint, path.read_text())
        return code, printed


class AdapterWireTest(WireSupport):
    def assert_body(self, request: Any, order: tuple[str, ...]) -> None:
        reply = self.provider.answer(request, order, 2000000)
        rubric = json.loads(request.rubric_text)
        question = dict(
            type="noul" if request.kind == "yes_no" else "choice",
            instructions=rubric["instructions"],
        )
        if request.kind == "choice":
            descriptions = {r["label"]: r["description"] for r in rubric["criteria"]}
            question["criteria"] = {label: descriptions[label] for label in order}
        expected = dict(
            model="jev-1.14.0",
            state=request.input_text,
            questions=dict(decision=question),
        )
        self.assertEqual(set(self.received[-1]), set(expected))
        self.assertEqual(self.received[-1], expected)
        if request.kind == "choice":
            self.assertEqual(
                list(self.received[-1]["questions"]["decision"]["criteria"]),
                list(order),
            )
        headers = {k.lower(): v for k, v in self.headers[-1].items()}
        self.assertEqual(headers["authorization"], "Bearer fixture-key")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["user-agent"], "eii-typed-decision-tool")
        self.assertIsNotNone(reply)
        self.assertEqual(reply.model, "jev-1.14.0")
        self.assertEqual(reply.tokens, 5)
        if request.kind == "yes_no":
            self.assertEqual(reply.label, "yes")
            self.assertEqual(reply.scores, {"yes": 0.9, "no": 1 - 0.9})
        else:
            self.assertEqual(reply.label, min(order))
            self.assertEqual(reply.scores, {v: float(v == min(order)) for v in order})

    def choice_request(self) -> Any:
        cases = json.loads(self.harness.CASES.read_text())
        case = next(c for c in cases if c["question_type"] == "choice")
        return self.harness.request_for(case, cases)

    def test_yes_no_body_headers_and_reply(self) -> None:
        self.assert_body(self.request, self.request.labels)

    def test_choice_first_order_body_headers_and_reply(self) -> None:
        from eii_gateway.memo import option_orders

        request = self.choice_request()
        self.assert_body(request, option_orders(request)[0])

    def test_choice_second_order_body_headers_and_reply(self) -> None:
        from eii_gateway.memo import option_orders

        request = self.choice_request()
        self.assert_body(request, option_orders(request)[1])

    def test_unknown_body_member_plant_is_caught(self) -> None:
        from unittest.mock import patch

        original = self.adapter.HTTPRequest

        def changed(*args: Any, **kwargs: Any) -> Any:
            body = json.loads(kwargs["data"])
            body["max_tokens"] = 1
            kwargs["data"] = json.dumps(body).encode()
            return original(*args, **kwargs)

        with patch.object(self.adapter, "HTTPRequest", changed):
            with self.assertRaises(AssertionError):
                self.assert_body(self.request, self.request.labels)

    def test_yes_no_cut_half(self) -> None:
        self.response = self.reply(noul=0.5)
        self.assertEqual(self.answer().label, "yes")

    def test_yes_no_cut_below_half(self) -> None:
        self.response = self.reply(noul=0.49)
        self.assertEqual(self.answer().label, "no")

    def reply(self, **answer: Any) -> dict[str, Any]:
        return dict(
            model="jev-1.14.0",
            answers=dict(decision=dict(type="noul", noul=0.9) | answer),
            usage=dict(input_tokens=3, output_tokens=2),
        )

    def bad_reply(self, response: Any) -> None:
        self.response = response
        with self.assertRaises(ValueError) as caught:
            self.answer()
        self.assertNotIn("fixture-key", str(caught.exception))

    def test_rubric_form_one_only(self) -> None:
        for rubric in (
            "raw text",
            "[]",
            "{}",
            '{"instructions":"","criteria":[]}',
            '{"instructions":true,"criteria":[]}',
            '{"instructions":"x","criteria":[],"extra":true}',
            '{"instructions":"x","criteria":[{"label":"a"}]}',
        ):
            with self.subTest(rubric=rubric), self.assertRaises(ValueError):
                self.answer(rubric_text=rubric)
        self.assertEqual(self.received, [])

    def test_yes_no_criteria_must_be_empty(self) -> None:
        rubric = dict(instructions="x", criteria=[dict(label="yes", description="x")])
        with self.assertRaises(ValueError):
            self.answer(rubric_text=json.dumps(rubric))
        self.assertEqual(self.received, [])

    def test_choice_labels_must_match_order(self) -> None:
        request = self.choice_request()
        with self.assertRaises(ValueError):
            self.provider.answer(
                request, ("synthetic-other", "synthetic-label"), 2000000
            )
        self.assertEqual(self.received, [])

    def test_choice_duplicate_criteria_refused(self) -> None:
        from dataclasses import replace

        request = self.choice_request()
        rubric = json.loads(request.rubric_text)
        rubric["criteria"].append(rubric["criteria"][0])
        with self.assertRaises(ValueError):
            self.provider.answer(
                replace(request, rubric_text=json.dumps(rubric)),
                request.labels,
                2000000,
            )
        self.assertEqual(self.received, [])

    def test_choice_count_and_duplicate_order_refused(self) -> None:
        request = self.choice_request()
        for order in (request.labels[:1], request.labels + request.labels):
            with self.subTest(order=order), self.assertRaises(ValueError):
                self.provider.answer(request, order, 2000000)
        self.assertEqual(self.received, [])

    def test_ordinal_refused(self) -> None:
        from dataclasses import replace

        request = replace(self.choice_request(), kind="ordinal")
        with self.assertRaises(ValueError):
            self.provider.answer(request, request.labels, 2000000)
        self.assertEqual(self.received, [])

    def test_wrong_answer_type_refused(self) -> None:
        self.bad_reply(self.reply(type="choice"))

    def test_out_of_range_weight_refused(self) -> None:
        self.bad_reply(self.reply(noul=1.2))

    def test_boolean_weight_refused(self) -> None:
        self.bad_reply(self.reply(noul=True))

    def test_missing_usage_refused(self) -> None:
        reply = self.reply()
        del reply["usage"]
        self.bad_reply(reply)

    def test_fractional_tokens_refused(self) -> None:
        reply = self.reply()
        reply["usage"]["input_tokens"] = 0.5
        self.bad_reply(reply)

    def test_missing_and_wrong_types_refused(self) -> None:
        response: Any
        for response in (
            [],
            {},
            self.reply() | {"model": True},
            self.reply() | {"answers": []},
            self.reply() | {"usage": {"input_tokens": True, "output_tokens": 0}},
            self.reply() | {"usage": {"input_tokens": -1, "output_tokens": 0}},
            self.reply(noul="fixture-key"),
            self.reply(noul=float("nan")),
        ):
            with self.subTest(response=response):
                self.bad_reply(response)

    def choice_reply(self) -> dict[str, Any]:
        self.request = self.choice_request()
        labels = self.request.labels
        return self.reply(
            type="choice",
            choice=labels[0],
            probabilities={v: float(v == labels[0]) for v in labels},
            confidence=1.0,
        )

    def test_unknown_choice_label_refused(self) -> None:
        reply = self.choice_reply()
        reply["answers"]["decision"]["choice"] = "synthetic-unknown"
        self.bad_reply(reply)

    def test_missing_probability_label_refused(self) -> None:
        reply = self.choice_reply()
        del reply["answers"]["decision"]["probabilities"][self.request.labels[0]]
        self.bad_reply(reply)

    def test_choice_signal_types_refused(self) -> None:
        reply = self.choice_reply()
        reply["answers"]["decision"]["confidence"] = True
        self.bad_reply(reply)
        reply = self.choice_reply()
        reply["answers"]["decision"]["probabilities"][self.request.labels[0]] = True
        self.bad_reply(reply)

    def test_choice_confidence_is_numeric_not_a_ranking_signal(self) -> None:
        reply = self.choice_reply()
        reply["answers"]["decision"]["confidence"] = 2
        self.response = reply
        self.assertEqual(self.answer().label, self.request.labels[0])

    def test_model_string_preserved(self) -> None:
        self.response = self.reply() | {"model": "synthetic-other-model"}
        self.assertEqual(self.answer().model, "synthetic-other-model")

    def test_body_byte_cap_prevents_request(self) -> None:
        self.assertIsNone(self.provider.answer(self.request, self.request.labels, 1))
        self.assertEqual(self.received, [])

    def test_body_cap_exact_boundary(self) -> None:
        rubric = json.loads(self.request.rubric_text)
        body = json.dumps(
            dict(
                model="jev-1.14.0",
                state=self.request.input_text,
                questions=dict(
                    decision=dict(type="noul", instructions=rubric["instructions"])
                ),
            )
        ).encode("utf-8")
        self.assertIsNone(
            self.provider.answer(self.request, self.request.labels, len(body) - 1)
        )
        self.assertEqual(self.received, [])
        self.assertIsNotNone(
            self.provider.answer(self.request, self.request.labels, len(body))
        )
        self.assertEqual(len(self.received), 1)

    def test_choice_above_service_label_limit(self) -> None:
        from dataclasses import replace

        labels = tuple(f"synthetic-label-{i}" for i in range(256))
        request = replace(
            self.request,
            kind="choice",
            options=labels,
            rubric_text=json.dumps(
                dict(
                    instructions="Choose an invented label.",
                    criteria=[
                        dict(label=label, description="Invented.") for label in labels
                    ],
                )
            ),
        )
        with self.assertRaises(ValueError):
            self.provider.answer(request, labels, 2000000)
        self.assertEqual(self.received, [])

    def test_rubric_member_types_and_extra_row_member(self) -> None:
        criteria: Any
        for criteria in (
            None,
            {},
            [dict(label=True, description="x")],
            [dict(label="a", description=True)],
            [dict(label="a", description="x", extra="x")],
        ):
            with self.subTest(criteria=criteria), self.assertRaises(ValueError):
                self.answer(
                    rubric_text=json.dumps(dict(instructions="x", criteria=criteria))
                )
        self.assertEqual(self.received, [])

        from dataclasses import replace

        request = self.choice_request()
        for change in ({"label": True}, {"description": True}, {"extra": "x"}):
            rubric = json.loads(request.rubric_text)
            rubric["criteria"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.provider.answer(
                    replace(request, rubric_text=json.dumps(rubric)),
                    request.labels,
                    2000000,
                )
        self.assertEqual(self.received, [])

    def test_missing_response_members(self) -> None:
        from copy import deepcopy

        for keys in (
            ("model",),
            ("answers",),
            ("answers", "decision"),
            ("answers", "decision", "type"),
            ("answers", "decision", "noul"),
            ("usage", "input_tokens"),
            ("usage", "output_tokens"),
        ):
            response = deepcopy(self.reply())
            target = response
            for key in keys[:-1]:
                target = target[key]
            del target[keys[-1]]
            with self.subTest(keys=keys):
                self.bad_reply(response)

    def test_http_error_unchanged_and_no_retry(self) -> None:
        from urllib.error import HTTPError

        self.status, self.fail_at = 422, 1
        with self.assertRaises(HTTPError) as caught:
            self.answer()
        self.assertEqual(caught.exception.code, 422)
        self.assertEqual(len(self.received), 1)
        caught.exception.close()

    def test_redirect_not_followed(self) -> None:
        from urllib.error import HTTPError

        self.status, self.fail_at = 302, 1
        with self.assertRaises(HTTPError) as caught:
            self.answer()
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(len(self.received), 1)
        caught.exception.close()

    def test_timeout_and_exception_identity(self) -> None:
        from unittest.mock import patch

        error = TimeoutError("synthetic transport")
        with patch.object(self.adapter, "urlopen", side_effect=error) as opener:
            with self.assertRaises(TimeoutError) as caught:
                self.answer()
        self.assertIs(caught.exception, error)
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(opener.call_args.kwargs["timeout"], 30)


class HarnessWireTest(WireSupport):
    def test_completed_report_labels_decision_evidence(self) -> None:
        code, output = self.invoke(matching=True)
        self.assertEqual(code, 0)
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(result["evidence"], "live decision evidence")
        self.assertEqual(
            output.splitlines()[-2:],
            [
                "match",
                "live run recorded; reproduction_reason="
                + result["reproduction_reason"],
            ],
        )

    def test_model_drift_stops_before_next_request(self) -> None:
        self.response = dict(
            model="synthetic-other-model",
            answers=dict(decision=dict(type="noul", noul=0.9)),
            usage=dict(input_tokens=3, output_tokens=2),
        )
        code, output = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(
            output.splitlines()[-1],
            f"STOPPED: provider failure at case {self.cases[0]['id']}; "
            "status model drift; calls made 1; tokens used 5",
        )
        self.assertEqual(len(self.received), 1)
        self.assertEqual(
            list(self.root.glob("evals/typed_decisions/results_*.json")), []
        )
        records = list(self.root.glob("evals/typed_decisions/runs/*.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(
            json.loads(records[0].read_text())["threshold_outcome"], "ERROR"
        )

    def test_third_case_http_error_stops(self) -> None:
        self.status, self.fail_at = 422, 3
        code, output = self.invoke()
        self.assertEqual(code, 4)
        self.assertEqual(len(self.received), 3)
        self.assertEqual(
            output.splitlines()[-1],
            f"STOPPED: provider failure at case {self.cases[2]['id']}; status 422; calls made 3; tokens used 10",
        )
        self.assertEqual(
            list(self.root.glob("evals/typed_decisions/results_*.json")), []
        )

    def test_closed_connection_stops(self) -> None:
        self.close_connection = True
        code, output = self.invoke()
        self.assertEqual(code, 4)
        self.assertIn("status RemoteDisconnected; calls made 1; tokens used 0", output)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(
            list(self.root.glob("evals/typed_decisions/results_*.json")), []
        )

    def test_invalid_response_stops(self) -> None:
        self.response = {}
        code, output = self.invoke()
        self.assertEqual(code, 4)
        self.assertIn("status invalid response; calls made 1; tokens used 0", output)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(
            list(self.root.glob("evals/typed_decisions/results_*.json")), []
        )

    def test_existing_memo_refuses_before_call(self) -> None:
        from dataclasses import replace
        from unittest.mock import patch

        from eii_gateway import Gateway
        from eii_gateway.memo import digest
        from eii_gateway.providers.none_provider import NoneProvider

        provider = NoneProvider()
        with patch.object(provider, "model", "jev-1.14.0"):
            gateway = Gateway(self.root)
            gateway.provider = provider
            gateway.decide(
                replace(
                    self.request,
                    route="offline-requalification-" + digest(self.endpoint),
                )
            )
        before = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        code, output = self.invoke()
        self.assertEqual(code, 3)
        self.assertEqual(output, "REFUSED: earlier records exist\n")
        self.assertEqual(self.received, [])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*.json")})

    def test_unavailable_stops_without_transport(self) -> None:
        from unittest.mock import patch

        with patch.object(self.adapter.JevProvider, "answer", return_value=None):
            code, output = self.invoke()
        self.assertEqual(code, 4)
        self.assertIn("status invalid response; calls made 0; tokens used 0", output)
        self.assertEqual(self.received, [])
        self.assertEqual(
            list(self.root.glob("evals/typed_decisions/results_*.json")), []
        )

    def test_post_call_cap_still_stops(self) -> None:
        self.response = dict(
            model="jev-1.14.0",
            answers=dict(decision=dict(type="noul", noul=0.9)),
            usage=dict(input_tokens=2000000, output_tokens=1),
        )
        code, output = self.invoke()
        self.assertEqual(code, 4)
        self.assertIn(
            "status invalid response; calls made 1; tokens used 2000001", output
        )
        self.assertEqual(len(self.received), 1)
        self.assertEqual(
            list(self.root.glob("evals/typed_decisions/results_*.json")), []
        )

    def test_complete_other_route_requalifies(self) -> None:
        code, output = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("requalify", output)
        self.assert_counts()

    def test_complete_matching_route(self) -> None:
        code, output = self.invoke(matching=True)
        self.assertEqual(code, 0)
        self.assertIn("match\n", output)
        self.assert_counts()

    def assert_counts(self) -> None:
        result = json.loads(
            next(self.root.glob("evals/typed_decisions/results_*.json")).read_text()
        )
        self.assertEqual(result["calls_made"], len(self.received))
        self.assertEqual(result["tokens_used"], self.tokens_sent)
        from eii_gateway.memo import option_orders

        self.assertEqual(
            len(self.received),
            sum(
                len(option_orders(self.harness.request_for(case, self.cases)))
                for case in self.cases
            ),
        )


class KeyedRunReadmeTest(unittest.TestCase):
    heading = "## Keyed run of 2026-11-13\n\n"
    result_name = "results_2026-11-13T04-19-15-163796.json"

    @classmethod
    def expected_section(cls) -> str:
        from hashlib import sha256

        result = json.loads((ADMITTED.parent / cls.result_name).read_text())
        admitted = json.loads(ADMITTED.read_text())["arms"][
            "jev-1.14.0 (typed-decision provider)"
        ]
        current = result["raw_answers"]["overall"]
        identity = result["identity"]
        models = [
            model
            for row in result["raw_answers"]["cases"]
            for model in row["response_models"]
        ]
        pinned = sum(model == identity["model"] for model in models)
        other = sum(model != identity["model"] for model in models)
        lines = [
            f"Result: [{cls.result_name}]({cls.result_name}).",
            f"Provider: `{identity['provider']}`; model: `{identity['model']}`.",
            f"Reply model identifiers: {pinned} named the pinned model; {other} named another model or none. Replies outside the pin are excluded from the result (L-99).",
            f"Case digest: `{identity['cases_sha256']}`.",
            f"Rubric digest: `{identity['rubric_sha256']}`.",
            f"Route digest: `{identity['route_sha256']}`.",
            f"Thresholds: high {identity['thresholds']['high']}; low {identity['thresholds']['low']}.",
            f"Route status: `{result['route_status']}`; reproduction reason: `{result['reproduction_reason']}`.",
            f"First answers: {current['correct']} of {current['total']}, {current['rate']}%; "
            f"interval {current['ci95']}; admitted: {admitted['correct']} of {admitted['answered']}, "
            f"{admitted['accuracy_of_answered']}; stated interval {result['stated_ci95']}.",
        ]
        for name, row in result["raw_answers"]["by_test"].items():
            lines.append(
                f"{name}: current {row['current']['correct']} of {row['current']['total']}; "
                f"admitted {row['admitted']['correct']} of {row['admitted']['n']}."
            )
        outcomes = result["gateway_accepted"]["outcomes"]
        wrong = [
            row["id"]
            for row in result["gateway_accepted"]["cases"]
            if row["outcome"] == "DECIDED" and not row["correct"]
        ]
        lines.extend(
            [
                f"Gateway outcomes: DECIDED {outcomes['DECIDED']}; BELOW_THRESHOLD {outcomes['BELOW_THRESHOLD']}.",
                "Wrong decided cases: " + ", ".join(wrong) + ".",
                f"Calls made: {result['calls_made']}; tokens used: {result['tokens_used']}.",
                *result["protocol_differences"],
            ]
        )
        return (
            cls.heading
            + "\n".join("- " + line for line in lines)
            + (
                "\n\nFigures and digests above are copied from the linked result, with the admitted "
                "overall figure from `results_2026-11-11.json`. Run records under `runs/` are not committed.\n"
                "The committed aggregate omits each case's memo key because it identifies an uncommitted "
                "run record and supplies no task-criterion evidence (OI-117; ruling L-75).\n"
                "Aggregate SHA-256 before conversion: "
                "`80c34464b1883061ce68391e2af4b974ab258e4a8b52190ee5b6a63dad768c72`; "
                "after conversion: "
                f"`{sha256((ADMITTED.parent / cls.result_name).read_bytes()).hexdigest()}`.\n"
                "The lead made this run under the owner's answer to OI-18, on public and invented cases only "
                "(task brief, keyed-run record). This records this set and this version only; "
                "fresh human qualification remains OI-15.\n"
            )
        )

    def test_keyed_run_figures_match_result(self) -> None:
        readme = (ADMITTED.parent / "README.md").read_text()
        self.assertIn(self.heading, readme)
        section = self.heading + readme.split(self.heading, 1)[1].split("\n## ", 1)[0]
        self.assertEqual(section, self.expected_section())
