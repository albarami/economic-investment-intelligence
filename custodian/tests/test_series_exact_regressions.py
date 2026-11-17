"""Invented regressions from the lead's verification, with literal expectations."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest
from custodian.tests.test_public_series import series_cache

from eii_custodian.publicdata.series.figures import compute_checks, country_totals


def pub64_rows():
    """Source-shaped invented rows; no separate total row in either group."""
    shapes = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    data = {
        key: shapes[key]
        for key in ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size")
    }
    data["sec_hr_ind"] = [
        {
            **data["sec_hr_ind"][0],
            "compensation_of_employees_value_in_1_000_qr": 3,
            "operating_surplus_value_in_1_000_qr": 7,
            "productivity_of_employee_qr": 2500,
            "value_added_per_worker_qr": 999,
            "average_annual_wage_qr": 123,
            "percentage_of_intermediate_goods_to_output": 40,
            "percentage_of_intermediate_services_to_output": 15,
        }
    ]
    goods = data["sec_hr_goods"][0]
    data["sec_hr_goods"] = [
        {
            **goods,
            "type_of_commodity": label,
            "estimates_of_intermediate_goods_value_value_in_1_000_qr": value,
        }
        for label, value in (
            ("fOoD sTuFf", 30),
            ("BEVERAGES", 10),
            ("invented-other", 40),
        )
    ]
    services = data["sec_hr_serv"][0]
    data["sec_hr_serv"] = [
        {
            **services,
            "type_of_service": label,
            "estimates_of_intermediate_services_value_value_in_1_000_qr": value,
        }
        for label, value in (("rEnTs Of BuIlDiNgS", 11), ("invented-other", 13))
    ]
    size = data["sec_hr_size"][0]
    data["sec_hr_size"] = [
        {
            **size,
            "size_of_establishment": label,
            "number_of_employees": employees,
            "number_of_establishments": establishments,
        }
        for label, employees, establishments in (
            ("invented-small", 3, 2),
            ("invented-large", 5, 1),
        )
    ]
    return data


# An oracle authored independently of EXPECTED and sector_norms. Goods sum to
# 80, services to 24, employees to 8. Food 30/80*40=15, beverages 10/80*40=5;
# rent 11/24*15=6.875 -> 6.9; compensation 3000/8/2500*100=15;
# surplus 7000/8/2500*100=35. Published wage/productivity are distinct inputs.
PUB64_INVENTED = {
    "establishments": "3",
    "employees": "8",
    "compensation": "3",
    "operating_surplus": "7",
    "average_annual_wage": "123",
    "output_per_employee": "2500",
    "goods_share_1dp": "40.0",
    "services_share_1dp": "15.0",
    "compensation_share_1dp": "15.0",
    "operating_surplus_share_1dp": "35.0",
    "food_share_1dp": "15.0",
    "beverages_share_1dp": "5.0",
    "building_rent_share_1dp": "6.9",
}
PUB64_NEW_KEYS = (
    "output_per_employee",
    "compensation_share_1dp",
    "operating_surplus_share_1dp",
    "food_share_1dp",
    "beverages_share_1dp",
    "building_rent_share_1dp",
)


def pub64_receipts(data):
    """Invented receipt metadata for direct arithmetic calls only."""
    return {
        source: {
            "source_id": source,
            "publisher": "Invented publisher",
            "slug": source,
            "licence_id": "CC-BY-4.0",
            "licence_basis": "dataset",
            "retrieved_utc": "2026-11-14T00:00:00Z",
            "sha256": "a" * 64,
            "fetch_url": "https://example.invalid/" + source,
        }
        for source in data
    }


def pub64_build(tmp_path, data):
    from eii_custodian.publicdata.series.figures import build_series

    entries, selected = [], {}
    for source, rows in data.items():
        entry, digest = series_cache(tmp_path, source, rows)
        entries.append(entry)
        selected[source] = digest
    return build_series(tmp_path, entries, selected)


def test_pub64_computes_all_norms_from_mapped_fields(tmp_path):
    data = pub64_rows()
    # Wrong activity and wrong year have conspicuous values and must be ignored.
    for rows in data.values():
        row = rows[0]
        rows.extend([{**row, "activity_code": 999}, {**row, "year": "2021"}])
    result = pub64_build(tmp_path, data)
    assert result["checks"]["PUB-64"] == PUB64_INVENTED
    assert result["mismatch"] == "PUB-64"  # invented values are not pack anchors
    evidence = json.loads((tmp_path / "series/regression/PUB-64.json").read_text())
    assert evidence["values"] == PUB64_INVENTED
    assert {r["source_id"]: r["sha256"] for r in evidence["source_chain"]} == result[
        "selected"
    ]
    assert not list((tmp_path / "series/display").glob("*.json"))
    assert "production_value" not in evidence["values"]
    assert "output_per_establishment" not in evidence["values"]


def test_pub64_rounds_once_at_half_up_boundary(tmp_path):
    data = pub64_rows()
    # Raw goods 40.35: food 30/80*40.35=15.13125 -> 15.1;
    # beverages 10/80*40.35=5.04375 -> 5.0. Published goods -> 40.4.
    # Using 40.4 early instead yields food 15.2 and beverages 5.1.
    data["sec_hr_ind"][0]["percentage_of_intermediate_goods_to_output"] = 40.35
    got = pub64_build(tmp_path, data)["checks"]["PUB-64"]
    assert got == {
        **PUB64_INVENTED,
        "goods_share_1dp": "40.4",
        "food_share_1dp": "15.1",
    }


@pytest.mark.parametrize(
    "source,label,component",
    [
        ("sec_hr_goods", "type_of_commodity", "food stuff"),
        ("sec_hr_goods", "type_of_commodity", "beverages"),
        ("sec_hr_serv", "type_of_service", "rents of buildings"),
    ],
)
@pytest.mark.parametrize(
    "violation", ["missing", "duplicate", "wrong_activity", "wrong_year"]
)
def test_pub64_component_selection_refuses(
    tmp_path, source, label, component, violation
):
    data = pub64_rows()
    row = next(r for r in data[source] if r[label].casefold() == component)
    if violation == "missing":
        data[source].remove(row)
    elif violation == "duplicate":
        data[source].append({**row, label: row[label].swapcase()})
    elif violation == "wrong_activity":
        row["activity_code"] = 999
    else:
        row["year"] = "2021"
    result = pub64_build(tmp_path, data)
    assert result["mismatch"] == "PUB-64"
    assert "PUB-64" not in result["checks"]
    reason = (
        source + ": duplicate restaurant source row"
        if violation == "duplicate"
        else source
        + ": one component required: "
        + {
            "food stuff": "Food Stuff",
            "beverages": "Beverages",
            "rents of buildings": "Rents of Buildings",
        }[component]
    )
    assert list(result["blocked"].values()) == [("regression: " + reason,)]
    assert not (tmp_path / "series/regression/PUB-64.json").exists()


@pytest.mark.parametrize(
    "source", ["sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"]
)
@pytest.mark.parametrize(
    "violation", ["empty", "wrong_activity", "wrong_year", "duplicate"]
)
def test_pub64_source_selection_refuses(tmp_path, source, violation):
    data = pub64_rows()
    if violation == "empty":
        data[source] = []
    elif violation == "duplicate":
        # Include a non-component duplicate: totals must not silently grow.
        data[source].append(dict(data[source][-1]))
    else:
        field, value = (
            ("activity_code", 999)
            if violation == "wrong_activity"
            else ("year", "2021")
        )
        data[source] = [{**r, field: value} for r in data[source]]
    result = pub64_build(tmp_path, data)
    assert result["mismatch"] == "PUB-64"
    assert "PUB-64" not in result["checks"]
    if source == "sec_hr_ind":
        reason = "sec_hr_ind: one restaurant indicator row required"
    elif violation == "duplicate":
        reason = source + ": duplicate restaurant source row"
    elif source == "sec_hr_size":
        reason = "sec_hr_size: restaurant size rows required"
    else:
        reason = source + ": restaurant rows required"
    assert list(result["blocked"].values()) == [("regression: " + reason,)]


@pytest.mark.parametrize(
    "violation",
    ["employees", "productivity", "goods_total", "services_total", "outside_total"],
)
def test_pub64_invalid_denominators_refuse(tmp_path, violation):
    data = pub64_rows()
    if violation == "employees":
        for row in data["sec_hr_size"]:
            row["number_of_employees"] = 0
    elif violation == "productivity":
        data["sec_hr_ind"][0]["productivity_of_employee_qr"] = 0
    else:
        source, field = (
            (
                "sec_hr_serv",
                "estimates_of_intermediate_services_value_value_in_1_000_qr",
            )
            if violation == "services_total"
            else (
                "sec_hr_goods",
                "estimates_of_intermediate_goods_value_value_in_1_000_qr",
            )
        )
        if violation == "outside_total":
            data[source][-1][field] = -25  # food 30 exceeds the resulting total 15
        else:
            for row in data[source]:
                row[field] = 0
    result = pub64_build(tmp_path, data)
    assert result["mismatch"] == "PUB-64"
    assert "PUB-64" not in result["checks"]


@pytest.mark.parametrize(
    "violation",
    [
        "absent",
        "missing_source",
        "wrong_source",
        "empty_publisher",
        "bad_hash",
        "bad_date",
        "bad_timestamp",
        "bad_url",
        "missing_licence",
        "absent_field",
    ],
)
def test_pub64_requires_receipt_lineage(violation):
    data = pub64_rows()
    receipts = pub64_receipts(data)
    if violation == "absent":
        with pytest.raises(ValueError) as caught:
            compute_checks(data)
        assert str(caught.value) == "PUB-64 receipts required"
        return
    if violation == "missing_source":
        del receipts["sec_hr_size"]
    elif violation == "absent_field":
        del receipts["sec_hr_goods"]["publisher"]
    else:
        field, value = {
            "wrong_source": ("source_id", "invented-other"),
            "empty_publisher": ("publisher", ""),
            "bad_hash": ("sha256", "bad"),
            "bad_date": ("retrieved_utc", "2026-02-30T00:00:00Z"),
            "bad_timestamp": ("retrieved_utc", "2026-11-14Tnot-a-time"),
            "bad_url": ("fetch_url", "invalid"),
            "missing_licence": ("licence_id", ""),
        }[violation]
        receipts["sec_hr_goods"][field] = value
    with pytest.raises(ValueError) as caught:
        compute_checks(data, receipts=receipts)
    expected = {
        "missing_source": "PUB-64 receipts required",
        "wrong_source": "PUB-64 receipt source mismatch",
        "absent_field": "PUB-64 incomplete receipt",
    }
    if violation in expected:
        assert str(caught.value) == expected[violation]


@pytest.mark.public_data
@pytest.mark.parametrize("key", PUB64_NEW_KEYS)
def test_pub64_wrong_anchor_fails_stage(tmp_path, monkeypatch, key):
    from eii_custodian.publicdata.stage import EXPECTED, run_stage

    # This independent invented oracle is test-local; production anchors stay fixed.
    monkeypatch.setitem(EXPECTED, "PUB-64", dict(PUB64_INVENTED))
    assert pub64_build(tmp_path, pub64_rows())["mismatch"] == ""
    monkeypatch.setitem(EXPECTED["PUB-64"], key, "planted-wrong")
    assert run_stage(tmp_path, required=("PUB-64",), evidence=True).mismatch == "PUB-64"
    monkeypatch.setitem(EXPECTED["PUB-64"], key, PUB64_INVENTED[key])
    path = tmp_path / "series/regression/PUB-64.json"
    evidence = json.loads(path.read_text())
    del evidence["values"][key]
    path.write_text(json.dumps(evidence))
    assert run_stage(tmp_path, required=("PUB-64",), evidence=True).mismatch == "PUB-64"


@pytest.mark.public_data
@pytest.mark.parametrize(
    "source,first,second",
    [
        ("sec_hr_ind", "productivity_of_employee_qr", "value_added_per_worker_qr"),
        (
            "sec_hr_ind",
            "percentage_of_intermediate_goods_to_output",
            "percentage_of_intermediate_services_to_output",
        ),
        (
            "sec_hr_goods",
            "type_of_commodity",
            "estimates_of_intermediate_goods_value_value_in_1_000_qr",
        ),
        (
            "sec_hr_serv",
            "type_of_service",
            "estimates_of_intermediate_services_value_value_in_1_000_qr",
        ),
    ],
)
def test_pub64_wrong_mapping_fails_stage(tmp_path, monkeypatch, source, first, second):
    from eii_custodian.publicdata.series.parse import FIELD_MAP
    from eii_custodian.publicdata.stage import EXPECTED

    monkeypatch.setitem(EXPECTED, "PUB-64", dict(PUB64_INVENTED))
    data = pub64_rows()
    assert pub64_build(tmp_path, data)["mismatch"] == ""
    mapping = dict(FIELD_MAP[source])
    mapping[first], mapping[second] = mapping[second], mapping[first]
    monkeypatch.setitem(FIELD_MAP, source, mapping)
    result = pub64_build(tmp_path, data)
    assert result["mismatch"] == "PUB-64"
    if source in ("sec_hr_goods", "sec_hr_serv"):
        assert list(result["blocked"].values()) == [
            ("regression: PUB-64 numeric source field required",)
        ]


@pytest.mark.parametrize(
    "source,field,slot",
    [
        ("sec_hr_ind", "productivity_of_employee_qr", "value:productivity_of_employee"),
        ("sec_hr_ind", "value_added_per_worker_qr", "value:value_added_per_worker"),
        (
            "sec_hr_ind",
            "compensation_of_employees_value_in_1_000_qr",
            "value:compensation",
        ),
        (
            "sec_hr_ind",
            "operating_surplus_value_in_1_000_qr",
            "value:operating_surplus",
        ),
        ("sec_hr_ind", "average_annual_wage_qr", "value:average_annual_wage"),
        (
            "sec_hr_ind",
            "percentage_of_intermediate_goods_to_output",
            "value:goods_share",
        ),
        (
            "sec_hr_ind",
            "percentage_of_intermediate_services_to_output",
            "value:services_share",
        ),
        (
            "sec_hr_goods",
            "estimates_of_intermediate_goods_value_value_in_1_000_qr",
            "value:intermediate_goods",
        ),
        (
            "sec_hr_serv",
            "estimates_of_intermediate_services_value_value_in_1_000_qr",
            "value:intermediate_services",
        ),
        ("sec_hr_size", "number_of_employees", "value:employees"),
        ("sec_hr_size", "number_of_establishments", "value:establishments"),
    ],
)
def test_pub64_registry_mapping_is_independent(source, field, slot):
    from eii_custodian.publicdata.series.parse import FIELD_MAP

    assert FIELD_MAP[source][field] == ("pub_sector_accounts", slot)


def test_pub64_uses_receipt_backed_core_inputs(tmp_path, monkeypatch):
    from eii_core.calc.facts import SourceChain
    from eii_core.calc.sector_economics import sector_norms
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.series import figures

    seen = []

    def norms(**kwargs):
        seen.append(kwargs)
        return sector_norms(**kwargs)

    monkeypatch.setattr(figures, "sector_norms", norms, raising=False)
    result = pub64_build(tmp_path, pub64_rows())
    assert result["checks"]["PUB-64"] == PUB64_INVENTED
    assert len(seen) == 1
    inputs = seen[0]
    entries = {e.source_id: e for e in load_registry()}

    def source_chain(source):
        entry = entries[source]
        return SourceChain(
            lineage_ref=source + ":" + result["selected"][source],
            table="pub_sector_accounts",
            method="public-series",
            version="1",
            publisher=entry.publisher,
            dataset=entry.slug,
            url=entry.url,
            licence=entry.licence_id,
            retrieved="2026-11-14",
            sha256=result["selected"][source],
        )

    assert set(inputs) == {
        "employees",
        "productivity",
        "compensation_thousand",
        "surplus_thousand",
        "goods_percent",
        "services_percent",
        "components",
    }
    for key, unit, source in (
        ("employees", "count", "sec_hr_size"),
        ("productivity", "qar", "sec_hr_ind"),
        ("compensation_thousand", "qar_thousand", "sec_hr_ind"),
        ("surplus_thousand", "qar_thousand", "sec_hr_ind"),
        ("goods_percent", "percent", "sec_hr_ind"),
        ("services_percent", "percent", "sec_hr_ind"),
    ):
        reading = inputs[key]
        assert reading.unit == unit
        assert (reading.geography, reading.geography_kind, reading.period) == (
            "national",
            "national",
            "2022",
        )
        assert reading.input_class == "public"
        assert reading.sources == (source_chain(source),)
    assert [c.group_total.value for c in inputs["components"]] == [D(80), D(80), D(24)]
    for c, source in zip(
        inputs["components"],
        ("sec_hr_goods", "sec_hr_goods", "sec_hr_serv"),
        strict=True,
    ):
        assert c.value.unit == c.group_total.unit == "qar_thousand"
        assert c.group == c.total_group
        assert c.value.sources == c.group_total.sources == (source_chain(source),)


@pytest.mark.parametrize("violation", ["missing", "duplicate"])
def test_pub64_mapping_slot_must_be_unique(monkeypatch, violation):
    from eii_custodian.publicdata.series.parse import FIELD_MAP

    data = pub64_rows()
    mapping = dict(FIELD_MAP["sec_hr_ind"])
    field = "productivity_of_employee_qr"
    if violation == "missing":
        del mapping[field]
    else:
        mapping["invented_alias"] = mapping[field]
    monkeypatch.setitem(FIELD_MAP, "sec_hr_ind", mapping)
    with pytest.raises(ValueError) as caught:
        compute_checks(data, receipts=pub64_receipts(data))
    assert (
        str(caught.value)
        == "sec_hr_ind: one field required for value:productivity_of_employee"
    )


@pytest.mark.parametrize("violation", ["untyped", "nonnumeric"])
def test_pub64_refuses_nonnumeric_core_result(tmp_path, monkeypatch, violation):
    from types import SimpleNamespace

    from eii_core.calc.sector_economics import sector_norms
    from eii_custodian.publicdata.series import figures

    def norms(**kwargs):
        result = sector_norms(**kwargs)
        if violation == "untyped":
            result["food_share_1dp"] = SimpleNamespace(value=D("15.0"))
        else:
            # Plant corruption after construction, so the adapter's check is reached.
            object.__setattr__(result["food_share_1dp"], "value", "not numeric")
        return result

    monkeypatch.setattr(figures, "sector_norms", norms, raising=False)
    result = pub64_build(tmp_path, pub64_rows())
    assert result["mismatch"] == "PUB-64"
    assert "PUB-64" not in result["checks"]
    assert list(result["blocked"].values()) == [
        ("regression: PUB-64 numeric C4 result required",)
    ]


def test_missing_restaurant_size_refuses():
    data = {
        key: [] for key in ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size")
    }
    data["sec_hr_ind"] = [
        dict(
            activity_code="561",
            year="2022",
            compensation_of_employees_value_in_1_000_qr=1,
            operating_surplus_value_in_1_000_qr=1,
            average_annual_wage_qr=1,
            percentage_of_intermediate_goods_to_output=1,
            percentage_of_intermediate_services_to_output=1,
        )
    ]
    with pytest.raises(ValueError, match="sec_hr_size: restaurant size rows required"):
        compute_checks(data)


def cancellation(year, month, count):
    return dict(sn_llg=year, shhr_llg=month, dd_lrkhs_lmlg=count)


@pytest.mark.parametrize("year,month", [("2025", 6), ("2014", 12)])
def test_outside_calendar_refuses_at_check(year, month):
    rows = [
        cancellation("2020", 7, 42),
        cancellation("2022", 6, 9),
        cancellation("2024", 9, 8),
        cancellation("2020", 1, 2),
        cancellation(None, None, 9),
    ]
    with pytest.raises(
        ValueError,
        match=f"lic_cancelled period outside the C2 calendar: {year}-{month:02}",
    ):
        compute_checks({"lic_cancelled": [*rows, cancellation(year, month, 4)]})
    # 42+9+8+2=61 dated; 59/61*100=96.721... -> 97, plus 9 undated.
    result = compute_checks({"lic_cancelled": rows})["PUB-68"]
    assert result["dated_total"] == "61"
    assert result["sum_count"] == "70"
    assert result["combined_share_0dp"] == "97"


def test_quantity_without_unit_is_not_totalled():
    rows = [
        dict(origin_iso3="SYN", value_qar=D(100), weight_kg=D(4), quantity=D(3)),
        dict(origin_iso3="SYN", value_qar=D(30), weight_kg=D(2), quantity=D(40)),
    ]
    assert country_totals(rows) == [
        dict(country="SYN", row_count=2, value_qar=D(130), weight_kg=D(6))
    ]
