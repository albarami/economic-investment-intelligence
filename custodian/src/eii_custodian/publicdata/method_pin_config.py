"""Tracked method settings; missing pack choices stay explicitly pending (rule 46)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .gis.snapshot_policy import safe_child
from .method_card_validation import (
    REQUIRED_PINS,
    S7_DEFERRED_PINS,
    _load_json,
    _mapping,
    _read,
)

CONFIG_RELATIVE = "custodian/publicdata/review/s2_t09_generation_config.json"


def load_generation_config(root: Path) -> dict[str, object]:
    """Load the reviewed canonical bytes, never a source-check record or a cache."""
    path = safe_child(root.absolute(), CONFIG_RELATIVE)
    if not path.is_file():
        raise ValueError("pin_configuration_missing")
    body = _read(path)
    config = _mapping(_load_json(body), {"schema_version", "pins"})
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("pin_schema_version")
    settings = _mapping(config["pins"])
    if set(settings) != REQUIRED_PINS:
        raise ValueError("pin_configuration_pins")
    for item in settings.values():
        _mapping(item)
    canonical = (
        json.dumps(config, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    )
    if body != canonical.encode("utf-8"):
        raise ValueError("pin_configuration_not_canonical")
    return config


def configuration_pending(config: Mapping[str, object]) -> bool:
    """Unspecified settings withhold automatic production; no default is guessed."""
    return any(
        "pending_reason" in _mapping(settings)
        for pin, settings in _mapping(config["pins"]).items()
        if pin not in S7_DEFERRED_PINS
    )
