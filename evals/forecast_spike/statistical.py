"""Pinned CPU Auto models, kept strictly inside the offline experiment."""

import math
import os
from dataclasses import dataclass
from decimal import Decimal
from importlib.metadata import version

from .backtest import Predictor
from .contract import AUTOS, level, number, season

# Set before the lazy numerical-library imports, also inherited by spawn workers.
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
for _variable in THREAD_VARIABLES:
    os.environ[_variable] = "1"


@dataclass(frozen=True)
class StatisticalForecast:
    point: Decimal
    low: Decimal
    high: Decimal


def interval_level(frequency: str) -> int:
    percentage = level(frequency) * 100
    if percentage.denominator != 1:
        raise ValueError("lossless_interval_level")
    return percentage.numerator


def _output(
    candidate: str, prefix: tuple[Decimal, ...], frequency: str
) -> tuple[float, float, float]:
    """Fit exactly the supplied prefix, always requesting the exact family level."""
    if candidate not in AUTOS or not prefix or type(prefix) is not tuple:
        raise ValueError("statistical_candidate_or_prefix")
    if any(type(v) is not Decimal for v in prefix):
        raise ValueError("decimal_observations_required")
    values = [float(number(v)) for v in prefix]
    if any(not math.isfinite(v) for v in values):
        raise ValueError("finite_float_input_required")
    if version("statsforecast") != "2.1.1":
        raise ValueError("statsforecast_pin")
    import numpy as np
    from statsforecast.models import AutoARIMA, AutoETS, AutoTheta
    from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

    model = {"auto_ets": AutoETS, "auto_theta": AutoTheta, "auto_arima": AutoARIMA}[
        candidate
    ](season_length=season(frequency))
    percentage = interval_level(frequency)
    with threadpool_limits(limits=1):
        output = model.forecast(
            y=np.array(values, dtype=np.float64), h=1, level=[percentage]
        )
    converted = []
    for key in ("mean", f"lo-{percentage}", f"hi-{percentage}"):
        if key not in output or np.shape(output[key]) != (1,):
            raise ValueError("statistical_output_shape")
        converted.append(float(output[key][0]))
    return converted[0], converted[1], converted[2]


def forecast(
    candidate: str, prefix: tuple[Decimal, ...], frequency: str
) -> StatisticalForecast:
    """Validate native intervals for adapter evidence, independently of conformal.

    A short training prefix can have a finite point but undefined native bounds.
    Such bounds are refused here. The harness needs only its finite point for
    prospective conformal residuals; it never consumes the native bounds.
    """
    point, low, high = (number(v) for v in _output(candidate, prefix, frequency))
    if not low <= point <= high:
        raise ValueError("statistical_interval_order")
    return StatisticalForecast(point, low, high)


def predictors(frequency: str) -> dict[str, Predictor]:
    expected_season = season(frequency)

    def callback(candidate: str) -> Predictor:
        def predict(prefix: tuple[Decimal, ...], season_length: int) -> Decimal:
            if season_length != expected_season:
                raise ValueError("family_season_mismatch")
            # Native bounds are intentionally separate: at early origins their
            # variance can be undefined even though the point is usable.
            return number(_output(candidate, prefix, frequency)[0])

        return predict

    return {key: callback(key) for key in AUTOS}
