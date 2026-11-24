"""Process configuration. Names only; values stay in the environment, and secrets are read at request time."""

from __future__ import annotations

import os

_FC_REGISTER_FILE = "EII_FC_REGISTER_FILE"


class ConfigError(Exception):
    """An invalid setting stops the start. The message names the variable."""

    def __init__(self, variable: str) -> None:
        super().__init__(variable)
        self.variable = variable


def read_esri_api_key() -> str | None:
    """Return ``ESRI_API_KEY`` from the process environment, or nothing."""
    value = os.environ.get("ESRI_API_KEY")
    if type(value) is not str or value == "":
        return None
    return value


def read_fc_register_file() -> str | None:
    """Return ``EII_FC_REGISTER_FILE``, or nothing when it is unset.

    A value that is not a single trimmed line stops the start. The error
    names the variable and carries neither the value nor a path.
    """
    value = os.environ.get(_FC_REGISTER_FILE)
    if value is None or value == "":
        return None
    if value != value.strip() or any(ord(char) < 32 for char in value):
        raise ConfigError(_FC_REGISTER_FILE)
    return value


def read_maptile_api_key() -> str | None:
    """Read the photorealistic key only in the serving process."""
    return os.environ.get("MAPTILE_API_KEY") or None


def map_setting(name: str) -> str:
    """Closed set of non-secret map settings; no independent settings store."""
    if name not in {
        "EII_IMAGERY_TILE_BASE",
        "EII_PHOTOREAL_TILE_BASE",
        "EII_PHOTOREAL_LIMIT",
        "EII_PHOTOREAL_PRICE_PER_THOUSAND",
    }:
        raise ValueError("unknown_map_setting")
    return os.environ.get(name, "")
