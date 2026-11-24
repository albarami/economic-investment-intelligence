"""Fixed application-schema readers for C36-C38 (MTH-109 to MTH-111).

Read only supplied, verified release projections. Geometry selection is here;
arithmetic is exclusively in eii_core.calc. There is no custodian import or IO.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from eii_core.calc.facts import NoData, SourceChain
from eii_core.calc.public_context import (
    NightLightsDisplay,
    PopulationCell,
    PopulationDisplay,
    RadianceCell,
    VenueBusynessDisplay,
    calc_night_lights,
    calc_population_age_sex,
    calc_venue_busyness,
)
from eii_core.facts import Fact, validate_chain
from eii_product.tools.area_outline import CircleOutline, PolygonOutline, covers
from eii_product.tools.areas import parse_area_id
from eii_product.tools.fact_builder import build_published

Row = Mapping[str, object]
_POP = frozenset(
    {"grid_key", "lon", "lat", "age_band", "sex", "people", "period", "source_id"}
)
_NIGHT = frozenset({"cell", "period", "radiance", "source_id"})
_BUSY = frozenset(
    {
        "place_id",
        "day_of_week",
        "hour",
        "busyness_index",
        "retrieved_on",
        "provider_updated_on",
        "source_id",
    }
)
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass(frozen=True)
class ContextBinding:
    """Selection identity beside the strict Fact, carried unchanged to the API."""

    fact: Fact
    metric_key: str
    qualifiers: Mapping[str, str]

    def wire(self) -> dict[str, object]:
        return {
            "fact": self.fact.model_dump(mode="json"),
            "metricKey": self.metric_key,
            "presentation": "ordinary",
            "qualifiers": dict(self.qualifiers),
        }


def _text(value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError("release text missing")
    return value


def _decimal(value: object) -> Decimal:
    if type(value) is Decimal:
        return value
    if type(value) is int:
        return Decimal(value)
    raise ValueError("release decimal missing")


def _date(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is date:
        return value.isoformat()
    if type(value) is str:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return None


def _schema(row: Row, keys: frozenset[str], source_id: str) -> None:
    if set(row) != keys or row["source_id"] != source_id:
        raise ValueError("Public context release schema mismatch")


def _build(
    result: NightLightsDisplay | PopulationDisplay | VenueBusynessDisplay | NoData,
    *,
    geography: Mapping[str, str],
    source: SourceChain,
    release_id: str,
    lineage_rows: Sequence[Row],
    source_rows: Sequence[Row],
    qualifiers: Mapping[str, str],
) -> Fact | NoData:
    if isinstance(result, NoData):
        return result
    if (
        validate_chain(
            source.lineage_ref,
            lineage_rows,
            source_rows,
            required_sources=result.sources,
            numerator_table=source.table,
        )
        is not None
    ):
        return NoData("missing_input")
    fact = build_published(
        value=result.value,
        unit=result.unit,
        metric_key=result.metric_key,
        period=result.period,
        geography=geography,
        release_id=release_id,
        lineage_ref=source.lineage_ref,
        lineage_rows=lineage_rows,
        source_rows=source_rows,
        qualifiers=qualifiers,
        caveat_keys=result.caveat_keys,
    )
    return NoData("missing_input") if fact is None else fact


def read_night_lights(
    rows: Sequence[Row],
    *,
    centres: Mapping[int, tuple[float, float]],
    area: CircleOutline | PolygonOutline,
    area_id: str,
    period: str,
    source: SourceChain,
    release_id: str,
    lineage_rows: Sequence[Row],
    source_rows: Sequence[Row],
) -> Fact | NoData:
    """Fixed pub_night_lights projection; frame centres, never overlap weights."""
    parse_area_id(area_id, release_id)
    selected = []
    for row in rows:
        _schema(row, _NIGHT, "ntl_blackmarble")
        if row["period"] != period:
            continue
        key = row["cell"]
        if type(key) is not int or key not in centres:
            raise ValueError("frame centre missing")
        if covers(area, *centres[key]):
            value = row["radiance"]
            selected.append(
                RadianceCell(str(key), None if value is None else _decimal(value))
            )
    result = calc_night_lights(selected, source, period)
    return _build(
        result,
        geography={"kind": "area_shape", "area_id": area_id},
        source=source,
        release_id=release_id,
        lineage_rows=lineage_rows,
        source_rows=source_rows,
        qualifiers={},
    )


def read_population_age_sex(
    rows: Sequence[Row],
    *,
    area: CircleOutline | PolygonOutline,
    area_id: str,
    period: str,
    source: SourceChain,
    release_id: str,
    lineage_rows: Sequence[Row],
    source_rows: Sequence[Row],
    sex: Literal["female", "male"] | None = None,
    age_band: str | None = None,
) -> ContextBinding | NoData:
    """Fixed native-grid read, boundary included; never resample or split cells."""
    parse_area_id(area_id, release_id)
    if sex not in {None, "female", "male"}:
        raise ValueError("source sex category required")
    selected = []
    for row in rows:
        _schema(row, _POP, "worldpop_qat_agesex")
        if (
            row["period"] != period
            or (sex is not None and row["sex"] != sex)
            or (age_band is not None and row["age_band"] != age_band)
        ):
            continue
        if covers(area, _decimal(row["lat"]), _decimal(row["lon"])):
            selected.append(
                PopulationCell(
                    _text(row["grid_key"]),
                    _text(row["age_band"]),
                    _text(row["sex"]),
                    _decimal(row["people"]),
                )
            )
    result = calc_population_age_sex(selected, source, period)
    qualifiers = {"sex": sex or "none", "age_band": age_band or "all"}
    fact = _build(
        result,
        geography={"kind": "area_shape", "area_id": area_id},
        source=source,
        release_id=release_id,
        lineage_rows=lineage_rows,
        source_rows=source_rows,
        qualifiers=qualifiers,
    )
    return (
        ContextBinding(fact, "population_grid_people", qualifiers)
        if isinstance(fact, Fact)
        else fact
    )


@dataclass(frozen=True)
class VenueLineage:
    """Row citation beside the fact; never substitute the registry receipt date."""

    lineage_ref: str
    source: SourceChain
    place_id: str
    day: str
    hour: int
    retrieved_on: str | None
    provider_updated_on: str | None


@dataclass(frozen=True)
class VenueContext:
    fact: Fact | NoData
    retrieved_on: str | None
    provider_updated_on: str | None
    day: str
    hour: int
    lineage: VenueLineage
    reason: str | None
    binding: ContextBinding | None


def read_venue_busyness(
    rows: Sequence[Row],
    *,
    place_id: str,
    day: str,
    hour: int,
    source: SourceChain,
    release_id: str,
    lineage_rows: Sequence[Row],
    source_rows: Sequence[Row],
    coverage_reasons: Mapping[str, str] | None = None,
) -> VenueContext:
    """One named venue/hour only, no borrowing, ordering, scoring or imputation."""
    if day not in DAYS or type(hour) is not int or not 0 <= hour <= 23:
        raise ValueError("venue time invalid")
    selected = []
    for row in rows:
        _schema(row, _BUSY, "busy_besttime")
        if (row["place_id"], row["day_of_week"], row["hour"]) == (place_id, day, hour):
            selected.append(row)
    if len(selected) > 1:
        raise ValueError("duplicate venue hour")
    chosen = selected[0] if selected else None
    retrieved = _date(chosen["retrieved_on"]) if chosen else None
    updated = _date(chosen["provider_updated_on"]) if chosen else None
    value = chosen["busyness_index"] if chosen else None
    result = calc_venue_busyness(
        None if value is None else _decimal(value), source, retrieved
    )
    qualifiers = {"day_of_week": day, "hour": str(hour)}
    fact = _build(
        result,
        geography={"kind": "public", "public_code": "place:" + place_id},
        source=source,
        release_id=release_id,
        lineage_rows=lineage_rows,
        source_rows=source_rows,
        qualifiers=qualifiers,
    )
    reason = None
    if isinstance(fact, NoData):
        reason = "missing_input"
        if not selected and coverage_reasons is not None:
            reason = coverage_reasons.get(place_id, "missing_input")
            if reason not in {
                "missing_input",
                "no_forecast",
                "not_found",
                "no_match",
                "credit_limit",
                "venue_address_absent",
            }:
                raise ValueError("unknown venue coverage reason")
    lineage = VenueLineage(
        source.lineage_ref, source, place_id, day, hour, retrieved, updated
    )
    binding = (
        ContextBinding(fact, "venue_busyness_index", qualifiers)
        if isinstance(fact, Fact)
        else None
    )
    return VenueContext(fact, retrieved, updated, day, hour, lineage, reason, binding)
