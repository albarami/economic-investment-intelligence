"""S6-T27 plants: invented values only; no Public cache; prefix-last functions here are named test doubles."""

import sys
from dataclasses import replace
from decimal import Decimal, getcontext, localcontext
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.forecast_spike.backtest import (
    Predictor,
    Run,
    run,
    stage_verdict,
    strict_beat,
)
from evals.forecast_spike.contract import (
    AUTOS,
    BASELINES,
    COMBINATION,
    POLICY,
    Family,
    Registration,
    SeriesSpec,
    calibration_minimum,
    first_origin,
    level,
    number,
)

D = Decimal
FAMILY = Family(
    "syn-series", "year", "count", "count", "none", "none", "none", "generated"
)


def spec(
    key: str = "syn-a", *, length: int = 28, family: Family = FAMILY
) -> SeriesSpec:
    start = 13 + 9 if family.frequency == "month" else 6
    if family.frequency == "quarter":
        start = 9
    return SeriesSpec(
        key,
        family,
        tuple(range(length)),
        tuple(range(start, length)),
        "syn-geography",
        "syn-category",
        "invented-fixture-v1",
    )


def generated(length: int = 28) -> tuple[Decimal, ...]:
    return tuple(D(10 + 2 * i + i % 3) for i in range(length))


def prefix_last_test_doubles() -> dict[str, Predictor]:
    return {name: lambda prefix, _season: prefix[-1] for name in AUTOS}


def execute(
    registration: Registration | None = None,
    values: dict[str, tuple[Decimal, ...]] | None = None,
    supplied: dict[str, Predictor] | None = None,
) -> Run:
    registration = registration or Registration((spec(),))
    return run(
        registration,
        values or {"syn-a": generated()},
        prefix_last_test_doubles() if supplied is None else supplied,
        expected_registration_sha256=registration.sha256,
    )


def present(value: Decimal | None) -> Decimal:
    assert value is not None
    return value


@pytest.mark.parametrize(
    "frequency,expected",
    [("year", Fraction(4, 5)), ("quarter", Fraction(4, 5)), ("month", Fraction(9, 10))],
)
def test_preregistered_exact_levels(frequency: str, expected: Fraction) -> None:
    assert level(frequency) == expected
    assert calibration_minimum(expected) == (9 if frequency == "month" else 4)


def test_registration_hash_changes_with_targets_and_membership() -> None:
    registration = Registration((spec(),))
    assert len(registration.sha256) == 64
    changed = replace(spec(), targets=spec().targets[:-1])
    assert registration.sha256 != replace(registration, series=(changed,)).sha256


def test_changed_preregistration_cannot_reuse_old_hash() -> None:
    original = Registration((spec(),))
    changed = replace(original, seed=28)
    with pytest.raises(ValueError, match="registration_hash"):
        run(
            changed,
            {"syn-a": generated()},
            prefix_last_test_doubles(),
            expected_registration_sha256=original.sha256,
        )


def test_f1_scale_and_weights_do_not_use_evaluation_values() -> None:
    registration = Registration((spec(), spec("syn-b")))
    first = execute(registration, {"syn-a": generated(), "syn-b": generated()})
    changed = generated()[:6] + (D(800),) * 22
    second = execute(registration, {"syn-a": changed, "syn-b": generated()})
    assert [(r.spec.key, r.scale) for r in first.series] == [
        (r.spec.key, r.scale) for r in second.series
    ]
    assert first.series[0].scale == D(3)  # Initial two observations: 10, 13.
    assert first.registration_sha256 == second.registration_sha256
    assert first.input_sha256 != second.input_sha256


def test_f2_f3_suffix_change_preserves_earlier_policy_and_interval() -> None:
    original = execute()
    changed = generated()[:14] + (D(900),) * 14
    revised = execute(values={"syn-a": changed})
    for left, right in zip(original.series, revised.series, strict=True):
        earlier = tuple(row for row in left.origins if row.origin <= 14)
        later = tuple(row for row in right.origins if row.origin <= 14)
        # The target at origin 14 changes, but its fit/selection/interval cannot.
        assert tuple(replace(row, error=None, target=D(0)) for row in earlier) == tuple(
            replace(row, error=None, target=D(0)) for row in later
        )


def test_nested_selection_uses_matured_errors_and_own_residuals() -> None:
    result = execute()
    policy = next(row for row in result.series if row.candidate == POLICY)
    fixed = {row.candidate: row for row in result.series}
    for index, row in enumerate(policy.origins):
        for name, errors in row.selection_errors:
            assert errors == tuple(
                r.error.copy_abs()
                for r in fixed[name].origins[:index]
                if r.error is not None
            )
        if index >= 4:
            with localcontext() as context:
                context.prec = 50
                radius = sorted(
                    abs(r.error) for r in policy.origins[:index] if r.error is not None
                )[((index + 1) * 4 + 4) // 5 - 1]
                assert row.low == present(row.prediction) - radius
                assert row.high == present(row.prediction) + radius


def test_frozen_candidates_combination_and_prefix_only_fits() -> None:
    seen: list[int] = []

    def fit(prefix: tuple[Decimal, ...], _season: int) -> Decimal:
        seen.append(len(prefix))
        return prefix[-1]

    result = execute(supplied={name: fit for name in AUTOS})
    assert seen and max(seen) == 27 and min(seen) == 2
    assert {row.candidate for row in result.series} == set(
        BASELINES + AUTOS + (COMBINATION, POLICY)
    )
    fixed = {row.candidate: row for row in result.series}
    for index, row in enumerate(fixed[COMBINATION].origins):
        assert (
            row.prediction
            == sum(
                (present(fixed[name].origins[index].prediction) for name in AUTOS), D(0)
            )
            / 3
        )


def test_conformal_uses_exact_order_statistic_and_previous_errors() -> None:
    result = execute()
    naive = next(row for row in result.series if row.candidate == "seasonal_naive")
    assert naive.origins[3].low is None
    row = naive.origins[4]
    radius = max(abs(present(r.error)) for r in naive.origins[:4])
    assert (row.low, row.high) == (
        present(row.prediction) - radius,
        present(row.prediction) + radius,
    )


def test_empty_evaluation_cannot_pass() -> None:
    result = execute(Registration((replace(spec(), targets=()),)))
    assert all(
        row.status == "insufficient" and row.evaluated == 0 for row in result.summaries
    )


def test_missing_predictions_cannot_pass_or_shrink_denominator() -> None:
    result = execute(supplied={})
    row = next(row for row in result.summaries if row.candidate == "auto_ets")
    assert row.status == "blocked" and row.expected == 22 and row.evaluated == 0
    assert not strict_beat(result, FAMILY, "auto_ets", "seasonal_naive")


def test_minimum_twelve_is_separate_from_c30_minimum() -> None:
    result = execute(Registration((spec(length=17),)), {"syn-a": generated(17)})
    assert all(
        row.status == "insufficient" and row.evaluated == 11 for row in result.summaries
    )
    short = Registration((spec(length=4),))
    with pytest.raises(ValueError, match="series_too_short"):
        execute(short, {"syn-a": generated(4)})


def test_cross_candidate_pooling_cannot_rescue_failed_coverage() -> None:
    supplied = prefix_last_test_doubles()
    supplied["auto_ets"] = lambda prefix, _season: prefix[-1] + D(10000)
    # A jump beyond all earlier errors produces a miss in the bad candidate.
    values = (*generated()[:27], D(20000))
    result = execute(values={"syn-a": values}, supplied=supplied)
    for summary in result.summaries:
        assert summary.expected == 22
        assert summary.evaluated == 22
        assert (summary.status == "pass") == (
            summary.covered * 5 >= 4 * summary.evaluated
        )
    assert len(result.summaries) == 8


def test_zero_scale_mae_is_separate_and_never_dimensionless() -> None:
    values = (D(10), D(10), *generated()[2:])
    result = execute(values={"syn-a": values})
    assert all(
        row.score is None and row.reason == "zero_scale" for row in result.summaries
    )
    assert all(row.zero_scale_mae[0][0] == "syn-a" for row in result.summaries)


def test_strict_beat_rejects_ties() -> None:
    result = execute()
    assert not strict_beat(result, FAMILY, "auto_ets", "seasonal_naive")


def test_three_of_four_coverage_cannot_pass_four_fifths() -> None:
    supplied = prefix_last_test_doubles()
    supplied["auto_ets"] = lambda prefix, _season: (
        prefix[-1] + 1 - (2 if len(prefix) >= 15 else 1)
    )
    values = tuple(D(10 + i) for i in range(18))
    result = execute(Registration((spec(length=18),)), {"syn-a": values}, supplied)
    bad = next(r for r in result.summaries if r.candidate == "auto_ets")
    assert (bad.covered, bad.evaluated, bad.status) == (9, 12, "fail")
    assert stage_verdict(result, FAMILY, "statistical") == "fail"


def test_stage_requires_every_auto_and_combination_to_strictly_beat() -> None:
    result = execute()
    assert stage_verdict(result, FAMILY, "statistical") == "fail"
    missing = execute(supplied={})
    assert stage_verdict(missing, FAMILY, "statistical") == "blocked"
    assert stage_verdict(missing, FAMILY, "challenger") == "blocked"


def test_initial_prefix_zero_scale_is_never_pooled_with_another_series() -> None:
    registration = Registration((spec(), spec("syn-b")))
    values = (D(10), D(10), *generated()[2:])
    result = execute(registration, {"syn-a": generated(), "syn-b": values})
    assert all(r.score is None and r.reason == "zero_scale" for r in result.summaries)


def test_empty_series_cannot_hide_inside_nonempty_family() -> None:
    registration = Registration((spec(), replace(spec("syn-b"), targets=())))
    result = execute(registration, {"syn-a": generated(), "syn-b": generated()})
    assert all(row.status == "insufficient" for row in result.summaries)


def test_challenger_needs_unambiguous_baseline_stage_first() -> None:
    result = execute()
    with pytest.raises(ValueError, match="unknown_stage"):
        stage_verdict(result, FAMILY, "unregistered")


def test_public_revision_break_cannot_be_stitched() -> None:
    row = replace(spec(), classifications=("HS-a",) * 14 + ("HS-b",) * 14)
    with pytest.raises(ValueError, match="classification_break"):
        execute(Registration((row,)))


def test_late_missing_prediction_is_not_an_outcome_dependent_exclusion() -> None:
    supplied = prefix_last_test_doubles()

    def missing(prefix: tuple[Decimal, ...], _season: int) -> Decimal:
        if len(prefix) == 26:
            raise ValueError("invented_missing_prediction")
        return prefix[-1]

    supplied["auto_ets"] = missing
    result = execute(supplied=supplied)
    bad = next(r for r in result.summaries if r.candidate == "auto_ets")
    assert bad.status == "blocked" and bad.expected == 22 and bad.evaluated < 22
    assert stage_verdict(result, FAMILY, "statistical") == "blocked"


def test_equal_series_weights_not_origin_weights() -> None:
    registration = Registration((spec(), spec("syn-b", length=20)))
    result = execute(registration, {"syn-a": generated(), "syn-b": generated(20)})
    summary = next(row for row in result.summaries if row.candidate == "seasonal_naive")
    with localcontext() as context:
        context.prec = 50
        scores = []
        for row in result.series:
            if row.candidate == "seasonal_naive":
                errors = [
                    abs(present(r.error))
                    for r in row.origins
                    if r.origin in row.spec.targets
                ]
                scores.append(sum(errors, D(0)) / len(errors) / row.scale)
        assert summary.score == sum(scores, D(0)) / 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "another"),
        ("unit", "qar"),
        ("classification", "HS-other"),
        ("provenance", "public"),
    ],
)
def test_family_strata_cannot_be_stitched(field: str, value: str) -> None:
    fields = {
        "source": FAMILY.source,
        "unit": FAMILY.unit,
        "classification": FAMILY.classification,
        "provenance": FAMILY.provenance,
    }
    fields[field] = value
    separate = replace(
        FAMILY,
        source=fields["source"],
        unit=fields["unit"],
        classification=fields["classification"],
        provenance=fields["provenance"],
    )
    registration = Registration((spec(), spec("syn-b", family=separate)))
    result = execute(registration, {"syn-a": generated(), "syn-b": generated()})
    assert len({row.family for row in result.summaries}) == 2


@pytest.mark.parametrize(
    "change",
    [
        "gap",
        "early_target",
        "duplicate_series",
        "duplicate_targets",
        "horizon",
        "minimum",
        "unknown_candidate",
        "baseline_drop",
        "version",
    ],
)
def test_invalid_contracts_refuse(change: str) -> None:
    row = spec()
    registration = Registration((row,))
    if change == "gap":
        registration = replace(
            registration, series=(replace(row, periods=(0, 2, *row.periods[2:])),)
        )
    elif change == "early_target":
        registration = replace(registration, series=(replace(row, targets=(2,)),))
    elif change == "duplicate_series":
        registration = replace(registration, series=(row, row))
    elif change == "duplicate_targets":
        registration = replace(registration, series=(replace(row, targets=(6, 6)),))
    elif change == "horizon":
        registration = replace(registration, horizon=2)
    elif change == "minimum":
        registration = replace(registration, minimum=0)
    elif change == "unknown_candidate":
        registration = replace(registration, candidates=(*BASELINES, "unknown"))
    elif change == "baseline_drop":
        registration = replace(registration, candidates=AUTOS)
    elif change == "version":
        registration = replace(registration, version="unreviewed")
    with pytest.raises(ValueError):
        registration.validate()


@pytest.mark.parametrize("value", [float("inf"), float("nan"), D("Infinity"), D("NaN")])
def test_nonfinite_outputs_refuse(value: Decimal | float) -> None:
    with pytest.raises(ValueError, match="finite"):
        number(value)


def test_lossless_float_conversion_and_context_independence() -> None:
    assert number(0.1) == D.from_float(0.1)
    with localcontext() as context:
        context.prec = 6
        low = execute()
    with localcontext() as context:
        context.prec = 70
        high = execute()
    assert low == high
    assert first_origin("year") == 2


def test_invented_real_shaped_swap_reuses_same_calculation_path() -> None:
    first = execute()
    second = execute(values={"syn-a": tuple(value + 2 for value in generated())})
    assert first.registration_sha256 == second.registration_sha256
    assert first.input_sha256 != second.input_sha256
    assert (
        present(first.series[0].origins[0].prediction) + 2
        == second.series[0].origins[0].prediction
    )


def test_predictor_cannot_change_shared_arithmetic_context() -> None:
    ordinary = execute()

    def contaminating(prefix: tuple[Decimal, ...], _season: int) -> Decimal:
        getcontext().prec = 6
        return prefix[-1]

    changed = execute(supplied={key: contaminating for key in AUTOS})
    assert changed == ordinary


def test_coverage_uses_original_target_instead_of_rounded_error_reconstruction() -> (
    None
):
    supplied = {key: lambda _prefix, _season: D("-1e60") for key in AUTOS}
    result = execute(supplied=supplied)
    bad = next(row for row in result.summaries if row.candidate == "auto_ets")
    assert bad.evaluated == 22 and bad.covered == 0 and bad.status == "fail"


@pytest.mark.parametrize("value", [1.0, "1", True])
def test_observations_require_exact_decimal_values(value: object) -> None:
    with pytest.raises(ValueError, match="decimal_observations"):
        run(
            Registration((spec(),)),
            {"syn-a": cast(tuple[Decimal, ...], (value,) * 28)},
            prefix_last_test_doubles(),
            expected_registration_sha256=Registration((spec(),)).sha256,
        )


@pytest.mark.parametrize("field", ["series", "candidates", "periods"])
def test_mutable_contract_collections_refuse(field: str) -> None:
    registration = Registration((spec(),))
    if field == "series":
        registration = replace(
            registration, series=cast(tuple[SeriesSpec, ...], list(registration.series))
        )
    elif field == "candidates":
        registration = replace(
            registration,
            candidates=cast(tuple[str, ...], list(registration.candidates)),
        )
    else:
        registration = replace(
            registration,
            series=(
                replace(spec(), periods=cast(tuple[int, ...], list(spec().periods))),
            ),
        )
    with pytest.raises(ValueError, match="immutable_contract"):
        registration.validate()
