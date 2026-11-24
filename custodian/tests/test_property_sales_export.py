"""S2-T08 part B, mismatch class 3: the observed ``prop_sales`` export shape.

The live shape pack's Mismatches item 3 shows the export with ``usage`` in place
of ``property_usage``, five further fields (``lstkhdm``, ``share_area``,
``share_value``, ``number_of_shares_2400``, ``price_per_square_foot``) and no
``area_square_feet``. A source-specific adapter checks that exact shape, reads
the published square metres and leaves square feet absent. Ruling L-1724 keeps
only whole-property rows, counting partial and inconsistent share exclusions.
The share semantics remain unconfirmed. Every row below is invented.
"""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_property_quarter import _blocked, _frame, _map
from hypothesis import example, given
from hypothesis import strategies as st

from eii_custodian.publicdata.additions.common import AdditionError, read_measure
from eii_custodian.publicdata.fetch.checks import schema_failure
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.build import read_cached
from eii_custodian.publicdata.property.bulletin import (
    SALES_EXPORT_FIELDS,
    SALES_SHARE_FIELDS,
    parse_bulletin,
    sales_export_rows,
)
from eii_custodian.publicdata.property.quarter import quarter_aggregates
from eii_custodian.publicdata.review.cache_fixture import write_cached

REPO = repository_root(Path(__file__))
# The names of the shape pack's prop_sales row, in the portal metadata's order.
OBSERVED = (
    "registration_date",
    "encrypted_transaction_number",
    "encrypted_parcel_number",
    "sm_lbldy",
    "municipality_name",
    "sm_lmntq",
    "district_name",
    "nw_l_qr",
    "property_type",
    "lstkhdm",
    "usage",
    "area_square_meters",
    "share_area",
    "price_per_square_foot",
    "price_per_square_meter",
    "number_of_shares_2400",
    "share_value",
    "property_value",
)


def _export(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "registration_date": "2025-10-02",
        "encrypted_transaction_number": "SYN-TX-S1",
        "encrypted_parcel_number": "SYN-PX-S1",
        "sm_lbldy": "SYN Coast AR",
        "municipality_name": "SYN Coast",
        "sm_lmntq": "SYN North AR",
        "district_name": "SYN North",
        "nw_l_qr": "SYN-LAND-1",
        "property_type": "SYN-EN-LAND",
        "lstkhdm": "SYN-USE-AR",
        "usage": "SYN-USE-RESI",
        "area_square_meters": 100,
        "share_area": None,
        "price_per_square_foot": None,
        "price_per_square_meter": None,
        "number_of_shares_2400": None,
        "share_value": None,
        "property_value": 100000,
    }
    row.update(overrides)
    return row


def _parse(rows: list[dict[str, object]], tmp_path: Path):
    return parse_bulletin(
        sales_export_rows(rows).rows, "prop_sales", _map(), _frame(tmp_path / "frame")
    )


def test_the_adapter_names_the_observed_fields() -> None:
    assert SALES_EXPORT_FIELDS == OBSERVED
    assert SALES_SHARE_FIELDS == (
        "share_area",
        "number_of_shares_2400",
        "share_value",
    )


def test_registry_declares_the_exact_observed_shape() -> None:
    entry = next(
        e
        for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
        if e.key == "prop_sales"
    )
    assert tuple(name for name, _kind in entry.columns) == OBSERVED
    kinds = dict(entry.columns)
    assert kinds["usage"] == "string"
    assert kinds["area_square_meters"] == "integer"
    assert "property_usage" not in kinds
    assert "area_square_feet" not in kinds
    assert entry.commit_allowed is False
    assert schema_failure(entry, [_export()], "https://invented.test") is None
    old = _export()
    old["property_usage"] = old.pop("usage")
    failure = schema_failure(entry, [old], "https://invented.test")
    assert failure is not None
    assert (failure.check, failure.expected) == ("schema_missing", "usage")


def test_exact_shape_keeps_a_deal_in_published_square_metres(tmp_path: Path) -> None:
    parsed = _parse([_export()], tmp_path)
    assert len(parsed.deals) == 1
    deal = parsed.deals[0]
    assert deal.area_m2 == Decimal(100)
    assert deal.area_ft2 is None
    assert deal.use_key == "residential"
    row = next(
        r
        for r in quarter_aggregates(
            parsed.deals, as_of_by_source={"prop_sales": "2026-11-17"}
        )
        if r["unit_type"] == "all"
    )
    # 100000 * 0.09290304 / 100, the card's factor; no published square feet.
    assert row["median_price_per_ft2"] == Decimal("92.90")


@pytest.mark.parametrize("value", [1500, 1500.0, 1234.5])
def test_cached_sales_measure_matches_the_float_path(
    tmp_path: Path, value: int | float
) -> None:
    entry = next(e for e in load_registry() if e.key == "prop_sales")
    rows = [_export(property_value=value)]
    digest = write_cached(tmp_path, entry, json.dumps(rows).encode()).stem
    cached, _receipt = read_cached(tmp_path, entry, digest=digest)
    assert isinstance(
        cached[0]["property_value"], Decimal if isinstance(value, float) else int
    )
    if value == 1234.5:
        for payload in (rows, cached):
            with pytest.raises(AdditionError, match=r"^measure_not_integral$"):
                _parse(payload, tmp_path)
    else:
        expected = _parse(rows, tmp_path)
        assert _parse(cached, tmp_path) == expected
        assert expected.deals[0].value == Decimal("1500")


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_decimal_measure_is_unparsed(value: str) -> None:
    with pytest.raises(AdditionError, match=r"^measure_unparsed$"):
        read_measure(Decimal(value), missing_forms=frozenset(), integral=False)


@given(value=st.decimals(allow_nan=False, allow_infinity=False), integral=st.booleans())
def test_decimal_measure_matches_a_rational_oracle(
    value: Decimal, integral: bool
) -> None:
    exact = Fraction(value)
    if integral and exact.denominator != 1:
        with pytest.raises(AdditionError, match=r"^measure_not_integral$"):
            read_measure(value, missing_forms=frozenset(), integral=integral)
    else:
        result = read_measure(value, missing_forms=frozenset(), integral=integral)
        assert result.number is not None
        assert Fraction(result.number) == exact


def test_published_price_per_square_foot_is_never_read(tmp_path: Path) -> None:
    parsed = _parse([_export(price_per_square_foot=1)], tmp_path)
    assert parsed.deals[0].area_ft2 is None
    row = next(
        r
        for r in quarter_aggregates(
            parsed.deals, as_of_by_source={"prop_sales": "2026-11-17"}
        )
        if r["unit_type"] == "all"
    )
    assert row["median_price_per_ft2"] == Decimal("92.90")


def test_adapter_output_never_carries_square_feet_or_share_fields() -> None:
    (row,) = sales_export_rows([_export()]).rows
    assert "area_square_feet" not in row
    assert not set(SALES_SHARE_FIELDS) & set(row)
    assert "price_per_square_foot" not in row
    assert row["property_usage"] == "SYN-USE-RESI"


@pytest.mark.parametrize("old", ["property_usage", "area_square_feet"])
def test_old_field_names_are_refused(old: str) -> None:
    row = _export()
    row[old] = row.pop("usage") if old == "property_usage" else 2000
    with pytest.raises(AdditionError) as refused:
        sales_export_rows([row])
    assert refused.value.name == "unknown_source_field"


def test_extra_field_is_refused() -> None:
    with pytest.raises(AdditionError) as refused:
        sales_export_rows([_export(syn_extra="invented")])
    assert refused.value.name == "unknown_source_field"


@pytest.mark.parametrize("missing", ["usage", "lstkhdm", "share_value"])
def test_missing_field_is_refused(missing: str) -> None:
    row = _export()
    del row[missing]
    with pytest.raises(AdditionError) as refused:
        sales_export_rows([row])
    assert refused.value.name == "source_field_missing"


def _whole(**overrides: object) -> dict[str, object]:
    return _export(
        **dict(share_area=100, share_value=100000, number_of_shares_2400=2400)
        | overrides
    )


def test_whole_and_null_rows_keep_only_whole_price_and_area() -> None:
    result = sales_export_rows([_whole(), _export()])
    assert len(result.rows) == 2
    assert result.blocked == ()
    for row in result.rows:
        assert row["property_value"] == 100000
        assert row["area_square_meters"] == 100
        assert not set(SALES_SHARE_FIELDS) & row.keys()


def test_mixed_batch_counts_each_closed_exclusion_reason() -> None:
    result = sales_export_rows(
        [
            _whole(),
            _export(),
            _whole(share_area=50, share_value=50000, number_of_shares_2400=1200),
            _whole(share_value=None),
            _whole(share_value=0),
        ]
    )
    assert len(result.rows) == 2
    assert [(c.reason, c.count) for c in result.blocked] == [
        ("partial_share_deal", 1),
        ("share_fields_inconsistent", 2),
    ]


@pytest.mark.parametrize("field", SALES_SHARE_FIELDS)
@pytest.mark.parametrize(
    "value",
    [
        {"toString": None},
        [],
        True,
        "",
        "nonsense",
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
    ],
)
def test_malformed_share_is_counted_as_inconsistent(field: str, value: object) -> None:
    result = sales_export_rows([_export(), _whole(**{field: value})])
    assert len(result.rows) == 1
    assert [(c.reason, c.count) for c in result.blocked] == [
        ("share_fields_inconsistent", 1)
    ]


@pytest.mark.parametrize("fixture", [_export(), _whole()], ids=["null", "whole"])
@pytest.mark.parametrize("field", OBSERVED)
@pytest.mark.parametrize("hostile", [{"toString": None}, 7, None, []])
def test_every_export_leaf_handles_hostile_values(fixture, field, hostile) -> None:
    row = dict(fixture) | {field: hostile}
    result = sales_export_rows([_export(), row])
    assert len(result.rows) + sum(c.count for c in result.blocked) == 2
    assert {c.reason for c in result.blocked} <= {
        "partial_share_deal",
        "share_fields_inconsistent",
    }
    assert all(not set(SALES_SHARE_FIELDS) & kept.keys() for kept in result.rows)


@pytest.mark.parametrize(
    "changes,reason",
    [
        (
            {"share_value": 50000, "share_area": 50, "number_of_shares_2400": 1200},
            "partial_share_deal",
        ),
        ({"share_value": None}, "share_fields_inconsistent"),
        ({"share_value": None, "share_area": None}, "share_fields_inconsistent"),
        ({"property_value": None}, "share_fields_inconsistent"),
        ({"share_value": 100001}, "share_fields_inconsistent"),
        ({"share_area": 101}, "share_fields_inconsistent"),
        ({"number_of_shares_2400": 2401}, "share_fields_inconsistent"),
        ({"share_value": 0}, "share_fields_inconsistent"),
        ({"share_area": 0}, "share_fields_inconsistent"),
        ({"number_of_shares_2400": 0}, "share_fields_inconsistent"),
        ({"share_value": -1}, "share_fields_inconsistent"),
        ({"share_area": -1}, "share_fields_inconsistent"),
        ({"number_of_shares_2400": -1}, "share_fields_inconsistent"),
        ({"share_area": 50}, "share_fields_inconsistent"),
        ({"share_value": 50000}, "share_fields_inconsistent"),
        (
            {"share_value": Decimal("99999.999999999999999999999999")},
            "share_fields_inconsistent",
        ),
    ],
)
def test_exclusions_are_per_row_and_counted(
    changes: dict[str, object], reason: str
) -> None:
    result = sales_export_rows([_whole(), _whole(**changes), _whole(**changes)])
    assert len(result.rows) == 1
    assert [(c.reason, c.count) for c in result.blocked] == [(reason, 2)]


@pytest.mark.parametrize("rows", [[], [_whole(share_value=0)]])
def test_no_whole_rows_refuses_by_closed_name(rows: list[dict[str, object]]) -> None:
    with pytest.raises(AdditionError, match=r"^no_whole_property_deals$"):
        sales_export_rows(rows)


@given(
    triples=st.lists(
        st.tuples(
            *(
                st.one_of(
                    st.none(),
                    st.integers(),
                    st.decimals(allow_nan=False, allow_infinity=False),
                )
                for _ in SALES_SHARE_FIELDS
            )
        ),
        max_size=30,
    )
)
@example(
    triples=[
        (None, None, None),
        (100, 2400, 100000),
        (50, 1200, 50000),
        (None, 2400, 100000),
    ]
)
def test_share_triples_partition_every_row_without_leaking_fields(triples) -> None:
    # Fraction oracle: unit-matched ratios, independent of Decimal comparisons.
    counts = {"partial_share_deal": 0, "share_fields_inconsistent": 0}
    expected = [_export()]
    rows = [_export()]
    for index, triple in enumerate(triples):
        row = _export(
            **dict(zip(SALES_SHARE_FIELDS, triple, strict=True)),
            encrypted_transaction_number=f"SYN-TX-{index}",
        )
        rows.append(row)
        ratios = [
            None if value is None else Fraction(value) / whole
            for value, whole in zip(triple, (100, 2400, 100000), strict=True)
        ]
        if all(value is None for value in ratios) or ratios == [1, 1, 1]:
            expected.append(row)
        elif all(value is not None and 0 < value < 1 for value in ratios):
            counts["partial_share_deal"] += 1
        else:
            counts["share_fields_inconsistent"] += 1
    result = sales_export_rows(rows)
    assert len(result.rows) + sum(c.count for c in result.blocked) == len(rows)
    assert {c.reason: c.count for c in result.blocked} == {
        k: v for k, v in counts.items() if v
    }
    assert [r["encrypted_transaction_number"] for r in result.rows] == [
        r["encrypted_transaction_number"] for r in expected
    ]
    assert all(not set(SALES_SHARE_FIELDS) & row.keys() for row in result.rows)


@pytest.mark.parametrize(
    "rows,reason",
    [
        (None, "bulletin_rows"),
        ({}, "bulletin_rows"),
        ("rows", "bulletin_rows"),
        ([["not", "a", "row"]], "bulletin_row"),
    ],
)
def test_rows_that_are_not_a_list_of_objects_are_refused(
    rows: object, reason: str
) -> None:
    with pytest.raises(AdditionError) as refused:
        sales_export_rows(rows)
    assert refused.value.name == reason


@pytest.mark.parametrize("area", [None, 0, -5])
def test_missing_or_nonpositive_area_keeps_no_deal(
    tmp_path: Path, area: object
) -> None:
    parsed = _parse([_export(area_square_meters=area)], tmp_path)
    assert parsed.deals == ()
    assert _blocked(parsed, "nonpositive_area") == 1


def test_duplicate_deal_that_disagrees_is_blocked(tmp_path: Path) -> None:
    parsed = _parse(
        [_export(), _export(property_value=200000)],
        tmp_path,
    )
    assert parsed.deals == ()
    assert _blocked(parsed, "repeated_deal_price_disagreement") == 1


def test_duplicate_deal_that_agrees_counts_once(tmp_path: Path) -> None:
    parsed = _parse([_export(), _export()], tmp_path)
    assert len(parsed.deals) == 1


def test_review_record_holds_the_correction() -> None:
    import yaml

    review = yaml.safe_load(
        (REPO / "custodian/publicdata/review/s2_t08_source_review.yaml").read_text(
            encoding="utf-8"
        )
    )
    (row,) = [r for r in review["rows"] if r["mismatch"] == 3]
    assert row["key"] == "prop_sales"
    assert row["export_sha256"].startswith("9f4867dc")
    assert len(row["export_sha256"]) == 64
    assert set(row["change"]["columns"]["removed"]) == {
        "property_usage",
        "area_square_feet",
    }
