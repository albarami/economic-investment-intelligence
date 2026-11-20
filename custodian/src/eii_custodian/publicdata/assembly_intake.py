"""First-phase local intake evidence, independent of later fail-fast fetches.

Profiles contain columns, counts and lineage only. They never activate a source
or replace a reviewed declaration. Missing reviewed inputs remain pending.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .assembly import AssemblyError
from .assembly_io import local, read_object, write_record
from .assembly_profile import bounded_input, observe_profile
from .fetch.award_checks import AwardError
from .fetch.awards import ingest_awards
from .fetch.partitions import PartitionError, partition_spans


def write_intake_evidence(
    cache: Path,
    document: Mapping[str, Any],
    seed: int,
    stamp: str,
    *,
    awards_selected: bool = True,
) -> dict[str, str]:
    if type(seed) is not int:
        raise AssemblyError("figure_seed_invalid")
    sources = document.get("sources", {})
    declaration = (
        sources.get("awards_owner_scrape", {}) if isinstance(sources, dict) else {}
    )
    if not isinstance(declaration, dict):
        raise AssemblyError("assembly_intake_invalid")
    awards: dict[str, object]
    bound = declaration.get("max_bytes")
    if not awards_selected:
        awards = {"state": "unselected", "reason": "source_not_selected"}
    elif not isinstance(declaration.get("profile"), dict) and (
        type(bound) is not int or bound <= 0
    ):
        awards = {"state": "pending", "reason": "awards_profile_pending"}
    elif type(declaration.get("max_bytes")) is not int or declaration["max_bytes"] <= 0:
        awards = {"state": "pending", "reason": "acquisition_bound_unconfirmed"}
    else:
        manifest = read_object(cache, "intake/awards_owner_scrape/intake.json")
        filename = manifest.get("file")
        if not isinstance(filename, str) or "/" in filename or "\\" in filename:
            raise AssemblyError("assembly_intake_invalid")
        path = local(cache, "intake/awards_owner_scrape/" + filename)
        if type(manifest.get("seed")) is not int or manifest["seed"] != seed:
            raise AssemblyError("assembly_seed_mismatch")
        try:
            if path.stat().st_size > declaration["max_bytes"]:
                raise AssemblyError("assembly_intake_bound")
            if isinstance(declaration.get("profile"), dict):
                batch = ingest_awards(
                    cache,
                    path,
                    manifest["sha256"],
                    declaration["profile"],
                    stamp,
                    max_bytes=declaration["max_bytes"],
                )
                observed = observe_profile(
                    batch.body,
                    declaration["profile"]["format"],
                    declaration["profile"]["sheet"],
                )
                awards = {
                    "state": "profiled",
                    "summary": batch.summary,
                    "profile": declaration["profile"],
                    "observed_profile": observed,
                    "sha256": batch.sha256,
                    "seed": seed,
                    "mapping_state": "reviewed",
                }
            else:
                request = manifest.get("profile_request", {})
                if (
                    not isinstance(request, dict)
                    or set(request) - {"sheet"}
                    or not isinstance(request.get("sheet", ""), str)
                ):
                    raise AssemblyError("assembly_intake_invalid")
                observed = observe_profile(
                    bounded_input(path, declaration["max_bytes"], manifest["sha256"]),
                    path.suffix.removeprefix("."),
                    request.get("sheet", ""),
                )
                awards = {
                    "state": "profiled",
                    "observed_profile": observed,
                    "summary": {
                        "row_count": observed["row_count"],
                        "dated_rows": None,
                        "unparsed_dates": None,
                        "blank_dates": None,
                        "date_first": None,
                        "date_last": None,
                        "date_mapping_state": "pending",
                    },
                    "sha256": manifest["sha256"],
                    "seed": seed,
                    "mapping_state": "pending",
                }
        except (OSError, KeyError, AwardError):
            raise AssemblyError("assembly_intake_invalid") from None
    try:
        spans = partition_spans(document.get("accident_spans"))
    except PartitionError:
        accident: dict[str, object] = {
            "state": "pending",
            "reason": "partition_byte_bound_unconfirmed",
        }
    else:
        accident = {"state": "accepted", "spans": spans}
    return write_record(
        cache,
        "assembly/intake_evidence.json",
        {"method": "assembly-intake.v1", "awards": awards, "accident": accident},
    )
