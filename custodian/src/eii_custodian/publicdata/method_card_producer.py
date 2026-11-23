"""Assemble the S2-T08 method-pin artifact from a recorded generation configuration.

The producer never opens a public snapshot or invents a regression value; callers
supply every checked pin row. Configuration pins carry empty source lineage.
Under decision 0094 a deferred result pin may stay pending: such a row carries
empty values and empty lineage, never a stand-in value, and no other pin may
take that shape.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from .method_card_validation import (
    CONFIGURATION_PINS,
    REQUIRED_PINS,
    S7_DEFERRED_PINS,
    _canonical,
    _mapping,
)


def produce_pin_artifact(
    generation_config: Mapping[str, object],
    pin_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Write the closed S2-T08 pin artifact shape from config settings and rows.

    Each output row binds ``pin_id``, ``values``, ``settings`` and
    ``source_lineage``. Settings come from the generation configuration; values
    and lineage come from the supplied pin rows.
    """
    config = _mapping(generation_config, {"schema_version", "pins"})
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("pin_schema_version")
    settings_by_pin = _mapping(config["pins"])
    if set(settings_by_pin) - REQUIRED_PINS:
        raise ValueError("pin_artifact_fields")
    produced: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in pin_rows:
        row = _mapping(item, {"pin_id", "values", "source_lineage"})
        pin = str(row["pin_id"])
        if pin not in REQUIRED_PINS or pin in seen:
            raise ValueError("pin_artifact_duplicate_or_unknown")
        seen.add(pin)
        settings = settings_by_pin.get(pin)
        if not isinstance(settings, dict):
            raise ValueError("pin_artifact_missing")
        lineage = row["source_lineage"]
        values = row["values"]
        if pin in S7_DEFERRED_PINS and values == {}:
            # The closed pending representation of decision 0094: a deferred
            # result pin stays unpinned with no value and no lineage, only its
            # recorded settings; a lineage beside a missing value is refused.
            if lineage != []:
                raise ValueError("pin_pending_lineage_forbidden")
        elif values == {}:
            raise ValueError("pin_pending_not_deferred")
        elif pin in CONFIGURATION_PINS:
            if lineage != []:
                raise ValueError("pin_configuration_lineage_forbidden")
        elif not isinstance(lineage, list) or not lineage:
            raise ValueError("pin_source_lineage_required")
        produced.append(
            {
                "pin_id": pin,
                "values": row["values"],
                "settings": cast(dict[str, Any], settings),
                "source_lineage": lineage,
            }
        )
    if seen != REQUIRED_PINS:
        raise ValueError("pin_missing_or_duplicate")
    return {"schema_version": 1, "pins": produced}


def artifact_matches_config(
    artifact: Mapping[str, object], generation_config: Mapping[str, object]
) -> None:
    """Refuse an artifact whose per-pin settings diverge from the configuration."""
    built = produce_pin_artifact(
        generation_config,
        [
            {
                "pin_id": row["pin_id"],
                "values": row["values"],
                "source_lineage": row["source_lineage"],
            }
            for row in cast(list[dict[str, object]], artifact["pins"])
        ],
    )
    if _canonical(built) != _canonical(dict(artifact)):
        raise ValueError("pin_artifact_mismatch")
