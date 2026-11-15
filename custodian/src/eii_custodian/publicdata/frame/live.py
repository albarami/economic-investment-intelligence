"""Raw-cache assembly; no network, inferred name match or geometry substitution."""

import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from eii_custodian.publicdata.fetch.registry import Entry

from .build import FrameResult, read_cached
from .census import census_rows, validate_tables
from .checks import FrameError
from .crosswalk import (
    check_municipality_names,
    check_zones,
    district_free_zones,
    greater_doha_keys,
    load_municipality_names,
    observed_zones,
    propose_reviews,
    read_csv,
)
from .gazetteer import administrative_rows, validate_frame_tables
from .geometry import Boundary, release_rows
from .grid import build_grid
from .joins import check_census_zones, join_districts, join_municipalities
from .layers import COUNTS, layer_rows
from .mapping import inspect_source
from .measures import zone_measures
from .population import population_rows
from .raw import read_archive


def build_live_frame(
    cache: Path,
    registry: tuple[Entry, ...],
    review: Path,
    output: Path | None,
    result: FrameResult,
) -> FrameResult:
    entries = {e.source_id: e for e in registry}
    tables, sources, inventory = result.tables, result.sources, result.inventory
    report = [
        r
        for r in result.report
        if not r.startswith(("frame:", "bnd_hdx: cache_shape_unconfirmed"))
    ]
    hdx = entries["bnd_hdx"]
    for table in ("municipality", "zone", "district", "gazetteer"):
        if hdx.licence_basis == "none_stated" or table not in hdx.release_tables:
            raise FrameError(f"bnd_hdx: invalid release source for {table}")
    body, receipt = read_cached(cache, hdx)
    sources["bnd_hdx"] = receipt
    frame = read_archive(body)
    raw_layers: dict[str, list[dict[str, Any]]] = {}
    for name in ("bnd_zone_2020", "bnd_district_2020", "census_district_pop"):
        if name not in entries or entries[name].skip_reason:
            if name == "census_district_pop":
                raw_layers[name] = []
                report.append(f"{name}: unavailable; no census rows")
                continue
            raise FrameError(f"{name}: required join source unavailable")
        payload, receipt = read_cached(cache, entries[name])
        sources[name] = receipt
        raw_layers[name] = layer_rows(name, payload)
    mapping, municipality_review = join_municipalities(
        frame["municipality"], frame["zone"], raw_layers["bnd_zone_2020"]
    )
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        with (output / "municipality_names.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "hdx_code",
                    "municipality_code",
                    "name_en",
                    "name_ar",
                    "layer_name_en",
                    "layer_name_ar",
                ],
            )
            writer.writeheader()
            writer.writerows(municipality_review)
    aliases = district_aliases(review, cache)
    district_map, differences = join_districts(
        frame["district"],
        raw_layers["bnd_district_2020"],
        raw_layers["census_district_pop"],
        aliases,
    )
    report.extend(differences)
    names = load_municipality_names(review, set(mapping.values()))
    check_municipality_names(municipality_review, names)
    doha = greater_doha_keys(review, set(mapping.values()))
    municipalities = [
        replace(m, key=mapping[m.key], municipality_code=mapping[m.key])
        for m in frame["municipality"]
    ]
    zones = [
        replace(z, municipality_code=mapping[z.municipality_code])
        for z in frame["zone"]
    ]
    districts = [
        replace(d, municipality_code=mapping[d.municipality_code])
        for d in frame["district"]
    ]
    inventory["bnd_hdx"] = {"zone_code": tuple(sorted(z.key for z in zones))}
    report = [line for line in report if "unlisted zone numbers" not in line]
    propose_reviews(review, output, {z.key for z in zones}, inventory, report)
    check_zones(
        read_csv(review / "zone_crosswalk.csv"),
        observed_zones(inventory),
        {z.key for z in zones},
    )
    report = [line for line in report if "unlisted zone numbers" not in line]
    staged_population: list[dict[str, Any]] = []
    if "pop_muni" in sources:
        payload, _ = read_cached(cache, entries["pop_muni"])
        staged_population, population_reason = population_rows(
            payload,
            review,
            names,
            output / "build_report.json" if output is not None else None,
        )
        if population_reason.startswith("unreviewed_indicator"):
            raise FrameError(f"pop_muni: {population_reason}")
    free_zones = district_free_zones(review)
    grid = build_grid(municipalities, zones, districts, doha, free_zones, report)
    tables["grid_cell"] = grid
    for kind, boundaries in (
        ("municipality", municipalities),
        ("zone", zones),
        ("district", districts),
    ):
        tables[kind] = licensed_rows(boundaries, kind)
    tables["gazetteer"] = administrative_rows(
        municipalities, zones, districts, grid, report
    )
    for filename in ("showcase_gazetteer.yaml", "flagship_candidates.yaml"):
        for spec in json.loads((review / filename).read_text(encoding="utf-8")):
            report.append(
                f"gazetteer: source point pending S2-T06: {spec['place_key']}"
            )
    staged = []
    for row in raw_layers["census_district_pop"]:
        pair = (row["ZONENO"], row["DISTRICTNO"])
        if pair in district_map and row["POP2020"] is not None:
            staged.append(
                {
                    "district_key": district_map[pair],
                    "period": "2020",
                    "indicator": "residents",
                    "value": row["POP2020"],
                    "unit": "persons",
                }
            )
    if "census_district_pop" in sources:
        entry = entries["census_district_pop"]
        tables["pub_census_district"], ignored = census_rows(
            entry,
            staged,
            sources[entry.source_id]["retrieved_utc"],
            "pub_census_district",
        )
        report.extend(ignored)
    zone_layers = {}
    for name in COUNTS:
        if name != "census_district_pop" and name in sources:
            payload, _ = read_cached(cache, entries[name])
            zone_layers[name] = layer_rows(name, payload)
    staged_zones, ignored = zone_measures(zone_layers, entries)
    report.extend(ignored)
    for name, rows in zone_layers.items():
        check_census_zones(name, rows, {z.key: z.municipality_code for z in zones})
    for name, rows in staged_zones.items():
        loaded, ignored = census_rows(
            entries[name], rows, sources[name]["retrieved_utc"], "pub_census_zone"
        )
        tables["pub_census_zone"].extend(loaded)
        report.extend(ignored)
    if "pop_muni" in sources:
        tables["pub_population_municipality"], ignored = census_rows(
            entries["pop_muni"],
            staged_population,
            sources["pop_muni"]["retrieved_utc"],
            "pub_population_municipality",
        )
        report.extend(ignored)
    if "est_census" in sources:
        payload, _ = read_cached(cache, entries["est_census"])
        tables["pub_census_national"], ignored = census_rows(
            entries["est_census"],
            inspect_source("est_census", payload).rows,
            sources["est_census"]["retrieved_utc"],
            "pub_census_national",
        )
        sources["est_census"]["method"] = (
            "frame.v1: sum count columns over source activity rows"
        )
        report.extend(ignored)
    validate_frame_tables(tables, free_zones)
    validate_tables(
        tables,
        {
            "municipality_code": {m.key for m in municipalities},
            "zone_code": {z.key for z in zones},
            "district_key": {d.key for d in districts},
        },
    )
    report.append("frame: partial; place points remain")
    return FrameResult(tables, report, sources, inventory)


def district_aliases(review: Path, cache: Path) -> list[dict[str, str]]:
    """Reviewed district aliases of the committed header plus the local file.

    `bnd_district_2020` has no open licence (decision 0026 item 5): reviewed
    alias rows live only in `cache/review/district_layer_aliases.csv` of the
    uncommitted cache; the committed file keeps its header and no data row.
    """
    rows = read_csv(review / "district_layer_aliases.csv")
    local = cache / "review" / "district_layer_aliases.csv"
    if local.is_file():
        rows += read_csv(local)
    return rows


def licensed_rows(boundaries: list[Boundary], kind: str) -> list[dict[str, object]]:
    """The licensed source supplies every geometry under L-202 R1."""
    if kind == "municipality":
        return [
            {
                "municipality_code": b.key,
                "name_en": b.name_en,
                "name_ar": b.name_ar,
                "geometry": b.geometry,
                "source_id": "bnd_hdx",
            }
            for b in boundaries
        ]
    return release_rows(boundaries, kind, "bnd_hdx")
