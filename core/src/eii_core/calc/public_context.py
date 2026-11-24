"""C36-C38 arithmetic over whole rows selected by fixed application readers.

Display results deliberately do not inherit CalculationFact or Measure: they
cannot be supplied to comparisons, ranking criteria, features or weighting.
This module reads no file, geometry, store, cache or provider.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction
from typing import ClassVar

from .facts import NoData, SourceChain
from .public_series import rounded


@dataclass(frozen=True)
class RadianceCell:
    cell: str
    radiance: Decimal | None


@dataclass(frozen=True)
class PopulationCell:
    grid_key: str
    age_band: str
    sex: str
    people: Decimal


@dataclass(frozen=True)
class _Display:
    value: Decimal
    sources: tuple[SourceChain, ...]
    period: str
    provenance: ClassVar[str] = "public"
    evidence_status: ClassVar[str] = "observed"


@dataclass(frozen=True)
class NightLightsDisplay(_Display):
    metric_key: ClassVar[str] = "night_lights_radiance"
    unit: ClassVar[str] = "radiance_nw_cm2_sr"
    caveat_keys: ClassVar[tuple[str, ...]] = ("calculated", "night_lights_not_activity")


@dataclass(frozen=True)
class PopulationDisplay(_Display):
    """Display-only C38 value, outside every arithmetic input union."""

    metric_key: ClassVar[str] = "population_grid_people"
    unit: ClassVar[str] = "count"
    caveat_keys: ClassVar[tuple[str, ...]] = ("calculated", "grid_cells_summed")


@dataclass(frozen=True)
class VenueBusynessDisplay(_Display):
    retrieved_on: str
    metric_key: ClassVar[str] = "venue_busyness_index"
    unit: ClassVar[str] = "relative_index"
    subject: ClassVar[str] = "place_public"
    caveat_keys: ClassVar[tuple[str, ...]] = ("relative_busyness_not_people",)


def _source(source: SourceChain, table: str) -> None:
    source.__post_init__()
    if source.table != table:
        raise ValueError("source table mismatch")


def _number(value: Decimal) -> Fraction:
    if type(value) is not Decimal or not value.is_finite() or value < 0:
        raise ValueError("invalid Public context value")
    return Fraction(value)


def calc_night_lights(
    selected_rows: Sequence[RadianceCell], source: SourceChain, period: str
) -> NightLightsDisplay | NoData:
    """MTH-109: mean of kept frame-cell values, once per centre-selected cell."""
    _source(source, "pub_night_lights")
    if any(type(row) is not RadianceCell for row in selected_rows):
        raise TypeError("RadianceCell required")
    if len({row.cell for row in selected_rows}) != len(selected_rows):
        raise ValueError("duplicate radiance cell")
    values = [
        _number(row.radiance) for row in selected_rows if row.radiance is not None
    ]
    if not values:
        return NoData("missing_input")
    # Fraction arithmetic is independent of ambient Decimal precision.
    mean = sum(values, Fraction()) / len(values)
    return NightLightsDisplay(Decimal(rounded(mean, 4)), (source,), period)


def calc_population_age_sex(
    selected_rows: Sequence[PopulationCell], source: SourceChain, period: str
) -> PopulationDisplay | NoData:
    """MTH-111: whole cells only, no overlap argument, round the sum once."""
    _source(source, "pub_pop_agesex_grid")
    if any(type(row) is not PopulationCell for row in selected_rows):
        raise TypeError("PopulationCell required")
    keys = [(row.grid_key, row.age_band, row.sex) for row in selected_rows]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate population cell category")
    if not selected_rows:
        return NoData("missing_input")
    if any(
        row.sex not in {"female", "male"} or not row.age_band for row in selected_rows
    ):
        raise ValueError("population category missing")
    total = sum((_number(row.people) for row in selected_rows), Fraction())
    return PopulationDisplay(Decimal(rounded(total, 0)), (source,), period)


def calc_venue_busyness(
    index: Decimal | None, source: SourceChain, retrieved_on: str | None
) -> VenueBusynessDisplay | NoData:
    """MTH-110 fixed read: unchanged index and per-row retrieval, no imputation."""
    _source(source, "pub_venue_busyness")
    if index is None or not retrieved_on:
        return NoData("missing_input")
    date.fromisoformat(retrieved_on)
    if _number(index) > 100:
        raise ValueError("relative index outside published scale")
    return VenueBusynessDisplay(index, (source,), retrieved_on, retrieved_on)
