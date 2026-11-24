"""Closed card runners: named release reads, exact outlines, existing calculators."""

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from eii_core.calc.facts import NoData, SourceChain
from eii_core.facts import Fact, validate_chain
from eii_core.grid import cell_centre
from eii_product.api.results import PublicResult
from eii_product.store.protocol import Param, ReleaseStore
from eii_product.store.registry import PACKAGED
from eii_product.tools.area_outline import read_outline
from eii_product.tools.areas import parse_area_id
from eii_product.tools.make_area import MakeAreaContext, MakeAreaResult, decode_area
from eii_product.tools.public_context import (
    DAYS,
    read_night_lights,
    read_population_age_sex,
    read_venue_busyness,
)


class ClosedInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class NightInput(ClosedInput):
    area_id: str
    month_key: str = Field(pattern=r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$")


class PopulationInput(ClosedInput):
    area_id: str
    split: Literal["none", "sex"]


class VenueInput(ClosedInput):
    place_keys: list[str] = Field(min_length=1, max_length=10)
    weekday: (
        Literal[
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
        ]
        | None
    ) = None


# Public record keys may start with a digit; membership still comes from pub_place.
PLACE_KEY = re.compile(r"(?!(?:[0-9]{8}|[0-9]{11})\Z)[A-Za-z0-9][A-Za-z0-9-]*\Z")
CARD_MODELS: dict[str, type[ClosedInput]] = {
    "night_lights": NightInput,
    "population_age_sex": PopulationInput,
    "venue_busyness": VenueInput,
}


def read(store: ReleaseStore, name: str, **params: Param) -> list[dict[str, Any]]:
    result = store.fetch(PACKAGED.lookup(name), params)
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]


def chain(
    store: ReleaseStore, table: str
) -> tuple[SourceChain, list[dict[str, Any]], list[dict[str, Any]]]:
    lines = read(store, "public_lineage_for_table", table_name=table)
    refs = {r["lineage_id"] for r in lines}
    if len(refs) != 1:
        raise ValueError("missing_input")
    ref = next(iter(refs))
    sources = read(
        store,
        "sector_facts_sources",
        sources=list(dict.fromkeys(r["source_id"] for r in lines)),
    )
    if validate_chain(ref, lines, sources) is not None:
        raise ValueError("missing_input")
    line = next(r for r in lines if r["table_name"] == table)
    src = next(r for r in sources if r["source_id"] == line["source_id"])
    method, version = line["transform"].rsplit("@", 1)
    return (
        SourceChain(
            ref,
            table,
            method,
            version,
            src["publisher"],
            src["title"],
            src["url"],
            src["licence"],
            str(src["retrieved_on"]),
            src["sha256"],
        ),
        lines,
        sources,
    )


def run_card(
    store: ReleaseStore, tool: str, args: Mapping[str, Any], context: MakeAreaContext
) -> PublicResult | MakeAreaResult:
    if tool == "venue_busyness":
        return venue(store, args)
    parse_area_id(args["area_id"], store.release_id)
    decoded = decode_area(store, args["area_id"], context)
    if decoded.status != "OK":
        return PublicResult(
            tool, decoded.status, store.release_id, reason=decoded.reason
        )
    if decoded.payload is None:
        raise ValueError("missing_input")
    outline = read_outline(decoded.payload["outline"])
    table = "pub_night_lights" if tool == "night_lights" else "pub_pop_agesex_grid"
    source, lines, sources = chain(store, table)
    common = dict(
        area=outline,
        area_id=args["area_id"],
        source=source,
        release_id=store.release_id,
        lineage_rows=lines,
        source_rows=sources,
    )
    facts: list[Fact] = []
    entries: list[dict[str, object]] = []
    if tool == "night_lights":
        rows = read(store, "night_lights_cells", month_key=args["month_key"])
        centres = {
            r["cell"]: cell_centre(r["cell"])
            for r in read(store, "make_area_grid_cells")
        }
        fact = read_night_lights(
            rows, centres=centres, period=args["month_key"], **common
        )
        if isinstance(fact, Fact):
            facts.append(fact)
    else:
        rows = read(store, "population_age_sex_rows")
        bands = read(store, "population_age_sex_bands")
        for band in bands:
            sexes: tuple[Literal["female", "male"] | None, ...] = (
                ("female", "male") if args["split"] == "sex" else (None,)
            )
            for sex in sexes:
                bound = read_population_age_sex(
                    rows,
                    period=band["period"],
                    age_band=band["age_band"],
                    sex=sex,
                    **common,
                )
                if not isinstance(bound, NoData):
                    facts.append(bound.fact)
                    entries.append(
                        {
                            "fact_id": bound.fact.fact_id,
                            "age_band": band["age_band"],
                            "sex": sex or "none",
                        }
                    )
    return PublicResult(
        tool,
        "OK" if facts else "NO_DATA",
        store.release_id,
        payload={"entries": entries},
        facts=tuple(facts),
    )


def venue(store: ReleaseStore, args: Mapping[str, Any]) -> PublicResult:
    places = {r["place_id"] for r in read(store, "venue_busyness_places")}
    if any(key not in places for key in args["place_keys"]):
        return PublicResult(
            "venue_busyness", "OUT_OF_SCOPE", store.release_id, reason="unlisted_place"
        )
    rows = read(store, "venue_busyness_rows", place_keys=args["place_keys"])
    source, lines, sources = chain(store, "pub_venue_busyness")
    facts = []
    entries = []
    for place in dict.fromkeys(args["place_keys"]):
        for day in DAYS if args.get("weekday") is None else (args["weekday"],):
            for hour in range(24):
                result = read_venue_busyness(
                    rows,
                    place_id=place,
                    day=day,
                    hour=hour,
                    source=source,
                    release_id=store.release_id,
                    lineage_rows=lines,
                    source_rows=sources,
                )
                fact = result.fact
                entry = {
                    "place_key": place,
                    "weekday": day,
                    "hour": str(hour),
                    "status": "NO_DATA",
                    "reason_key": result.reason,
                    "retrieved_on": result.retrieved_on,
                    "provider_updated_on": result.provider_updated_on,
                }
                if isinstance(fact, Fact):
                    facts.append(fact)
                    entry.update(status="OK", fact_id=fact.fact_id)
                entries.append(entry)
    return PublicResult(
        "venue_busyness",
        "OK" if facts else "NO_DATA",
        store.release_id,
        payload={"entries": entries},
        facts=tuple(facts),
    )
