"""Default provider must be complete without a socket or configured adapter."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class NoneProviderNetwork(unittest.TestCase):
    def test_none_never_opens_socket(self) -> None:
        # Import inside the patched boundary so import-time egress also fails.
        with (
            patch.dict(
                os.environ,
                {
                    key: value
                    for key, value in os.environ.items()
                    if key != "EII_DECISION_PROVIDER"
                },
                clear=True,
            ),
            patch("socket.socket", side_effect=AssertionError("network forbidden")),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("network forbidden"),
            ),
            tempfile.TemporaryDirectory() as folder,
        ):
            from eii_gateway import Gateway, Request

            request = Request(
                decision_class="spine_match",
                kind="yes_no",
                input_class="synthetic",
                input_text="SYNTHETIC activity example",
                language="en",
                rubric_id="synthetic-match",
                rubric_text="Flag this invented pair for human review.",
                route="synthetic-offline",
            )
            gateway = Gateway(Path(folder))
            record = gateway.decide(request)
            self.assertEqual(record["threshold_outcome"], "DISABLED")
            self.assertEqual(record["provider_configured"], "none")
            self.assertEqual(record["provider_used"], "none")
            self.assertTrue(record["fallback_applied"])
            self.assertEqual(
                len(list(Path(folder).glob("evals/typed_decisions/runs/*.json"))), 1
            )
            self.assertNotIn("eii_gateway.providers.jev_provider", sys.modules)

    def test_none_ignores_jev_key(self) -> None:
        from eii_gateway import Gateway

        from .support import request

        original_get = os.environ.get

        def checked_get(key: str, default: str | None = None) -> str | None:
            if key == "JEV_PRO_API_KEY":
                raise AssertionError("default provider read a key")
            return original_get(key, default)

        with (
            patch.dict(
                os.environ,
                {
                    "EII_DECISION_PROVIDER": "none",
                    "JEV_PRO_API_KEY": "SYNTHETIC_UNUSED",
                },
            ),
            patch.object(os.environ, "get", side_effect=checked_get),
            tempfile.TemporaryDirectory() as folder,
        ):
            self.assertEqual(
                Gateway(Path(folder)).decide(request())["provider_used"], "none"
            )
