"""Public places inside the exact outline; release reads only (BE-49)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Self, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from eii_core.calc import scan_places as calc
from eii_core.calc.facts import SourceChain
from eii_core.facts import Fact, fact_id, validate_chain
from eii_core.shapes import (
    Point,
    canonical_ring,
    exact_point,
    point_in_ring,
    representative_point,
    within_radius,
)
from eii_product.store.protocol import Param, ReleaseStore
from eii_product.store.registry import Inventory
from eii_product.tools.make_area import MakeAreaContext, decode_area
from eii_product.tools.routing import network_distance

CAVEAT = "open_listings_incomplete"
PLACE_QUERIES = tuple(
    "scan_places_" + name
    for name in (
        "places",
        "fsq",
        "verification",
        "visits",
        "categories",
        "lineage",
        "sources",
    )
)
QUERY_NAMES = (*PLACE_QUERIES, "make_area_grid_cells", "make_area_municipalities")
Route = Callable[[str, str, Point, Point], tuple[object, str]]


@dataclass(frozen=True)
class RoutingBinding:
    """Release-owned graph identity and sources, using the area's tile configuration."""

    graph: str
    area: MakeAreaContext
    sources: tuple[SourceChain, ...]


@dataclass(frozen=True)
class ScanPlacesContext:
    inventory: Inventory
    area: MakeAreaContext
    period: str
    graph: str
    mapping: Mapping[str, str] | None
    route: Route | None
    chains: Mapping[str, tuple[SourceChain, ...]]
    routing_binding: RoutingBinding | None = None


class Closed(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Request(Closed):
    area_id: str
    categories: list[str]
    limit: int = 50
    include_neighbours: bool = False

    @field_validator("limit")
    @classmethod
    def limit_valid(cls, value: int) -> int:
        return calc.validate_limit(value)

    @field_validator("categories")
    @classmethod
    def categories_valid(cls, value: list[str]) -> list[str]:
        if not value or any(not key.startswith("place_category:") for key in value):
            raise ValueError("categories_invalid")
        return value


class Slot(Closed):
    status: Literal["OK", "NO_DATA"]
    fact_id: str | None = None

    @model_validator(mode="after")
    def binding(self) -> Self:
        if (self.status == "OK") != (self.fact_id is not None):
            raise ValueError("slot_invalid")
        return self


class Place(Closed):
    place_id: str
    source_table: Literal["pub_place", "pub_place_fsq"]
    category: str
    source_provider: str | Slot | None
    licence: str | Slot
    source_attribution: str | Slot | None
    name: str | None
    name_ar: str | None
    name_fact: Slot
    name_ar_fact: Slot
    name_unshowable: bool
    name_ar_unshowable: bool
    distance: Slot
    confidence: Slot
    source_release: Slot
    check_date: Slot
    verification_status: Literal["verified_open", "duplicate"] | None = None

    @field_validator("source_provider", "licence", "source_attribution")
    @classmethod
    def provider_label(cls, value: str | Slot | None) -> str | Slot | None:
        if isinstance(value, str) and any(c.isdigit() for c in value):
            raise ValueError("label_digit")
        return value

    @field_validator("name", "name_ar")
    @classmethod
    def labels(cls, value: str | None) -> str | None:
        if value is not None and any(c.isdigit() for c in value):
            raise ValueError("label_digit")
        return value

    @model_validator(mode="after")
    def distance_required(self) -> Self:
        if self.source_table == "pub_place_fsq" and self.source_provider is not None:
            raise ValueError("provider_unavailable")
        if self.source_table == "pub_place" and self.source_attribution is not None:
            raise ValueError("attribution_unavailable")
        if self.distance.status != "OK":
            raise ValueError("distance_required")
        return self


class Visit(Closed):
    place_id: str
    indicator: Literal["visitors", "patient_visits"]
    value: Slot


class CircleOutline(Closed):
    type: Literal["Circle"]
    coordinates: list[Decimal]
    radius_m: int


class PolygonOutline(Closed):
    type: Literal["Polygon"]
    coordinates: list[list[list[Decimal]]]


class Payload(Closed):
    outline: CircleOutline | PolygonOutline | None = None
    places: list[Place] = []
    places_fsq: list[Place] = []
    place_visits: list[Visit] = []
    found_near: None = Field(default=None, exclude=True)


class Blocks(Closed):
    places: Literal["OK", "NO_DATA"] = "NO_DATA"
    places_fsq: Literal["OK", "NO_DATA"] = "NO_DATA"
    places_fsq_reason: Literal["mapping_missing"] | None = None
    place_visits: Literal["OK", "NO_DATA"] = "NO_DATA"
    found_near: None = Field(default=None, exclude=True)
    found_near_reason: Literal["neighbours_geography_unreleased"] | None = None


class ScanPlacesResult(Closed):
    tool: Literal["scan_places"] = "scan_places"
    call_id: str
    release_id: str
    engine: Literal["embedded", "postgres"]
    status: Literal["OK", "NO_DATA", "OUT_OF_SCOPE", "INVALID_ARGUMENT", "INTERNAL"]
    blocks: Blocks
    facts: list[Fact]
    payload: Payload
    caveat_keys: list[Literal["open_listings_incomplete"]]

    @model_validator(mode="after")
    def public_boundary(self) -> Self:
        if self.caveat_keys != [CAVEAT]:
            raise ValueError("incompleteness_required")
        by_id = {fact.fact_id: fact for fact in self.facts}
        references = set()
        for fact in self.facts:
            if (
                fact.provenance != "public"
                or fact.input_classes != ["public"]
                or CAVEAT not in fact.caveat_keys
            ):
                raise ValueError("public_fact_required")
        for place in (*self.payload.places, *self.payload.places_fsq):
            for slot in (
                place.distance,
                place.confidence,
                place.source_release,
                place.check_date,
                place.name_fact,
                place.name_ar_fact,
                place.source_provider
                if isinstance(place.source_provider, Slot)
                else Slot(status="NO_DATA"),
                place.licence
                if isinstance(place.licence, Slot)
                else Slot(status="NO_DATA"),
                place.source_attribution
                if isinstance(place.source_attribution, Slot)
                else Slot(status="NO_DATA"),
            ):
                if slot.fact_id is not None and slot.fact_id not in by_id:
                    raise ValueError("fact_reference_missing")
                if slot.fact_id is not None:
                    references.add(slot.fact_id)
            if by_id[cast(str, place.distance.fact_id)].unit != "metres":
                raise ValueError("distance_unit_invalid")
        place_ids = {place.place_id for place in self.payload.places}
        for visit in self.payload.place_visits:
            if visit.place_id not in place_ids:
                raise ValueError("visit_place_missing")
            if visit.value.fact_id is not None:
                visit_fact = by_id.get(visit.value.fact_id)
                if visit_fact is None or visit_fact.unit != "count":
                    raise ValueError("visit_fact_invalid")
                references.add(visit.value.fact_id)
        if set(by_id) != references:
            raise ValueError("unreferenced_fact")
        return self


def _read(
    store: ReleaseStore,
    context: ScanPlacesContext,
    name: str,
    params: Mapping[str, Param],
) -> list[dict[str, Any]]:
    result = store.fetch(context.inventory.lookup("scan_places_" + name), params)
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]


class _Facts:
    def __init__(self, store: ReleaseStore, context: ScanPlacesContext) -> None:
        self.context = context
        self.lines = _read(store, context, "lineage", {})
        self.sources = _read(store, context, "sources", {})
        self.facts: list[Fact] = []

    def chain(self, table: str, lineage: str) -> list[dict[str, Any]] | None:
        """Resolve this table's validated registry rows, never a global source row."""
        expected = self.context.chains.get(lineage)
        if (
            not expected
            or validate_chain(
                lineage,
                self.lines,
                self.sources,
                required_sources=expected,
                numerator_table=table,
            )
            is not None
        ):
            return None
        if any(
            source.table != table or source.lineage_ref != lineage
            for source in expected
        ):
            return None
        released_methods = {
            line["transform"] for line in self.lines if line["lineage_id"] == lineage
        }
        expected_methods = {source.method + "@" + source.version for source in expected}
        if released_methods != expected_methods:
            return None
        source_ids = {
            line["source_id"] for line in self.lines if line["lineage_id"] == lineage
        }
        return [source for source in self.sources if source["source_id"] in source_ids]

    def text(
        self, value: object, metric: str, table: str, row: Mapping[str, Any]
    ) -> str | Slot:
        if self.chain(table, "lin_" + table) is None or not isinstance(value, str):
            return Slot(status="NO_DATA")
        if not value.strip():
            return Slot(status="NO_DATA")
        if not any(c.isdigit() for c in value):
            return value
        return self.add(
            value,
            "published_text",
            metric,
            table,
            row["place_id"],
            row["source_release"],
        )

    def attribution(self, table: str, row: Mapping[str, Any]) -> str | Slot:
        sources = self.chain(table, "lin_" + table)
        if sources is None:
            return Slot(status="NO_DATA")
        try:
            (value,) = {source.get("attribution") for source in sources}
        except ValueError:
            return Slot(status="NO_DATA")
        return self.text(value, "place_source_attribution", table, row)

    def add(
        self,
        value: object,
        unit: str,
        metric: str,
        table: str,
        place: str,
        period: str,
        qualifiers: Mapping[str, str] | None = None,
        *,
        lineage: str | None = None,
        caveats: tuple[str, ...] = (),
    ) -> Slot:
        lineage = lineage or "lin_" + table
        if self.chain(table, lineage) is None:
            return Slot(status="NO_DATA")
        geo = {"kind": "public", "public_code": "place:" + place}
        try:
            if unit in {"metres", "ratio", "count"}:
                value = calc.canonical_number(value)
            fact = Fact.model_validate(
                dict(
                    fact_id=fact_id(
                        release_id=self.context.area.release_id,
                        metric_key=metric,
                        geography=geo,
                        period=period,
                        qualifiers={"source_table": table, **(qualifiers or {})},
                    ),
                    value=value,
                    unit=unit,
                    period=period,
                    geography=geo,
                    provenance="public",
                    input_classes=["public"],
                    evidence_status="observed",
                    reliability="not_applicable",
                    coverage_keys=[],
                    caveat_keys=[CAVEAT, *caveats],
                    label_en="Public place fact",
                    label_ar="معلومة مكان عامة",
                    lineage_ref=lineage,
                    release_id=self.context.area.release_id,
                )
            )
        except ValueError:
            return Slot(status="NO_DATA")
        self.facts.append(fact)
        return Slot(status="OK", fact_id=fact.fact_id)


def _name(
    value: Any, language: str, row: Mapping[str, Any], table: str, facts: _Facts
) -> tuple[str | None, Slot, bool]:
    missing = Slot(status="NO_DATA")
    if value is None:
        return None, missing, False
    if type(value) is not str:
        return None, missing, True
    if not any(c.isdigit() for c in value):
        return value, missing, False
    slot = facts.add(
        value,
        "published_text",
        "place_name",
        table,
        row["place_id"],
        row["source_release"],
        {"language": language},
    )
    return None, slot, slot.status != "OK"


def _origin(payload: Mapping[str, Any]) -> tuple[Point, str]:
    record = payload["record"]
    if record["shape"] == "polygon":
        ring = canonical_ring(
            [(p[1], p[0]) for p in payload["outline"]["coordinates"][0]]
        )
        return representative_point(ring), "walk"
    point = record["request"]["point"]
    return exact_point(
        Decimal(point["latitude"]), Decimal(point["longitude"])
    ), "drive" if record["shape"] == "drive" else "walk"


def _inside(row: Mapping[str, Any], payload: Mapping[str, Any], origin: Point) -> bool:
    point = exact_point(row["lat"], row["lon"])
    record = payload["record"]
    if record["shape"] == "radius":
        return within_radius(
            (float(origin[0]), float(origin[1])),
            (float(point[0]), float(point[1])),
            record["request"]["radius_m"],
        )
    ring = canonical_ring([(p[1], p[0]) for p in payload["outline"]["coordinates"][0]])
    return point_in_ring(point, ring)


def _distance(
    row: Mapping[str, Any],
    table: str,
    origin: Point,
    mode: str,
    context: ScanPlacesContext,
    facts: _Facts,
) -> tuple[Slot, Decimal | None]:
    binding = context.routing_binding
    lineage = "lin_road_link_scan_places_distance"
    if (
        binding is None
        or context.graph != binding.graph
        or context.area.release_id != binding.area.release_id
        or context.area.tile_folder != binding.area.tile_folder
        or not binding.sources
        or context.chains.get(lineage) != binding.sources
    ):
        return Slot(status="NO_DATA"), None
    destination = exact_point(row["lat"], row["lon"])
    if context.route is not None:
        raw, unit = context.route(binding.graph, mode, origin, destination)
    else:
        if binding.area.tile_folder is None:
            return Slot(status="NO_DATA"), None
        raw, unit = network_distance(
            binding.area.tile_folder,
            mode,
            (float(origin[0]), float(origin[1])),
            (float(destination[0]), float(destination[1])),
        )
    distance = calc.route_metres(raw, unit)
    if distance is None:
        return Slot(status="NO_DATA"), None
    lineage = "lin_road_link_scan_places_distance"
    if not any(
        line["lineage_id"] == lineage and line["source_id"] == "roads_osm"
        for line in facts.lines
    ):
        return Slot(status="NO_DATA"), None
    slot = facts.add(
        distance,
        "metres",
        "place_distance_metres",
        "road_link",
        row["place_id"],
        context.period,
        {
            "source_table": table,
            "origin": str(origin[0]) + "," + str(origin[1]),
            "routing_method": mode,
            "routing_graph": binding.graph,
        },
        lineage=lineage,
    )
    return slot, distance


def _places(
    rows: list[dict[str, Any]],
    table: str,
    checks: list[dict[str, Any]],
    payload: Mapping[str, Any],
    request: Request,
    context: ScanPlacesContext,
    facts: _Facts,
) -> list[Place]:
    origin, mode = _origin(payload)
    candidates = []
    for row in rows:
        if not _inside(row, payload, origin):
            continue
        check = (
            calc.latest_verification(
                [c for c in checks if c["place_id"] == row["place_id"]]
            )
            if table == "pub_place"
            else None
        )
        if check is not None:
            if check["status"] in {"closed_or_moved", "not_found"}:
                continue
            if check["status"] not in {"verified_open", "duplicate"}:
                raise ValueError("verification_invalid")
        elif table == "pub_place" and not calc.confidence_passes(row["confidence"]):
            continue
        slot, distance = _distance(row, table, origin, mode, context, facts)
        if slot.status != "OK":
            continue
        candidates.append(dict(row, distance=distance, distance_slot=slot, check=check))
    result = []
    for row in calc.order_places(candidates, request.limit):
        name, name_fact, hidden = _name(row["name"], "en", row, table, facts)
        name_ar, name_ar_fact, hidden_ar = _name(
            row["name_ar"], "ar", row, table, facts
        )
        provider: str | Slot | None = None
        if table == "pub_place":
            value = row["source_provider"]
            if any(c.isdigit() for c in value):
                provider = facts.add(
                    value,
                    "published_text",
                    "place_name",
                    table,
                    row["place_id"],
                    row["source_release"],
                    {"category": "source_provider"},
                )
            else:
                provider = value
        confidence = Slot(status="NO_DATA")
        if table == "pub_place":
            confidence = facts.add(
                row["confidence"],
                "ratio",
                "place_confidence",
                table,
                row["place_id"],
                row["source_release"],
            )
        check_date = Slot(status="NO_DATA")
        if row["check"] is not None:
            check = row["check"]
            check_date = facts.add(
                check["check_date"].isoformat(),
                "calendar_date",
                "place_check_date",
                "pub_place_verification",
                row["place_id"],
                check["check_date"].isoformat(),
            )
        release_unit = "calendar_date" if table == "pub_place_fsq" else "published_text"
        released = facts.add(
            row["source_release"],
            release_unit,
            "place_source_release",
            table,
            row["place_id"],
            row["source_release"],
        )
        result.append(
            Place(
                place_id=row["place_id"],
                source_table=cast(Literal["pub_place", "pub_place_fsq"], table),
                category=row["category"],
                source_provider=provider,
                licence=facts.text(row["licence"], "place_licence", table, row),
                source_attribution=facts.attribution(table, row)
                if table == "pub_place_fsq"
                else None,
                name=name,
                name_ar=name_ar,
                name_fact=name_fact,
                name_ar_fact=name_ar_fact,
                name_unshowable=hidden,
                name_ar_unshowable=hidden_ar,
                distance=row["distance_slot"],
                confidence=confidence,
                source_release=released,
                check_date=check_date,
                verification_status=None
                if row["check"] is None
                else row["check"]["status"],
            )
        )
    return result


def _result(
    store: ReleaseStore,
    status: str,
    payload: Payload | None = None,
    facts: list[Fact] | None = None,
    *,
    mapping_missing: bool = False,
    neighbours_requested: bool = False,
) -> ScanPlacesResult:
    payload = payload or Payload()
    references: set[str | None] = set()
    for place in (*payload.places, *payload.places_fsq):
        references.update(
            slot.fact_id
            for slot in (
                place.distance,
                place.confidence,
                place.source_release,
                place.check_date,
                place.name_fact,
                place.name_ar_fact,
                place.source_provider
                if isinstance(place.source_provider, Slot)
                else Slot(status="NO_DATA"),
                place.licence
                if isinstance(place.licence, Slot)
                else Slot(status="NO_DATA"),
                place.source_attribution
                if isinstance(place.source_attribution, Slot)
                else Slot(status="NO_DATA"),
            )
        )
    references.update(visit.value.fact_id for visit in payload.place_visits)
    blocks = Blocks(
        places="OK" if payload.places else "NO_DATA",
        places_fsq="OK" if payload.places_fsq else "NO_DATA",
        places_fsq_reason="mapping_missing" if mapping_missing else None,
        place_visits="OK" if payload.place_visits else "NO_DATA",
        found_near_reason="neighbours_geography_unreleased"
        if neighbours_requested
        else None,
    )
    return ScanPlacesResult.model_validate(
        dict(
            call_id=str(uuid4()),
            release_id=store.release_id,
            engine=store.engine,
            status=status,
            blocks=blocks,
            facts=[fact for fact in (facts or []) if fact.fact_id in references],
            payload=payload,
            caveat_keys=[CAVEAT],
        )
    )


def scan_places(
    store: ReleaseStore, inputs: Mapping[str, object], context: ScanPlacesContext
) -> ScanPlacesResult:
    """Validate before reads; retain closed refusals and no engine error text."""
    try:
        request = Request.model_validate(dict(inputs))
    except ValueError:
        return _result(store, "INVALID_ARGUMENT")
    try:
        if store.release_id != context.area.release_id:
            return _result(
                store,
                "INVALID_ARGUMENT",
                neighbours_requested=request.include_neighbours,
            )
        area = decode_area(store, request.area_id, context.area)
        if area.status != "OK" or area.payload is None:
            status = (
                area.status
                if area.status in {"OUT_OF_SCOPE", "NO_DATA", "INVALID_ARGUMENT"}
                else "INTERNAL"
            )
            return _result(
                store, status, neighbours_requested=request.include_neighbours
            )
        categories = _read(
            store, context, "categories", {"categories": request.categories}
        )
        nodes = {
            row["node_id"]: row
            for row in categories
            if row["provenance"] == "public" and row["node_type"] == "place_category"
        }
        if any(key not in nodes for key in request.categories):
            return _result(
                store, "OUT_OF_SCOPE", neighbours_requested=request.include_neighbours
            )
        facts = _Facts(store, context)
        rows = _read(
            store,
            context,
            "places",
            {"categories": [nodes[key]["code"] for key in request.categories]},
        )
        checks = _read(
            store,
            context,
            "verification",
            {"places": [row["place_id"] for row in rows]},
        )
        places = _places(
            rows, "pub_place", checks, area.payload, request, context, facts
        )
        fsq_rows = _read(store, context, "fsq", {})
        mapped = []
        if context.mapping is not None:
            for row in fsq_rows:
                matches = [
                    context.mapping[key]
                    for key in row["category_ids"].split(";")
                    if key in context.mapping
                    and context.mapping[key] in request.categories
                ]
                if matches:
                    mapped.append(
                        dict(row, place_id=row["fsq_place_id"], category=matches[0])
                    )
        fsq = _places(
            mapped, "pub_place_fsq", [], area.payload, request, context, facts
        )
        visits = []
        for row in _read(
            store, context, "visits", {"places": [place.place_id for place in places]}
        ):
            if (
                row["place_id"] not in {place.place_id for place in places}
                or row["unit"] != "visits"
            ):
                continue
            slot = facts.add(
                row["value"],
                "count",
                "venue_visits",
                "pub_venue_visits",
                row["place_id"],
                row["period"],
                {"indicator": row["indicator"]},
            )
            visits.append(
                Visit(place_id=row["place_id"], indicator=row["indicator"], value=slot)
            )
        payload = Payload.model_validate(
            dict(
                outline=area.payload["outline"],
                places=places,
                places_fsq=fsq,
                place_visits=visits,
            )
        )
        return _result(
            store,
            "OK" if places or fsq else "NO_DATA",
            payload,
            facts.facts,
            mapping_missing=context.mapping is None,
            neighbours_requested=request.include_neighbours,
        )
    except Exception:
        return _result(
            store, "INTERNAL", neighbours_requested=request.include_neighbours
        )
