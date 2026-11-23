"""Pure Public card arithmetic; source approval and row selection are external.
Wilson uses exact rational radicands and exact roots when both parts are squares.
Other roots use CALC_CONTEXT; approximate outputs refuse rounding/comparison
within 1e-40 of a boundary through public_series.rounded/compare.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from math import isqrt
from typing import Literal

from .facts import (
    CalculationFact,
    Measure,
    MeasureMismatch,
    NoData,
    SourceLink,
    emit,
    require_aligned,
)
from .public_series import (
    CALC_CONTEXT,
    Approximate,
    Number,
    bulk_months,
    count,
    decimal_value,
    divide,
    finite,
    ratio,
    rounded,
    unit_value,
)

CARD_BASELINE_KWH = Decimal(1000000)


def wilson(k: int, n: int) -> tuple[Number, Number]:
    """MTH-12 descriptive interval, unrounded; not a survey interval."""
    count(k)
    count(n)
    if n == 0 or k > n:
        raise ValueError("invalid binomial counts")
    p, size, z = Fraction(k, n), Fraction(n), Fraction(49, 25)
    denominator = 1 + z * z / size
    centre = (p + z * z / (2 * size)) / denominator
    radicand = p * (1 - p) / size + z * z / (4 * size * size)
    numerator_root, denominator_root = (
        isqrt(radicand.numerator),
        isqrt(radicand.denominator),
    )
    if (
        numerator_root**2 == radicand.numerator
        and denominator_root**2 == radicand.denominator
    ):
        half = z * Fraction(numerator_root, denominator_root) / denominator
        return centre - half, centre + half
    with localcontext(CALC_CONTEXT):
        half_decimal = decimal_value(z / denominator) * decimal_value(radicand).sqrt()
        midpoint = decimal_value(centre)
        return Approximate(midpoint - half_decimal), Approximate(
            midpoint + half_decimal
        )


def reliability(n: int | None) -> Literal["not_applicable", "low_count", "standard"]:
    if n is None:
        return "not_applicable"
    count(n)
    return "low_count" if n < 30 else "standard"


def _whole(measure: Measure, unit: str) -> int:
    if not isinstance(measure, Measure) or measure.unit != unit:
        raise MeasureMismatch("unit")
    finite(measure.value)
    if measure.value != measure.value.to_integral_value():
        raise ValueError("fractional count")
    return int(measure.value)


def _show(
    value: Number,
    *,
    places: int,
    unit: str,
    metric_key: str,
    inputs: Sequence[Measure],
    period: str | None = None,
    base_period: str = "",
) -> CalculationFact:
    anchor = inputs[0]
    return emit(
        value,
        unit=unit,
        places=places,
        metric_key=metric_key,
        release_id="published",
        geography=anchor.geography,
        geography_kind=anchor.geography_kind,
        period=anchor.period if period is None else period,
        base_period=base_period,
        inputs=inputs,
    )


def licence_density(licences: Measure, population: Measure) -> CalculationFact:
    """Licences per 10,000 residents. Both inputs are counts of one place and period."""
    require_aligned((licences, population), unit="count")
    licence_count = _whole(licences, "count")
    population_count = _whole(population, "count")
    count(licence_count)
    count(population_count)
    with localcontext(CALC_CONTEXT):
        density = ratio(Fraction(licence_count) * 10000, Fraction(population_count))
    return _show(
        density,
        places=0,
        unit="ratio",
        metric_key="licence_density",
        inputs=(licences, population),
    )


def location_quotient(
    local_row: Measure,
    local_all_row: Measure,
    national_row: Measure,
    national_all_row: Measure,
) -> dict[str, object]:
    """Location quotient. Local rows share a place; national rows share theirs."""
    require_aligned((local_row, local_all_row), unit="count")
    require_aligned((national_row, national_all_row), unit="count")
    if (
        national_row.geography_kind != "national"
        or local_row.geography_kind == "national"
    ):
        raise MeasureMismatch("geography")
    if local_row.period != national_row.period:
        raise MeasureMismatch("period")
    local = _whole(local_row, "count")
    local_all = _whole(local_all_row, "count")
    national = _whole(national_row, "count")
    national_all = _whole(national_all_row, "count")
    for value in (local, local_all, national, national_all):
        count(value)
    if local > local_all or national > national_all:
        raise ValueError("activity count exceeds all activities")
    inputs = (local_row, local_all_row, national_row, national_all_row)
    with localcontext(CALC_CONTEXT):
        share = ratio(Decimal(national), Decimal(national_all))
        local_share = ratio(Decimal(local), Decimal(local_all))
        if share == 0:
            raise ValueError("non-positive national share")
        if local < 10:
            return {
                "status": NoData("too_few_licences"),
                "count": _show(
                    Decimal(local),
                    places=0,
                    unit="count",
                    metric_key="local_count",
                    inputs=inputs,
                ),
            }
        lo, hi = wilson(local, local_all)
        return {
            "value": _show(
                local_share / share,
                places=2,
                unit="ratio",
                metric_key="location_quotient",
                inputs=inputs,
            ),
            "interval": (
                _show(
                    divide(lo, share),
                    places=2,
                    unit="ratio",
                    metric_key="lq_low",
                    inputs=inputs,
                ),
                _show(
                    divide(hi, share),
                    places=2,
                    unit="ratio",
                    metric_key="lq_high",
                    inputs=inputs,
                ),
            ),
            "interval_unrounded": (divide(lo, share), divide(hi, share)),
            "reliability_unrounded": reliability(local),
        }


def licence_churn(
    active_row: Measure,
    cancellations: Mapping[str, Measure],
    national_totals: Mapping[str, Measure],
    calendar: Sequence[str],
    all_cancellations_row: Measure,
    dated_cancellations_row: Measure,
) -> dict[str, object]:
    """Selected activity flow over the stock; flags use the full calendar."""
    expected = tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))
    if tuple(calendar) != expected:
        raise ValueError("complete declared calendar required")
    all_row = all_cancellations_row
    dated_row = dated_cancellations_row
    require_aligned((active_row, *cancellations.values()), unit="count", period=False)
    require_aligned(
        (all_row, dated_row, *national_totals.values()), unit="count", period=False
    )
    if all_row.geography_kind != "national":
        raise MeasureMismatch("geography")
    active = _whole(active_row, "count")
    all_cancellations = _whole(all_row, "count")
    dated_cancellations = _whole(dated_row, "count")
    for value in (active, all_cancellations, dated_cancellations):
        count(value)
    if dated_cancellations > all_cancellations:
        raise ValueError("dated count exceeds total")
    cancel_counts: dict[str, int] = {}
    national_counts: dict[str, int] = {}
    for month, row in cancellations.items():
        if row.period != month:
            raise MeasureMismatch("period")
        cancel_counts[month] = _whole(row, "count")
    for month, row in national_totals.items():
        if row.period != month:
            raise MeasureMismatch("period")
        national_counts[month] = _whole(row, "count")
    for rows in (cancel_counts, national_counts):
        for month, value in rows.items():
            count(value)
            if month not in expected:
                raise ValueError("month outside calendar")
    flags = bulk_months({key: Decimal(value) for key, value in national_counts.items()})
    included = sum(cancel_counts.values())
    excluded = sum(value for key, value in cancel_counts.items() if key not in flags)
    flagged = sum(national_counts.get(key, 0) for key in flags)
    if flagged > dated_cancellations:
        raise ValueError("bulk count exceeds dated count")
    local_inputs = (
        active_row,
        *cancellations.values(),
        all_row,
        dated_row,
        *national_totals.values(),
    )
    national_inputs = (
        all_row,
        dated_row,
        *national_totals.values(),
        active_row,
        *cancellations.values(),
    )

    def interval(k: int) -> tuple[CalculationFact, CalculationFact] | NoData:
        if k > active:
            return NoData("not_coverable")
        low, high = wilson(k, active)
        return (
            _show(
                low,
                places=3,
                unit="ratio",
                metric_key="churn_low",
                inputs=local_inputs,
            ),
            _show(
                high,
                places=3,
                unit="ratio",
                metric_key="churn_high",
                inputs=local_inputs,
            ),
        )

    with localcontext(CALC_CONTEXT):
        incl = ratio(Decimal(included), Decimal(active))
        excl = ratio(Decimal(excluded), Decimal(active))
        return {
            "active_count": _show(
                Decimal(active),
                places=0,
                unit="count",
                metric_key="active_count",
                inputs=local_inputs,
            ),
            "including_ratio": _show(
                incl,
                places=2,
                unit="ratio",
                metric_key="including_ratio",
                inputs=local_inputs,
            ),
            "including_percent": _show(
                incl * 100,
                places=1,
                unit="percent",
                metric_key="including_percent",
                inputs=local_inputs,
            ),
            "excluding_percent": _show(
                excl * 100,
                places=1,
                unit="percent",
                metric_key="excluding_percent",
                inputs=local_inputs,
            ),
            "including_interval": interval(included),
            "excluding_interval": interval(excluded),
            "including_interval_unrounded": wilson(included, active)
            if included <= active
            else None,
            "excluding_interval_unrounded": wilson(excluded, active)
            if excluded <= active
            else None,
            "undated_count": _show(
                Decimal(all_cancellations - dated_cancellations),
                places=0,
                unit="count",
                metric_key="undated_count",
                inputs=national_inputs,
            ),
            "bulk_months_unrounded": flags,
            "bulk_share_percent": _show(
                Fraction(flagged, dated_cancellations) * 100,
                places=1,
                unit="percent",
                metric_key="bulk_share",
                inputs=national_inputs,
            )
            if dated_cancellations
            else NoData("no_denominator"),
        }


def coverage_share(
    private_row: Measure | None,
    employed_row: Measure | None,
    *,
    workplace: bool = False,
) -> dict[str, object] | NoData:
    if workplace:
        return NoData("coverage_by_workplace_not_published")
    if private_row is None or employed_row is None:
        return NoData("no_denominator")
    require_aligned((private_row, employed_row), unit="count")
    private_employed = _whole(private_row, "count")
    employed = _whole(employed_row, "count")
    count(private_employed)
    count(employed)
    if private_employed > employed:
        raise ValueError("private employed exceeds employed")
    inputs = (private_row, employed_row)
    with localcontext(CALC_CONTEXT):
        low, high = wilson(private_employed, employed)
        return {
            "percent": _show(
                ratio(Decimal(private_employed), Decimal(employed)) * 100,
                places=1,
                unit="percent",
                metric_key="coverage_percent",
                inputs=inputs,
            ),
            "geography_unrounded": private_row.geography,
            "reliability_unrounded": reliability(employed),
            "interval": (
                _show(
                    low,
                    places=3,
                    unit="ratio",
                    metric_key="coverage_low",
                    inputs=inputs,
                ),
                _show(
                    high,
                    places=3,
                    unit="ratio",
                    metric_key="coverage_high",
                    inputs=inputs,
                ),
            ),
            "interval_unrounded": (low, high),
        }


def _unrounded(fact: object, geography: str) -> Number:
    """The exact value of one result on the geography it was asked for."""
    if (
        not isinstance(fact, CalculationFact)
        or fact.geography != geography
        or fact.exact_unrounded is None
    ):
        raise ValueError("geography_invalid")
    return fact.exact_unrounded


def _counts(measure_of: Callable[[int], Measure], values: Sequence[int]) -> Measure:
    if any(value < 0 for value in values):
        raise ValueError("negative_count")
    return measure_of(sum(values))


def private_employer_share(
    zones: Sequence[tuple[int, int | None, int | None]],
    source: SourceLink,
    period: str,
    named: Sequence[int],
) -> dict[str, str]:
    """PUB-71: private divided by all employed residents, on the source's zones.

    Each zone is (zone number, private, all employed). A zone with both counts
    null is unavailable and left out; one null of the pair is refused. The
    national share is over the remaining zones (one decimal); each named zone
    has its own share (no decimal). Each share is rounded once, half up.
    """
    numbers = [zone for zone, _, _ in zones]
    if len(set(numbers)) != len(numbers):
        raise ValueError("duplicate_zone")
    if any((private is None) != (total is None) for _, private, total in zones):
        raise ValueError("null_pair")
    kept = [(zone, p, t) for zone, p, t in zones if p is not None and t is not None]
    if not set(named) <= {zone for zone, _, _ in kept}:
        raise ValueError("zone_missing")

    def percent(group: Sequence[tuple[int, int, int]], geography: str) -> Number:
        def measure(value: int) -> Measure:
            kind = "national" if geography == "national" else "public"
            return Measure(
                Decimal(value), "count", period, geography, kind, "public", (source,)
            )

        result = coverage_share(
            _counts(measure, [p for _, p, _ in group]),
            _counts(measure, [t for _, _, t in group]),
        )
        if not isinstance(result, dict):
            raise ValueError("no_denominator")
        return _unrounded(result["percent"], geography)

    values = {
        "national_private": str(sum(p for _, p, _ in kept)),
        "national_all": str(sum(t for _, _, t in kept)),
        "national_1dp": rounded(percent(kept, "national"), 1),
    }
    for zone in named:
        group = [row for row in kept if row[0] == zone]
        values[f"zone_{zone}_0dp"] = rounded(percent(group, f"zone:{zone}"), 0)
    return values


def licence_density_pair(
    licences: Sequence[tuple[str, str, int]],
    residents: Sequence[tuple[str, int]],
    *,
    target: str,
    activity: str,
    period: str,
    licence_source: SourceLink,
    resident_source: SourceLink,
) -> dict[str, str]:
    """PUB-72: licences of one activity per 10,000 residents, local and national.

    Licences are (municipality key, activity code, count); residents are
    (municipality key, count) for one period. Both sides must name the same
    municipalities. Each density is rounded once, half up, to no decimal.
    """
    keys = [key for key, _ in residents]
    if len(set(keys)) != len(keys):
        raise ValueError("population_duplicate")
    licence_keys = {key for key, _, _ in licences}
    if target not in licence_keys:
        raise ValueError("municipality_missing")
    if set(keys) != licence_keys:
        raise ValueError("population_missing")

    def density(local: bool) -> tuple[int, str]:
        geography = f"municipality:{target}" if local else "national"

        def measure_of(source: SourceLink) -> Callable[[int], Measure]:
            kind = "public" if local else "national"
            return lambda value: Measure(
                Decimal(value), "count", period, geography, kind, "public", (source,)
            )

        population = _counts(
            measure_of(resident_source),
            [n for key, n in residents if not local or key == target],
        )
        fact = licence_density(
            _counts(
                measure_of(licence_source),
                [
                    n
                    for key, code, n in licences
                    if code == activity and (not local or key == target)
                ],
            ),
            population,
        )
        return int(population.value), rounded(_unrounded(fact, geography), 0)

    local_residents, local_density = density(True)
    national_residents, national_density = density(False)
    return {
        "local_residents": str(local_residents),
        "national_residents": str(national_residents),
        "local_0dp": local_density,
        "national_0dp": national_density,
    }


def places_in_country(
    records: Iterable[
        tuple[tuple[float, float, float, float], Sequence[str | None] | None]
    ],
    box: tuple[float, float, float, float],
    country: str,
) -> int:
    """PUB-73: records inside the box with an address in the country.

    A record is its bounding box (xmin, xmax, ymin, ymax) and the countries of
    its addresses; the box is (west, south, east, north). A record counts once
    when its whole bounding box is inside the box, edges included, and any
    address country equals ``country`` exactly; a null or empty list does not.
    """
    west, south, east, north = box
    return sum(
        1
        for (xmin, xmax, ymin, ymax), countries in records
        if xmin >= west
        and xmax <= east
        and ymin >= south
        and ymax <= north
        and country in (countries or ())
    )


@dataclass(frozen=True)
class TradeRow:
    product: str
    origin: str
    month: str
    value: Decimal
    weight: Decimal
    unit: str
    value_row: Measure
    weight_row: Measure


def _months(months: Sequence[str]) -> None:
    if len(months) != 12 or len(set(months)) != 12:
        raise ValueError("twelve complete months required")
    serial = []
    for month in months:
        parts = month.split("-")
        if (
            len(parts) != 2
            or len(parts[0]) != 4
            or len(parts[1]) != 2
            or not all(part.isdigit() for part in parts)
        ):
            raise ValueError("invalid month")
        year, number = map(int, parts)
        if not 1 <= number <= 12:
            raise ValueError("invalid month")
        serial.append(year * 12 + number)
    if serial != list(range(serial[0], serial[0] + 12)):
        raise ValueError("consecutive months required")


def _trade(row: TradeRow) -> None:
    if row.value_row.period != row.month or row.weight_row.period != row.month:
        raise MeasureMismatch("period")
    if row.value_row.unit != "qar":
        raise MeasureMismatch("unit")
    weight_unit = "kg" if row.unit == "kg" else "quantity"
    if row.weight_row.unit != weight_unit:
        raise MeasureMismatch("unit")
    if row.value_row.value != row.value or row.weight_row.value != row.weight:
        raise ValueError("row value does not match its measure")
    if (row.value_row.geography, row.value_row.geography_kind) != (
        row.weight_row.geography,
        row.weight_row.geography_kind,
    ):
        raise MeasureMismatch("geography")


def supplier_metrics(
    rows: Iterable[TradeRow],
    products: Iterable[str],
    months: Iterable[str],
    complete_months: Iterable[str],
    *,
    reviewed: bool,
    prior_rows: Iterable[TradeRow] | None = None,
    prior_months: Iterable[str] = (),
) -> dict[str, object] | NoData:
    """Reviewed basket membership is resolved upstream; never trim to top origins."""
    rows = tuple(rows)
    products = tuple(products)
    months = tuple(months)
    complete_months = tuple(complete_months)
    prior_months = tuple(prior_months)
    if prior_rows is not None:
        prior_rows = tuple(prior_rows)
    if not reviewed or not products or len(set(products)) != len(products):
        raise ValueError("reviewed basket required")
    _months(months)
    if not set(months) <= set(complete_months):
        raise ValueError("incomplete window")
    for row in rows:
        _trade(row)
    require_aligned(
        tuple(row.value_row for row in rows), period=False
    ) if rows else None
    window = months[0] + ".." + months[-1]

    def show(
        value: Number,
        *,
        places: int,
        unit: str,
        metric_key: str,
        inputs: Sequence[Measure],
    ) -> CalculationFact:
        return _show(
            value,
            places=places,
            unit=unit,
            metric_key=metric_key,
            inputs=inputs,
            period=window,
        )

    grouped: dict[str, list[TradeRow]] = {}
    for row in rows:
        if row.product not in products or row.month not in months:
            raise ValueError("row outside selected basket/window")
        finite(row.value)
        finite(row.weight)
        if row.value < 0:
            raise ValueError("negative import value")
        grouped.setdefault(row.origin, []).append(row)
    readings = tuple(cell for row in rows for cell in (row.value_row, row.weight_row))
    with localcontext(CALC_CONTEXT):
        total = sum((Fraction(row.value) for row in rows), Fraction(0))
        if total == 0 and (prior_rows is None or not rows):
            return NoData("no_denominator")
        origins: dict[str, dict[str, object]] = {}
        hhi = Fraction(0)
        for origin in sorted(grouped) if total else ():
            values = grouped[origin]
            share = sum((Fraction(row.value) for row in values), Fraction(0)) / total
            uv, other, nonpositive = unit_value(
                [(row.value, row.weight, row.unit) for row in values]
            )
            hhi += share * share * 10000
            origins[origin] = {
                "share_percent": show(
                    share * 100,
                    places=1,
                    unit="percent",
                    metric_key="share",
                    inputs=readings,
                ),
                "unit_value": show(
                    uv,
                    places=2,
                    unit="qar_per_kg",
                    metric_key="unit_value",
                    inputs=readings,
                )
                if uv is not None
                else NoData("no_denominator"),
                "unit_value_unrounded": uv,
                "other_units": show(
                    Decimal(other),
                    places=0,
                    unit="count",
                    metric_key="other_units",
                    inputs=readings,
                ),
                "nonpositive_kg": show(
                    Decimal(nonpositive),
                    places=0,
                    unit="count",
                    metric_key="nonpositive_kg",
                    inputs=readings,
                ),
            }
        trend: CalculationFact | NoData | None = None
        trend_unrounded = None
        prior: Fraction | None = None  # {QAR}, exact sum over the prior window.
        if prior_rows is not None:
            _months(prior_months)
            if (
                not set(prior_months) <= set(complete_months)
                or prior_months[-1] >= months[0]
            ):
                raise ValueError("incomplete or overlapping prior window")
            first_year, first_month = map(int, months[0].split("-"))
            last_year, last_month = map(int, prior_months[-1].split("-"))
            if first_year * 12 + first_month != last_year * 12 + last_month + 1:
                raise ValueError("prior window must be adjacent")
            for row in prior_rows:
                _trade(row)
                if row.product not in products or row.month not in prior_months:
                    raise ValueError("prior row outside selected basket/window")
                finite(row.value)
                if row.value < 0:
                    raise ValueError("negative import value")
            prior = sum((Fraction(row.value) for row in prior_rows), Fraction(0))
            trend = NoData("no_denominator")
            if prior > 0:
                trend_unrounded = (total - prior) / prior
                trend = _show(
                    trend_unrounded,
                    places=4,
                    unit="ratio",
                    metric_key="trend",
                    inputs=(*readings, *(row.value_row for row in prior_rows)),
                    period=window,
                    base_period=prior_months[0] + ".." + prior_months[-1],
                )
        return {
            "total_value": show(
                total, places=2, unit="qar", metric_key="total_value", inputs=readings
            ),
            "total_value_unrounded": total,
            "prior_total_value_unrounded": prior,
            "origin_count": show(
                Decimal(len(origins)),
                places=0,
                unit="count",
                metric_key="origin_count",
                inputs=readings,
            ),
            "origins": origins,
            "hhi": show(hhi, places=2, unit="index", metric_key="hhi", inputs=readings)
            if total
            else NoData("no_denominator"),
            **({"trend": trend} if trend is not None else {}),
            "trend_unrounded": trend_unrounded,
        }


@dataclass(frozen=True)
class AnnualEnergy:
    zone: str
    year: int
    value: Decimal
    complete: bool
    reading: Measure


def _zone_tie(key: str) -> tuple[int, int | str]:
    """Digit zone keys tie-break in numeric order; any other key is a label."""
    if key.isdigit():
        return (0, int(key))
    return (1, key)


def zone_momentum(
    rows: Iterable[AnnualEnergy],
    national_before: AnnualEnergy,
    national_after: AnnualEnergy,
    *,
    minimum_baseline: Decimal = CARD_BASELINE_KWH,
) -> dict[str, object]:
    """C9 level multiples. Ranking uses the card's 1 GWh floor, not a lower caller floor."""
    rows = tuple(rows)
    finite(minimum_baseline)
    if minimum_baseline != CARD_BASELINE_KWH:
        raise ValueError("card baseline is 1,000,000 kWh")
    threshold = CARD_BASELINE_KWH
    if (
        national_before.year >= national_after.year
        or national_before.zone != national_after.zone
    ):
        raise ValueError("incompatible national series")
    if national_before.year != 2021 or national_after.year != 2025:
        raise ValueError("card years are 2021 and 2025")
    for row in (*rows, national_before, national_after):
        if row.reading.value != row.value or row.reading.period != str(row.year):
            raise MeasureMismatch("period")
        if row.reading.unit != "kwh":
            raise MeasureMismatch("unit")
        finite(row.value)
        if not row.complete or row.value < 0:
            raise ValueError("partial year or negative energy")
    pairs: dict[str, dict[int, Decimal]] = {}
    zone_inputs: dict[str, list[Measure]] = {}
    for row in rows:
        years = pairs.setdefault(row.zone, {})
        zone_inputs.setdefault(row.zone, []).append(row.reading)
        if row.year in years or row.year not in (
            national_before.year,
            national_after.year,
        ):
            raise ValueError("duplicate or wrong year")
        years[row.year] = row.value
    national_inputs = (
        national_before.reading,
        national_after.reading,
        *(row.reading for row in rows),
    )
    with localcontext(CALC_CONTEXT):
        national = ratio(national_after.value, national_before.value)
        if national <= 0:
            raise ValueError("non-positive national ratio")
        ratios: dict[str, Fraction] = {}
        present: dict[str, Fraction] = {}
        for zone, years in pairs.items():
            if len(years) != 2:
                raise ValueError("incomplete annual pair")
            before = years[national_before.year]
            if before > 0:
                present[zone] = ratio(years[national_after.year], before)
                if before >= threshold:
                    ratios[zone] = present[zone]
        order = tuple(sorted(ratios, key=lambda key: (-ratios[key], _zone_tie(key))))
        missing = NoData("no_denominator")
        return {
            "national_ratio": _show(
                national,
                places=2,
                unit="ratio",
                metric_key="national_ratio",
                inputs=national_inputs,
                period="2025",
                base_period="2021",
            ),
            "national_ratio_unrounded": national,
            "order_unrounded": order,
            "zones": {
                key: (
                    {
                        "ratio": _show(
                            present[key],
                            places=2,
                            unit="ratio",
                            metric_key="zone_ratio",
                            inputs=(*zone_inputs[key], *national_inputs),
                            period="2025",
                            base_period="2021",
                        ),
                        "ranked_ratio": _show(
                            present[key],
                            places=1,
                            unit="ratio",
                            metric_key="ranked_ratio",
                            inputs=(*zone_inputs[key], *national_inputs),
                            period="2025",
                            base_period="2021",
                        ),
                        "ratio_unrounded": present[key],
                        "relative": _show(
                            present[key] / national,
                            places=2,
                            unit="ratio",
                            metric_key="relative",
                            inputs=(*zone_inputs[key], *national_inputs),
                            period="2025",
                            base_period="2021",
                        ),
                        "ranked_unrounded": key in ratios,
                    }
                    if key in present
                    else {
                        "ratio": missing,
                        "ranked_ratio": missing,
                        "ratio_unrounded": None,
                        "relative": missing,
                        "ranked_unrounded": False,
                    }
                )
                for key in pairs
            },
        }
