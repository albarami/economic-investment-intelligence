"""S2-P58: regression records of section 10 figures PUB-71, PUB-72 and PUB-73.

Each figure is computed by ``eii_core.calc`` from its selected snapshots and
written to ``series/regression/<id>.json`` in the envelope ``build_series``
uses, with the receipts of those snapshots as its source chain. A figure whose
input is not selected is not written; it stays not measured. A chain's
``slug`` is the registry slug; a registry row without one names its registry
key, which resolves to title, address and hash through the registry and the
receipt. PUB-73 counts the places file's records whose ``bbox`` lies inside
the frame box (edges included) and that have an address with country ``QA``
(exact), on the shape the lead confirmed for release 2026-10-21.0, beside the
2020 establishment total of the frame's ``est_census`` reader.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from eii_core.calc.facts import SourceChain
from eii_core.calc.public_methods import (
    licence_density_pair,
    places_in_country,
    private_employer_share,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.frame.crosswalk import (
    municipality_key,
    municipality_keys,
    read_csv,
)
from eii_custodian.publicdata.frame.establishments import establishment_rows
from eii_custodian.publicdata.frame.layers import layer_rows
from eii_custodian.publicdata.frame.mapping import POP_MAPPING
from eii_custodian.publicdata.frame.population import population_rows
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.read import (
    _column_names,
    _connect,
    _require_schema,
)
from eii_custodian.publicdata.places_fsq.select import FRAME_BOX

from .figures import CHAIN_FIELDS, METHOD, VERSION, _write, validate_figure
from .parse import FIELD_MAP, confirmed_rows

SECTION10_REFUSED = "assembly_section10_input_invalid"
INPUTS = {
    "PUB-71": ("census_zone_sector",),
    "PUB-72": ("lic_active", "pop_muni"),
    "PUB-73": ("places_ovt", "est_census"),
}
SOURCES = frozenset(source for sources in INPUTS.values() for source in sources)
# Section 10 rows: PUB-71 names zones 69 and 70 (census 2020); PUB-72 names
# Al Daayen, activity 5610101 and the 2025 residents.
ZONES = (69, 70)
TARGET = "Al Daayen"
ACTIVITY = "5610101"
# PUB-73: the frame box (inclusive) and the address country, compared exactly.
BOX = (FRAME_BOX.west, FRAME_BOX.south, FRAME_BOX.east, FRAME_BOX.north)
COUNTRY = "QA"
BOUNDS = ("xmin", "xmax", "ymin", "ymax")
SECTOR = {
    "ZONE_NO": ("pub_census_zone", "zone_code"),
    "Private": ("pub_census_zone", "private_employed"),
    "Total_Economic_active___15": ("pub_census_zone", "employed_residents"),
}
FIELD_MAPPING = {
    "census_zone_sector": SECTOR,
    "lic_active": FIELD_MAP["lic_active"],
    "pop_muni": POP_MAPPING,
    "places_ovt": {
        "bbox": ("PUB-73", "places_qa"),
        "addresses": ("PUB-73", "places_qa"),
    },
    "est_census": {"census_2020": ("pub_census_national", "value")},
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


def _bounds(bbox: object) -> tuple[float, float, float, float]:
    if (
        not isinstance(bbox, dict)
        or sorted(bbox) != sorted(BOUNDS)
        or any(type(bbox[name]) is not float for name in BOUNDS)
    ):
        raise ValueError("places_bbox_invalid")
    return (bbox["xmin"], bbox["xmax"], bbox["ymin"], bbox["ymax"])


def _countries(addresses: object) -> list[str | None]:
    """Address countries; a null list or a null address has none."""
    if addresses is None:
        return []
    if not isinstance(addresses, list) or any(
        address is not None
        and (
            not isinstance(address, dict)
            or not isinstance(address.get("country", 0), str | None)
        )
        for address in addresses
    ):
        raise ValueError("places_addresses_invalid")
    return [address["country"] for address in addresses if address is not None]


def place_records(
    path: Path,
) -> Iterator[tuple[tuple[float, float, float, float], list[str | None]]]:
    """``bbox`` and address countries of each row of a receipt-proven file.

    The file's places schema version is admitted as every places reader admits it.
    """
    import duckdb

    connection = _connect()
    try:
        try:
            _require_schema(connection, path)
        except PlacesError:
            raise ValueError("places_schema_invalid") from None
        if not {"bbox", "addresses"} <= _column_names(connection, path):
            raise ValueError("places_column_missing")
        cursor = connection.execute(
            "SELECT bbox, addresses FROM read_parquet(?)", [str(path)]
        )
        while batch := cursor.fetchmany(2048):
            for bbox, addresses in batch:
                yield _bounds(bbox), _countries(addresses)
    except duckdb.Error:
        raise ValueError("places_parquet_invalid") from None
    finally:
        connection.close()


def pub73(places: Input, census: Input) -> dict[str, str]:
    """Places half from the places file; 2020 total from the frame's reader."""
    totals = establishment_rows(census[1])
    return {
        "places_qa": str(places_in_country(place_records(places[1]), BOX, COUNTRY)),
        "establishments_2020": str(
            next(row["value"] for row in totals if row["period"] == "2020")
        ),
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
        if figure == "PUB-71":
            values = pub71(selected[0])
        elif figure == "PUB-72":
            values = pub72(selected[0], selected[1], review)
        else:
            values = pub73(selected[0], selected[1])
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
