"""S2-P58: regression records of section 10 figures PUB-71 and PUB-72.

Each figure is computed by ``eii_core.calc`` from its selected snapshots and
written to ``series/regression/<id>.json`` in the envelope ``build_series``
uses, with the receipts of those snapshots as its source chain. A figure whose
input is not selected is not written; it stays not measured. PUB-73 has no
producer: its count of open-places records with country QA needs a country
field that no places reader parses (PUB-17 keeps no country filter), so it
stays not measured and the gate stays pending.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eii_core.calc.facts import SourceChain
from eii_core.calc.public_methods import licence_density_pair, private_employer_share
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.frame.crosswalk import (
    municipality_key,
    municipality_keys,
    read_csv,
)
from eii_custodian.publicdata.frame.layers import layer_rows
from eii_custodian.publicdata.frame.mapping import POP_MAPPING
from eii_custodian.publicdata.frame.population import population_rows

from .figures import CHAIN_FIELDS, METHOD, VERSION, _write, validate_figure
from .parse import FIELD_MAP, confirmed_rows

SECTION10_REFUSED = "assembly_section10_input_invalid"
INPUTS = {"PUB-71": ("census_zone_sector",), "PUB-72": ("lic_active", "pop_muni")}
SOURCES = frozenset(source for sources in INPUTS.values() for source in sources)
# Section 10 rows: PUB-71 names zones 69 and 70 (census 2020); PUB-72 names
# Al Daayen, activity 5610101 and the 2025 residents.
ZONES = (69, 70)
TARGET = "Al Daayen"
ACTIVITY = "5610101"
SECTOR = {
    "ZONE_NO": ("pub_census_zone", "zone_code"),
    "Private": ("pub_census_zone", "private_employed"),
    "Total_Economic_active___15": ("pub_census_zone", "employed_residents"),
}
FIELD_MAPPING = {
    "census_zone_sector": SECTOR,
    "lic_active": FIELD_MAP["lic_active"],
    "pop_muni": POP_MAPPING,
}

Input = tuple[Entry, Any, Mapping[str, Any]]


def _chain(entry: Entry, receipt: Mapping[str, Any]) -> dict[str, str]:
    """Receipt fields; a layer source without a registry slug names its key."""
    return {
        **{key: receipt[key] for key in CHAIN_FIELDS if key != "slug"},
        "slug": entry.slug or entry.key,
    }


def _source(entry: Entry, receipt: Mapping[str, Any]) -> SourceChain:
    return SourceChain(
        entry.key,
        entry.release_tables[0],
        METHOD,
        VERSION,
        str(receipt["publisher"]),
        str(receipt["title_en"]),
        str(receipt["fetch_url"]),
        str(receipt["licence_id"]),
        str(receipt["retrieved_utc"])[:10],
        str(receipt["sha256"]),
    )


def pub71(sector: Input) -> dict[str, str]:
    entry, payload, receipt = sector
    zones = [
        (row["ZONE_NO"], row["Private"], row["Total_Economic_active___15"])
        for row in layer_rows(entry.source_id, payload)
    ]
    return private_employer_share(zones, _source(entry, receipt), "2020", ZONES)


def pub72(active: Input, population: Input, review: Path) -> dict[str, str]:
    names = read_csv(review / "municipality_names.csv")
    active_rows = confirmed_rows(active[0], active[1])
    keys = municipality_keys("lic_active", active_rows, ("lbldy",), names, None)
    residents, reason = population_rows(population[1], review, names, None)
    if reason.startswith("unreviewed_indicator"):
        raise ValueError("population_indicator_unreviewed")
    values = licence_density_pair(
        [
            (key, str(row["rmz_lnsht_ltjry"]), int(str(row["dd_lrkhs_lnsht"])))
            for row, key in zip(active_rows, keys, strict=True)
        ],
        [
            (str(row["municipality_code"]), row["value"])
            for row in residents
            if row["period"] == "2025" and row["indicator"] == "residents"
        ],
        target=municipality_key(TARGET, names),
        activity=ACTIVITY,
        period="2025",
        licence_source=_source(active[0], active[2]),
        resident_source=_source(population[0], population[2]),
    )
    return {
        "al_daayen_residents": values["local_residents"],
        "national_residents": values["national_residents"],
        "al_daayen_0dp": values["local_0dp"],
        "national_0dp": values["national_0dp"],
    }


def produce(cache: Path, review: Path, inputs: Mapping[str, Input]) -> tuple[str, ...]:
    """Write every figure whose inputs are all selected; return their ids.

    Every figure is computed and validated before any is written, so a refused
    input leaves no record of this producer behind.
    """
    envelopes = {}
    for figure, sources in INPUTS.items():
        if not set(sources) <= inputs.keys():
            continue
        selected = [inputs[source] for source in sources]
        values = (
            pub71(selected[0])
            if figure == "PUB-71"
            else pub72(selected[0], selected[1], review)
        )
        envelopes[figure] = {
            "method": METHOD,
            "method_version": VERSION,
            "source_chain": [_chain(entry, receipt) for entry, _, receipt in selected],
            "release_tables": sorted(
                {table for entry, _, _ in selected for table in entry.release_tables}
            ),
            "field_mapping": {source: FIELD_MAPPING[source] for source in sources},
            "values": values,
        }
        validate_figure(envelopes[figure])
    for figure, envelope in envelopes.items():
        _write(cache / "series" / "regression" / f"{figure}.json", envelope)
    return tuple(envelopes)
