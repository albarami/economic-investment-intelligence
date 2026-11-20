"""INVENTED: snapshot-dated ``as_of`` on property price figures."""

from __future__ import annotations

from decimal import Decimal

import pytest
from custodian.tests.test_property_quarter import _all_row, _parse, _resi, _sale

from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.gis.layers import land_price_rows
from eii_custodian.publicdata.property.price_as_of import (
    as_of_from_receipt,
    require_price_as_of,
    require_rows_price_as_of,
)
from eii_custodian.publicdata.property.quarter import quarter_aggregates

INVENTED_AS_OF = "2026-11-14"
OTHER_AS_OF = "2026-11-15"


def test_as_of_from_receipt_uses_snapshot_retrieval_date() -> None:
    assert (
        as_of_from_receipt({"retrieved_utc": "2026-11-14T08:00:00Z"}) == INVENTED_AS_OF
    )


def test_quarter_rows_carry_snapshot_as_of(tmp_path) -> None:
    parsed = _parse([_sale()], tmp_path, source_id="prop_sales")
    rows = quarter_aggregates(
        parsed.deals, as_of_by_source={"prop_sales": INVENTED_AS_OF}
    )
    row = _all_row(rows)
    assert row["as_of"] == INVENTED_AS_OF
    assert row["deal_value"] is not None


def test_quarter_refuses_missing_as_of(tmp_path) -> None:
    parsed = _parse([_sale()], tmp_path, source_id="prop_sales")
    row = _all_row(quarter_aggregates(parsed.deals))
    with pytest.raises(AdditionError, match="price_as_of_missing"):
        require_rows_price_as_of((row,))


def test_quarter_refuses_other_snapshot_as_of(tmp_path) -> None:
    parsed = _parse([_sale()], tmp_path, source_id="prop_sales")
    rows = quarter_aggregates(
        parsed.deals, as_of_by_source={"prop_sales": INVENTED_AS_OF}
    )
    row = dict(_all_row(rows))
    row["as_of"] = OTHER_AS_OF
    with pytest.raises(AdditionError, match="price_as_of_missing"):
        require_price_as_of(row, INVENTED_AS_OF)


def test_quarter_refuses_mismatched_source_snapshot_dates(tmp_path) -> None:
    sale = _parse([_sale()], tmp_path / "sale", source_id="prop_sales")
    resi = _parse([_resi()], tmp_path / "resi", source_id="prop_resi_units")
    deals = sale.deals + resi.deals
    mapping = {"prop_sales": INVENTED_AS_OF, "prop_resi_units": OTHER_AS_OF}
    with pytest.raises(AdditionError, match="price_as_of_mismatch"):
        quarter_aggregates(deals, as_of_by_source=mapping)


def test_land_price_rows_carry_as_of() -> None:
    feature = {
        "attributes": {
            "DIST_NO": 14,
            "District_No": 14,
            "ANAME": "SYN",
            "ENAME": "SYN DISTRICT",
            "ResidentialPrices": "1,200",
            "ResidentialCityCenter": "2,000",
            "ResidentialPriceFlats": "3,000",
            "ResidentialPriceVillas": "4,000",
            "CommercialPrices": "5,000",
        },
        "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
    }
    rows = land_price_rows([feature], "LandPricing2026", as_of=INVENTED_AS_OF)
    price = next(row for row in rows if row["use_category"] == "ResidentialPrices")
    assert price["as_of"] == INVENTED_AS_OF
    assert price["guide_price"] == Decimal("1200.00")
