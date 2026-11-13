"""Replay agreement, abstention, memoisation and ranking-signal boundaries."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from eii_gateway import Gateway
from eii_gateway.memo import input_hash, memo_key, normalise, option_orders
from eii_gateway.providers.base import Reply
from eii_gateway.thresholds import outcome

from .support import request

FIXTURE = Path(__file__).parent / "fixtures/recorded/synthetic.json"


class RecordedProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {"EII_DECISION_PROVIDER": "recorded"})
        env.start()
        self.addCleanup(env.stop)

    def test_replays_yes_no_and_choice(self) -> None:
        gateway = Gateway(self.root, fixtures=FIXTURE)
        record = gateway.decide(request())
        self.assertEqual(record["returned_label"], "yes")
        self.assertEqual(record["returned_scores"], {"yes": 0.92, "no": 0.08})
        self.assertEqual(record["threshold_outcome"], "DECIDED")
        choice = replace(
            request(),
            kind="choice",
            options=("synthetic-alpha", "synthetic-beta"),
            case_id="synthetic-choice",
        )
        record = gateway.decide(choice)
        self.assertEqual(record["returned_label"], "synthetic-alpha")
        self.assertEqual(record["threshold_outcome"], "DECIDED")
        self.assertEqual(
            record["option_order"], [list(order) for order in option_orders(choice)]
        )

    def test_first_answer_stands_across_instances_and_writes_each_call(self) -> None:
        first = Gateway(self.root, fixtures=FIXTURE).decide(request())
        with patch(
            "eii_gateway.providers.recorded_provider.RecordedProvider.answer",
            side_effect=AssertionError("memo must win"),
        ):
            replay = Gateway(self.root, fixtures=FIXTURE).decide(request())
        self.assertEqual(first["returned_label"], replay["returned_label"])
        self.assertEqual(first["memo_key"], replay["memo_key"])
        self.assertEqual(
            len(list(self.root.glob("evals/typed_decisions/runs/*.json"))), 2
        )

    def test_missing_replay_unavailable(self) -> None:
        for change in (
            {"case_id": "synthetic-missing"},
            {"input_text": "SYNTHETIC different input"},
        ):
            record = Gateway(self.root, fixtures=FIXTURE).decide(request(**change))
            self.assertEqual(record["threshold_outcome"], "UNAVAILABLE")
            self.assertIsNone(record["returned_label"])

    def test_choice_disagreement_and_weak_second_answer(self) -> None:
        req = replace(
            request(),
            kind="choice",
            options=("synthetic-alpha", "synthetic-beta"),
            case_id="synthetic-choice",
        )
        first = Reply(
            "synthetic-alpha",
            {"synthetic-alpha": 0.92, "synthetic-beta": 0.08},
            "synthetic-recorded",
            0,
        )
        for second in (
            Reply(
                "synthetic-beta",
                {"synthetic-beta": 0.92, "synthetic-alpha": 0.08},
                "synthetic-recorded",
                0,
            ),
            Reply(
                "synthetic-alpha",
                {"synthetic-alpha": 0.6, "synthetic-beta": 0.4},
                "synthetic-recorded",
                0,
            ),
        ):
            with (
                tempfile.TemporaryDirectory() as folder,
                patch(
                    "eii_gateway.providers.recorded_provider.RecordedProvider.answer",
                    side_effect=[first, second],
                ) as calls,
            ):
                record = Gateway(Path(folder), fixtures=FIXTURE).decide(req)
                self.assertEqual(calls.call_count, 2)
                self.assertEqual(record["threshold_outcome"], "BELOW_THRESHOLD")
                self.assertTrue(record["fallback_applied"])

    def test_choice_missing_second_answer_applies_fallback_and_writes_record(
        self,
    ) -> None:
        req = replace(
            request(),
            kind="choice",
            options=("synthetic-alpha", "synthetic-beta"),
            case_id="synthetic-choice",
        )
        first = Reply(
            "synthetic-alpha",
            {"synthetic-alpha": 0.92, "synthetic-beta": 0.08},
            "synthetic-recorded",
            0,
        )
        with patch(
            "eii_gateway.providers.recorded_provider.RecordedProvider.answer",
            side_effect=[first, None],
        ) as calls:
            record = Gateway(self.root, fixtures=FIXTURE).decide(req)
        self.assertEqual(
            [call.args[1] for call in calls.call_args_list], list(option_orders(req))
        )
        self.assertEqual(record["threshold_outcome"], "UNAVAILABLE")
        self.assertIsNone(record["returned_label"])
        self.assertTrue(record["fallback_applied"])
        paths = list(self.root.glob("evals/typed_decisions/runs/*.json"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_text()), record)

    def test_threshold_edges(self) -> None:
        for score, label, expected in (
            (0.9, "yes", "DECIDED"),
            (0.899, "yes", "BELOW_THRESHOLD"),
            (0.1, "no", "DECIDED"),
            (0.101, "no", "BELOW_THRESHOLD"),
            (0.95, "no", "BELOW_THRESHOLD"),
            (0.05, "yes", "BELOW_THRESHOLD"),
        ):
            self.assertEqual(
                outcome("yes_no", label, {"yes": score, "no": 1 - score}), expected
            )
        self.assertEqual(
            outcome("ordinal", "synthetic-high", {"synthetic-high": 0.9}), "DECIDED"
        )
        self.assertEqual(
            outcome("choice", "synthetic-alpha", {"synthetic-alpha": 0.899}),
            "BELOW_THRESHOLD",
        )

    def test_errors_and_token_budget(self) -> None:
        for reply in (
            Reply("fact", {"yes": 0.9, "no": 0.1}, "synthetic-recorded", 0),
            Reply("yes", {"yes": 0.9, "no": 0.1}, "changed-model", 0),
            Reply("yes", {"yes": float("nan"), "no": 0.1}, "synthetic-recorded", 0),
            Reply("yes", {"yes": 0.9}, "synthetic-recorded", 0),
            Reply("yes", {"yes": 0.9, "no": 0.1}, "synthetic-recorded", -1),
            Reply("yes", {"yes": 0.9, "no": 0.1}, "synthetic-recorded", 1),
        ):
            with (
                tempfile.TemporaryDirectory() as folder,
                patch(
                    "eii_gateway.providers.recorded_provider.RecordedProvider.answer",
                    return_value=reply,
                ),
            ):
                record = Gateway(Path(folder), fixtures=FIXTURE).decide(request())
                self.assertEqual(record["threshold_outcome"], "ERROR")
                self.assertEqual(record["returned_scores"], {})
        for cap in (-1, True):
            with self.assertRaises(ValueError):
                Gateway(self.root, token_cap=cap)
        with patch(
            "eii_gateway.providers.recorded_provider.RecordedProvider.answer",
            return_value=Reply("yes", {"yes": 0.9, "no": 0.1}, "synthetic-recorded", 1),
        ):
            gateway = Gateway(self.root, fixtures=FIXTURE, token_cap=1)
            self.assertEqual(gateway.decide(request())["threshold_outcome"], "DECIDED")
            self.assertEqual(gateway.remaining, 0)

    def test_memo_context_and_normalisation(self) -> None:
        req = request()
        first = memo_key(req, "synthetic-recorded")
        for key in (
            "input_text",
            "language",
            "rubric_text",
            "route",
            "rubric_id",
            "case_id",
        ):
            self.assertNotEqual(
                first,
                memo_key(request(**{key: "synthetic-change"}), "synthetic-recorded"),
            )
        self.assertNotEqual(first, memo_key(req, "other-model"))
        self.assertEqual(normalise("synthetic\r\ncafe\u0301"), "synthetic\ncafé")
        self.assertEqual(len(input_hash(req)), 64)
        self.assertEqual(option_orders(req), (("no", "yes"),))
        self.assertEqual(len(json.loads(FIXTURE.read_text())), 3)
