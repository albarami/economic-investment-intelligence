"""MTH-03 independent path-input replays and exact invented-input arithmetic.

Only invented tmp_path files are read. The assumed file shapes are recorded in
method_card_data_replay.py and must be confirmed against live sources in pass 2.
There are no actual public pins yet. C6 and C7 production calculators are absent
on this tree: their tests exercise independent reference arithmetic only; they
are not evidence that a production implementation exists.
"""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from eii_core.calc.facts import Measure, SourceChain
from eii_core.calc.public_methods import TradeRow, supplier_metrics, wilson
from eii_core.calc.public_series import rounded
from eii_custodian.publicdata.series.parse import customs_code

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
# The card computes HHI, shares and the trend per basket line (docs/07 C5).
LINES = {"pasta": ("1902.11.10.0000",), "other": ("1902.19.10.0000",)}
POOLED = {"pooled": ("1902.11.10.0000", "1902.19.10.0000")}
# The row shapes confirmed on main for the licence and customs sources.
CONFIRMED_SHAPES = (
    Path(__file__).resolve().parent / "fixtures" / "series" / "confirmed_shapes.json"
)


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


def test_replay_wilson_skips_the_undated_cancelled_row_of_the_confirmed_shape(tmp_path):
    # The shapes confirmed on main: an undated cancelled-licence row carries
    # a null year and month. It is skipped, never a crash, and only the dated
    # 2020-07 row of the confirmed shapes enters k.
    shapes = json.loads(CONFIRMED_SHAPES.read_text(encoding="utf-8"))
    result = replay_wilson(
        write_json(tmp_path / "confirmed-active.json", shapes["lic_active"]),
        write_json(tmp_path / "confirmed-cancelled.json", shapes["lic_cancelled"]),
        municipality="بلدية تجريبية",
        activity="invented-code",
        period=("2020-07",),
    )
    assert result["period"] == "2020-07..2020-07"
    assert (result["k"], result["n"]) == (3, 3)
    low, high = wilson(result["k"], result["n"])
    assert rounded(low, 6) == result["low"]
    assert rounded(high, 6) == result["high"]


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
    prior += [
        {
            "lsn_year": "2024",
            "lshhr_month": m,
            "hs8": "1902.19.10",
            "country_of_origin": "invented_origin_c",
            "weight_kg": 1,
            "value_qr": 5,
        }
        for m in range(1, 13)
    ]
    latest = [
        {
            "year": "2025",
            "month": m,
            # The confirmed cus_imp_2025 shape carries integer codes; the
            # series parser's own rule reads them (never a second rule).
            "harmonized_system_code": 190211100000,
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
    latest += [
        {
            "year": "2025",
            "month": m,
            "harmonized_system_code": 190219100000,
            "country_of_origin": origin,
            "weight_in_kilograms": weight,
            "value_in_qatari_riyals": value,
        }
        for m in range(1, 13)
        for origin, weight, value in (
            ("invented_origin_c", 3, 30),
            ("invented_origin_d", 1, 15),
            ("invented_origin_e", 0, 15),
        )
    ]
    # A reviewed exclusion and unrelated year must not enter any line's sums.
    latest.append(
        dict(
            latest[0],
            harmonized_system_code=190230100000,
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
        before, after, prior_months=PRIOR, latest_months=LATEST, basket_lines=LINES
    )
    assert result == {
        "pasta": {"hhi": D(6250), "prior12": D(120), "latest12": D(480), "trend": D(3)},
        "other": {"hhi": D(3750), "prior12": D(60), "latest12": D(720), "trend": D(11)},
    }
    # Each line's HHI differs from the pooled figure one old-style replay of
    # both lines would have produced.
    pooled = replay_c5(
        before, after, prior_months=PRIOR, latest_months=LATEST, basket_lines=POOLED
    )["pooled"]
    assert pooled["hhi"] == D(2350)
    assert result["pasta"]["hhi"] != pooled["hhi"]
    assert result["other"]["hhi"] != pooled["hhi"]


def test_replay_c5_reads_integer_codes_as_the_series_parser_reads_them(tmp_path):
    # The shapes confirmed on main: the 2025 table carries integer
    # harmonized_system_code values. The replay reads them exactly as the
    # series parser does (never a second rule), so a chapter 01 to 09 code
    # whose leading zero the integer encoding dropped is restored and kept,
    # not silently dropped from its line.
    shapes = json.loads(CONFIRMED_SHAPES.read_text(encoding="utf-8"))
    latest = [
        *shapes["cus_imp_2025"],
        dict(
            shapes["cus_imp_2025"][0],
            harmonized_system_code=int("0406.20.00.0001".replace(".", "")),
            country_of_origin="invented cheese origin",
            value_in_qatari_riyals=7,
        ),
    ]
    result = replay_c5(
        write_json(tmp_path / "confirmed-prior.json", shapes["cus_imp_2019"]),
        write_json(tmp_path / "confirmed-latest.json", latest),
        prior_months=("2019-01",),
        latest_months=("2025-01",),
        basket_lines={"pasta": ("1902.00.00.0001",), "cheese": ("0406.20.00.0001",)},
    )
    # The confirmed 2025 row: one origin (null), so a fully concentrated line.
    assert result["pasta"]["latest12"] == D(2000000000)
    assert result["pasta"]["hhi"] == D(10000)
    # The confirmed 2019 row is a different eight-digit parent: no prior row.
    assert result["pasta"]["prior12"] == D(0)
    assert result["pasta"]["trend"] == "NO_DATA"
    # The chapter 04 row is kept by its restored leading zero, not dropped.
    assert result["cheese"]["latest12"] == D(7)
    assert result["cheese"]["hhi"] == D(10000)


def test_c5_arithmetic_on_exact_replayed_inputs(tmp_path):
    before, after = customs_files(tmp_path)
    expected = replay_c5(
        before, after, prior_months=PRIOR, latest_months=LATEST, basket_lines=LINES
    )
    # This adapter copies the invented raw fields; the independent oracle above
    # never calls this adapter or supplier_metrics.
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

    def trade(row, product, old):
        month = f"{row['lsn_year'] if old else row['year']}-{int(row['lshhr_month'] if old else row['month']):02}"
        value, weight = (
            row["value_qr" if old else "value_in_qatari_riyals"],
            row["weight_kg" if old else "weight_in_kilograms"],
        )
        # Prior rows have already been reviewed and rolled to the selected
        # fine-line identity for this invented uncontaminated parent.
        return TradeRow(
            product,
            row["country_of_origin"],
            month,
            D(value),
            D(weight),
            "kg",
            reading(value, "qar", month),
            reading(weight, "kg", month),
        )

    from eii_core.calc.facts import NoData

    for line, codes in LINES.items():
        product = codes[0]
        parent = product.replace(".", "")[:8]
        old = [
            trade(row, product, True)
            for row in json.loads(before.read_text())
            if row["lsn_year"] == "2024" and row["hs8"].replace(".", "") == parent
        ]
        new = [
            trade(row, product, False)
            for row in json.loads(after.read_text())
            # Integer source codes are read by the series parser's own rule.
            if customs_code("cus_imp_2025", row["harmonized_system_code"])
            == product.replace(".", "")
        ]
        result = supplier_metrics(
            new,
            codes,
            LATEST,
            (*PRIOR, *LATEST),
            reviewed=True,
            prior_rows=old,
            prior_months=PRIOR,
        )
        assert result["hhi"].value == expected[line]["hhi"]
        assert result["total_value"].value == expected[line]["latest12"]
        assert result["trend"].value == expected[line]["trend"]
        zero_weight = "invented_origin_b" if line == "pasta" else "invented_origin_e"
        assert result["origins"][zero_weight]["unit_value"] == NoData("no_denominator")


def test_independent_c6_paths_box_filter_seed_and_thresholds(tmp_path):
    # Reuse the existing writer of invented Overture-shaped Parquet. These
    # locations are invented; the metric projection below is ONLY a fixture
    # transform, not a choice of the unrecorded live C6 projection.
    from custodian.tests.fixtures.places.invented import place_row, write_places

    source = tmp_path / "invented-places.parquet"
    # (x, y, category, confidence) around (51.5 E, 25.4695 N). The research
    # box clips at 25.47 N, so the y=150 point lies inside the 250 m radius
    # but outside the box and must not change any kept figure.
    points = (
        (0, 0, "italian", 1),
        (0, 1, "pizza", 1),
        (0, 2, "b", 1),
        (0, 3, "b", 1),
        (1000, 0, "c", 1),
        (1000, 1, "c", 1),
        (0, 4, "b", 0.1),
        (0, 150, "b", 1),
    )
    write_places(
        source,
        [
            place_row(
                place_id=f"SYN-METHOD-P-{index}",
                basic_category=category,
                lon=51.5 + x / 100000,
                lat=25.4695 + y / 100000,
                confidence=confidence,
            )
            for index, (x, y, category, confidence) in enumerate(points)
        ],
    )

    def project(lon, lat):
        return (lon - D("51.5")) * 100000, (lat - D("25.4695")) * 100000

    settings = dict(
        candidates=("b", "c"),
        seed=7,
        radius_m=D(250),
        confidence_min=D("0.5"),
        permutations=999,
        project=project,
    )
    # The card's keep rule: N_B >= 20, CLQ >= 1.2, q <= 0.05, at most six.
    card_display = dict(
        box=(D("25.18"), D("25.47"), D("51.35"), D("51.65")),
        fdr=D("0.05"),
        min_neighbours=20,
        min_clq=D("1.2"),
        max_shown=6,
    )
    assert (
        replay_c6(source, focal=("italian", "pizza"), **settings, **card_display) == []
    )
    assert replay_c6(source, focal=("italian",), **settings, **card_display) == []
    # Permissive display settings expose every candidate's statistics.
    permissive = dict(card_display, fdr=D(1), min_neighbours=0, min_clq=D(0))
    broad = replay_c6(source, focal=("italian", "pizza"), **settings, **permissive)
    assert [row["candidate"] for row in broad] == ["b", "c"]
    assert abs(broad[0]["clq"] - D(5) / 3) < D("1e-24")
    assert broad[0]["n_focal"] == 2
    assert (broad[0]["p"], broad[0]["q"]) == (D("0.327"), D("0.654"))
    assert broad[1]["clq"] == 0
    assert broad[1]["n_neighbour"] == 2
    narrow = replay_c6(source, focal=("italian",), **settings, **permissive)
    assert narrow[0]["candidate"] == "b"
    assert (narrow[0]["p"], narrow[0]["q"]) == (D("0.348"), D("0.696"))
    assert narrow[0]["n_focal"] == 1
    assert all(D(0) < row["p"] <= row["q"] <= D(1) for row in broad)
    # Without the box filter the outside point changes the focal CLQ.
    with_outside = replay_c6(
        source,
        focal=("italian", "pizza"),
        **settings,
        **dict(permissive, box=(D("25.18"), D("25.48"), D("51.35"), D("51.65"))),
    )
    assert with_outside[0]["clq"] == D(3) / 2
    assert with_outside[0]["clq"] != broad[0]["clq"]
    # Display order and cut: highest CLQ first, at most max_shown kept.
    assert [
        row["candidate"]
        for row in replay_c6(
            source,
            focal=("italian", "pizza"),
            **settings,
            **dict(permissive, max_shown=1),
        )
    ] == ["b"]
    assert (
        replay_c6(source, focal=("italian", "pizza"), **settings, **permissive) == broad
    )


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


def checked_c5_c14_values(deals, crosswalk, before, after):
    """The pin-value encoding of one full independent replay, as written."""
    c5 = replay_c5(
        before, after, prior_months=PRIOR, latest_months=LATEST, basket_lines=LINES
    )
    c14 = replay_c14(deals, crosswalk)
    values = {
        f"c5.{key}": {line: str(stats[key]) for line, stats in c5.items()}
        for key in ("hhi", "prior12", "latest12", "trend")
    }
    for year in ("2024", "2025"):
        values[f"c14.medians_{year}"] = {
            district + "|" + kind: f"median={price};count={count}"
            for (district, group_year, kind), (price, count) in c14.items()
            if group_year == year
        }
    return values


def test_checked_c5_and_c14_values_match_second_replay_without_producer(tmp_path):
    from eii_custodian.publicdata.method_card_validation import (
        validate_source_check_record,
    )

    from .method_card_data_replay import assert_record_matches_replay
    from .method_card_pin_fixtures import case, lineage_context, save

    paths, record, artifact, _ = case(tmp_path)
    before, after = customs_files(tmp_path)
    deals, crosswalk = property_files(tmp_path)
    expected = checked_c5_c14_values(deals, crosswalk, before, after)
    for row in record["pins"]:
        if row["pin_id"] in expected:
            row["values"] = expected[row["pin_id"]].copy()
    for row in artifact["pins"]:
        if row["pin_id"] in expected:
            row["values"] = expected[row["pin_id"]].copy()
    save(paths, record, artifact)
    checked = validate_source_check_record(*paths[:3], **lineage_context(record))
    # The comparison is made against a second replay call made after
    # validation, never against the dictionary that was written. The replays
    # read only the invented source files, never the producer artifact.
    second = checked_c5_c14_values(deals, crosswalk, before, after)
    for pin, values in second.items():
        assert checked[pin].values == values
    assert assert_record_matches_replay(checked, second)


def test_plant_record_and_artifact_agree_but_differ_from_source_replay(tmp_path):
    from eii_custodian.publicdata.method_card_validation import (
        validate_source_check_record,
    )

    from .method_card_data_replay import assert_record_matches_replay
    from .method_card_pin_fixtures import case, lineage_context, save

    # The replay is computed first, before anything is written.
    deals, crosswalk = property_files(tmp_path)
    c14 = replay_c14(deals, crosswalk)
    replayed = {
        "c14.medians_2024": {
            district + "|" + kind: f"median={price};count={count}"
            for (district, year, kind), (price, count) in c14.items()
            if year == "2024"
        }
    }
    paths, record, artifact, _ = case(tmp_path)
    # The plant is the replay's own encoding with one tampered value: the
    # key set is exactly the replay's, so only the value can differ.
    tampered = dict(replayed["c14.medians_2024"])
    tampered["invented_district|نوع تجريبي أ"] = "median=16;count=2"
    assert set(tampered) == set(replayed["c14.medians_2024"])
    for row in record["pins"]:
        if row["pin_id"] == "c14.medians_2024":
            row["values"] = tampered.copy()
    for row in artifact["pins"]:
        if row["pin_id"] == "c14.medians_2024":
            row["values"] = tampered.copy()
    save(paths, record, artifact)
    # The artifact comparison is blind to this: record and artifact agree.
    entries = validate_source_check_record(*paths[:3], **lineage_context(record))
    with pytest.raises(AssertionError, match="replay_value_mismatch"):
        assert_record_matches_replay(entries, replayed)
    # Positive control: the same record holding the untampered replayed
    # value passes the replay comparison.
    paths, record, artifact, _ = case(tmp_path)
    for row in record["pins"]:
        if row["pin_id"] == "c14.medians_2024":
            row["values"] = replayed["c14.medians_2024"].copy()
    for row in artifact["pins"]:
        if row["pin_id"] == "c14.medians_2024":
            row["values"] = replayed["c14.medians_2024"].copy()
    save(paths, record, artifact)
    entries = validate_source_check_record(*paths[:3], **lineage_context(record))
    assert assert_record_matches_replay(entries, replayed)
