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
    rows = quarter_aggregates(
        parsed.deals, as_of_by_source={"prop_sales": INVENTED_AS_OF}
    )
    row = dict(_all_row(rows))
    row.pop("as_of", None)
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


def test_assembly_land_price_rows_carry_receipt_as_of(tmp_path) -> None:
    import json
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_source_completeness import receipt

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    row = replace(
        next(e for e in load_registry() if e.source_id == "gis_land_price"),
        key="gis_land_price",
    )
    feature = {
        "attributes": {
            "DIST_NO": 14,
            "District_No": 14,
            "ResidentialPrices": "1",
            "ResidentialCityCenter": "1",
            "ResidentialPriceFlats": "1",
            "ResidentialPriceVillas": "1",
            "CommercialPrices": "1",
        },
        "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
    }
    digest = write_cached(
        tmp_path, row, json.dumps({"layers": [{"features": [feature]}]}).encode()
    )
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest.stem}
    build.receipts = {row.key: receipt(row)}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    build.gis_property_singles()
    expected = as_of_from_receipt(build.receipts[row.key])
    for land_row in build.tables["pub_land_price"]:
        if land_row.get("guide_price") is not None:
            assert land_row["as_of"] == expected


def test_assembly_refuses_land_price_missing_as_of(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_source_completeness import receipt

    import eii_custodian.publicdata.gis.layers as gis_layers
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    row = replace(
        next(e for e in load_registry() if e.source_id == "gis_land_price"),
        key="gis_land_price",
    )
    feature = {
        "attributes": {
            "DIST_NO": 14,
            "District_No": 14,
            "ResidentialPrices": "1",
            "ResidentialCityCenter": "1",
            "ResidentialPriceFlats": "1",
            "ResidentialPriceVillas": "1",
            "CommercialPrices": "1",
        },
        "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
    }
    digest = write_cached(
        tmp_path, row, json.dumps({"layers": [{"features": [feature]}]}).encode()
    )
    original = gis_layers.land_price_rows

    def omit_as_of(*args, **kwargs):
        rows = original(*args, **kwargs)
        broken = [dict(item) for item in rows]
        broken[0].pop("as_of", None)
        return broken

    monkeypatch.setattr(gis_layers, "land_price_rows", omit_as_of)
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest.stem}
    build.receipts = {row.key: receipt(row)}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    with pytest.raises(AdditionError, match="price_as_of_missing"):
        build.gis_property_singles()


def test_assembly_property_quarter_carries_receipt_as_of(tmp_path) -> None:
    import json
    import shutil
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_property_quarter import USE_MAP, _frame, _parse, _sale
    from custodian.tests.test_property_sales_export import _export
    from custodian.tests.test_source_completeness import receipt

    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    _frame(tmp_path)
    shutil.copy(USE_MAP, tmp_path / "property_use_map.csv")
    assert _parse([_sale()], tmp_path, source_id="prop_sales").deals
    digest = write_cached(tmp_path, row, json.dumps([_export()]).encode())
    build = context(tmp_path, (row,))
    build.review = tmp_path
    build.selected = {row.key: digest.stem}
    build.receipts = {row.key: receipt(row)}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    build.gis_property_singles()
    quarter_row = next(row for row in build.tables["pub_property_quarter"])
    assert quarter_row["as_of"] == as_of_from_receipt(build.receipts[row.key])


SALES_SNAPSHOT_AS_OF = "2026-11-17"
RESI_SNAPSHOT_AS_OF = "2026-11-18"


@pytest.mark.parametrize(
    ("field", "identifier"),
    (
        ("encrypted_transaction_number", "SYN-TX-Z"),
        ("price_basis", "SYN-TX-S1"),
        ("price_basis", "SYN-PX-S1"),
        ("price_basis", "SYN-TX-1"),
        ("price_basis", "SYN-PX-1"),
    ),
)
def test_assembly_refuses_quarter_identifier_before_writing_table(
    tmp_path, monkeypatch: pytest.MonkeyPatch, field: str, identifier: str
) -> None:
    """PUB-14: neither bulletin's identifiers may cross the assembly boundary."""
    import json
    import shutil
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_property_quarter import USE_MAP, _frame, _resi
    from custodian.tests.test_property_sales_export import _export

    import eii_custodian.publicdata.property.quarter as quarter_mod
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    registry = load_registry()
    entries = tuple(
        replace(next(e for e in registry if e.source_id == source), key=source)
        for source in ("prop_sales", "prop_resi_units")
    )
    _frame(tmp_path)
    shutil.copy(USE_MAP, tmp_path / "property_use_map.csv")
    selected = {
        row.key: write_cached(tmp_path, row, json.dumps([raw]).encode()).stem
        for row, raw in zip(entries, (_export(), _resi()), strict=True)
    }
    original = quarter_mod.quarter_aggregates

    def leak_identifier(*args, **kwargs):
        rows = original(*args, **kwargs)
        assert rows
        return (dict(rows[0], **{field: identifier}), *rows[1:])

    monkeypatch.setattr(quarter_mod, "quarter_aggregates", leak_identifier)
    build = context(tmp_path, entries)
    build.review = tmp_path
    build.selected = selected
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    with pytest.raises(AdditionError, match="identifier_leak") as caught:
        build.gis_property_singles()
    assert caught.value.name == "identifier_leak"
    assert "pub_property_quarter" not in build.tables
    assert "pub_property_quarter" not in build.table_sources
    assert not (tmp_path / "assembly" / "gis_property_singles.json").exists()


def test_assembly_refuses_quarter_foreign_source_as_of(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import shutil
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_property_quarter import USE_MAP, _frame, _resi
    from custodian.tests.test_property_sales_export import _export

    import eii_custodian.publicdata.property.quarter as quarter_mod
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    sale_row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    resi_row = replace(
        next(e for e in load_registry() if e.source_id == "prop_resi_units"),
        key="prop_resi_units",
    )
    _frame(tmp_path)
    shutil.copy(USE_MAP, tmp_path / "property_use_map.csv")
    (tmp_path / "district_crosswalk.csv").write_text(
        "name,district_keys\n"
        "SYN North,syn_north\nSYN North AR,syn_north\n"
        "SYN Inland,syn_inland\nSYN Inland AR,syn_inland\n",
        encoding="utf-8",
    )
    inland = dict(
        district_name="SYN Inland",
        sm_lmntq="SYN Inland AR",
        municipality_name="SYN Inland",
        sm_lbldy="SYN Inland AR",
    )
    sale_digest = write_cached(
        tmp_path,
        sale_row,
        json.dumps([_export()]).encode(),
        retrieved_utc="2026-11-17T00:00:00Z",
    )
    resi_digest = write_cached(
        tmp_path,
        resi_row,
        json.dumps([_resi(**inland)]).encode(),
        retrieved_utc="2026-11-18T00:00:00Z",
    )
    original = quarter_mod.quarter_aggregates

    def stamp_foreign_as_of(deals, *, as_of_by_source):
        rows = original(deals, as_of_by_source=as_of_by_source)
        broken = [dict(item) for item in rows]
        for item in broken:
            if item["district_key"] == "syn_north" and item["unit_type"] == "all":
                item["as_of"] = RESI_SNAPSHOT_AS_OF
        return tuple(broken)

    monkeypatch.setattr(quarter_mod, "quarter_aggregates", stamp_foreign_as_of)
    build = context(tmp_path, (sale_row, resi_row))
    build.review = tmp_path
    build.selected = {sale_row.key: sale_digest.stem, resi_row.key: resi_digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    with pytest.raises(AdditionError, match="price_as_of_missing"):
        build.gis_property_singles()


def test_assembly_refuses_quarter_wrong_snapshot_as_of(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import shutil
    from dataclasses import replace

    from custodian.tests.test_production_adapters import context
    from custodian.tests.test_property_quarter import USE_MAP, _frame, _parse, _sale
    from custodian.tests.test_property_sales_export import _export
    from custodian.tests.test_source_completeness import receipt

    import eii_custodian.publicdata.property.quarter as quarter_mod
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.frame.build import FrameResult
    from eii_custodian.publicdata.review.cache_fixture import write_cached

    row = replace(
        next(e for e in load_registry() if e.source_id == "prop_sales"),
        key="prop_sales",
    )
    _frame(tmp_path)
    shutil.copy(USE_MAP, tmp_path / "property_use_map.csv")
    assert _parse([_sale()], tmp_path, source_id="prop_sales").deals
    digest = write_cached(tmp_path, row, json.dumps([_export()]).encode())
    original = quarter_mod.quarter_aggregates

    def wrong_date(*args, **kwargs):
        rows = original(*args, **kwargs)
        broken = [dict(item) for item in rows]
        for item in broken:
            if item.get("as_of"):
                item["as_of"] = OTHER_AS_OF
        return broken

    monkeypatch.setattr(quarter_mod, "quarter_aggregates", wrong_date)
    build = context(tmp_path, (row,))
    build.review = tmp_path
    build.selected = {row.key: digest.stem}
    build.receipts = {row.key: receipt(row)}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    with pytest.raises(AdditionError, match="price_as_of_missing"):
        build.gis_property_singles()
