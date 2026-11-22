"""Hand-made rows for local banks' credit by economic activity."""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.singles_entries import bank_credit_entry
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.singles.bank_credit import (
    CreditError,
    credit_period_bounds,
    parse_bank_credit,
)


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "year": "2012-01-01",
        "economic_activity": "Invented activity",
        "lnsht_lqtsdy": "نشاط مخترع",
        "value": "10.50",
    }
    row.update(changes)
    return row


def test_entry_matches_the_recorded_slug() -> None:
    # The registry row is built here; part R appends sources.yaml.
    entry = bank_credit_entry()
    assert entry.publisher == "National Planning Council"
    assert entry.licence_basis == "dataset"
    # S2-T08 part B mismatch 2: the export sends the year as four-digit text.
    assert entry.period_field == "sit=row;form=year_text;field=year"
    assert entry.period_first == "2012"
    assert entry.period_last == "2022"
    assert entry.public_splits == ()
    assert [name for name, _kind in entry.columns] == [
        "year",
        "economic_activity",
        "lnsht_lqtsdy",
        "value",
    ]


def test_fixture_file_parses() -> None:
    path = (
        repository_root(Path(__file__))
        / "custodian/tests/fixtures/bank_credit/credit.json"
    )
    rows = parse_bank_credit(json.loads(path.read_text(encoding="utf-8")))
    assert rows[0].activity_key == "Invented activity"
    assert rows[0].value == Decimal("10.50")


def test_parse_returns_national_credit_rows() -> None:
    rows = parse_bank_credit((_row(), _row(year="2022-01-01", value="20")))
    assert rows[0].activity_key == "Invented activity"
    assert rows[0].period == "2012-01-01"
    assert rows[0].value == Decimal("10.50")
    assert rows[0].unit is None
    assert rows[1].period == "2022-01-01"
    assert rows[1].value == Decimal("20.00")
    assert rows[1].value.as_tuple().exponent == -2
    whole = parse_bank_credit((_row(value=20),))
    assert whole[0].value.as_tuple().exponent == -2
    assert not hasattr(rows[0], "area")


def test_modified_date_does_not_extend_the_period() -> None:
    first, last = credit_period_bounds(
        (_row(), _row(year="2022-01-01")), modified="2026-07-24"
    )
    assert first == "2012-01-01"
    assert last == "2022-01-01"


@pytest.mark.parametrize("value", ["0", "0.01", "25.5", "25.50", "1E+2"])
def test_decimal_credit_is_exact_cents(value: str) -> None:
    (row,) = parse_bank_credit((_row(value=Decimal(value)),))
    assert Fraction(row.value) == Fraction(Decimal(value))
    assert row.value.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "value",
    [
        Decimal("25.555"),
        Decimal("25.500"),
        Decimal("-1.5"),
        Decimal("-0.00"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        25.5,
        True,
    ],
)
def test_invalid_credit_value_has_the_closed_reason(value: object) -> None:
    with pytest.raises(CreditError, match=r"^value$"):
        parse_bank_credit((_row(value=value),))


@given(
    coefficient=st.integers(-(10**18 - 1), 10**18 - 1),
    exponent=st.integers(-6, 2),
)
@example(coefficient=0, exponent=-2)
@example(coefficient=1, exponent=-2)
@example(coefficient=10**18 - 1, exponent=-2)
@example(coefficient=-15, exponent=-1)
@example(coefficient=25555, exponent=-3)
def test_decimal_credit_matches_a_rational_oracle(
    coefficient: int, exponent: int
) -> None:
    # All decimal(18,2) contract values, plus signs and excessive scales.
    value = Decimal(f"{coefficient}e{exponent}")
    if coefficient < 0 or exponent < -2:
        with pytest.raises(CreditError, match=r"^value$"):
            parse_bank_credit((_row(value=value),))
    else:
        (row,) = parse_bank_credit((_row(value=value),))
        assert Fraction(row.value) == Fraction(coefficient) * Fraction(10) ** exponent
        assert row.value.as_tuple().exponent == -2


def test_unexpected_shape_loads_nothing() -> None:
    with pytest.raises(CreditError) as missing:
        parse_bank_credit((_row(value=""),))
    assert missing.value.reason == "value"
    with pytest.raises(CreditError) as extra:
        parse_bank_credit((_row(municipality="Doha"),))
    assert extra.value.reason == "unexpected_column"
    with pytest.raises(CreditError) as sex:
        parse_bank_credit((_row(gender="invented"),))
    assert sex.value.reason == "unexpected_column"
    with pytest.raises(CreditError) as bad:
        parse_bank_credit((_row(value="not-a-number"),))
    assert "not-a-number" not in bad.value.reason
