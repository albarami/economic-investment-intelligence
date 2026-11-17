"""One final guard for persisted projections and command diagnostics."""

from __future__ import annotations

import json
from collections.abc import Mapping

KEYS = ("BESTTIME_API_KEY_PRIVATE", "BESTTIME_API_KEY_PUBLIC")


def assert_clean(environ: Mapping[str, str], value: object) -> None:
    """Reject secret values or a keyed address without echoing the rejected text."""
    text = json.dumps(value, sort_keys=True)
    if (
        any(environ.get(key) and environ[key] in text for key in KEYS)
        or "api_key_private=" in text
        or "api_key_public=" in text
    ):
        raise ValueError(
            "busy_besttime https://besttime.app/api/v1/forecasts secret_in_output"
        )
