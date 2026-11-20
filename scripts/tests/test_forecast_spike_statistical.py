"""Actual pinned Auto models and isolated output/prefix/thread guards."""

import importlib.metadata
import socket
from dataclasses import replace
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Protocol, cast
from unittest.mock import patch

import pytest
from evals.forecast_spike.backtest import run
from evals.forecast_spike.contract import (
    AUTOS,
    COMBINATION,
    Family,
    Registration,
    SeriesSpec,
)
from evals.forecast_spike.statistical import (
    StatisticalForecast,
    forecast,
    interval_level,
    predictors,
)


class SeasonalModel(Protocol):
    season_length: int


def test_library_pin_and_real_models_match_official_forecast_api() -> None:
    import numpy as np
    from statsforecast.models import AutoARIMA, AutoETS, AutoTheta

    assert importlib.metadata.version("statsforecast") == "2.1.1"
    values = tuple(Decimal(10 + 2 * i + i % 3) for i in range(24))
    for key, model in zip(AUTOS, (AutoETS, AutoTheta, AutoARIMA), strict=True):
        expected = model(season_length=4).forecast(
            y=np.array([float(v) for v in values]), h=1, level=[80]
        )
        with patch.object(
            socket, "socket", side_effect=AssertionError("network forbidden")
        ):
            result = forecast(key, values, "quarter")
        assert result == StatisticalForecast(
            Decimal.from_float(float(expected["mean"][0])),
            Decimal.from_float(float(expected["lo-80"][0])),
            Decimal.from_float(float(expected["hi-80"][0])),
        )
        assert result.low <= result.point <= result.high
        assert result.point != values[-1]  # The retired prefix-last test double.


@pytest.mark.parametrize(
    "frequency,expected", [("year", 80), ("quarter", 80), ("month", 90)]
)
def test_exact_library_interval_levels(frequency: str, expected: int) -> None:
    assert interval_level(frequency) == expected


def test_nonintegral_percentage_is_refused_without_rounding() -> None:
    with patch("evals.forecast_spike.statistical.level", return_value=Fraction(2, 3)):
        with pytest.raises(ValueError, match="lossless_interval_level"):
            interval_level("year")


@pytest.mark.parametrize("candidate", AUTOS)
@pytest.mark.parametrize(
    "frequency,season_length", [("year", 1), ("quarter", 4), ("month", 12)]
)
def test_library_receives_prefix_frequency_level_and_one_cpu_thread(
    candidate: str, frequency: str, season_length: int
) -> None:
    import numpy as np
    from statsforecast import models
    from threadpoolctl import (  # type: ignore[import-untyped]
        threadpool_info,
        threadpool_limits,
    )

    values = tuple(Decimal(i + 10) for i in range(24))
    cls = getattr(
        models,
        {"auto_ets": "AutoETS", "auto_theta": "AutoTheta", "auto_arima": "AutoARIMA"}[
            candidate
        ],
    )

    def inspect_call(
        self: object,
        *,
        y: np.ndarray[tuple[int], np.dtype[np.float64]],
        h: int,
        level: list[int],
    ) -> dict[str, object]:
        assert cast(SeasonalModel, self).season_length == season_length
        assert np.array_equal(y, np.array([float(v) for v in values]))
        assert h == 1
        assert level == [90 if frequency == "month" else 80]
        pools = threadpool_info()
        assert pools and all(pool["num_threads"] == 1 for pool in pools)
        return {
            "mean": np.array([0.1]),
            f"lo-{level[0]}": np.array([-0.1]),
            f"hi-{level[0]}": np.array([0.3]),
        }

    with threadpool_limits(limits=3), patch.object(cls, "forecast", new=inspect_call):
        result = forecast(candidate, values, frequency)
    assert result.point == Decimal.from_float(0.1)
    assert result.low == Decimal.from_float(-0.1)
    assert result.high == Decimal.from_float(0.3)


@pytest.mark.parametrize(
    "plant", ["unknown", "empty", "nan_input", "infinite_input", "float_overflow"]
)
def test_adapter_input_plants_refuse(plant: str) -> None:
    key = "unknown" if plant == "unknown" else "auto_ets"
    values = {
        "empty": (),
        "nan_input": (Decimal("NaN"),),
        "infinite_input": (Decimal("Infinity"),),
        "float_overflow": (Decimal("1e999"),),
    }.get(plant, (Decimal(1), Decimal(2)))
    with pytest.raises(ValueError):
        forecast(key, values, "year")


@pytest.mark.parametrize(
    "plant", ["missing", "nan", "infinity", "length", "reversed", "point_outside"]
)
def test_adapter_output_plants_refuse(plant: str) -> None:
    import numpy as np
    from statsforecast.models import AutoETS

    output = {
        "mean": np.array([0.1]),
        "lo-80": np.array([-0.1]),
        "hi-80": np.array([0.3]),
    }
    if plant == "missing":
        del output["lo-80"]
    elif plant == "nan":
        output["mean"] = np.array([np.nan])
    elif plant == "infinity":
        output["hi-80"] = np.array([np.inf])
    elif plant == "length":
        output["mean"] = np.array([0.1, 0.2])
    elif plant == "reversed":
        output["lo-80"] = np.array([0.5])
    else:
        output["mean"] = np.array([0.9])
    with patch.object(AutoETS, "forecast", return_value=output):
        with pytest.raises(ValueError):
            forecast("auto_ets", (Decimal(1), Decimal(2)), "year")


def test_real_model_suffix_plant_and_equal_weight_combination() -> None:
    from eii_core.calc.public_series import CALC_CONTEXT

    family = Family(
        "syn-prefix", "quarter", "count", "count", "none", "none", "none", "invented"
    )
    spec = SeriesSpec(
        "syn-prefix",
        family,
        tuple(range(18)),
        tuple(range(9, 18)),
        "syn-area",
        "syn-category",
        "invented-prefix-v1",
    )
    registration = Registration((spec,))
    values = tuple(Decimal(10 + 2 * i + i % 3) for i in range(18))
    changed = values[:12] + tuple(v * 9 for v in values[12:])
    original = run(
        registration,
        {spec.key: values},
        predictors(family.frequency),
        expected_registration_sha256=registration.sha256,
    )
    altered = run(
        registration,
        {spec.key: changed},
        predictors(family.frequency),
        expected_registration_sha256=registration.sha256,
    )
    for left, right in zip(original.series, altered.series, strict=True):
        assert left.scale == right.scale
        for a, b in zip(left.origins, right.origins, strict=True):
            if a.origin <= 12:
                assert replace(a, target=Decimal(0), error=None) == replace(
                    b, target=Decimal(0), error=None
                )
    rows = {r.candidate: r for r in original.series}
    with localcontext(CALC_CONTEXT):
        for i, combined in enumerate(rows[COMBINATION].origins):
            parts = [rows[key].origins[i].prediction for key in AUTOS]
            if any(p is None for p in parts):
                assert combined.prediction is None
                assert combined.refusal == "missing_prediction"
            else:
                assert (
                    combined.prediction
                    == sum((p for p in parts if p is not None), Decimal(0)) / 3
                )
        assert all(
            rows[key].origins[-1].prediction is not None
            for key in (*AUTOS, COMBINATION)
        )
    assert all(
        row.status == "blocked" and row.reason == "missing_prediction_or_interval"
        for row in original.summaries
        if row.candidate in ("auto_ets", COMBINATION, "nested_policy")
    )


@pytest.mark.parametrize("candidate", ["auto_ets", "auto_theta"])
def test_real_tiny_prefix_refuses_without_substituting_test_double(
    candidate: str,
) -> None:
    with pytest.raises(NotImplementedError, match="tiny datasets"):
        predictors("year")[candidate]((Decimal(10), Decimal(13)), 1)


def test_callback_rejects_wrong_family_season() -> None:
    with pytest.raises(ValueError, match="family_season_mismatch"):
        predictors("month")["auto_ets"]((Decimal(1), Decimal(2)), 4)


def test_unpinned_library_is_refused() -> None:
    with patch("evals.forecast_spike.statistical.version", return_value="0.0.0"):
        with pytest.raises(ValueError, match="statsforecast_pin"):
            forecast("auto_ets", (Decimal(1), Decimal(2)), "year")
