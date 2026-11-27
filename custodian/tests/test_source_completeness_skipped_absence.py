"""Tracked absence caveats for the sixteen skipped registry rows.

The invented row that has a skip reason and no caveat still fails
``source_absence_reason_missing`` in
``test_source_completeness_survivors.test_absence_exact_refusals_and_verbatim_reason``.
This file checks the real registry, document 03, document 04 and the
assembly source lists, with no cache, network or receipts.
"""

from pathlib import Path

from eii_custodian.publicdata import completeness as c
from eii_custodian.publicdata.assembly_sources import (
    CITATIONS,
    DECISION_0019,
    FAMILY_COUNTS,
    PACK_IDENTITIES,
    SOURCE_COMPONENTS,
)
from eii_custodian.publicdata.fetch.registry import load_registry

_ROOT = Path(__file__).resolve().parents[2]
_CAVEAT_HEADING = "| Caveat key | Carried by |"

# Registry key, recorded skip reason, catalogue caveat.
_ABSENT = (
    (
        "accident",
        "partition_byte_bound_unconfirmed",
        "accident_partition_bound_unconfirmed",
    ),
    ("places_fsq", "fetcher_owned_by_S2-T15", "places_fsq_fetcher_owned_by_s2_t15"),
    ("weather_openmeteo", "fetcher_owned_by_S2-T14", "weather_fetcher_owned_by_s2_t14"),
    (
        "bldg_ovt/part-00288",
        "not_required_part_decision_0090",
        "bldg_ovt_part_not_required",
    ),
    ("gis_boundaries", "schema_unconfirmed", "gis_schema_unconfirmed"),
    ("gis_imagery_history", "schema_unconfirmed", "gis_schema_unconfirmed"),
    (
        "insurance_tables",
        "acquisition_bound_unconfirmed",
        "acquisition_bound_unconfirmed",
    ),
    (
        "events_visit_qatar",
        "acquisition_bound_unconfirmed",
        "acquisition_bound_unconfirmed",
    ),
    ("events_qncc", "schema_evidence_pending", "qncc_schema_evidence_pending"),
    (
        "suppliers_tawteen",
        "anonymous_access_not_approved",
        "tawteen_anonymous_access_not_approved",
    ),
    (
        "manateq_tariffs",
        "acquisition_bound_unconfirmed",
        "acquisition_bound_unconfirmed",
    ),
    (
        "monaqasat_classified",
        "acquisition_bound_unconfirmed",
        "acquisition_bound_unconfirmed",
    ),
    (
        "schools_private_directory",
        "acquisition_bound_unconfirmed",
        "acquisition_bound_unconfirmed",
    ),
    (
        "satellite_cdse_backup",
        "provider_contract_pending",
        "cdse_provider_contract_pending",
    ),
    ("fc_register", "fc_activation_review_pending", "fc_activation_review_pending"),
    (
        "landmark_skyscraperpage_com/page-a4474c164d99fd530665e2e45c1419e2e7872e9ba8cefe248e372243c595d794",
        "page_not_served",
        "citation_page_not_served",
    ),
)


def catalogue_caveat_keys(text: str) -> frozenset[str]:
    """Read the caveat-key column of document 03's caveat table."""
    lines = text.splitlines()
    start = lines.index(_CAVEAT_HEADING)
    keys: list[str] = []
    for line in lines[start + 2 :]:
        if not line.startswith("| `"):
            break
        keys.append(line.split("`", maxsplit=2)[1])
    return frozenset(keys)


def tracked_absence_record() -> list[dict[str, str]]:
    """Run completeness on the tracked inputs the assembly report uses."""
    contracts = (_ROOT / "docs/03_DATA_CONTRACTS.md").read_text(encoding="utf-8")
    pack = c.pack_sources(
        (_ROOT / "docs/04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8"),
        FAMILY_COUNTS,
    )
    _, required = c.independent_inventory(FAMILY_COUNTS, DECISION_0019, CITATIONS)
    inventory = {
        **PACK_IDENTITIES,
        **{key: PACK_IDENTITIES.get(key, ()) for key in required},
    }
    entries = load_registry()
    absences = {
        row.key: c.Absence(row.skip_reason, row.caveat_keys[0])
        for row in entries
        if row.skip_reason and row.caveat_keys
    }
    return c.check(
        entries=entries,
        pack=pack,
        inventory=inventory,
        catalogue=c.table_catalogue(contracts),
        receipts={},
        outputs={},
        absences=absences,
        cached_source_ids=(),
        family_counts=FAMILY_COUNTS,
        component_keys=SOURCE_COMPONENTS,
    )


def test_sixteen_skipped_registry_rows_carry_a_catalogue_absence() -> None:
    """Each skipped row names one catalogue caveat and is not missing its absence."""
    contracts = (_ROOT / "docs/03_DATA_CONTRACTS.md").read_text(encoding="utf-8")
    catalogue = catalogue_caveat_keys(contracts)
    rows = {row.key: row for row in load_registry()}
    for key, reason, caveat in _ABSENT:
        row = rows[key]
        assert row.skip_reason == reason
        assert row.caveat_keys == (caveat,)
        assert caveat in catalogue
    record = tracked_absence_record()
    missing = [
        item["id"]
        for item in record
        if item["id"] in {key for key, _, _ in _ABSENT}
        and item["reason"] == "source_absence_reason_missing"
    ]
    assert missing == []
    for key, reason, caveat in _ABSENT:
        assert {
            "id": key,
            "state": "NO_DATA",
            "reason": reason,
            "caveat": caveat,
        } in record
