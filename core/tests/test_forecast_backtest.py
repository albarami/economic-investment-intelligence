"""C30 hand-worked fixtures; no source records."""

from decimal import Decimal as D

from eii_core.calc.forecast_backtest import backtest
from eii_core.calc.public_series import rounded


def test_c30_worked_example():
    result = backtest(
        tuple(map(D, (10, 12, 11, 13, 14))),
        season=1,
        horizon=1,
        candidates=("seasonal_naive", "drift"),
    )
    assert result.scale == D("1.5")
    assert result.candidates[0].errors == ((D(-1),), (D(2),), (D(1),))
    assert rounded(result.candidates[0].error, 3) == "0.889"
    assert rounded(result.candidates[0].error, 2) == "0.89"
    assert result.candidates[1].error == D(1)
    assert result.model == "seasonal_naive"
    assert result.forecasts == (D(14),)
    assert result.low == (D(13),)
    assert result.high == (D(16),)
    assert result.inside == (1,)
    assert result.tested == 3


def test_minimum_ties_zero_scale_and_iterables():
    from eii_core.calc.facts import NoData

    for size in (0, 3, 4):
        assert backtest(
            (D(10) for _ in range(size)),
            season=1,
            horizon=1,
            candidates=("drift", "seasonal_naive"),
        ) == NoData("series_too_short")
    result = backtest(
        (D(10) for _ in range(5)),
        season=1,
        horizon=1,
        candidates=(c for c in ("drift", "seasonal_naive")),
    )
    assert result.model == "drift"
    assert result.scale == result.error == D(0)
    assert result.low == result.high == (D(10),)
    assert result.inside == (3,)
    assert result.tested == 3
    assert (
        backtest(
            [D(10)] * 5, season=1, horizon=1, candidates=["drift", "seasonal_naive"]
        )
        == result
    )


def test_horizons_and_seasonal_scale():
    from eii_core.calc.facts import NoData

    values = tuple(map(D, (2, 4, 6, 8, 10, 12, 14, 16)))
    result = backtest(
        values, season=2, horizon=2, candidates=("seasonal_naive", "drift")
    )
    assert result.scale == D(4)
    assert result.model == "drift"
    assert result.forecasts == (D(18), D(20))
    assert result.low == result.high == result.forecasts
    assert result.inside == (3, 3)
    assert result.tested == 3
    assert result.candidates[0].errors == ((D(4), D(4)),) * 3
    assert backtest(values[:-1], season=2, horizon=2, candidates=("drift",)) == NoData(
        "series_too_short"
    )


def test_backtest_rejects_invalid_inputs():
    import pytest

    for changes in (
        {"season": 0},
        {"season": True},
        {"horizon": 0},
        {"horizon": True},
        {"candidates": ()},
        {"candidates": ("unknown",)},
        {"values": (D("NaN"),)},
    ):
        args = (
            dict(values=(D(1),) * 5, season=1, horizon=1, candidates=("drift",))
            | changes
        )
        with pytest.raises(ValueError):
            backtest(**args)


def test_each_fit_sees_its_origin_prefix_only(monkeypatch):
    from eii_core.calc import forecast_backtest as module

    original = module.predict
    values = tuple(map(D, (10, 12, 11, 13, 99)))
    calls = []

    def recorded(prefix, model, season, horizon):
        calls.append((prefix, model))
        return original(prefix, model, season, horizon)

    monkeypatch.setattr(module, "predict", recorded)
    result = module.backtest(
        values, season=1, horizon=1, candidates=("seasonal_naive", "drift")
    )
    assert calls == [
        *(
            (values[:origin], model)
            for model in ("seasonal_naive", "drift")
            for origin in (2, 3, 4)
        ),
        (values, result.model),
    ]


def test_residual_columns_never_borrow_from_another_horizon():
    result = backtest(
        tuple(map(D, (2, 4, 3, 7, 5, 8, 9, 11))),
        season=1,
        horizon=2,
        candidates=("seasonal_naive",),
    )
    assert result.candidates[0].errors == ((D(-2), D(1)), (D(3), D(4)), (D(1), D(3)))
    assert result.forecasts == (D(11), D(11))
    assert result.low == (D(9), D(12))
    assert result.high == (D(14), D(15))
    assert result.inside == (1, 1)


def test_frequency_history_minimum_boundaries():
    from eii_core.calc.facts import NoData

    for season, minimum in ((1, 5), (4, 8), (12, 16)):
        assert backtest(
            (D(10),) * (minimum - 1),
            season=season,
            horizon=1,
            candidates=("seasonal_naive",),
        ) == NoData("series_too_short")
        assert (
            backtest(
                (D(10),) * minimum,
                season=season,
                horizon=1,
                candidates=("seasonal_naive",),
            ).tested
            == 3
        )
