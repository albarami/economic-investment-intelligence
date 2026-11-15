"""Closed method refusal strings and invented count boundaries."""

from decimal import Decimal as D

import pytest
from method_rows import measure

from eii_core.calc import public_methods as p


@pytest.mark.parametrize(
    "call,reason",
    [
        (lambda: p.wilson(0, 0), "invalid binomial counts"),
        (lambda: p.wilson(2, 1), "invalid binomial counts"),
        (lambda: p._whole(measure(1, unit="qar"), "count"), "unit mismatch"),
        (lambda: p._whole(measure("1.5"), "count"), "fractional count"),
    ],
    ids=("empty", "excess", "unit", "fraction"),
)
def test_method_exact_refusals(call, reason):
    with pytest.raises(ValueError) as error:
        call()
    assert str(error.value) == reason


def test_one_trial_interval_endpoints():
    assert p.wilson(0, 1)[0] == D(0)
    assert p.wilson(1, 1)[1] == D(1)


def national(value):
    return measure(value, geography="national", kind="national")


def test_density_and_location_metadata_and_equal_total_boundaries():
    density = p.licence_density(measure(10), measure(10))
    assert density.value == D(10000)
    assert density.metric_key == "licence_density"
    assert density.release_id == "published"
    full = p.location_quotient(measure(30), measure(30), national(30), national(30))
    assert str(full["value"].value) == "1.00"
    assert full["value"].metric_key == "location_quotient"
    assert full["interval"][0].metric_key == "lq_low"
    assert full["interval"][1].metric_key == "lq_high"
    assert full["reliability_unrounded"] == "standard"
    small = p.location_quotient(measure(1), measure(30), national(30), national(30))
    assert str(small["count"].value) == "1"
    assert small["count"].metric_key == "local_count"


@pytest.mark.parametrize(
    "rows,reason",
    [
        (
            (national(10), national(20), national(10), national(20)),
            "geography mismatch",
        ),
        (
            (
                measure(10, period="2021"),
                measure(20, period="2021"),
                national(10),
                national(20),
            ),
            "period mismatch",
        ),
        (
            (measure(20), measure(10), national(10), national(20)),
            "activity count exceeds all activities",
        ),
        (
            (measure(10), measure(20), national(0), national(20)),
            "non-positive national share",
        ),
    ],
)
def test_location_exact_refusals(rows, reason):
    with pytest.raises(ValueError) as error:
        p.location_quotient(*rows)
    assert str(error.value) == reason
