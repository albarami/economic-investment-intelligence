"""Prefix scoring and prospective conformal residuals; spike only."""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from hashlib import sha256

from eii_core.calc.forecast_models import predict
from eii_core.calc.public_series import CALC_CONTEXT

from .contract import (
    AUTOS,
    BASELINES,
    CHALLENGERS,
    COMBINATION,
    POLICY,
    Family,
    Registration,
    SeriesSpec,
    first_origin,
    level,
    number,
    season,
)

Predictor = Callable[[tuple[Decimal, ...], int], Decimal]


@dataclass(frozen=True)
class Origin:
    origin: int
    target: Decimal
    prediction: Decimal | None
    error: Decimal | None
    low: Decimal | None
    high: Decimal | None
    selected: str
    selection_errors: tuple[tuple[str, tuple[Decimal, ...]], ...]
    refusal: str = ""


@dataclass(frozen=True)
class SeriesResult:
    spec: SeriesSpec
    candidate: str
    scale: Decimal
    origins: tuple[Origin, ...]


@dataclass(frozen=True)
class Summary:
    family: Family
    candidate: str
    horizon: int
    level_numerator: int
    level_denominator: int
    expected: int
    evaluated: int
    covered: int
    score: Decimal | None
    zero_scale_mae: tuple[tuple[str, Decimal], ...]
    status: str
    reason: str


@dataclass(frozen=True)
class Run:
    registration_sha256: str
    input_sha256: str
    series: tuple[SeriesResult, ...]
    summaries: tuple[Summary, ...]
    fixture_only: bool = True


def run(
    registration: Registration,
    values: Mapping[str, tuple[Decimal, ...]],
    predictors: Mapping[str, Predictor],
    *,
    expected_registration_sha256: str,
) -> Run:
    registration.validate()
    if registration.sha256 != expected_registration_sha256:
        raise ValueError("registration_hash_mismatch")
    if set(values) != {s.key for s in registration.series}:
        raise ValueError("series_membership")
    if any(key not in AUTOS + CHALLENGERS for key in predictors):
        raise ValueError("closed_predictor_schema")
    for spec in registration.series:
        if len(values[spec.key]) != len(spec.periods):
            raise ValueError("missing_observations")
        for value in values[spec.key]:
            if type(value) is not Decimal:
                raise ValueError("decimal_observations_required")
            number(value)
    input_bytes = json.dumps(
        {key: [str(v) for v in value] for key, value in values.items()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with localcontext(CALC_CONTEXT):
        results = tuple(
            result
            for spec in registration.series
            for result in _series(
                spec, values[spec.key], registration.candidates, predictors
            )
        )
        families = tuple(dict.fromkeys(s.family for s in registration.series))
        summaries = tuple(
            _summary(
                family,
                candidate,
                tuple(
                    r
                    for r in results
                    if r.spec.family == family and r.candidate == candidate
                ),
            )
            for family in families
            for candidate in registration.candidates
        )
    return Run(registration.sha256, sha256(input_bytes).hexdigest(), results, summaries)


def _radius(errors: tuple[Decimal, ...], frequency: str) -> Decimal | None:
    coverage = level(frequency)
    k = (
        (len(errors) + 1) * coverage.numerator + coverage.denominator - 1
    ) // coverage.denominator
    return sorted(errors)[k - 1] if 0 < k <= len(errors) else None


def _series(
    spec: SeriesSpec,
    values: tuple[Decimal, ...],
    candidates: tuple[str, ...],
    predictors: Mapping[str, Predictor],
) -> tuple[SeriesResult, ...]:
    m = season(spec.family.frequency)
    first = first_origin(spec.family.frequency)
    prefix = values[:first]
    scale = sum(
        (abs(prefix[t] - prefix[t - m]) for t in range(m, first)), Decimal(0)
    ) / (first - m)
    rows: dict[str, list[Origin]] = {name: [] for name in candidates}
    fixed = tuple(name for name in candidates if name != POLICY)
    selectable = tuple(name for name in fixed if name not in CHALLENGERS)
    for origin in range(first, len(values)):
        points: dict[str, Decimal | None] = {}
        selected = ""
        selection_errors: tuple[tuple[str, tuple[Decimal, ...]], ...] = ()
        # All predictions at this origin precede all scoring at this origin.
        for name in fixed:
            point: Decimal | None = None
            try:
                if name in BASELINES:
                    point = predict(values[:origin], name, m, 1)[0]
                elif name == COMBINATION:
                    parts = tuple(points.get(key) for key in AUTOS)
                    if all(p is not None for p in parts):
                        point = sum((p for p in parts if p is not None), Decimal(0)) / 3
                elif name in predictors:
                    with localcontext(CALC_CONTEXT):
                        point = number(predictors[name](values[:origin], m))
            except (ValueError, ArithmeticError, RuntimeError):
                point = None
            points[name] = point
        if POLICY in candidates:
            selection_errors = tuple(
                (name, tuple(abs(r.error) for r in rows[name] if r.error is not None))
                for name in selectable
            )
            if all(len(errors) == origin - first for _, errors in selection_errors):
                # A common frozen scale cancels within a series. Compare sums on
                # identical matured inner targets; ties retain the fixed order.
                selected = min(
                    selection_errors, key=lambda item: sum(item[1], Decimal(0))
                )[0]
                points[POLICY] = points[selected]
            else:
                points[POLICY] = None
        for name in candidates:
            point = points[name]
            previous = tuple(abs(r.error) for r in rows[name] if r.error is not None)
            radius = (
                _radius(previous, spec.family.frequency)
                if len(previous) == origin - first
                else None
            )
            rows[name].append(
                Origin(
                    origin,
                    values[origin],
                    point,
                    values[origin] - point if point is not None else None,
                    point - radius
                    if point is not None and radius is not None
                    else None,
                    point + radius
                    if point is not None and radius is not None
                    else None,
                    selected if name == POLICY else name,
                    selection_errors if name == POLICY else (),
                    "missing_prediction" if point is None else "",
                )
            )
    return tuple(
        SeriesResult(spec, name, scale, tuple(rows[name])) for name in candidates
    )


def _summary(
    family: Family, candidate: str, results: tuple[SeriesResult, ...]
) -> Summary:
    expected = sum(len(row.spec.targets) for row in results)
    evaluated = covered = 0
    scores: list[Decimal] = []
    zero_scale: list[tuple[str, Decimal]] = []
    missing = False
    for result in results:
        targets = tuple(
            row for row in result.origins if row.origin in result.spec.targets
        )
        valid = tuple(
            row
            for row in targets
            if row.prediction is not None
            and row.low is not None
            and row.high is not None
            and row.error is not None
        )
        missing = missing or len(valid) != len(targets)
        evaluated += len(valid)
        for row in valid:
            assert row.error is not None and row.prediction is not None
            assert row.low is not None and row.high is not None
            covered += row.low <= row.target <= row.high
        if valid:
            mae = sum(
                (abs(row.error) for row in valid if row.error is not None), Decimal(0)
            ) / len(valid)
            if result.scale == 0:
                zero_scale.append((result.spec.key, mae))
            else:
                scores.append(mae / result.scale)
    coverage = level(family.frequency)
    score = (
        sum(scores, Decimal(0)) / len(scores)
        if scores and not zero_scale and not missing and len(scores) == len(results)
        else None
    )
    if missing:
        status, reason = "blocked", "missing_prediction_or_interval"
    elif (
        any(not row.spec.targets for row in results) or evaluated == 0 or evaluated < 12
    ):
        status, reason = "insufficient", "minimum_evaluated_targets"
    elif zero_scale:
        status, reason = "refused", "zero_scale"
    elif covered * coverage.denominator < evaluated * coverage.numerator:
        status, reason = "fail", "coverage_below_level"
    else:
        status, reason = "pass", ""
    return Summary(
        family,
        candidate,
        1,
        coverage.numerator,
        coverage.denominator,
        expected,
        evaluated,
        covered,
        score,
        tuple(zero_scale),
        status,
        reason,
    )


def strict_beat(result: Run, family: Family, candidate: str, baseline: str) -> bool:
    rows = {row.candidate: row for row in result.summaries if row.family == family}
    if candidate not in rows or baseline not in rows:
        return False
    left, right = rows[candidate], rows[baseline]
    return (
        left.status == "pass"
        and right.evaluated == right.expected
        and left.expected == right.expected
        and left.score is not None
        and right.score is not None
        and left.score < right.score
    )


def stage_verdict(result: Run, family: Family, stage: str) -> str:
    if stage not in ("statistical", "challenger"):
        raise ValueError("unknown_stage")
    candidates = (*AUTOS, COMBINATION) if stage == "statistical" else CHALLENGERS
    baseline = "seasonal_naive" if stage == "statistical" else COMBINATION
    rows = {r.candidate: r for r in result.summaries if r.family == family}
    required = (*candidates, baseline)
    if any(c not in rows or rows[c].status == "blocked" for c in required):
        return "blocked"
    if any(rows[c].status in ("insufficient", "refused") for c in required):
        return "insufficient"
    return (
        "pass"
        if all(strict_beat(result, family, c, baseline) for c in candidates)
        else "fail"
    )
