"""Pure, independent Public-pack evidence checks (PUB-04/13/85, DAT-106).

Inputs are already loaded by the caller. No cache discovery, transport, release
selection or successful-fetch inference occurs here. Part B supplies the joined
tasks' component inventories and verified output/table references.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, replace
from datetime import datetime

from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import (
    _SKIP_LICENCE,
    _SKIP_TERMS,
    Entry,
)

REGISTER_IDS = frozenset({"biz_register", "fc_register"})
FORBIDDEN = frozenset({"traffic_tomtom_flow", "traffic_tomtom_range", "tiles3d_google"})
# Source identities, not fetch evidence: decisions 0023, 0040, 0046; doc 04 §2.
TASK_SOURCES = frozenset(
    "fdi_projects investqa_pages gis_land_price gis_rail gis_phcc gis_landmarks "
    "gis_locator gis_zoning gis_address gis_parcels gis_poi_comm gis_boundaries "
    "gis_context gis_imagery_history bldg_3dglobfp bldg_wsf3d bank_credit_act "
    "tenders_pub dcool_capacity trade_ext survey_ext price_ext hotel_ext talent_ext "
    "jobseekers utilities_ext coverage_ext fdi_stats completions_ext un_comtrade "
    "cepii_baci cepii_gravity atlas_complexity wb_wdi unctad_fdi imf_weo ilostat_qat "
    "wage_sector wage_bands_priv work_hours_act cpi_group zone_population "
    "census_hh_type_2020 accident bnd_muni_2025 places_ovt bldg_ovt "
    "worldpop_qat_2020 census_2020_workbook insurance_tables events_visit_qatar "
    "events_qncc suppliers_tawteen manateq_tariffs monaqasat_classified "
    "schools_private_directory awards_owner_scrape".split()
)
Record = list[dict[str, str]]


@dataclass(frozen=True)
class Pack:
    sources: Mapping[str, tuple[str, ...]]
    forbidden: frozenset[str]


@dataclass(frozen=True)
class Absence:
    reason: str
    caveat: str


def independent_inventory(
    family_counts: Mapping[str, int], decision_0019: Set[str], citations: Set[str]
) -> tuple[Mapping[str, int], frozenset[str]]:
    """Use caller-supplied expectations without importing repository tests.

    B9 moves their authoritative definitions after the dependency join; until
    then tests pass the existing constants without copying them here.
    """
    return family_counts, frozenset(decision_0019 | citations) | TASK_SOURCES


def section(text: str, heading: str) -> str:
    """Read a stable Markdown anchor, retaining its subordinate sections."""
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        raise ValueError("pack_section_missing") from None
    level = len(heading) - len(heading.lstrip("#"))
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(r"^#{1," + str(level) + r"} ", lines[i])
        ),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end])


def pack_sources(text: str, family_counts: Mapping[str, int]) -> Pack:
    """Read document 04 §2.1, §2.3 and §2.4, never its coverage table."""
    sources: dict[str, tuple[str, ...]] = {}
    for prefix in ("### 2.1 ", "### 2.3 ", "### 2.4 "):
        heading = next(
            (line for line in text.splitlines() if line.startswith(prefix)), ""
        )
        if not heading:
            raise ValueError("pack_section_missing")
        block = section(text, heading)
        header = next(
            (line for line in block.splitlines() if line.startswith("| ")), ""
        )
        width = len(header.split("|"))
        block_seen: set[str] = set()
        for line in block.splitlines():
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) < 2 or not re.fullmatch(r"`[a-z0-9_]+`", cells[1]):
                continue
            source = cells[1].strip("`")
            # PO-S2-72: a family row is held to the larger of the header width
            # and five cells before the width skip can pass over it.
            if source in family_counts and len(cells) < max(width, 5):
                raise ValueError("pack_family_row_truncated")
            if len(cells) < max(width, 4):
                continue
            if source in block_seen or (
                source in sources
                and not (
                    source == "un_comtrade"
                    and prefix == "### 2.3 "
                    and not sources[source]
                )
            ):
                raise ValueError("pack_source_duplicate")
            block_seen.add(source)
            sources[source] = (
                tuple(re.findall(r"`([^`]+)`", cells[4]))
                if source in family_counts
                else ()
            )
    return Pack(sources, FORBIDDEN)


def table_catalogue(text: str) -> frozenset[str]:
    """Read document 03 §7.2; joined task contracts can extend the supplied set."""
    return frozenset(
        re.findall(r"^\| `([^`]+)` \|", section(text, "### 7.2 Table catalogue"), re.M)
    )


def receipt_valid(row: Entry, receipt: Mapping[str, object]) -> bool:
    """Validate receipt shape/identity against the producer, not a PASS log line.

    Snapshot bytes/hash verification belongs to the existing readers; this check
    verifies their supplied receipt and the registry chain, without reading data.
    """
    digest = receipt.get("sha256")
    if row.kind == "citation_only":
        if digest != "CITATION_ONLY":
            return False
    elif not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        return False
    stored_row = row
    if (
        row.key == row.source_id
        and row.key in {"places_ovt", "bldg_ovt"}
        and receipt.get("key") == row.key + "/listing"
    ):
        stored_row = replace(row, key=row.key + "/listing", extension="json")
    expected = sidecar_for(
        stored_row,
        digest=str(digest),
        nbytes=0,
        fetch_url=row.url,
        fetch_host=row.fetch_host,
        retrieved_utc="",
        publisher=row.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    if not expected.keys() <= receipt.keys():
        return False
    variable = {
        "bytes",
        "retrieved_utc",
        "source_modified",
        "row_count",
        "terms_sha256",
        "portal_licence",
        "portal_licence_url",
        "fetch_url",
        "fetch_host",
    }
    if any(
        receipt[key] != value for key, value in expected.items() if key not in variable
    ):
        return False
    # Ruling L-1001: pending terms fields (words, reading date, basis of use)
    # are records and never exclude a source; only identity, publisher, licence
    # id and fetch address have to be present.
    if any(
        not isinstance(receipt.get(key), str) or not str(receipt[key]).strip()
        for key in (
            "publisher",
            "title_en",
            "licence_id",
            "fetch_url",
        )
    ):
        return False
    retrieved = receipt.get("retrieved_utc")
    try:
        if (
            not isinstance(retrieved, str)
            or datetime.fromisoformat(retrieved.replace("Z", "+00:00")).tzinfo is None
        ):
            return False
    except ValueError:
        return False
    nbytes = receipt.get("bytes")
    return type(nbytes) is int and nbytes >= 0 and receipt.get("switched_off") is False


def in_use(row: Entry, receipts: Mapping[str, Mapping[str, object]]) -> bool:
    return (
        not row.skip_reason
        and row.key in receipts
        and receipt_valid(row, receipts[row.key])
    )


def register_in_use(row: Entry, receipts: Mapping[str, Mapping[str, object]]) -> bool:
    """A register file row is in use through its reviewed projection receipt.

    The ``lead_shell_file_input`` dispatch marker is not an evidence absence;
    the receipt is the file-input shape verified by the bundle reader.
    """
    receipt = receipts.get(row.key)
    if not isinstance(receipt, Mapping):
        return False
    digest = receipt.get("sha256")
    retrieved = receipt.get("retrieved_utc")
    try:
        stamp = (
            datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
            if isinstance(retrieved, str)
            else None
        )
    except ValueError:
        stamp = None
    return (
        receipt.get("version") == "register_input_v1"
        and receipt.get("kind") == "register_file"
        and receipt.get("key") == row.key
        and receipt.get("source_id") == row.source_id
        and isinstance(receipt.get("period"), str)
        and isinstance(digest, str)
        and re.fullmatch(r"[a-f0-9]{64}", digest) is not None
        and stamp is not None
        and stamp.tzinfo is not None
        and all(
            isinstance(receipt.get(name), str) and str(receipt[name]).strip()
            for name in ("publisher", "dataset", "licence_id", "licence_basis")
        )
    )


def check(
    *,
    entries: Sequence[Entry],
    pack: Pack,
    inventory: Mapping[str, tuple[str, ...]],
    catalogue: set[str] | frozenset[str],
    receipts: Mapping[str, Mapping[str, object]],
    outputs: Mapping[str, Sequence[str]],
    absences: Mapping[str, Absence],
    cached_source_ids: Sequence[str],
    family_counts: Mapping[str, int] | None = None,
    component_keys: Mapping[str, frozenset[str]] | None = None,
) -> Record:
    """Check independent inventories, then registry, receipt and output evidence.

    `inventory` comes from independent_inventory plus the joined tasks' slug
    contracts, never by projecting the current registry. `outputs` lists tables
    actually verified by assembly, not merely each row's declared tables.
    """
    record: Record = []

    def add(
        key: str, state: str, reason: str = "", *, caveat: str | None = None
    ) -> None:
        item = {"id": key, "state": state, "reason": reason}
        if caveat is not None:
            item["caveat"] = caveat
        record.append(item)

    def fail(key: str, reason: str) -> None:
        add(key, "failed", reason)

    forbidden = pack.forbidden | FORBIDDEN
    components = component_keys or {}
    ids = {row.source_id for row in entries}
    keys = {row.key for row in entries}
    for source in sorted(
        (set(pack.sources) | set(inventory)) - forbidden - REGISTER_IDS
    ):
        if source not in pack.sources:
            fail(source, "source_completeness: missing pack source")
        if source not in ids:
            fail(source, "source_completeness: missing registry source")
        rows = [
            row
            for row in entries
            if row.source_id == source and row.key not in components.get(source, ())
        ]
        slugs = inventory.get(source) or pack.sources.get(source, ())
        if slugs:
            if len(set(slugs)) != len(slugs) or len(
                set(pack.sources.get(source, ()))
            ) != len(pack.sources.get(source, ())):
                fail(source, "source_completeness: duplicate slug")
            if set(slugs) != set(pack.sources.get(source, ())):
                fail(source, "source_completeness: pack slugs")
            if sorted(row.slug for row in rows) != sorted(slugs):
                fail(source, "source_completeness: registry slugs")
        elif components.get(source):
            expected_components = set(components[source])
            actual_keys = {row.key for row in entries if row.source_id == source}
            # A closed component family can have a named parent or consist
            # wholly of independently inventoried leaf sources. Unknown,
            # jointly omitted and duplicated rows still fail below.
            if actual_keys not in (expected_components, expected_components | {source}):
                fail(source, "source_completeness: component keys")
            if expected_components - actual_keys or (
                rows and (len(rows) != 1 or rows[0].key != source)
            ):
                fail(source, "source_completeness: duplicate or missing row")
        elif len(rows) != 1:
            fail(source, "source_completeness: duplicate or missing row")
    if family_counts is not None:
        for source, count in family_counts.items():
            if (
                len(pack.sources.get(source, ())) != count
                or sum(row.source_id == source for row in entries) != count
            ):
                fail(source, "source_completeness: family count")
        if sum(len(pack.sources.get(source, ())) for source in family_counts) != 77:
            fail("PUB-85", "source_completeness: family total")
    for source in sorted(REGISTER_IDS):
        if source not in ids:
            add(source, "not yet read")
    for key, received in receipts.items():
        if key not in keys:
            fail(key, "source_receipt_missing: receipt without registry row")
        if received.get("source_id") in forbidden:
            fail(key, "source_completeness: forbidden receipt")
    for source in sorted(set(cached_source_ids) & forbidden):
        fail(source, "source_completeness: forbidden cached file")
    for row in entries:
        forbidden_row = row.source_id in forbidden
        if forbidden_row:
            fail(row.key, "source_completeness: forbidden row")
        elif row.source_id not in pack.sources and row.source_id not in REGISTER_IDS:
            fail(row.key, "source_completeness: extra registry source")
        if sum(other.key == row.key for other in entries) != 1:
            fail(row.key, "source_completeness: duplicate key")
        for table in row.release_tables:
            if table not in catalogue:
                fail(row.key, "source_table_uncatalogued: " + table)
        if forbidden_row:
            continue
        absence = absences.get(row.key)
        if row.kind == "register_file":
            if not register_in_use(row, receipts):
                fail(row.key, "source_receipt_missing: missing or invalid receipt")
            elif set(outputs.get(row.key, ())) != set(row.release_tables):
                fail(row.key, "source_completeness: output tables")
            else:
                add(row.key, "in use")
        elif absence is not None or row.skip_reason:
            # Reuse the registry's refusal markers, including for direct Entry
            # inputs; permission-based omissions are forbidden by D4 as well.
            if any(
                marker in reason.casefold()
                for reason in (row.skip_reason, absence.reason if absence else "")
                for marker in (_SKIP_LICENCE, _SKIP_TERMS, "permission")
            ):
                fail(row.key, "source_absence_terms_forbidden")
            elif (
                absence is None
                or not absence.reason.strip()
                or not absence.caveat.strip()
            ):
                fail(row.key, "source_absence_reason_missing")
            elif absence.caveat not in row.caveat_keys:
                fail(row.key, "source_absence_caveat_invalid")
            elif row.skip_reason and row.skip_reason != absence.reason:
                fail(row.key, "source_completeness: absence reason mismatch")
            else:
                add(row.key, "NO_DATA", absence.reason, caveat=absence.caveat)
            if outputs.get(row.key):
                fail(row.key, "source_completeness: output for absent source")
        elif not in_use(row, receipts):
            fail(row.key, "source_receipt_missing: missing or invalid receipt")
        elif set(outputs.get(row.key, ())) != set(row.release_tables):
            fail(row.key, "source_completeness: output tables")
        else:
            add(row.key, "in use")
    for key in (set(outputs) | set(absences)) - keys:
        fail(key, "source_completeness: evidence without registry row")
    return record


def committed_derived_check(
    files: Mapping[str, object], entries: Sequence[Entry]
) -> Record:
    """Inspect declared source IDs in committed objects and review CSV rows (B15)."""
    records: Record = []

    def visit(name: str, value: object) -> None:
        if isinstance(value, dict):
            if "source_id" in value:
                rows = [row for row in entries if row.source_id == value["source_id"]]
                if not rows or not all(
                    row.commit_allowed
                    and row.licence_basis == "dataset"
                    and row.licence_id.strip()
                    for row in rows
                ):
                    records.append(
                        {
                            "id": name,
                            "state": "failed",
                            "reason": "committed_source_value",
                        }
                    )
            for child in value.values():
                visit(name, child)
        elif isinstance(value, list):
            for child in value:
                visit(name, child)

    for name, value in files.items():
        if name.endswith(".csv") and isinstance(value, str):
            value = list(csv.DictReader(io.StringIO(value), strict=True))
        visit(name, value)
    return records
