"""Hand-checkable C30 candidates, prefix fitting and exact-type boundaries."""

from decimal import Decimal as D

import pytest

from eii_core.calc.forecast_models import ALPHAS, best_alpha, predict, smoothing


def test_each_formula_and_prefix():
    assert predict(map(D, (10, 12, 11)), "seasonal_naive", 2, 3) == (
        D(12),
        D(11),
        D(12),
    )
    assert predict(map(D, (10, 12, 11)), "drift", 1, 2) == (D("11.5"), D(12))
    assert predict(map(D, (10, 12)), "drift", 1, 1) == (D(14),)
    assert smoothing(map(D, (10, 12, 11)), D("0.5")) == ((D(10), D(11), D(11)), D(4))
    # Errors for alpha .1: 2, .8 -> 4.64; alpha .5: 2, 0 -> 4.
    assert smoothing(map(D, (10, 12, 11)), D("0.1"))[1] == D("4.64")
    assert best_alpha(map(D, (10, 12, 11))) == D("0.5")
    assert best_alpha(map(D, (10, 10, 10))) == D("0.1")
    assert predict(map(D, (10, 12, 11)), "simple_exponential_smoothing", 1, 2) == (
        D(11),
        D(11),
    )
    assert ALPHAS == tuple(D(f"0.{i}") for i in range(1, 10))


@pytest.mark.parametrize(
    "value", [1, True, 1.5, D("NaN"), D("Infinity"), type("SubDecimal", (D,), {})(1)]
)
def test_exact_finite_history(value):
    with pytest.raises(ValueError, match="finite Decimal"):
        predict((D(1), value), "drift", 1, 1)


@pytest.mark.parametrize(
    "model,season,horizon,values",
    [
        ("unknown", 1, 1, (D(1),)),
        (type("SubText", (str,), {})("drift"), 1, 1, (D(1), D(2))),
        ("drift", True, 1, (D(1), D(2))),
        ("drift", 0, 1, (D(1), D(2))),
        ("drift", 1, True, (D(1), D(2))),
        ("drift", 1, 0, (D(1), D(2))),
        ("drift", 1, 1, (D(1),)),
        ("seasonal_naive", 2, 1, (D(1),)),
        ("seasonal_naive", 1, 1, ()),
    ],
)
def test_invalid_model_inputs(model, season, horizon, values):
    with pytest.raises(ValueError):
        predict(values, model, season, horizon)


@pytest.mark.parametrize("alpha", [D(0), D(1), D(-1), D(2), 0.5])
def test_invalid_alpha(alpha):
    with pytest.raises(ValueError):
        smoothing((D(1), D(2)), alpha)
