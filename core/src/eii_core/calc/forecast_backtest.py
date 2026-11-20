"""C30 rolling origins, common scale and leave-one-origin-out empirical ranges."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, localcontext

from .facts import NoData
from .forecast_models import CANDIDATES, history, predict
from .public_series import CALC_CONTEXT

METHOD = "c30_rolling_origin"
METHOD_VERSION = "v1"
MINIMUM_ORIGINS = 3


@dataclass(frozen=True)
class CandidateResult:
    model: str
    errors: tuple[tuple[Decimal, ...], ...]
    error: Decimal


@dataclass(frozen=True)
class Backtest:
    candidates: tuple[CandidateResult, ...]
    model: str
    scale: Decimal
    error: Decimal
    forecasts: tuple[Decimal, ...]
    low: tuple[Decimal, ...]
    high: tuple[Decimal, ...]
    inside: tuple[int, ...]
    tested: int


def backtest(
    values: Iterable[Decimal], *, season: int, horizon: int, candidates: Iterable[str]
) -> Backtest | NoData:
    values, candidates = tuple(values), tuple(candidates)
    if type(season) is not int or season < 1 or type(horizon) is not int or horizon < 1:
        raise ValueError("positive season and horizon required")
    if not candidates or any(
        type(c) is not str or c not in CANDIDATES for c in candidates
    ):
        raise ValueError("unknown candidate")
    if values:
        history(values)
    with localcontext(CALC_CONTEXT):
        first = max(2 * horizon, season + 1)
        origins = tuple(range(first, len(values) - horizon + 1))
        if len(origins) < MINIMUM_ORIGINS:
            return NoData("series_too_short")
        scale = sum(
            (abs(values[t] - values[t - season]) for t in range(season, len(values))),
            Decimal(0),
        ) / (len(values) - season)
        scores = []
        for model in candidates:
            errors = tuple(
                tuple(
                    values[origin + k] - prediction
                    for k, prediction in enumerate(
                        predict(values[:origin], model, season, horizon)
                    )
                )
                for origin in origins
            )
            mean = sum((abs(e) for row in errors for e in row), Decimal(0)) / (
                len(origins) * horizon
            )
            scores.append(
                CandidateResult(model, errors, mean / scale if scale else mean)
            )
        chosen = min(scores, key=lambda candidate: candidate.error)
        forecasts = predict(values, chosen.model, season, horizon)
        columns = tuple(tuple(row[k] for row in chosen.errors) for k in range(horizon))
        inside = tuple(
            sum(
                min(errors[:i] + errors[i + 1 :])
                <= error
                <= max(errors[:i] + errors[i + 1 :])
                for i, error in enumerate(errors)
            )
            for errors in columns
        )
        return Backtest(
            tuple(scores),
            chosen.model,
            scale,
            chosen.error,
            forecasts,
            tuple(
                point + min(errors)
                for point, errors in zip(forecasts, columns, strict=True)
            ),
            tuple(
                point + max(errors)
                for point, errors in zip(forecasts, columns, strict=True)
            ),
            inside,
            len(origins),
        )
