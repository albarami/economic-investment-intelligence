"""Invented regressions from the lead's verification, with literal expectations."""

from decimal import Decimal as D

import pytest

from eii_custodian.publicdata.series.figures import compute_checks, country_totals


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
