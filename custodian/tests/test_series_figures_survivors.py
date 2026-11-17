"""Independent expectations for selected-series mutation survivors.

Only the existing invented source shapes and cache builders are used.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_public_series import fixture, series_cache
from custodian.tests.test_series_exact_regressions import cancellation

from eii_custodian.publicdata.fetch.build import FetchFailure
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import entry_by_key
from eii_custodian.publicdata.series import figures
from eii_custodian.publicdata.stage import StageResult


def _whole_text(found: object, literal: str) -> None:
    assert str(found) == literal


def _shapes() -> Any:
    return json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("method", " \t", "missing method"),
        ("method_version", "\n", "missing method_version"),
        ("source_chain", [], "missing source_chain"),
        ("source_chain", ({},), "missing source_chain"),
        ("source_chain", [{}], "incomplete source_chain"),
        ("sha256", "not-a-hash", "invalid source_chain hash"),
        ("release_tables", [], "missing source_chain release_tables"),
        ("release_tables", ("invented",), "missing source_chain release_tables"),
        ("field_mapping", {}, "missing source_chain field_mapping"),
    ],
)
def test_validate_whole_refusal(tmp_path, field, value, message):
    entry, _, receipt = fixture(tmp_path)
    envelope = {
        "method": "invented",
        "method_version": "1",
        "source_chain": [receipt],
        "release_tables": list(entry.release_tables),
        "field_mapping": {"invented": "value"},
    }
    if field == "sha256":
        receipt[field] = value
    else:
        envelope[field] = value
    with pytest.raises(ValueError) as caught:
        figures.validate_figure(envelope)
    _whole_text(caught.value, message)


def test_write_nested_exact_json(tmp_path):
    # Public builds create the output parents first, so exercise the helper's
    # own directory contract directly. Decimal is rendered with default=str.
    path = tmp_path / "missing" / "nested" / "invented.json"
    figures._write(path, {"z": "تجريبي", "a": Decimal("1.25")})
    assert path.read_bytes() == '{"a": "1.25", "z": "تجريبي"}\n'.encode()


def test_group_keys_and_zero_row_do_not_end_scan():
    rows = _shapes()["wage_occ"]
    rows[0]["paid_employment_workers"] = 0
    rows[1]["occupation"] = "تجريبي"
    grouped = figures._groups(rows, "wage_occ")
    assert grouped["2020"] == {'["invented-b", "تجريبي"]': (Decimal(3), Decimal(20))}
    assert len(grouped["2025"]) == 2


def test_contracts_escape_slashes_and_keep_active_name():
    shapes = _shapes()
    shapes["wage_occ"][0]["occupation"] = "invented/a"
    assert figures.contract_rows("wage_occ", shapes["wage_occ"])[0][
        "breakdown_key"
    ] == ("gender=invented-a&occupation=invented%2Fa")
    shapes["sec_hr_goods"][0]["type_of_commodity"] = "invented/a"
    assert (
        figures.contract_rows("sec_hr_goods", shapes["sec_hr_goods"])[0]["indicator"]
        == "intermediate_goods:invented%2Fa"
    )
    assert figures.contract_rows("lic_active", shapes["lic_active"]) == [
        {
            "municipality_code": None,
            "activity_code": "invented-code",
            "period": "2025-05",
            "active_count": 3,
            "activity_name_ar": "نشاط تجريبي",
        }
    ]
    transit = figures.contract_rows("transit_monthly", shapes["transit_monthly"])
    assert [row["anomaly_flag"] for row in transit] == [
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
    ]


@pytest.mark.parametrize(
    "case,message",
    [
        ("utility", "duplicate utility period"),
        ("transit", "duplicate transit period"),
        ("wages", "zero change has no mix share"),
        ("indicator", "sec_hr_ind: one restaurant indicator row required"),
        ("size", "sec_hr_size: restaurant size rows required"),
        ("customs", "cus_imp_2025 harmonized_system_code: unexpected code length"),
    ],
)
def test_check_whole_refusals(case, message):
    shapes = _shapes()
    if case == "utility":
        data = {"util_elec": shapes["util_elec"] * 2}
    elif case == "transit":
        data = {"transit_monthly": shapes["transit_monthly"] * 2}
    elif case == "wages":
        row = shapes["wage_occ"][0]
        data = {"wage_occ": [row, dict(row, year="2025")]}
    elif case == "customs":
        row = shapes["cus_imp_2025"][0]
        data = {"cus_imp_2025": [dict(row, harmonized_system_code=12)]}
    else:
        data = {
            key: value for key, value in shapes.items() if key.startswith("sec_hr_")
        }
        data["sec_hr_ind" if case == "indicator" else "sec_hr_size"] = []
    with pytest.raises(ValueError) as caught:
        figures.compute_checks(data)
    _whole_text(caught.value, message)


def test_restaurant_selection_requires_both_axes():
    shapes = _shapes()
    data = {key: value for key, value in shapes.items() if key.startswith("sec_hr_")}
    for rows in data.values():
        row = rows[0]
        rows.extend([dict(row, activity_code=551), dict(row, year="2021")])
    assert figures.compute_checks(data)["PUB-64"] == {
        "establishments": "12",
        "employees": "11",
        "compensation": "12",
        "operating_surplus": "11",
        "average_annual_wage": "17",
        "goods_share_1dp": "2.5",
        "services_share_1dp": "1.3",
    }


def test_present_restaurant_and_sparse_repeated_cancellations():
    shapes = _shapes()
    from custodian.tests.test_pub67 import FRAME, classes

    active = dict(
        shapes["lic_active"][0], rmz_lnsht_ltjry="5610101", lbldy=FRAME[0].name_ar
    )
    issued = dict(shapes["lic_issued"][0], rmz_lnsht_ltjry="5610101")
    checks = figures.compute_checks(
        {"lic_active": [active], "lic_issued": [issued]},
        isic_classes=classes(),
        municipalities=FRAME,
        activity_entry=entry_by_key(load_registry(), "lic_active"),
    )
    assert checks["PUB-67"]["national_5610101"] == "3"
    assert checks["PUB-69"]["restaurant_contract_rows"] == "1"
    assert figures.compute_checks(
        {
            "lic_cancelled": [
                cancellation("2020", 7, 2),
                cancellation("2020", 7, 3),
                cancellation("2020", 1, 5),
            ]
        }
    )["PUB-68"] == {
        "july_2020": "5",
        "june_2022": "0",
        "september_2024": "0",
        "july_2020_bulk": "true",
        "june_2022_bulk": "false",
        "september_2024_bulk": "false",
        "sum_count": "10",
        "undated": "0",
        "dated_total": "10",
        "combined_share_0dp": "50",
    }


@pytest.mark.parametrize("suffix", [" host=invented extra=invented", "\thost=invented"])
def test_finish_selected_line_separator(tmp_path, suffix):
    entry, digest = series_cache(tmp_path, "util_elec", _shapes()["util_elec"])
    lines = [f"PASS util_elec sha256={digest}" + suffix]
    got = figures.finish_build([entry], tmp_path, lines)
    if suffix.startswith(" "):
        assert got == FetchFailure(
            1, "PUB-62", "", "public_data", "section 10 anchor", "PUB-62"
        )
        _whole_text(lines[-1], "FAIL PUB-62 public_data selected-cache check")
    else:
        assert got == FetchFailure(
            1, "series", "", "public_data", "valid selected input", "ValueError"
        )
        _whole_text(lines[-1], "FAIL series selected input refused")


@pytest.mark.parametrize("count", [0, 2])
def test_finish_missing_selected_receipt_all_fields(tmp_path, count):
    entry, digest = series_cache(tmp_path, "util_elec", _shapes()["util_elec"])
    lines = [f"PASS util_elec sha256={digest} host=invented"] * count
    assert figures.finish_build([entry], tmp_path, lines) == FetchFailure(
        1, "util_elec", "", "selected_receipt", "one selected hash", "missing"
    )
    _whole_text(lines[-1], "FAIL util_elec selected receipt missing")


def test_finish_frame_refusal_all_fields(tmp_path):
    entry, digest = series_cache(tmp_path, "lic_active", _shapes()["lic_active"])
    lines = [f"PASS lic_active sha256={digest} host=invented"]
    assert figures.finish_build([entry], tmp_path, lines) == FetchFailure(
        1,
        "series",
        "",
        "public_data",
        "the municipalities of this build's frame",
        "municipality_frame_absent",
    )
    _whole_text(lines[-1], "FAIL series municipality_frame_not_supplied lic_active")


def test_finish_blocked_regression_all_fields(tmp_path, monkeypatch):
    entry, digest = series_cache(tmp_path, "util_elec", [_shapes()["util_elec"][0]])
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    lines = [f"PASS util_elec sha256={digest} host=invented"]
    assert figures.finish_build([entry], tmp_path, lines) == FetchFailure(
        1, "series_mapping", "", "public_data", "section 10 anchor", "series_mapping"
    )
    _whole_text(lines[-1], "FAIL series_mapping public_data selected-cache check")


def test_empty_cancellations_refuse_nonpositive_denominator():
    with pytest.raises(ValueError) as caught:
        figures.compute_checks({"lic_cancelled": []})
    _whole_text(caught.value, "non-positive denominator")
