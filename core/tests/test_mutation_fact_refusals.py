"""Invented constructor and boundary cases; literal contract expectations."""

from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction

import pytest
from method_rows import chain, measure

from eii_core.calc import facts as f


def fact():
    return f.CalculationFact(
        D(1),
        "count",
        "invented",
        "published",
        "national",
        "2022",
        ("public",),
        (chain(),),
        geography_kind="national",
    )


def withheld():
    return f.WithheldInput(
        "invented",
        "published",
        "national",
        "national",
        "2022",
        "count",
        "invented_withheld",
        (chain(),),
    )


@pytest.mark.parametrize(
    "call,reason",
    [
        (lambda: f.least_real(()), "invalid input classes"),
        (lambda: f.least_real(("user_input",)), "release input class required"),
        (lambda: f.weakest_evidence(("invented",)), "invalid evidence status"),
        (lambda: f.weakest_evidence(()), "invalid evidence status"),
        (lambda: replace(chain(), publisher=""), "incomplete source chain"),
        (lambda: replace(chain(), licence="none"), "incomplete source chain"),
        (lambda: replace(chain(), url="invented"), "incomplete source chain"),
        (lambda: replace(chain(), sha256="invented"), "invalid source hash"),
        (lambda: replace(chain(), retrieved="2022-W01-1"), "invalid retrieval date"),
        (
            lambda: f.RegistrySource("", "p", "d", "l", "http://example.org"),
            "incomplete source chain",
        ),
        (
            lambda: f.RegistrySource("r", "p", "d", "l", "invented"),
            "incomplete source chain",
        ),
        (lambda: f.NoData("invented"), "unknown NO_DATA reason"),
        (lambda: f.Suppressed(""), "suppression reason required"),
        (lambda: f.Suppressed(1), "suppression reason required"),
        (lambda: f.Suppressed("invented", status="bad"), "invalid suppression"),
        (lambda: f._band(D(1), "wage_band"), "band value required"),
        (lambda: f._band("B01", "volume_band"), "unsupported comparison band"),
        (lambda: f._band("invented", "wage_band"), "invalid band"),
        (lambda: f._band("B02..B01", "wage_band"), "invalid band range"),
        (lambda: f.require_aligned(()), "missing metadata or lineage"),
        (lambda: f.require_aligned((None,)), "unit mismatch"),
        (lambda: f.require_aligned((measure(1),), unit="qar"), "unit mismatch"),
    ],
    ids=[str(index) for index in range(22)],
)
def test_named_refusals(call, reason):
    with pytest.raises(ValueError) as error:
        call()
    assert str(error.value) == reason


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"unit": "invented"}, "unsupported numeric unit"),
        ({"value": "1"}, "numeric value required"),
        ({"input_class": "invented"}, "invalid input classes"),
        ({"evidence_status": "invented"}, "invalid evidence status"),
        ({"input_class": "user_input"}, "user inputs must be inferred"),
        ({"sources": []}, "invalid source chain"),
        ({"sources": ()}, "invalid source chain"),
        ({"sources": (None,)}, "invalid source chain"),
        ({"period": ""}, "missing metadata or lineage"),
        ({"metric_key": ""}, "missing metadata or lineage"),
    ],
)
def test_measure_named_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        replace(measure(1), **changes)
    assert str(error.value) == reason


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"unit": "invented"}, "unsupported numeric unit"),
        ({"value": "1"}, "numeric value required"),
        ({"value": D("1.5")}, "fractional count"),
        ({"evidence_status": "invented"}, "invalid evidence status"),
        ({"input_classes": ("public", "user_input")}, "user inputs must be inferred"),
        ({"sources": []}, "invalid source chain"),
        ({"sources": ()}, "missing metadata or lineage"),
        ({"sources": (None,)}, "invalid source chain"),
        ({"period": ""}, "missing metadata or lineage"),
        ({"value": "invented", "unit": "direction"}, "invalid direction"),
    ],
)
def test_fact_named_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        replace(fact(), **changes)
    assert str(error.value) == reason


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"sources": []}, "invalid source chain"),
        ({"sources": ()}, "invalid source chain"),
        ({"sources": (None,)}, "invalid source chain"),
        ({"reason": ""}, "missing metadata or lineage"),
        ({"metric_key": ""}, "missing metadata or lineage"),
    ],
)
def test_withheld_named_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        replace(withheld(), **changes)
    assert str(error.value) == reason


def test_valid_http_bands_user_inputs_and_exception_fields():
    assert (
        replace(chain(), url="http://example.org/invented").url
        == "http://example.org/invented"
    )
    assert (
        f.RegistrySource("r", "p", "d", "l", "http://example.org").url
        == "http://example.org"
    )
    assert measure("B01", unit="wage_band").value == "B01"
    assert (
        measure(1, input_class="user_input", status="inferred").evidence_status
        == "inferred"
    )
    assert (
        replace(
            fact(), input_classes=("public", "user_input"), evidence_status="inferred"
        ).provenance
        == "public"
    )
    assert f.MeasureMismatch("unit").kind == "unit"
    assert f.WithdrawnProduction("production").derivation == "production"


@pytest.mark.parametrize("kind", ["release_units", "user_scenario", "area_shape"])
def test_minimum_geography_suffix(kind):
    f._geography(kind + ":x", kind)
    for value in (kind + ":", "invented:x"):
        with pytest.raises(f.MeasureMismatch) as error:
            f._geography(value, kind)
        assert str(error.value) == "geography mismatch"


def emission(**changes):
    arguments = dict(
        unit="qar",
        places=2,
        metric_key="invented",
        release_id="published",
        geography="national",
        geography_kind="national",
        period="2022",
        inputs=(measure(1, period="2022", geography="national", kind="national"),),
    )
    arguments.update(changes)
    return f.emit(D("1.25"), **arguments)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"inputs": ()}, "missing metadata or lineage"),
        (
            {"geography": "zone:invented", "geography_kind": "public"},
            "geography mismatch",
        ),
        ({"period": "2021..2021"}, "period mismatch"),
        ({"period": "2023..2021"}, "period mismatch"),
        ({"period": "2021"}, "period mismatch"),
        ({"base_period": "2021"}, "period mismatch"),
        (
            {"base_geography": "zone:invented", "base_geography_kind": "public"},
            "geography mismatch",
        ),
    ],
)
def test_emission_exact_refusals(changes, reason):
    with pytest.raises(ValueError) as error:
        emission(**changes)
    assert str(error.value) == reason


def test_emission_inclusive_window_and_defaults():
    for period in ("2022..2022", "2021..2022"):
        made = emission(period=period)
        assert made.value == D("1.25")
        assert made.release_id == "published"
        assert made.base_geography_kind == ""


@pytest.mark.parametrize(
    "left,right,reason",
    [
        (None, None, "both comparison inputs missing"),
        (
            replace(fact(), input_classes=("synthetic",)),
            fact(),
            "Public release inputs only",
        ),
        (fact(), replace(fact(), unit="qar"), "incompatible comparison"),
        (fact(), fact(), "incompatible period/geography"),
        (
            replace(fact(), unit="direction", value="equal"),
            replace(fact(), unit="direction", value="higher", period="2023"),
            "numeric comparison required",
        ),
    ],
)
def test_comparison_exact_refusals(left, right, reason):
    with pytest.raises(ValueError) as error:
        f.compare_public_facts(left, right)
    assert str(error.value) == reason


def test_missing_comparison_all_slots_and_context():
    for left, right in ((fact(), None), (None, fact())):
        result = f.compare_public_facts(left, right)
        for field in ("difference", "ratio", "direction"):
            assert getattr(result, field) == f.NoData("missing_input")
        assert result.sources == (chain(),)
        assert result.metric_key == "invented"
        assert result.before_geography == ("national" if left else "")
        assert result.before_geography_kind == ("national" if left else "")
        assert result.before_period == ("2022" if left else "")
        assert result.after_geography == ("national" if right else "")
        assert result.after_geography_kind == ("national" if right else "")
        assert result.after_period == ("2022" if right else "")


def test_band_comparison_metadata_and_touching_boundaries():
    first = replace(fact(), unit="wage_band", value="B01..B02")
    last = replace(first, value="B03", period="2023")
    result = f.compare_public_facts(first, last)
    assert result.metric_key == "invented"
    assert result.before_geography == "national"
    assert result.before_geography_kind == "national"
    assert result.before_period == "2022"
    assert result.after_geography == "national"
    assert result.after_geography_kind == "national"
    assert result.after_period == "2023"
    assert result.sources == (chain(),)
    assert result.direction.metric_key == "invented.direction"
    assert result.direction.value == "higher"
    for before, after in (("B01..B02", "B02..B03"), ("B02..B03", "B01..B02")):
        result = f.compare_public_facts(
            replace(first, value=before), replace(last, value=after)
        )
        assert result.direction == f.NoData("not_coverable")


def test_numeric_comparison_metadata_and_default_money_precision():
    first = replace(fact(), unit="qar", value=D("1.12"))
    last = replace(first, value=D("2.245"), period="2023")
    result = f.compare_public_facts(first, last)
    assert str(result.difference.value) == "1.13"
    assert str(result.ratio.value) == "2.00"
    for slot in ("difference", "ratio", "direction"):
        assert getattr(result, slot).metric_key == "invented." + slot
        assert getattr(result, slot).release_id == "published"
    rows = f._measures_from(first, last)
    assert rows[0].value == D("1.12")
    assert rows[0].unit == "qar"
    assert rows[0].metric_key == "invented"


def test_adjacency_mixed_period_types_return_false():
    assert f._adjacent("2024", "2025-01") is False
    assert f._adjacent("2024-12", "2025") is False


def test_measure_reconstruction_band_fallback():
    before = replace(fact(), value="B01", unit="wage_band")
    after = replace(before, value="B02", period="2023")
    rows = f._measures_from(before, after)
    assert tuple(row.value for row in rows) == (D(0), D(0))
    assert tuple(row.unit for row in rows) == ("count", "count")


def test_order_rejects_missing_numeric_ratio():
    change = f.compare_public_facts(fact(), replace(fact(), period="2023"))
    with pytest.raises(ValueError) as error:
        f.order_changes((replace(change, ratio_unrounded=None),))
    assert str(error.value) == "numeric ratio required"


def test_numeric_comparison_working_precision_and_rounding():
    from decimal import ROUND_UP, DefaultContext, localcontext

    before = replace(fact(), unit="qar", value=D(3))
    after = replace(before, period="2023", value=D(1))
    with localcontext() as context:
        context.prec = 6
        result = f.compare_public_facts(before, after)
    assert result.ratio_unrounded == Fraction(1, 3)
    original_rounding = DefaultContext.rounding
    try:
        DefaultContext.rounding = ROUND_UP
        assert f.compare_public_facts(before, after).ratio_unrounded == Fraction(1, 3)
    finally:
        DefaultContext.rounding = original_rounding


def test_order_uses_declared_precision_for_near_ties():
    from decimal import localcontext

    change = f.compare_public_facts(fact(), replace(fact(), value=D(2), period="2023"))
    pairs = (
        (
            replace(
                change,
                metric_key="invented_a",
                ratio_unrounded=D("2." + "1" * 49 + "1"),
            ),
            replace(
                change,
                metric_key="invented_z",
                ratio_unrounded=D("2." + "1" * 49 + "2"),
            ),
            ("invented_z", "invented_a"),
        ),
        (
            replace(change, metric_key="invented_a", ratio_unrounded=D(2)),
            replace(
                change,
                metric_key="invented_z",
                ratio_unrounded=D("2." + "0" * 49 + "5"),
            ),
            ("invented_z", "invented_a"),
        ),
    )
    for first, second, expected in pairs:
        with localcontext() as context:
            context.prec = 6
            assert (
                tuple(row.metric_key for row in f.order_changes((first, second)))
                == expected
            )
