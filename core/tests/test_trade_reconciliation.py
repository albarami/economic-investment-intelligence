"""Invented trade figures, exact gaps and compatibility refusals."""

from dataclasses import replace

import pytest


def figure():
    from eii_core.calc.trade_reconciliation import TradeFigure

    return TradeFigure(
        input_id="invented-left",
        source_id="invented-source",
        source_version="invented-v1",
        role="reporter",
        partner="invented-partner",
        flow="import",
        year=2020,
        periods=("2020",),
        classification="invented-class",
        hs_revision="invented-revision",
        product_scope="invented-scope",
        coverage_key="invented-complete",
        currency="invented-currency",
        unit="invented-unit",
        scale="invented-scale",
        valuation_basis="invented-basis",
        value="12.25",
        lineage=("invented-receipt-row",),
    )


def test_mixed_valuation_refuses_gap():
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    left = figure()
    result = compare_trade_sources(
        left, replace(left, input_id="invented-right", valuation_basis="other")
    )
    assert result.gap is None
    assert "valuation_basis" in result.mismatch_codes


def test_exact_gap():
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    left = figure()
    result = compare_trade_sources(
        left, replace(left, input_id="invented-right", value="17.5")
    )
    assert result.gap == "5.25"


@pytest.mark.parametrize(
    "field",
    [
        "partner",
        "flow",
        "year",
        "periods",
        "classification",
        "hs_revision",
        "product_scope",
        "coverage_key",
        "currency",
        "unit",
        "scale",
        "valuation_basis",
    ],
)
def test_each_mismatch(field):
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    left = figure()
    value = (
        2021
        if field == "year"
        else ("2021",)
        if field == "periods"
        else "invented-other"
    )
    result = compare_trade_sources(
        left, replace(left, input_id="invented-right", **{field: value})
    )
    assert result.gap is None
    assert field in result.mismatch_codes


def test_missing_not_zero_and_unknown_not_equal():
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    assert compare_trade_sources(figure(), None).gap is None
    left = replace(figure(), valuation_basis="unknown")
    assert (
        compare_trade_sources(left, replace(left, input_id="invented-right")).gap
        is None
    )


def test_annual_sum_exact_complete_and_incomplete():
    from eii_core.calc.trade_reconciliation import annual_trade_sum

    items = tuple(
        replace(
            figure(),
            input_id=f"invented-{month}",
            periods=(f"2020-{month:02}",),
            value="0.1",
        )
        for month in range(1, 13)
    )
    result = annual_trade_sum(items, output_id="invented-annual")
    assert result.value == "1.2"
    assert result.figure_kind == "calculated"
    assert len(result.lineage) == 12
    with pytest.raises(ValueError, match="annual_coverage"):
        annual_trade_sum(items[:-1], output_id="invented-annual")
    with pytest.raises(ValueError, match="annual_coverage"):
        annual_trade_sum((*items, items[0]), output_id="invented-annual")


def test_all_pair_annual_inputs_resolve():
    from eii_core.calc.trade_reconciliation import all_pairs, comparison_figures

    rows = tuple(
        replace(
            figure(), input_id=f"invented-{m}", periods=(f"2020-{m:02}",), value="0.1"
        )
        for m in range(1, 13)
    )
    prepared = comparison_figures(rows)
    assert len(prepared) == 13
    assert prepared[-1].value == "1.2"
    result = all_pairs(
        prepared,
        (("invented-source", "reporter"), ("invented-other", "mirror")),
        ("invented-partner",),
        (2020,),
        ("import",),
        ("invented-scope",),
    )
    assert result[0].left_input_id in {r.input_id for r in prepared}
    assert len(comparison_figures(rows[:-1])) == 11


def test_all_pairs_incomplete_calendar_is_explicit():
    from eii_core.calc.trade_reconciliation import all_pairs

    rows = (replace(figure(), periods=("2020-01",)),)
    result = all_pairs(
        rows,
        (("invented-source", "reporter"), ("invented-other", "mirror")),
        ("invented-partner",),
        (2020,),
        ("import",),
        ("invented-scope",),
    )
    assert "incomplete_calendar" in result[0].mismatch_codes


@pytest.mark.parametrize("value", ["12,5", "1e5", "+1", ".5", "1.", "", 1])
def test_decimal_format_plant(value):
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    assert compare_trade_sources(figure(), figure()).gap == "0"
    with pytest.raises(ValueError, match=r"^decimal_format$"):
        compare_trade_sources(figure(), replace(figure(), value=value))


def test_nonterminating_plant():
    from fractions import Fraction

    from eii_core.calc.trade_reconciliation import _text

    assert _text(Fraction(1, 2)) == "0.5"
    with pytest.raises(ValueError, match=r"^nonterminating$"):
        _text(Fraction(1, 3))


@pytest.mark.parametrize("side", ["left", "right"])
def test_lineage_plant(side):
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    rows = [figure(), figure()]
    assert compare_trade_sources(*rows).gap == "0"
    rows[0 if side == "left" else 1] = replace(figure(), lineage=())
    with pytest.raises(ValueError, match=r"^lineage_missing$"):
        compare_trade_sources(*rows)


@pytest.mark.parametrize("side", ["left", "right"])
def test_source_missing_plant(side):
    from eii_core.calc.trade_reconciliation import compare_trade_sources

    rows = [figure(), figure()]
    assert compare_trade_sources(*rows).gap == "0"
    rows[0 if side == "left" else 1] = replace(figure(), value=None)
    result = compare_trade_sources(*rows)
    assert result.mismatch_codes == ("source_missing",)
    assert result.gap is None


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("currency", "invented-other", "annual_compatibility"),
        ("currency", "unknown", "annual_compatibility"),
        ("value", None, "annual_coverage"),
        ("figure_kind", "calculated", "annual_coverage"),
        ("lineage", (), "annual_coverage"),
    ],
    ids=["currency", "unknown", "missing", "calculated", "lineage"],
)
def test_annual_row_plants(field, value, reason):
    from eii_core.calc.trade_reconciliation import annual_trade_sum

    rows = [
        replace(
            figure(), input_id=f"invented-{m}", periods=(f"2020-{m:02}",), value="0.1"
        )
        for m in range(1, 13)
    ]
    assert annual_trade_sum(tuple(rows), output_id="invented-annual").value == "1.2"
    rows[-1] = replace(rows[-1], **{field: value})
    with pytest.raises(ValueError, match=rf"^{reason}$"):
        annual_trade_sum(tuple(rows), output_id="invented-annual")


@pytest.mark.parametrize("currency", ["", "unknown"])
def test_annual_unknown_currency(currency):
    from eii_core.calc.trade_reconciliation import annual_trade_sum

    rows = tuple(
        replace(
            figure(), input_id=f"invented-{m}", periods=(f"2020-{m:02}",), value="0.1"
        )
        for m in range(1, 13)
    )
    assert annual_trade_sum(rows, output_id="invented-annual").value == "1.2"
    with pytest.raises(ValueError, match=r"^annual_compatibility$"):
        annual_trade_sum(
            tuple(replace(row, currency=currency) for row in rows),
            output_id="invented-annual",
        )
