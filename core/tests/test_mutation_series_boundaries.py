"""Invented literal regressions for surviving series mutations."""

from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction

import pytest
from method_rows import chain
from test_public_series_calc import cell

from eii_core.calc import public_series as s


@pytest.mark.parametrize(
    "call,reason",
    [
        (lambda: s.finite(D("NaN")), "finite Decimal required"),
        (lambda: s.count(-1), "non-negative integer count required"),
        (lambda: s.ratio(D(1), D(0)), "non-positive denominator"),
        (
            lambda: s.growth(D(1), D(2), partial_year=True),
            "partial year cannot be compared",
        ),
        (lambda: s.weighted_mean({"invented": (D(-1), D(1))}), "invalid group cell"),
        (lambda: s._kitagawa({"invented": (D(1), D(1))}, {}), "different groups"),
        (lambda: s.decomposition({}, {}), "invalid group cell"),
        (lambda: s.unit_value([(D(-1), D(1), "kg")]), "negative import value"),
        (lambda: s.bulk_months({"2025-06": D(1)}), "invalid cancellation month/count"),
    ],
    ids=[
        "finite",
        "count",
        "denominator",
        "partial",
        "group",
        "groups",
        "empty",
        "import",
        "calendar",
    ],
)
def test_series_exact_refusals(call, reason):
    with pytest.raises(ValueError) as error:
        call()
    assert str(error.value) == reason


def test_decimal_decomposition_full_result():
    assert s.decomposition(
        {"invented_a": (D(3), D(10)), "invented_b": (D(1), D(30))},
        {"invented_a": (D(1), D(14)), "invented_b": (D(3), D(34))},
    ) == {
        "mean_before": D(15),
        "mean_after": D(29),
        "change": D(14),
        "within": D(4),
        "mix": D(10),
        "groups": D(2),
        "fixed_composition_change": D(4),
    }


@pytest.mark.parametrize("bad", [(D(1), 1), (1, D(1))])
def test_mixed_decimal_group_refused(bad):
    with pytest.raises(ValueError) as error:
        s.decomposition({"invented": (D(1), D(1))}, {"invented": bad})
    assert str(error.value) == "invalid group cell"


@pytest.mark.parametrize(
    "bad",
    [
        {1: cell(1, 1, "2020")},
        {"invented": list(cell(1, 1, "2020"))},
        {"invented": (*cell(1, 1, "2020"), D(1))},
        {"invented": (cell(1, 1, "2020")[0], D(1))},
        {"invented": (1, cell(1, 1, "2020")[1])},
    ],
)
def test_typed_group_shape_refused(bad):
    with pytest.raises(ValueError) as error:
        s.decomposition(bad, {"invented": cell(1, 1, "2025")})
    assert str(error.value) == "invalid group cell"


@pytest.mark.parametrize(
    "index,changes,reason",
    [
        (0, {"unit": "qar"}, "unit mismatch"),
        (1, {"unit": "qar"}, "unit mismatch"),
        (1, {"period": "2021"}, "period mismatch"),
        (
            1,
            {"geography": "zone:invented", "geography_kind": "public"},
            "geography mismatch",
        ),
    ],
)
def test_group_alignment_refusals(index, changes, reason):
    pair = list(cell(1, 1, "2020"))
    pair[index] = replace(pair[index], **changes)
    with pytest.raises(ValueError) as error:
        s.decomposition({"invented": tuple(pair)}, {"invented": cell(1, 1, "2025")})
    assert str(error.value) == reason


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"period": "2020"}, "period mismatch"),
        (
            {"geography": "zone:invented", "geography_kind": "public"},
            "geography mismatch",
        ),
    ],
)
def test_between_year_alignment_refusals(changes, reason):
    after = tuple(replace(x, **changes) for x in cell(1, 1, "2025"))
    with pytest.raises(ValueError) as error:
        s.decomposition({"invented": cell(1, 1, "2020")}, {"invented": after})
    assert str(error.value) == reason


def test_decomposition_metadata_and_independent_percentages():
    first = cell(1, 1, "2020")
    first = (replace(first[0], sources=(chain("invented_workers"),)), first[1])
    result = s.decomposition({"invented": first}, {"invented": cell(1, 2, "2025")})
    expected = {
        "mean_before": "1",
        "mean_after": "2",
        "change": "1",
        "within": "1",
        "mix": "0",
        "fixed_composition_change": "1",
        "mix_share_percent": "0.0",
        "fixed_composition_percent": "100.0",
        "change_percent": "100.0",
        "populated_groups": "1",
    }
    for key, value in expected.items():
        fact = result[key]
        assert str(fact.value) == value
        assert fact.metric_key == ("mix_share" if key == "mix_share_percent" else key)
        assert fact.release_id == "published"
        assert fact.period == ("2020" if key == "mean_before" else "2025")
        assert chain("invented_workers") in fact.sources
        if key != "populated_groups":
            assert fact.base_geography == "national"
            assert fact.base_geography_kind == "national"


def test_population_counts_use_workers_in_either_year():
    before = {
        "invented_a": cell(1, 0, "2020"),
        "invented_b": cell(0, 5, "2020"),
        "invented_c": cell(1, 2, "2020"),
    }
    after = {
        "invented_a": cell(0, 5, "2025"),
        "invented_b": cell(1, 0, "2025"),
        "invented_c": cell(1, 2, "2025"),
    }
    assert s.decomposition(before, after)["populated_groups"].value == D(3)


def test_unit_value_accumulates_all_rows_and_accepts_zero():
    assert s.unit_value(
        [
            (D(0), D(1), "kg"),
            (D(12), D(2), "kg"),
            (D(8), D(1), "kg"),
            (D(2), D(0), "kg"),
            (D(2), D(-1), "kg"),
            (D(2), D(1), "litre"),
            (D(2), D(1), "litre"),
        ]
    ) == (D(5), 2, 2)
    assert s.bulk_months({"2015-01": D(0)}) == ()


def test_series_working_precision_and_half_up():
    from decimal import ROUND_DOWN, localcontext

    midpoint = D("1." + "0" * 49 + "5")
    rounded_midpoint = Fraction(midpoint)
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        assert s.ratio(D(1), D(3)) == Fraction(1, 3)
        assert s.ratio(midpoint, D(1)) == rounded_midpoint
        assert s.growth(D(3), D(1)) == Fraction(-200, 3)
        assert s.weighted_mean({"invented": (D(1), midpoint)}) == (
            D(1),
            rounded_midpoint,
        )
        assert s.unit_value([(midpoint, D(1), "kg")]) == (rounded_midpoint, 0, 0)
        assert s.unit_value([(D(1), D(3), "kg")]) == (Fraction(1, 3), 0, 0)
        assert s.rounded(D("1." + "2" * 48), 48) == "1." + "2" * 48
    assert s.rounded(D("1." + "2" * 50), 50) == "1." + "2" * 50
    exact = s._kitagawa({"invented": (D(1), D(1))}, {"invented": (D(1), midpoint)})
    assert exact["fixed_composition_mean_unrounded"] == rounded_midpoint
    assert exact["fixed_composition_change_unrounded"] == Fraction(5, 10**50)


def test_kitagawa_identity_guard_at_and_above_tolerance(monkeypatch):
    # Plant an inconsistent mean to exercise the arithmetic identity guard.
    monkeypatch.setattr(s, "weighted_mean", lambda groups: (D(1), D(0)))
    before = {"invented": (D(1), D(0))}
    with pytest.raises(ValueError, match=r"within \+ mix != change"):
        s._kitagawa(before, {"invented": (D(1), D("1E-20"))})
    with pytest.raises(ValueError) as error:
        s._kitagawa(before, {"invented": (D(1), D("2E-20"))})
    assert str(error.value) == "within + mix != change"


def test_bulk_threshold_working_precision_half_up():
    from decimal import ROUND_DOWN, localcontext

    baseline = D("1" + "0" * 48 + "15")
    rows = {f"{2015 + i // 12}-{i % 12 + 1:02}": baseline for i in range(125)}
    rows["2025-05"] = D("3" + "0" * 48 + "50")
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        assert s.bulk_months(rows) == ()


def test_mix_share_keeps_fifty_digit_unrounded_value():
    from decimal import ROUND_DOWN, localcontext

    before = {"invented_a": cell(1, 0, "2020"), "invented_b": cell(1, 2, "2020")}
    after = {"invented_a": cell(1, 1, "2025"), "invented_b": cell(3, 3, "2025")}
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        result = s.decomposition(before, after)
    assert str(result["mix_share_percent"].exact_unrounded) == str(Fraction(100, 3))


def test_growth_half_up_when_subtraction_adds_a_digit():
    value = D("-9." + "0" * 47 + "05")
    assert s.growth(D(1), value) == Fraction(D("-1000." + "0" * 46 + "5"))


def test_worker_sum_has_declared_working_precision():
    assert s.weighted_mean({"invented": (D("1" + "0" * 49 + "1"), D(0))}) == (
        Fraction(10**50 + 1),
        D(0),
    )


def test_mix_share_ignores_decimal_default_rounding(monkeypatch):
    from decimal import ROUND_UP, DefaultContext

    monkeypatch.setattr(DefaultContext, "rounding", ROUND_UP)
    before = {"invented_a": cell(1, 0, "2020"), "invented_b": cell(1, 2, "2020")}
    after = {"invented_a": cell(1, 1, "2025"), "invented_b": cell(3, 3, "2025")}
    result = s.decomposition(before, after)
    assert str(result["mix_share_percent"].exact_unrounded) == str(Fraction(100, 3))
