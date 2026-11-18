"""Read closed, explicitly reviewed arguments for the existing milestone audit.

Absence is not an independent milestone claim. This reads no page and fetches
nothing; build_cache_evidence verifies every archive, parser and reviewed link.
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path
from typing import Any

from .assembly import AssemblyError
from .assembly_io import local, read_object
from .fetch.registry import Entry
from .investment_contracts import (
    MilestoneArchiveSelection,
    MilestoneShape,
    ReviewedMilestoneLink,
    SourceEnvelope,
)


def load_milestones(
    cache: Path, entries: tuple[Entry, ...]
) -> tuple[MilestoneArchiveSelection, ...]:
    name = "review/investment_milestones.json"
    if not local(cache, name).is_file():
        return ()
    document = read_object(cache, name)
    if set(document) != {"milestones"} or not isinstance(document["milestones"], list):
        raise AssemblyError("assembly_milestone_review_invalid")
    by_key = {entry.key: entry for entry in entries}
    result = []
    seen = set()
    try:
        for row in document["milestones"]:
            if not isinstance(row, dict) or set(row) != {
                "key",
                "identity",
                "shape",
                "envelope",
                "links",
                "crosswalk_key",
            }:
                raise ValueError
            key, identity = row["key"], row["identity"]
            if (
                not isinstance(key, str)
                or key not in by_key
                or not isinstance(identity, str)
                or re.fullmatch("[a-f0-9]{64}", identity) is None
                or (key, identity) in seen
            ):
                raise ValueError
            local(cache, key)
            seen.add((key, identity))
            shape = row["shape"]
            if (
                not isinstance(shape, dict)
                or set(shape) != {"shape_id", "fields", "confirmed"}
                or not isinstance(shape["shape_id"], str)
                or type(shape["confirmed"]) is not bool
                or not isinstance(shape["fields"], list)
                or any(not isinstance(field, str) for field in shape["fields"])
                or len(set(shape["fields"])) != len(shape["fields"])
            ):
                raise ValueError
            envelope = _text_fields(
                row["envelope"], {field.name for field in fields(SourceEnvelope)}
            )
            if envelope["source_id"] != by_key[key].source_id:
                raise ValueError
            links = []
            if not isinstance(row["links"], list):
                raise ValueError
            for link in row["links"]:
                names = {field.name for field in fields(ReviewedMilestoneLink)} - {
                    "crosswalk",
                    "crosswalk_key",
                }
                if (
                    not isinstance(link, dict)
                    or set(link) != names
                    or type(link["reviewed"]) is not bool
                    or any(
                        not isinstance(value, str)
                        for name, value in link.items()
                        if name != "reviewed"
                    )
                ):
                    raise ValueError
                links.append(ReviewedMilestoneLink(**link))
            crosswalk = row["crosswalk_key"]
            if not isinstance(crosswalk, str):
                raise ValueError
            if crosswalk:
                local(cache, crosswalk)
            result.append(
                MilestoneArchiveSelection(
                    key,
                    identity,
                    MilestoneShape(
                        shape["shape_id"],
                        frozenset(shape["fields"]),
                        shape["confirmed"],
                    ),
                    SourceEnvelope(**envelope),
                    tuple(links),
                    crosswalk,
                )
            )
    except (ValueError, KeyError, TypeError):
        raise AssemblyError("assembly_milestone_review_invalid") from None
    return tuple(result)


def _text_fields(value: Any, names: set[str]) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != names
        or any(not isinstance(item, str) for item in value.values())
    ):
        raise ValueError
    return {name: value[name] for name in names}
