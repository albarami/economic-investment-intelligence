"""Forbidden declarations never construct a provider or persist their content."""

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from eii_gateway import Gateway
from eii_gateway.policy import DataPolicyBlocked, check_policy
from eii_gateway.types import CLASS_RULES

from .support import request


class DataPolicy(unittest.TestCase):
    def test_visitor_typed_blocked(self) -> None:
        for kind in (
            "visitor_typed",
            "real_custodian",
            "real_identifier",
            "credential",
            "real_company_question",
            "other_project",
            "unknown",
        ):
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory() as folder,
                patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}),
                patch.object(
                    Gateway,
                    "_provider",
                    side_effect=AssertionError("policy must precede dispatch"),
                ),
            ):
                gateway = Gateway(Path(folder))
                with self.assertRaisesRegex(
                    DataPolicyBlocked, "BLOCKED_BY_DATA_POLICY"
                ):
                    gateway.decide(request(input_class=kind))
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_cleared_classes_and_class_restrictions(self) -> None:
        for kind in ("public", "synthetic", "project_text", "team_question"):
            check_policy(kind, "spine_match")
        for cls in ("router_miss_finder", "question_route"):
            check_policy("team_question", cls)
            with self.assertRaises(DataPolicyBlocked):
                check_policy("public", cls)
        check_policy("project_text", "string_parity")
        with self.assertRaises(DataPolicyBlocked):
            check_policy("synthetic", "string_parity")

    def test_five_classes_and_effects_are_closed(self) -> None:
        self.assertEqual(
            set(CLASS_RULES),
            {
                "spine_match",
                "router_miss_finder",
                "brief_second_reader",
                "question_route",
                "string_parity",
            },
        )
        self.assertEqual(
            CLASS_RULES["brief_second_reader"], ("admitted", "add_to_human_sample")
        )
        self.assertEqual(
            CLASS_RULES["question_route"], ("shadow", "record_shadow_route")
        )
        self.assertEqual(
            CLASS_RULES["string_parity"], ("experiment_first", "record_experiment")
        )
        for changes in (
            {"decision_class": "privacy"},
            {"kind": "number"},
            {"options": ("yes",)},
            {"kind": "choice", "options": ("same", "same")},
            {"kind": "ordinal", "options": ("", "other")},
            {"kind": "choice", "options": ("1", "other")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(request(), **changes)
