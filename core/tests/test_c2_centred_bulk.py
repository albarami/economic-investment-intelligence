"""Invented, hand-computable C2 windows for decision 0078 (S2-T50)."""

from decimal import ROUND_DOWN, Decimal, localcontext
from statistics import median

import pytest

from eii_core.calc.public_series import C2_CALENDAR, CALC_CONTEXT, bulk_months

D = Decimal


def test_centred_window_distinguishes_a_level_change_from_a_bulk_month():
    # Global median = 2: all sixty late months would exceed 6. In each local
    # window the median is its own level (2 or 20), including at the step.
    rows = {month: D(2 if i < 65 else 20) for i, month in enumerate(C2_CALENDAR)}
    assert bulk_months(rows) == ()


@pytest.mark.parametrize("reverse", [False, True], ids=["left", "right"])
def test_asymmetric_window_edges_have_exact_pinned_medians(reverse: bool):
    # Offsets -7..+7. Inside -6..+6, sorted values are
    # 1,2,3,4,5,6,10,20,21,22,23,24,31: median 10, threshold 30.
    # Adding the outside 25 or dropping the inside 1 gives median 15,
    # threshold 45. Mirroring puts these discriminating cells on the right.
    values = (25, 1, 2, 3, 4, 5, 6, 31, 10, 20, 21, 22, 23, 24, 7)
    if reverse:
        values = values[::-1]
    candidate = 60
    rows = {month: D(10) for month in C2_CALENDAR}
    rows.update(
        (C2_CALENDAR[candidate + offset], D(value))
        for offset, value in zip(range(-7, 8), values, strict=True)
    )
    with localcontext(CALC_CONTEXT):
        assert median(D(value) for value in values[1:-1]) == D(10)
        widened = values[1:] if reverse else values[:-1]
        narrowed = values[1:-2] if reverse else values[2:-1]
        assert median(D(value) for value in widened) == D(15)
        assert median(D(value) for value in narrowed) == D(15)
    assert bulk_months(rows) == (C2_CALENDAR[candidate],)


@pytest.mark.parametrize("reverse", [False, True], ids=["start", "end"])
def test_window_is_cut_at_both_calendar_ends(reverse: bool):
    # At the first month the seven-cell window is 31,1,2,3,10,20,21:
    # median 10, so 31 is flagged. Padding with zeros or wrapping is wrong.
    # At the second month the eight-cell window has middle values 3 and 10:
    # median 6.5, so 20 is flagged. Taking the upper middle loses that flag.
    values = (31, 20, 1, 2, 3, 10, 21, 0)
    months = C2_CALENDAR[::-1] if reverse else C2_CALENDAR
    rows = {month: D(10) for month in C2_CALENDAR}
    rows.update(
        (month, D(value))
        for month, value in zip(months[: len(values)], values, strict=True)
    )
    expected = (months[0], months[1])
    assert bulk_months(rows) == tuple(sorted(expected))


def test_even_window_uses_the_mean_of_both_middle_values():
    # Month 2 sees eight values: sorted 1,2,3,4,10,11,12,20.
    # Median = (4+10)/2 = 7, threshold = 21; 20 must not be flagged.
    rows = {month: D(10) for month in C2_CALENDAR}
    values = (1, 20, 2, 3, 4, 10, 11, 12)
    rows.update(
        (month, D(value))
        for month, value in zip(C2_CALENDAR[: len(values)], values, strict=True)
    )
    assert C2_CALENDAR[1] not in bulk_months(rows)


def test_equality_is_not_bulk_and_one_more_is_bulk():
    rows = {month: D(10) for month in C2_CALENDAR}
    rows["2020-01"] = D(30)
    assert bulk_months(rows) == ()
    rows["2020-01"] = D(31)
    assert bulk_months(rows) == ("2020-01",)


def test_flat_series_and_single_spike():
    rows = {month: D(10) for month in C2_CALENDAR}
    assert bulk_months(rows) == ()
    rows["2020-01"] = D(100)
    assert bulk_months(rows) == ("2020-01",)


def test_absent_months_count_as_zero_and_undated_is_refused():
    # Six omitted neighbours on either side give median zero.
    assert bulk_months({"2020-01": D(1)}) == ("2020-01",)
    with pytest.raises(ValueError, match="invalid cancellation month/count"):
        bulk_months({"UNDATED": D(1)})


@pytest.mark.parametrize("value", [D(-1), D("1.5")])
def test_negative_and_fractional_counts_still_refuse(value: Decimal):
    with pytest.raises(ValueError, match="invalid cancellation month/count"):
        bulk_months({"2020-01": value})


def test_even_window_is_independent_of_the_callers_decimal_context():
    rows = {month: D(10) for month in C2_CALENDAR}
    values = (1, 20, 2, 3, 4, 10, 11, 12)
    rows.update(
        (month, D(value))
        for month, value in zip(C2_CALENDAR[: len(values)], values, strict=True)
    )
    with localcontext() as context:
        context.prec = 1
        context.rounding = ROUND_DOWN
        assert C2_CALENDAR[1] not in bulk_months(rows)
