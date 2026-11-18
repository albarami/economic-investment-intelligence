"""Read the Earthdata token from the supplied environment."""

from __future__ import annotations

from collections.abc import Mapping

VARIABLE = "EARTHDATA_API_KEY"


def earthdata_token(environ: Mapping[str, str]) -> str:
    """Return the token, or an empty string when the variable is absent or blank."""
    return environ.get(VARIABLE, "").strip()
