"""Accepted monthly native periods are zero-padded and ordered as months."""

from dataclasses import replace

import pytest

from eii_core.calc.trade_reconciliation import annual_trade_sum

from .test_trade_reconciliation import figure


def test_unpadded_months_are_refused_because_text_order_is_not_chronological():
    unpadded = ("2020-10", "2020-2")
    assert sorted(unpadded) == ["2020-10", "2020-2"]
    rows = tuple(
        replace(
            figure(),
            input_id=f"invented-{month}",
            periods=(f"2020-{month}",),
            value="0.1",
        )
        for month in range(1, 13)
    )
    with pytest.raises(ValueError, match=r"^annual_coverage$"):
        annual_trade_sum(rows, output_id="invented-annual")


def test_lineage_follows_parsed_month_not_only_text():
    from eii_core.calc import trade_reconciliation as tr

    shuffled = tuple(
        replace(
            figure(),
            input_id=f"invented-{month}",
            periods=(f"2020-{month:02}",),
            value="0.1",
        )
        for month in (10, 2, 1, 12, 3, 4, 5, 6, 7, 8, 9, 11)
    )
    result = annual_trade_sum(shuffled, output_id="invented-annual")
    assert result.periods == ("2020",)
    assert result.lineage == tuple(f"invented-{month}" for month in range(1, 13))
    ordered = sorted(("2020-10", "2020-2"), key=tr.monthly_period_rank)
    assert ordered[0].endswith("-2")
