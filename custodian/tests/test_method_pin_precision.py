"""Exact-value pin serialization; every input and receipt is invented."""

import json
import tempfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from custodian.tests.method_card_pin_fixtures import case, producer_rows
from custodian.tests.test_method_pin_supply import supplied_build
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly_method_pins import (
    PIN_ARTIFACT_NAME,
    write_pin_pair,
)
from eii_custodian.publicdata.method_pin_rows import collect_pin_rows
from eii_custodian.publicdata.method_pin_supplier import _calculated_values


@given(
    value=st.one_of(st.integers(), st.decimals(allow_nan=False, allow_infinity=False))
)
@example(value=Decimal("123456789012345678901234567890.123456789012345678901"))
@example(value=9007199254740993)
@example(value=10**100)
@example(value=Decimal("-0.00000000000000000000000000001"))
@example(value=Decimal("-0"))
@example(value=Decimal("1E+3"))
@example(value=Decimal("1.2300"))
def test_every_card_pin_round_trips_exact_values(value):
    with tempfile.TemporaryDirectory() as directory:
        cache = Path(directory)
        _, _, artifact, config = case(cache)
        rows = producer_rows(artifact["pins"])
        pins = {
            row["pin_id"]
            for row in rows
            if row["values"] and row["pin_id"].startswith(("c5.", "c6.", "c7.", "c14."))
        }
        for row in rows:
            if row["pin_id"] in pins:
                row["values"] = {"SYN exact": value}
        write_pin_pair(cache, config, rows)
        stored = json.loads((cache / PIN_ARTIFACT_NAME).read_bytes())
        assert [row["pin_id"] for row in stored["pins"]] == [
            row["pin_id"] for row in rows
        ]
        for row in stored["pins"]:
            if row["pin_id"] in pins:
                actual = row["values"]["SYN exact"]
                assert type(actual) is (str if isinstance(value, Decimal) else int)
                assert_exact(actual, value)


def assert_exact(actual, value):
    """Numeric equality AND, for a Decimal, the same sign, digits and exponent."""
    if isinstance(value, Decimal):
        assert Decimal(actual).as_tuple() == value.as_tuple()
    else:
        assert Fraction(actual) == Fraction(value)


@given(
    value=st.one_of(
        st.integers(),
        st.decimals(allow_nan=False, allow_infinity=False),
        st.fractions(),
    )
)
@example(value=Decimal("123456789012345678901234567890.123456789012345678901"))
@example(value=9007199254740993)
@example(value=Decimal("-0"))
@example(value=Decimal("1E+3"))
@example(value=Decimal("1.2300"))
def test_c5_adapter_preserves_every_exact_calculator_output(value):
    result = _calculated_values(
        {
            "hhi": SimpleNamespace(exact_unrounded=value),
            "prior_total_value_unrounded": value,
            "total_value_unrounded": value,
            "trend_unrounded": value,
        }
    )
    assert set(result) == {"hhi", "prior12", "latest12", "trend"}
    assert all(type(cell) is str for cell in result.values())
    for cell in result.values():
        assert_exact(cell, value)


def test_a_decimal_normalising_serializer_fails_the_exact_oracle():
    """Planted corruption: a serializer that normalises a Decimal must fail."""
    for value, corrupted in (
        (Decimal("-0"), "0"),
        (Decimal("1E+3"), "1000"),
        (Decimal("1.2300"), "1.23"),
    ):
        try:
            assert_exact(corrupted, value)
        except AssertionError:
            continue
        raise AssertionError(f"normalised form passed for {value!r}")


def test_source_adapters_keep_exact_decimal_and_large_count_values(tmp_path):
    build, config = supplied_build(tmp_path)
    decimal = Decimal("123456789012345678901234567890.123456789012345678901")
    count = 9007199254740993
    build.tables["pub_census_district"][0]["value"] = decimal
    for row in build.tables["pub_property_sale"]:
        row["median_price_per_m2"] = decimal
        row["deal_count"] = count
    rows = collect_pin_rows(build, config)
    write_pin_pair(build.cache, config, rows)
    stored = {
        row["pin_id"]: row["values"]
        for row in json.loads((build.cache / PIN_ARTIFACT_NAME).read_bytes())["pins"]
    }
    assert Decimal(stored["c7.district_weights"]["SYN-district"]) == decimal
    for year in ("2024", "2025"):
        values = stored["c14.medians_" + year]
        assert Decimal(values["syn_north:residential:median_qar_per_m2"]) == decimal
        assert values["syn_north:residential:deal_count"] == count
