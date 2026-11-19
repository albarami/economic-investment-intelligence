"""C18 / MTH-74 and MTH-75: pure post-processing of published release inputs.

Callers supply geodesic WGS 84 intersection areas and resolved release lineage.
No geometry engine, store, grid file or custodian record is read here. The closed
count list is C18's people totals, licences, permits and released C15 counts.
Grid sums are relative weights only; admission requires file, licence and schema
confirmation. The S2-T13 confirmation currently selects area, never a live grid.
"""

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from fractions import Fraction

PEOPLE = frozenset({"population", "labour_force", "employed", "unemployed"})
SIMULATED = frozenset({"presence_count", "flow_hourly"})
STATISTICS = frozenset({"share", "rate", "mean", "median", "price", "index"})

# C18 reviewed counts, tied to release tables of document 03 section 7.3.
COUNT_TABLES = {
    "population": frozenset(
        {"pub_population_municipality", "pub_labour_sex_municipality"}
    ),
    "labour_force": frozenset({"pub_labour_sex_municipality"}),
    "employed": frozenset({"pub_labour_sex_municipality"}),
    "unemployed": frozenset({"pub_labour_sex_municipality"}),
    "licences": frozenset(
        {"pub_licence_active", "pub_licence_issued", "pub_licence_cancelled"}
    ),
    "building_permits": frozenset({"pub_building_permits"}),
}


@dataclass(frozen=True)
class Lineage:
    """Resolved source and method chain for a released value or geometry input."""

    source_id: str
    publisher: str
    page: str
    licence: str
    retrieved: str
    sha256: str
    method: str
    method_version: str

    def complete(self) -> bool:
        return all(
            value.strip()
            for value in (
                self.source_id,
                self.publisher,
                self.page,
                self.licence,
                self.retrieved,
                self.sha256,
                self.method,
                self.method_version,
            )
        )


@dataclass(frozen=True)
class Weight:
    """Explicit source identity; shape/frame weights carry geometry lineage per row."""

    source_id: str = "area"
    provenance: str = "frame"
    admitted: bool = False
    licence_id: str = ""
    licence_basis: str = ""
    file_confirmed: bool = False
    schema_confirmed: bool = False
    lineage: Lineage | None = None


AREA_WEIGHT = Weight()


def select_people_weight(weight: Weight) -> str:
    """Return area or a fully admitted grid; never silently accept a bad grid."""
    if weight.source_id == "area":
        if weight.provenance not in {"shape", "frame", "public"}:
            raise ValueError("weight must derive from shape, frame or Public data")
        return "area"
    if not (
        weight.source_id == "worldpop_qat_2020"
        and weight.provenance == "public"
        and weight.admitted
        and weight.licence_id == "CC-BY-4.0"
        and weight.licence_basis == "dataset"
        and weight.file_confirmed
        and weight.schema_confirmed
        and weight.lineage is not None
        and weight.lineage.complete()
        and weight.lineage.source_id == weight.source_id
    ):
        raise ValueError("weight grid is not admitted")
    return weight.source_id


@dataclass(frozen=True)
class Row:
    """One unchanged released geography value, with eligibility and numeric lineage.

    metric is the C18 count kind, not the release indicator column: population
    is the residents total of pub_population_municipality or the all-categories
    population total of pub_labour_sex_municipality.
    lineage covers value/low/high; geometry_lineage covers area/intersection.
    grid_total/grid_intersection use Weight.lineage. Split labels are eligibility
    metadata, never person attributes. all_categories_total means an already
    published total over every category, not a sum performed by this function.
    """

    geography: str
    geography_kind: str
    table: str
    metric: str
    value: Decimal | None
    area: Decimal
    intersection: Decimal
    lineage: Lineage
    geometry_lineage: Lineage
    provenance: str = "public"
    status: str = "published"
    in_release: bool = True
    split: str = "total"
    geometry_origin: str = "frame"
    complete_group: bool = True
    low: Decimal | None = None
    high: Decimal | None = None
    grid_total: Decimal | None = None
    grid_intersection: Decimal | None = None


@dataclass(frozen=True)
class Contribution:
    """Published input and computed weight; neither input is rewritten."""

    row: Row
    weight: Decimal


@dataclass(frozen=True)
class Result:
    """Typed count, unblended originals, or an empty refusal (DAT-147)."""

    status: str
    value: int | None = None
    low: Decimal | int | None = None
    high: Decimal | int | None = None
    originals: tuple[Row, ...] = ()
    contributions: tuple[Contribution, ...] = ()
    provenance: str = ""
    evidence_status: str = ""
    geography_kind: str = ""
    area_shape: str = ""
    apportioned_from: tuple[str, ...] = ()
    method: str = ""
    method_version: str = ""
    caveat: str = ""
    weight_source: Weight = Weight()


def _released(row: Row) -> bool:
    return bool(
        row.in_release
        and row.split in {"total", "all_categories_total"}
        and row.geography.strip()
        and row.lineage.complete()
        and row.geometry_lineage.complete()
        and row.geometry_origin in {"shape", "frame", "public"}
    )


def _withheld(row: Row) -> bool:
    return (
        _released(row)
        and row.status == "withheld"
        and row.provenance == "simulated"
        and row.metric == "presence_count"
        and row.table == row.metric
        and row.geography_kind == "release_unit"
    )


def _eligible(row: Row) -> bool:
    if not (_released(row) and row.status == "published" and row.value is not None):
        return False
    if row.provenance == "simulated":
        return (
            row.metric in SIMULATED
            and row.table == row.metric
            and row.geography_kind == "release_unit"
            and (row.low is not None) == (row.metric == "presence_count")
            and (row.high is not None) == (row.metric == "presence_count")
        )
    return (
        row.provenance == "public"
        and row.table.startswith("pub_")
        and row.table != "pub_pop_agesex_grid"
        and row.geography_kind == "official"
        and (
            row.metric in STATISTICS
            or row.table in COUNT_TABLES.get(row.metric, frozenset())
        )
        and (
            row.table != "pub_labour_sex_municipality"
            or row.split == "all_categories_total"
        )
    )


def _half_up(total: Fraction) -> int:
    """Round a nonnegative exact sum half-up to a whole number (C18)."""
    return (2 * total.numerator + total.denominator) // (2 * total.denominator)


def apportion(
    rows: tuple[Row, ...], area_shape: str, weight: Weight = AREA_WEIGHT
) -> Result:
    """Apply C18 once to the final sum; withheld groups emit no numeric inputs."""
    method = select_people_weight(weight)
    if not rows:
        return Result("NO_DATA")
    if not area_shape.strip() or not all(
        _eligible(row) or _withheld(row) for row in rows
    ):
        return Result("REFUSED")
    first = rows[0]
    if any(
        (row.metric, row.provenance) != (first.metric, first.provenance) for row in rows
    ):
        return Result("REFUSED")
    if first.metric in STATISTICS:
        values = tuple(row.value for row in rows if row.value is not None)
        return Result("UNBLENDED", low=min(values), high=max(values), originals=rows)
    if first.provenance == "simulated" and not all(
        row.status == "published" and row.complete_group for row in rows
    ):
        return Result("BELOW_PANEL_MINIMUM")
    if first.metric not in PEOPLE:
        method = "area"
    contributions: list[Contribution] = []
    exact: list[Fraction] = []
    for row in rows:
        numerator, denominator = row.intersection, row.area
        if method == "worldpop_qat_2020":
            if row.grid_total is None or row.grid_intersection is None:
                return Result("REFUSED")
            numerator, denominator = row.grid_intersection, row.grid_total
        if denominator == 0 or row.area == 0:
            return Result("NO_DATA")
        exact.append(Fraction(numerator) / Fraction(denominator))
        # Display weights are decimal; totals use the exact ratios above.
        with localcontext(Context(prec=28)):
            contributions.append(Contribution(row, numerator / denominator))
    count = _half_up(
        sum(
            (
                Fraction(r.value) * w
                for r, w in zip(rows, exact, strict=True)
                if r.value is not None
            ),
            Fraction(0),
        )
    )
    low = high = None
    if first.metric == "presence_count":
        low = _half_up(
            sum(
                (
                    Fraction(r.low) * w
                    for r, w in zip(rows, exact, strict=True)
                    if r.low is not None
                ),
                Fraction(0),
            )
        )
        high = _half_up(
            sum(
                (
                    Fraction(r.high) * w
                    for r, w in zip(rows, exact, strict=True)
                    if r.high is not None
                ),
                Fraction(0),
            )
        )
    result = Result(
        "APPORTIONED",
        count,
        low,
        high,
        contributions=tuple(contributions),
        provenance=first.provenance,
        evidence_status="inferred",
        geography_kind="area_shape",
        area_shape=area_shape,
        apportioned_from=_from(rows),
        method=method,
        method_version="C18-v1",
        caveat="apportioned_estimate",
        weight_source=weight if weight.source_id == method else AREA_WEIGHT,
    )
    validate_result(result)
    return result


def _from(rows: tuple[Row, ...]) -> tuple[str, ...]:
    if rows[0].provenance == "simulated":
        return ("release_units",)
    return tuple(row.geography for row in rows)


def validate_result(result: Result) -> None:
    """Reject altered count-fact metadata before downstream fact assembly."""
    rows = tuple(c.row for c in result.contributions)
    if not rows:
        raise ValueError("result has no published contributions")
    selected = select_people_weight(result.weight_source)
    expected_method = selected if rows[0].metric in PEOPLE else "area"
    if not (
        result.status == "APPORTIONED"
        and result.evidence_status == "inferred"
        and result.geography_kind == "area_shape"
        and result.area_shape.strip()
        and result.apportioned_from == _from(rows)
        and result.method == expected_method
        and selected == result.method
        and result.method_version == "C18-v1"
        and result.caveat == "apportioned_estimate"
        and all(_eligible(row) for row in rows)
        and all(result.provenance == row.provenance for row in rows)
        and (
            rows[0].provenance != "simulated" or all(row.complete_group for row in rows)
        )
    ):
        raise ValueError("result violates DAT-147")
