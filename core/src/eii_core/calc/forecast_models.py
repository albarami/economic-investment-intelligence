"""C30 candidate formulas; prefix-only fitting under the shared Decimal context."""

from collections.abc import Iterable
from decimal import Decimal, localcontext

from .public_series import CALC_CONTEXT, finite

CANDIDATE_VERSION = "c30-candidates-v1"
CANDIDATES = ("seasonal_naive", "drift", "simple_exponential_smoothing")
ALPHAS = tuple(Decimal(f"0.{i}") for i in range(1, 10))


def history(values: Iterable[Decimal]) -> tuple[Decimal, ...]:
    values = tuple(values)
    for value in values:
        finite(value)
    if not values:
        raise ValueError("empty history")
    return values


def smoothing(
    values: Iterable[Decimal], alpha: Decimal
) -> tuple[tuple[Decimal, ...], Decimal]:
    values = history(values)
    finite(alpha)
    with localcontext(CALC_CONTEXT):
        if not 0 < alpha < 1:
            raise ValueError("invalid alpha")
        levels = [values[0]]
        error = Decimal(0)
        for value in values[1:]:
            error += (value - levels[-1]) ** 2
            levels.append(alpha * value + (1 - alpha) * levels[-1])
        return tuple(levels), error


def best_alpha(values: Iterable[Decimal]) -> Decimal:
    values = history(values)
    with localcontext(CALC_CONTEXT):
        return min(ALPHAS, key=lambda alpha: smoothing(values, alpha)[1])


def predict(
    values: Iterable[Decimal], model: str, season: int, horizon: int
) -> tuple[Decimal, ...]:
    values = history(values)
    if type(model) is not str or model not in CANDIDATES:
        raise ValueError("unknown candidate")
    if type(season) is not int or season < 1 or type(horizon) is not int or horizon < 1:
        raise ValueError("positive season and horizon required")
    with localcontext(CALC_CONTEXT):
        if model == "seasonal_naive":
            if len(values) < season:
                raise ValueError("season exceeds history")
            return tuple(values[-season + (k % season)] for k in range(horizon))
        if model == "drift":
            if len(values) < 2:
                raise ValueError("drift requires two values")
            return tuple(
                values[-1] + k * (values[-1] - values[0]) / (len(values) - 1)
                for k in range(1, horizon + 1)
            )
        level = smoothing(values, best_alpha(values))[0][-1]
        return (level,) * horizon
