"""MTH-03 independent path-input replays and exact invented-input arithmetic.

Only invented tmp_path files are read. The assumed file shapes are recorded in
method_card_data_replay.py and must be confirmed against live sources in pass 2.
There are no actual public pins yet. C6 and C7 production calculators are absent
on this tree: their tests exercise independent reference arithmetic only; they
are not evidence that a production implementation exists.
"""

from decimal import Decimal as D

import pytest

from eii_core.calc.facts import Measure, SourceChain
from eii_core.calc.public_methods import TradeRow, supplier_metrics, wilson
from eii_core.calc.public_series import rounded

from .method_card_data_replay import (
    replay_c5,
    replay_c6,
    replay_c7,
    replay_c14,
    replay_wilson,
)
from .method_card_pin_fixtures import write_json

PRIOR = tuple(f"2024-{m:02}" for m in range(1, 13))
# Both windows are explicit invented choices, not live-release coverage claims.
LATEST = tuple(f"2025-{m:02}" for m in range(1, 13))
FINE = ("1902.11.10.0000", "1902.19.10.0000")


def test_independent_wilson_paths_and_arithmetic(tmp_path):
    active = write_json(
        tmp_path / "invented-active.json",
        [
            {
                "lbldy": "invented_muni",
                "rmz_lnsht_ltjry": "invented_activity",
                "dd_lrkhs_lnsht": 28,
            },
            {
                "lbldy": "other_muni",
                "rmz_lnsht_ltjry": "invented_activity",
                "dd_lrkhs_lnsht": 99,
            },
        ],
    )
    cancelled = write_json(
        tmp_path / "invented-cancelled.json",
        [
            {
                "lbldy": "invented_muni",
                "rmz_lnsht_ltjry": "invented_activity",
                "sn_llg": "2024",
                "shhr_llg": m,
                "dd_lrkhs_lmlg": 1,
            }
            for m in range(1, 7)
        ],
    )
    result = replay_wilson(
        active,
        cancelled,
        municipality="invented_muni",
        activity="invented_activity",
        period=PRIOR,
    )
    assert result["period"] == "2024-01..2024-12"
    assert (result["k"], result["n"]) == (6, 28)
    low, high = wilson(result["k"], result["n"])
    assert rounded(low, 6) == result["low"] == "0.102123"
    assert rounded(high, 6) == result["high"] == "0.395389"
    assert result["z"] == "1.96"


def customs_files(tmp_path):
    # Raw source field names follow the registry; extra publisher columns and
    # actual null/number encodings still require the live check in pass 2.
    prior = [
        {
            "lsn_year": "2024",
            "lshhr_month": m,
            "hs8": "1902.11.10",
            "country_of_origin": "invented_origin_a",
            "weight_kg": 1,
            "value_qr": 10,
        }
        for m in range(1, 13)
    ]
    latest = [
        {
            "year": "2025",
            "month": m,
            "harmonized_system_code": "1902.11.10.0000",
            "country_of_origin": origin,
            "weight_in_kilograms": weight,
            "value_in_qatari_riyals": value,
        }
        for m in range(1, 13)
        for origin, weight, value in (
            ("invented_origin_a", 2, 10),
            ("invented_origin_b", 0, 30),
        )
    ]
    # A reviewed exclusion and unrelated year must not enter any sum.
    latest.append(
        dict(
            latest[0],
            harmonized_system_code="1902.30.10.0000",
            value_in_qatari_riyals=999,
        )
    )
    prior.append(dict(prior[0], lsn_year="2019", value_qr=999))
    return write_json(tmp_path / "invented-prior.json", prior), write_json(
        tmp_path / "invented-latest.json", latest
    )


def test_independent_c5_paths(tmp_path):
    before, after = customs_files(tmp_path)
    result = replay_c5(
        before, after, prior_months=PRIOR, latest_months=LATEST, fine_codes=FINE
    )
    assert result == {
        "hhi": D(6250),
        "prior12": D(120),
        "latest12": D(480),
        "trend": D(3),
    }


def test_c5_arithmetic_on_exact_replayed_inputs(tmp_path):
    before, after = customs_files(tmp_path)
    expected = replay_c5(
        before, after, prior_months=PRIOR, latest_months=LATEST, fine_codes=FINE
    )
    # This adapter copies the invented raw fields; the independent oracle above
    # never calls this adapter or supplier_metrics.
    import json

    chain = SourceChain(
        "invented",
        "invented_table",
        "invented_method",
        "v1",
        "invented publisher",
        "invented dataset",
        "https://example.invalid/invented",
        "invented-licence",
        "2026-11-18",
        "a" * 64,
    )

    def reading(value, unit, month):
        return Measure(
            D(value), unit, month, "national", "national", "public", (chain,)
        )

    def trade(row, old):
        month = f"{row['lsn_year'] if old else row['year']}-{int(row['lshhr_month'] if old else row['month']):02}"
        value, weight = (
            row["value_qr" if old else "value_in_qatari_riyals"],
            row["weight_kg" if old else "weight_in_kilograms"],
        )
        # Prior rows have already been reviewed and rolled to the selected
        # fine-line identity for this invented uncontaminated parent.
        return TradeRow(
            FINE[0],
            row["country_of_origin"],
            month,
            D(value),
            D(weight),
            "kg",
            reading(value, "qar", month),
            reading(weight, "kg", month),
        )

    old = [
        trade(row, True)
        for row in json.loads(before.read_text())
        if row["lsn_year"] == "2024"
    ]
    new = [
        trade(row, False)
        for row in json.loads(after.read_text())
        if row["harmonized_system_code"] in FINE
    ]
    result = supplier_metrics(
        new,
        FINE,
        LATEST,
        (*PRIOR, *LATEST),
        reviewed=True,
        prior_rows=old,
        prior_months=PRIOR,
    )
    assert result["hhi"].value == expected["hhi"]
    assert result["total_value"].value == expected["latest12"]
    assert result["trend"].value == expected["trend"]
    from eii_core.calc.facts import NoData

    assert result["origins"]["invented_origin_b"]["unit_value"] == NoData(
        "no_denominator"
    )


def test_independent_c6_paths_seed_and_full_settings(tmp_path):
    # Reuse the existing writer of invented Overture-shaped Parquet. These
    # locations are invented; the metric projection below is ONLY a fixture
    # transform, not a choice of the unrecorded live C6 projection.
    from custodian.tests.fixtures.places.invented import place_row, write_places

    source = tmp_path / "invented-places.parquet"
    points = (
        (0, 0, "italian", 1),
        (0, 1, "pizza", 1),
        (0, 2, "b", 1),
        (0, 3, "b", 1),
        (1000, 0, "c", 1),
        (1000, 1, "c", 1),
        (0, 4, "b", 0.1),
    )
    write_places(
        source,
        [
            place_row(
                place_id=f"SYN-METHOD-P-{index}",
                basic_category=category,
                lon=51.5 + x / 100000,
                lat=25.3 + y / 100000,
                confidence=confidence,
            )
            for index, (x, y, category, confidence) in enumerate(points)
        ],
    )

    def project(lon, lat):
        return (lon - D("51.5")) * 100000, (lat - D("25.3")) * 100000

    settings = dict(
        candidates=("b", "c"),
        seed=7,
        radius_m=D(250),
        confidence_min=D("0.5"),
        permutations=999,
        project=project,
    )
    broad = replay_c6(source, focal=("italian", "pizza"), **settings)
    narrow = replay_c6(source, focal=("italian",), **settings)
    assert abs(broad["b"]["clq"] - D(5) / 3) < D("1e-24")
    assert broad["c"]["clq"] == 0
    assert (broad["b"]["p"], broad["b"]["q"]) == (D("0.327"), D("0.654"))
    assert (narrow["b"]["p"], narrow["b"]["q"]) == (D("0.348"), D("0.696"))
    assert all(D(0) < row["p"] <= row["q"] <= D(1) for row in broad.values())
    assert narrow["b"]["n_focal"] == 1
    assert broad["b"]["n_focal"] == 2
    # Card thresholds are recorded and applied to exactly these replayed inputs.
    kept = [
        key
        for key, row in broad.items()
        if row["n_neighbour"] >= 20 and row["clq"] >= D("1.2") and row["q"] <= D("0.05")
    ][:6]
    assert kept == []
    assert replay_c6(source, focal=("italian", "pizza"), **settings) == broad


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (["invented_d1", "invented_d2"], ["invented_d2"], (D(1), D("0.75"))),
        (["invented_d1"], ["invented_d2"], (D(0), D(0))),
        (["invented_d1"], ["invented_zero"], ("NO_DATA", "NO_DATA")),
        (["invented_zero"], ["invented_d2"], ("NO_DATA", "NO_DATA")),
    ],
)
def test_independent_c7_paths_and_directional_arithmetic(tmp_path, a, b, expected):
    # Assumed normalized weights and centroid membership, never invented
    # attributes attached to a named real place. Live geometry remains open.
    weights = write_json(
        tmp_path / "invented-weights.json",
        [
            {"district_key": "invented_d1", "value": 10},
            {"district_key": "invented_d2", "value": 30},
            {"district_key": "invented_zero", "value": 0},
        ],
    )
    areas = write_json(tmp_path / "invented-areas.json", {"a": a, "b": b})
    assert replay_c7(weights, areas) == expected


def property_files(tmp_path):
    # The source field names follow the registry. An invented JSON crosswalk
    # substitutes for the reviewed CSV only in this reference test fixture.
    rows = [
        {
            "district_name": "invented district",
            "registration_date": f"{year}-01-01",
            "nw_l_qr": kind,
            "property_type": "ignored English label",
            "property_value": price,
            "area_square_meters": area,
        }
        for year, kind, price, area in (
            (2024, "نوع تجريبي أ", 200, 20),
            (2024, "نوع تجريبي أ", 400, 20),
            (2024, "نوع تجريبي ب", 1200, 20),
            (2025, "نوع تجريبي أ", 600, 20),
            (2025, "نوع تجريبي أ", 1000, 20),
            (2024, "نوع تجريبي أ", 0, 20),
            (2024, "نوع تجريبي أ", 200, 0),
        )
    ]
    rows.append(dict(rows[0], district_name="unmatched district", property_value=999))
    return write_json(tmp_path / "invented-deals.json", rows), write_json(
        tmp_path / "invented-crosswalk.json",
        {
            "names": {"invented district": "invented_district"},
            "arabic_types": ["نوع تجريبي أ", "نوع تجريبي ب"],
        },
    )


def test_independent_c14_paths_arabic_type_year_and_small_counts(tmp_path):
    result = replay_c14(*property_files(tmp_path))
    # No minimum-ten-deals threshold: MTH-50/MTH-51 require counts beside medians.
    assert result == {
        ("invented_district", "2024", "نوع تجريبي أ"): (D(15), 2),
        ("invented_district", "2024", "نوع تجريبي ب"): (D(60), 1),
        ("invented_district", "2025", "نوع تجريبي أ"): (D(40), 2),
    }


def test_c14_zero_rows_no_data(tmp_path):
    _, crosswalk = property_files(tmp_path)
    assert (
        replay_c14(write_json(tmp_path / "invented-empty.json", []), crosswalk)
        == "NO_DATA"
    )


def test_plant_independent_data_replay_detects_value_tampering(tmp_path):
    import json

    paths = property_files(tmp_path)
    expected = replay_c14(*paths)
    source = json.loads(paths[0].read_text())
    source[0]["property_value"] = 2000
    write_json(paths[0], source)
    with pytest.raises(AssertionError):
        assert replay_c14(*paths) == expected


def test_c14_arithmetic_on_exact_invented_card_pair(tmp_path):
    from eii_custodian.publicdata.property.quarter import _median

    expected = replay_c14(*property_files(tmp_path))
    # The existing release median primitive is tested on the exact card pair;
    # this is not a claim that a new annual C14 adapter was implemented here.
    assert (
        _median([D(200) / 20, D(400) / 20])
        == expected[("invented_district", "2024", "نوع تجريبي أ")][0]
        == D(15)
    )


def test_source_replay_matches_checked_c5_and_c14_values_without_producer(tmp_path):
    from eii_custodian.publicdata.method_card_validation import (
        validate_source_check_record,
    )

    from .method_card_pin_fixtures import case, save

    paths, record, artifact, _ = case(tmp_path)
    before, after = customs_files(tmp_path)
    c5 = replay_c5(
        before, after, prior_months=PRIOR, latest_months=LATEST, fine_codes=FINE
    )
    c14 = replay_c14(*property_files(tmp_path))
    expected = {f"c5.{key}": {"value": str(value)} for key, value in c5.items()}
    for year in ("2024", "2025"):
        expected[f"c14.medians_{year}"] = {
            district + "|" + kind: f"median={price};count={count}"
            for (district, group_year, kind), (price, count) in c14.items()
            if group_year == year
        }
    for row in record["pins"]:
        if row["pin_id"] in expected:
            row["values"] = expected[row["pin_id"]].copy()
    for row in artifact["pins"]:
        if row["pin_id"] in expected:
            row["values"] = expected[row["pin_id"]].copy()
    save(paths, record, artifact)
    checked = validate_source_check_record(*paths[:3])
    # File-path replays above have no dependency on the producer artifact.
    for pin, values in expected.items():
        assert checked[pin].values == values
