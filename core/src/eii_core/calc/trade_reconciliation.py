"""Exact source-separated trade differences. No conversion or inferred equivalence."""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from .public_series import exact, subtract

METHOD = "trade_reconciliation.v1"
COMPATIBILITY = (
    "partner",
    "flow",
    "year",
    "periods",
    "classification",
    "hs_revision",
    "product_scope",
    "coverage_key",
    "currency",
    "unit",
    "scale",
    "valuation_basis",
)
UNKNOWN = {"", "unknown", "pending", "not stated by the source"}


@dataclass(frozen=True)
class TradeFigure:
    input_id: str
    source_id: str
    source_version: str
    role: str
    partner: str
    flow: str
    year: int
    periods: tuple[str, ...]
    classification: str
    hs_revision: str
    product_scope: str
    coverage_key: str
    currency: str
    unit: str
    scale: str
    valuation_basis: str
    value: str | None
    lineage: tuple[str, ...]
    figure_kind: str = "published"


@dataclass(frozen=True)
class Comparison:
    left: TradeFigure | None
    right: TradeFigure | None
    gap: str | None
    mismatch_codes: tuple[str, ...]
    unknown_cause: bool = True
    method: str = METHOD


def _number(text: str) -> Fraction:
    import re

    if (
        not isinstance(text, str)
        or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", text) is None
    ):
        raise ValueError("decimal_format")
    return exact(Decimal(text))


def _text(value: Fraction) -> str:
    """Serialize terminating rational without mutable Decimal context or rounding."""
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("nonterminating")
    places = max(twos, fives)
    integer = value.numerator * 2 ** (places - twos) * 5 ** (places - fives)
    sign = "-" if integer < 0 else ""
    digits = str(abs(integer)).zfill(places + 1)
    return sign + (digits[:-places] + "." + digits[-places:] if places else digits)


def _attributes(row: TradeFigure) -> dict[str, str | int | tuple[str, ...]]:
    """Closed compatibility fields, without dynamic attribute access."""
    return {
        "partner": row.partner,
        "flow": row.flow,
        "year": row.year,
        "periods": row.periods,
        "classification": row.classification,
        "hs_revision": row.hs_revision,
        "product_scope": row.product_scope,
        "coverage_key": row.coverage_key,
        "currency": row.currency,
        "unit": row.unit,
        "scale": row.scale,
        "valuation_basis": row.valuation_basis,
        "source_id": row.source_id,
        "source_version": row.source_version,
        "role": row.role,
    }


def compare_trade_sources(
    left: TradeFigure | None, right: TradeFigure | None
) -> Comparison:
    if left is None or right is None:
        return Comparison(left, right, None, ("missing_side",))
    mismatches = []
    left_fields, right_fields = _attributes(left), _attributes(right)
    for name in COMPATIBILITY:
        a, b = left_fields[name], right_fields[name]
        if a != b or (isinstance(a, str) and a in UNKNOWN) or not a:
            mismatches.append(name)
    if not left.lineage or not right.lineage:
        raise ValueError("lineage_missing")
    if left.value is None or right.value is None:
        mismatches.append("source_missing")
    if mismatches:
        return Comparison(left, right, None, tuple(mismatches))
    assert left.value is not None and right.value is not None
    gap = exact(subtract(_number(right.value), _number(left.value)))
    return Comparison(left, right, _text(gap), ())


def annual_trade_sum(rows: tuple[TradeFigure, ...], *, output_id: str) -> TradeFigure:
    """Sum one native product scope across a complete calendar, never components."""
    from dataclasses import replace

    if not rows:
        raise ValueError("annual_coverage")
    first = rows[0]
    expected = {f"{first.year}-{month:02}" for month in range(1, 13)}
    if (
        len(rows) != 12
        or any(len(row.periods) != 1 for row in rows)
        or {row.periods[0] for row in rows} != expected
        or len({row.input_id for row in rows}) != len(rows)
    ):
        raise ValueError("annual_coverage")
    first_fields = _attributes(first)
    for row in rows:
        row_fields = _attributes(row)
        for name in (*COMPATIBILITY, "source_id", "source_version", "role"):
            if name == "periods":
                continue
            value = row_fields[name]
            if value != first_fields[name] or (
                isinstance(value, str) and value in UNKNOWN
            ):
                raise ValueError("annual_compatibility")
        if row.value is None or not row.lineage or row.figure_kind != "published":
            raise ValueError("annual_coverage")
    total = sum(
        (_number(row.value) for row in rows if row.value is not None), Fraction()
    )
    return replace(
        first,
        input_id=output_id,
        periods=(str(first.year),),
        value=_text(total),
        figure_kind="calculated",
        lineage=tuple(
            row.input_id for row in sorted(rows, key=lambda row: row.periods)
        ),
    )


@dataclass(frozen=True)
class PairResult:
    partner: str
    year: int
    flow: str
    scope: str
    left_source: str
    left_role: str
    right_source: str
    right_role: str
    left_input_id: str | None
    right_input_id: str | None
    gap: str | None
    mismatch_codes: tuple[str, ...]
    unknown_cause: bool = True
    known_cause_codes: tuple[str, ...] = ()
    cause_evidence_refs: tuple[str, ...] = ()


def all_pairs(
    figures: tuple[TradeFigure, ...],
    sources: tuple[tuple[str, str], ...],
    partners: tuple[str, ...],
    years: tuple[int, ...],
    flows: tuple[str, ...],
    scopes: tuple[str, ...],
) -> tuple[PairResult, ...]:
    """Retain every requested source-role pair, even two absent sides."""
    results = []
    requested = (
        (partner, year, flow, scope)
        for partner in partners
        for year in years
        for flow in flows
        for scope in scopes
    )
    pairs = tuple(
        (left, right)
        for index, left in enumerate(sources)
        for right in sources[index + 1 :]
    )
    for partner, year, flow, scope in requested:
        candidates: dict[tuple[str, str], TradeFigure] = {}
        for source in sources:
            rows = tuple(
                r
                for r in figures
                if (r.source_id, r.role) == source
                and (r.partner, r.year, r.flow, r.product_scope)
                == (partner, year, flow, scope)
            )
            if not rows:
                continue
            annual = tuple(r for r in rows if r.periods == (str(year),))
            if len(annual) == 1:
                candidates[source] = annual[0]
        for left_key, right_key in pairs:
            left, right = candidates.get(left_key), candidates.get(right_key)
            comparison = compare_trade_sources(left, right)
            incomplete = any(
                r.periods != (str(year),)
                and (r.source_id, r.role) in {left_key, right_key}
                and (r.partner, r.year, r.flow, r.product_scope)
                == (partner, year, flow, scope)
                and (r.source_id, r.role) not in candidates
                for r in figures
            )
            codes = comparison.mismatch_codes + (
                ("incomplete_calendar",) if incomplete else ()
            )
            results.append(
                PairResult(
                    partner,
                    year,
                    flow,
                    scope,
                    *left_key,
                    *right_key,
                    left.input_id if left else None,
                    right.input_id if right else None,
                    comparison.gap,
                    codes,
                )
            )
    return tuple(results)


def comparison_figures(rows: tuple[TradeFigure, ...]) -> tuple[TradeFigure, ...]:
    """Published rows plus separately identified complete-calendar aggregates."""
    groups: dict[tuple[str, str, str, int, str, str], list[TradeFigure]] = {}
    for row in rows:
        key = (
            row.source_id,
            row.role,
            row.partner,
            row.year,
            row.flow,
            row.product_scope,
        )
        groups.setdefault(key, []).append(row)
    aggregates = []
    for group in groups.values():
        if any(r.periods == (str(r.year),) for r in group):
            continue
        ordered = tuple(sorted(group, key=lambda r: r.periods))
        try:
            aggregates.append(
                annual_trade_sum(
                    ordered, output_id="annual:" + ":".join(r.input_id for r in ordered)
                )
            )
        except ValueError:
            # Native rows remain present; all_pairs emits incomplete_calendar.
            pass
    return rows + tuple(aggregates)
