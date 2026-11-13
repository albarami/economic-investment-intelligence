"""Additional witnesses for gaps exposed by the S1-T07 break pass."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import get_args
from unittest.mock import patch

import eii_gateway
from eii_gateway import Gateway, Request
from eii_gateway.providers.base import Reply
from eii_gateway.schema import validate_record
from eii_gateway.settings import configured_provider
from eii_gateway.types import CLASS_RULES, KINDS, OUTCOMES, DecisionClass, Kind, Outcome

from .support import request


class ContractEdges(unittest.TestCase):
    def test_exported_vocabulary_matches_the_contract(self) -> None:
        self.assertEqual(eii_gateway.__all__, ["Gateway", "Request"])
        classes = {
            "spine_match",
            "router_miss_finder",
            "brief_second_reader",
            "question_route",
            "string_parity",
        }
        kinds = {"yes_no", "choice", "ordinal"}
        outcomes = {
            "DECIDED",
            "BELOW_THRESHOLD",
            "UNAVAILABLE",
            "DISABLED",
            "ERROR",
            "BLOCKED_BY_DATA_POLICY",
        }
        self.assertEqual(set(get_args(DecisionClass)), classes)
        self.assertEqual(set(get_args(Kind)), kinds)
        self.assertEqual(set(get_args(Outcome)), outcomes)
        self.assertEqual(set(KINDS), kinds)
        self.assertEqual(set(OUTCOMES), outcomes)
        self.assertEqual(CLASS_RULES["spine_match"], ("admitted", "order_human_review"))
        self.assertEqual(
            CLASS_RULES["router_miss_finder"], ("admitted", "flag_router_disagreement")
        )

    def test_settings_accept_known_routes_without_importing_adapter(self) -> None:
        for name in ("none", "recorded", "jev"):
            with patch.dict(os.environ, {"EII_DECISION_PROVIDER": name}):
                self.assertEqual(configured_provider(), name)
        with (
            patch.dict(os.environ, {"EII_DECISION_PROVIDER": "unknown"}),
            self.assertRaises(ValueError),
        ):
            configured_provider()
        self.assertNotIn("eii_gateway.providers.jev_provider", sys.modules)

    def test_configured_cap_with_an_in_memory_provider_only(self) -> None:
        class InMemoryProvider:
            name = "jev"
            model = "synthetic-memory"
            calls = 0

            def answer(
                self, req: Request, order: tuple[str, ...], token_limit: int
            ) -> Reply:
                self.calls += 1
                return Reply("yes", {"yes": 0.9, "no": 0.1}, self.model, 1)

        for cap, expected, calls in ((0, "UNAVAILABLE", 0), (1, "DECIDED", 1)):
            with (
                tempfile.TemporaryDirectory() as folder,
                patch.dict(os.environ, {"EII_DECISION_PROVIDER": "jev"}),
            ):
                gateway = Gateway(Path(folder), token_cap=cap)
                fake = InMemoryProvider()
                gateway.provider = fake
                result = gateway.decide(request())
                self.assertEqual(result["threshold_outcome"], expected)
                self.assertEqual(fake.calls, calls)
                self.assertEqual(gateway.remaining, 0)
                self.assertEqual(result["provider_used"], "jev")
        self.assertNotIn("eii_gateway.providers.jev_provider", sys.modules)

    def test_no_result_cannot_have_a_decision_outcome(self) -> None:
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
        ):
            gateway = Gateway(Path(folder))
            record = gateway.decide(request())
            replay = gateway.decide(request())
            self.assertEqual(replay["latency_ms"], 0.0)
            for status in ("DECIDED", "BELOW_THRESHOLD"):
                with self.subTest(status=status), self.assertRaises(ValueError):
                    validate_record(
                        {
                            **record,
                            "threshold_outcome": status,
                            "fallback_applied": status != "DECIDED",
                        }
                    )
