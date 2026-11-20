"""Mutation regressions for property readers; every input is invented."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import ROUND_DOWN, Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_additions_property_venues import _deal as venue_deal
from custodian.tests.test_property_quarter import (
    _all_row,
    _as_of_map,
    _frame,
    _parse,
    _resi,
    _sale,
    _unit_row,
)
from custodian.tests.test_property_use_map import _write

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.property import bulletin, quarter
from eii_custodian.publicdata.property.use_map import (
    UseMapping,
    load_use_map,
    use_lookup,
)


def _untyped(value: object) -> Any:
    """Pass a deliberately malformed value to a typed boundary."""
    return value


def _refuses(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(AdditionError) as caught:
        call()
    assert str(caught.value) == expected
    assert caught.value.name == expected


def _mappings(tmp_path: Path) -> tuple[UseMapping, ...]:
    return load_use_map(
        _write(
            tmp_path / "syn-map.csv",
            [
                "prop_resi_units,SYN-UNIT,*,syn_use,residential_unit,SYN reviewer,2025-01-01",
                "prop_sales,SYN-LAND-1,SYN-USE-RESI,syn_use,land,SYN reviewer,2025-01-01",
            ],
        )
    )


def test_property_bulletin_refuses_unknown_source(tmp_path: Path) -> None:
    _refuses(
        lambda: bulletin.parse_bulletin([], "syn_unknown", (), _frame(tmp_path)),
        "use_map_source",
    )


def test_property_lookup_refuses_unknown_source() -> None:
    _refuses(
        lambda: use_lookup((), "syn_unknown", "SYN-LABEL", "SYN-USAGE"),
        "use_map_source",
    )


def test_property_deal_refuses_unknown_mapping_source(tmp_path: Path) -> None:
    # parse_bulletin refuses the source before _deal; use_lookup scopes mappings.
    mapping = replace(_mappings(tmp_path)[0], source_id="syn_unknown")
    _refuses(
        lambda: bulletin._deal(_resi(), "syn_district", "syn_muni", mapping),
        "use_map_source",
    )


def test_property_unkept_refuses_missing_per_unit_price(tmp_path: Path) -> None:
    # _deal assigns value to per_unit price, so a missing price with positive
    # value cannot arrive through parse_bulletin. Exercise this guard directly.
    deal = _parse([_resi()], tmp_path / "frame", _mappings(tmp_path)).deals[0]
    assert bulletin._unkept(replace(deal, basis="per_unit", price=None)) == (
        "nonpositive_price"
    )


@pytest.mark.parametrize("period", [None, 1, (), "2025-Q0", "SYN-quarter"])
def test_property_window_refuses_malformed_period(period: object) -> None:
    _refuses(lambda: quarter.forecast_window([_untyped(period)]), "quarter_period")


@pytest.mark.parametrize(
    "field",
    [
        "property_value",
        "area_square_feet",
        "area_square_meters",
        "price_per_square_meter",
    ],
)
def test_property_measure_refuses_fractional_number(tmp_path: Path, field: str) -> None:
    _refuses(
        lambda: _parse(
            [venue_deal(**{field: 1.5})], tmp_path / "frame", _mappings(tmp_path)
        ),
        "measure_not_integral",
    )


def test_property_unmatched_row_does_not_stop_later_deals(tmp_path: Path) -> None:
    parsed = _parse(
        [
            _resi(district_name="SYN Absent", sm_lmntq="SYN Absent AR"),
            _resi(),
        ],
        tmp_path / "frame",
        _mappings(tmp_path),
    )
    assert [(item.reason, item.count) for item in parsed.blocked] == [
        ("unmatched_district", 1)
    ]
    assert [(item.transaction, item.period) for item in parsed.deals] == [
        ("SYN-TX-1", "2025-Q4")
    ]


def test_property_missing_usage_is_empty_not_marker_text(tmp_path: Path) -> None:
    mappings = _mappings(tmp_path)
    # Both reviewed rows are valid. Missing usage matches the wildcard alone;
    # the mutation marker would wrongly make both mappings match.
    exact = replace(mappings[0], usage_value="XXXX", use_key="syn_exact")
    parsed = _parse(
        [_resi(property_usage=None)], tmp_path / "frame", (*mappings, exact)
    )
    assert len(parsed.deals) == 1
    assert parsed.deals[0].use_key == "syn_use"
    assert parsed.blocked == ()


@pytest.mark.parametrize(
    ("area_m2", "area_ft2", "expected_m2", "expected_ft2"),
    [
        (1, None, Decimal("1"), None),
        (None, 1, Decimal("9.290304E-2"), Decimal("1")),
    ],
)
def test_property_one_unit_area_is_positive(
    tmp_path: Path,
    area_m2: int | None,
    area_ft2: int | None,
    expected_m2: Decimal,
    expected_ft2: Decimal | None,
) -> None:
    parsed = _parse(
        [
            _sale(
                area_square_meters=area_m2, area_square_feet=area_ft2, property_value=1
            )
        ],
        tmp_path / "frame",
        _mappings(tmp_path),
        source_id="prop_sales",
    )
    assert parsed.blocked == ()
    assert len(parsed.deals) == 1
    assert parsed.deals[0].area_m2 == expected_m2
    assert parsed.deals[0].area_ft2 == expected_ft2
    assert parsed.deals[0].value == Decimal("1")


def test_property_sale_price_divides_value_by_area(tmp_path: Path) -> None:
    parsed = _parse(
        [_sale(area_square_meters=2, area_square_feet=100, property_value=10)],
        tmp_path / "frame",
        _mappings(tmp_path),
        source_id="prop_sales",
    )
    assert parsed.blocked == ()
    assert len(parsed.deals) == 1
    deal = parsed.deals[0]
    assert (deal.price, deal.area_m2, deal.area_ft2, deal.basis) == (
        Decimal("5"),
        Decimal("2"),
        Decimal("100"),
        "per_m2",
    )


def test_property_residential_price_one_is_kept(tmp_path: Path) -> None:
    parsed = _parse(
        [_resi(price_per_square_meter=1, property_value=1, area_square_meters=1)],
        tmp_path / "frame",
        _mappings(tmp_path),
    )
    assert parsed.blocked == ()
    assert len(parsed.deals) == 1
    assert parsed.deals[0].price == Decimal("1")


def test_property_per_unit_deal_has_no_square_foot_median(tmp_path: Path) -> None:
    parsed = _parse(
        [_resi(area_square_meters=None, property_value=1)],
        tmp_path / "frame",
        _mappings(tmp_path),
    )
    assert parsed.blocked == ()
    assert len(parsed.deals) == 1
    deal = parsed.deals[0]
    assert (deal.basis, deal.price, deal.area_m2, deal.area_ft2) == (
        "per_unit",
        Decimal("1"),
        None,
        None,
    )
    assert quarter.quarter_aggregates(
        parsed.deals, as_of_by_source=_as_of_map("prop_resi_units")
    ) == (
        {
            "district_key": "syn_north",
            "municipality_code": "syn_coast",
            "period": "2025-Q4",
            "use_key": "syn_use",
            "unit_type": "all",
            "deal_count": 1,
            "deal_value": Decimal("1.00"),
            "median_price_per_ft2": None,
            "land_deal_count": 0,
            "land_median_price_per_ft2": None,
            "median_price": None,
            "price_basis": None,
            "as_of": "2026-11-17",
        },
        {
            "district_key": "syn_north",
            "municipality_code": "syn_coast",
            "period": "2025-Q4",
            "use_key": "syn_use",
            "unit_type": "residential_unit",
            "deal_count": 1,
            "deal_value": Decimal("1.00"),
            "median_price_per_ft2": None,
            "land_deal_count": None,
            "land_median_price_per_ft2": None,
            "median_price": Decimal("1.00"),
            "price_basis": "per_unit",
            "as_of": "2026-11-17",
        },
    )


def test_property_deduplication_keeps_quarter_cells_separate(tmp_path: Path) -> None:
    parsed = _parse(
        [_resi(registration_date="2025-01-01"), _resi(registration_date="2025-04-01")],
        tmp_path / "frame",
        _mappings(tmp_path),
    )
    assert parsed.blocked == ()
    assert [(deal.transaction, deal.period) for deal in parsed.deals] == [
        ("SYN-TX-1", "2025-Q1"),
        ("SYN-TX-1", "2025-Q2"),
    ]


def test_property_two_disagreeing_transactions_count_twice(tmp_path: Path) -> None:
    parsed = _parse(
        [
            _resi(encrypted_transaction_number="SYN-A", property_value=10),
            _resi(encrypted_transaction_number="SYN-A", property_value=20),
            _resi(encrypted_transaction_number="SYN-B", property_value=30),
            _resi(encrypted_transaction_number="SYN-B", property_value=40),
        ],
        tmp_path / "frame",
        _mappings(tmp_path),
    )
    assert parsed.deals == ()
    assert [(item.reason, item.count) for item in parsed.blocked] == [
        ("repeated_deal_price_disagreement", 2)
    ]


def test_property_square_feet_rounds_half_up_under_round_down() -> None:
    with localcontext() as context:
        context.rounding = ROUND_DOWN
        assert quarter.square_feet(Decimal("2")) == Decimal("21.53")


def test_property_sum_and_median_round_half_up(tmp_path: Path) -> None:
    base = _parse([_resi()], tmp_path / "frame", _mappings(tmp_path)).deals[0]
    # Exercise the typed aggregate boundary with fractional Decimal measures.
    deal = replace(
        base,
        basis="per_unit",
        price=Decimal("10.005"),
        value=Decimal("20.005"),
        area_m2=None,
        area_ft2=None,
    )
    with localcontext() as context:
        context.rounding = ROUND_DOWN
        rows = quarter.quarter_aggregates(
            [deal], as_of_by_source=_as_of_map(deal.source_id)
        )
    assert _all_row(rows)["deal_value"] == Decimal("20.01")
    assert _unit_row(rows)["deal_value"] == Decimal("20.01")
    assert _unit_row(rows)["median_price"] == Decimal("10.01")


def test_property_odd_median_uses_the_middle_value(tmp_path: Path) -> None:
    parsed = _parse(
        [
            _resi(encrypted_transaction_number="SYN-A", price_per_square_meter=1),
            _resi(encrypted_transaction_number="SYN-B", price_per_square_meter=9),
            _resi(encrypted_transaction_number="SYN-C", price_per_square_meter=5),
            _resi(encrypted_transaction_number="SYN-D", price_per_square_meter=3),
            _resi(encrypted_transaction_number="SYN-E", price_per_square_meter=7),
        ],
        tmp_path / "frame",
        _mappings(tmp_path),
    )
    unit = _unit_row(
        quarter.quarter_aggregates(
            parsed.deals, as_of_by_source=_as_of_map("prop_resi_units")
        )
    )
    assert unit["deal_count"] == 5
    assert unit["median_price"] == Decimal("5.00")


def test_property_null_value_sums_to_decimal_zero(tmp_path: Path) -> None:
    base = _parse([_resi()], tmp_path / "frame", _mappings(tmp_path)).deals[0]
    # The parser drops this candidate at _unkept; aggregate's public Deal
    # boundary still accepts nullable value fields and must not sum None.
    rows = quarter.quarter_aggregates(
        [replace(base, value=None, unit_type=None)],
        as_of_by_source=_as_of_map(base.source_id),
    )
    assert len(rows) == 1
    assert rows[0]["deal_count"] == 1
    assert rows[0]["deal_value"] == Decimal("0.00")
    assert rows[0]["median_price_per_ft2"] is None


def test_property_missing_unit_price_has_no_partial_median(tmp_path: Path) -> None:
    base = _parse([_resi()], tmp_path / "frame", _mappings(tmp_path)).deals[0]
    # _unkept refuses a missing per_m2 price during parsing. Test the public
    # aggregate boundary's nullable Deal.price branch without that parser.
    rows = quarter.quarter_aggregates(
        [base, replace(base, price=None)],
        as_of_by_source=_as_of_map(base.source_id),
    )
    unit = _unit_row(rows)
    assert unit["deal_count"] == 2
    assert unit["median_price"] is None
    assert unit["deal_value"] == Decimal("1600.00")


@pytest.mark.parametrize(
    ("value", "feet", "metres", "source", "basis", "expected"),
    [
        (0, 1, 1, "prop_sales", "per_m2", None),
        (1, 1, None, "prop_sales", "per_m2", Decimal("1.00")),
        (1, 0, 1, "prop_sales", "per_m2", Decimal("0.09")),
        (1, None, 1, "prop_sales", "per_m2", Decimal("0.09")),
        (1, None, 0, "prop_sales", "per_m2", None),
        (1, None, None, "prop_sales", "per_m2", None),
        (1, 1, None, "prop_sales", "per_unit", Decimal("1.00")),
        (1, 1, None, "prop_resi_units", "per_unit", None),
    ],
)
def test_property_square_foot_price_boundaries(
    tmp_path: Path,
    value: int,
    feet: int | None,
    metres: int | None,
    source: str,
    basis: str,
    expected: Decimal | None,
) -> None:
    base = _parse([_resi()], tmp_path / "frame", _mappings(tmp_path)).deals[0]
    # Deal fields are nullable at this public boundary. Several combinations
    # are removed or normalised by _deal/_unkept before normal aggregation.
    deal = replace(
        base,
        value=Decimal(value),
        area_ft2=None if feet is None else Decimal(feet),
        area_m2=None if metres is None else Decimal(metres),
        source_id=source,
        basis=basis,
        unit_type=None,
    )
    rows = quarter.quarter_aggregates([deal], as_of_by_source=_as_of_map(source))
    assert len(rows) == 1
    assert rows[0]["deal_count"] == 1
    assert rows[0]["median_price_per_ft2"] == expected


@pytest.mark.parametrize(
    ("field", "later", "earlier"),
    [
        ("district_key", "syn_z", "syn_a"),
        ("municipality_code", "syn_z", "syn_a"),
        ("period", "2025-Q4", "2025-Q1"),
        ("use_key", "syn_z", "syn_a"),
    ],
)
def test_property_aggregate_rows_sort_by_each_cell_key(
    tmp_path: Path, field: str, later: str, earlier: str
) -> None:
    base = _parse(
        [_sale()], tmp_path / "frame", _mappings(tmp_path), source_id="prop_sales"
    ).deals[0]
    rows = quarter.quarter_aggregates(
        [replace(base, **{field: later}), replace(base, **{field: earlier})],
        as_of_by_source=_as_of_map("prop_sales"),
    )
    assert [row[field] for row in rows] == [earlier, later]
    assert [row["deal_count"] for row in rows] == [1, 1]


def test_property_aggregate_rows_sort_unit_keys(tmp_path: Path) -> None:
    base = _parse([_resi()], tmp_path / "frame", _mappings(tmp_path)).deals[0]
    # The typed aggregation function accepts string unit keys directly; the
    # present reviewed map emits residential_unit, whose order alone would
    # conceal a missing final sort key.
    rows = quarter.quarter_aggregates(
        [replace(base, unit_type="SYN-Z"), replace(base, unit_type="SYN-A")],
        as_of_by_source=_as_of_map("prop_resi_units"),
    )
    assert [row["unit_type"] for row in rows] == ["SYN-A", "SYN-Z", "all"]
    assert [row["deal_count"] for row in rows] == [1, 1, 2]
