"""Selected receipts and exact column copying on invented source exports."""

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.series.parse import parse_rows, selected_source
from eii_custodian.publicdata.stage import run_stage


def test_numeric_source_decimal_is_not_rounded_by_json(tmp_path: Path) -> None:
    entry, _, receipt = fixture(tmp_path)
    entry = replace(entry, columns=(("invented_value", "number"),))
    body = b'[{"invented_value": 0.1234567890123456789}]'
    digest = sha256_hex(body)
    receipt["sha256"] = digest
    receipt["bytes"] = len(body)
    commit_pair(tmp_path / entry.key, digest, "json", body, receipt)
    rows, _ = selected_source(tmp_path, entry, digest)
    assert rows[0]["invented_value"] == Decimal("0.1234567890123456789")
    assert parse_rows(entry, rows, {"invented_value": "value"}) == [
        {"value": Decimal("0.1234567890123456789")}
    ]


def fixture(tmp_path: Path, value: str = "12.50"):
    entry = replace(
        next(e for e in load_registry() if e.key == "sec_hr_ind"),
        columns=(("invented_value", "string"),),
    )
    body = json.dumps([{"invented_value": value}]).encode()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=1,
        terms_sha256="",
    )
    commit_pair(tmp_path / entry.key, digest, "json", body, receipt)
    return entry, digest, receipt


def test_selected_hash_never_chooses_competing_version(tmp_path: Path) -> None:
    entry, first, _ = fixture(tmp_path)
    _, second, _ = fixture(tmp_path, "99.00")
    assert first != second
    rows, chain = selected_source(tmp_path, entry, first)
    assert rows == [{"invented_value": "12.50"}]
    assert chain["sha256"] == first
    with pytest.raises(ValueError, match="snapshot_index_invalid"):
        selected_source(tmp_path, entry, "a" * 64)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "bad"),
        ("publisher", ""),
        ("retrieved_utc", ""),
        ("fetch_url", ""),
        ("licence_id", ""),
        ("source_id", "wrong"),
        ("slug", "wrong"),
        ("switched_off", True),
    ],
)
def test_missing_or_mismatched_provenance_refused(
    tmp_path: Path, field: str, value: object
) -> None:
    entry, digest, receipt = fixture(tmp_path)
    receipt[field] = value
    (tmp_path / entry.key / f"{digest}.meta.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="snapshot_hash_mismatch"):
        selected_source(tmp_path, entry, digest)


def test_unknown_field_and_changed_value_refused(tmp_path: Path) -> None:
    entry, digest, _ = fixture(tmp_path)
    rows, _ = selected_source(tmp_path, entry, digest)
    assert parse_rows(entry, rows, {"invented_value": "value"}) == [{"value": "12.50"}]
    with pytest.raises(ValueError, match="unknown or missing source fields: unknown"):
        parse_rows(
            entry,
            [{"invented_value": "12.50", "unknown": 2}],
            {"invented_value": "value"},
        )
    with pytest.raises(ValueError, match="incomplete or duplicate field mapping"):
        parse_rows(entry, rows, {})
    with pytest.raises(ValueError, match="unconfirmed source columns"):
        parse_rows(replace(entry, columns=()), rows, {})
    (tmp_path / entry.key / f"{digest}.json").write_text('[{"invented_value": "13"}]')
    with pytest.raises(ValueError, match="snapshot_hash_mismatch"):
        selected_source(tmp_path, entry, digest)


def test_published_wage_is_copied_never_replaced(tmp_path: Path) -> None:
    entry, _, _ = fixture(tmp_path, "31.57")
    row = {"invented_value": "31.57"}
    assert parse_rows(entry, [row], {"invented_value": "average_annual_wage"}) == [
        {"average_annual_wage": "31.57"}
    ]


@pytest.mark.public_data
def test_missing_owned_regression_is_failure(tmp_path: Path) -> None:
    assert run_stage(tmp_path, required=("PUB-62",)).mismatch == "PUB-62"


@pytest.mark.public_data
def test_stage_rejects_missing_owned_assertions(tmp_path: Path) -> None:
    from eii_custodian.publicdata.stage import EXPECTED

    required_fields = {
        "PUB-63": ("populated_groups",),
        "PUB-64": (
            "output_per_employee",
            "compensation_share_1dp",
            "operating_surplus_share_1dp",
            "food_share_1dp",
            "beverages_share_1dp",
            "building_rent_share_1dp",
        ),
        "PUB-65": ("basket_excludes_noodles", "valuation_basis_present"),
        "PUB-68": (
            "combined_share_0dp",
            "july_2020_bulk",
            "june_2022_bulk",
            "september_2024_bulk",
        ),
        "PUB-69": (
            "restaurant_source_rows",
            "restaurant_contract_rows",
            "incompleteness_note",
            "net_formation_built",
        ),
    }
    folder = tmp_path / "figures"
    folder.mkdir()
    for figure, fields in required_fields.items():
        assert set(fields) <= EXPECTED[figure].keys()
        for field in fields:
            planted = dict(EXPECTED[figure])
            del planted[field]
            path = folder / f"{figure}.json"
            path.write_text(json.dumps(planted))
            assert run_stage(tmp_path, required=(figure,)).mismatch == figure
            path.unlink()


def test_parsed_wage_table_identity_cannot_be_swapped(tmp_path: Path) -> None:
    entry, _, _ = fixture(tmp_path)
    entry = replace(entry, source_id="wage_occ")
    assert parse_rows(
        entry, [{"invented_value": "10"}], {"invented_value": "value"}
    ) == [{"value": "10", "table_code": "wage_occ"}]
    with pytest.raises(
        ValueError, match="table identity comes from the source registry"
    ):
        parse_rows(
            entry, [{"invented_value": "wage_act"}], {"invented_value": "table_code"}
        )


@pytest.mark.parametrize(
    "kind,value", [("integer", 12), ("number", 12), ("number", Decimal("1.2"))]
)
def test_numeric_column_types(tmp_path: Path, kind: str, value: object) -> None:
    entry, _, _ = fixture(tmp_path)
    entry = replace(entry, columns=(("invented_value", kind),))
    assert parse_rows(
        entry, [{"invented_value": value}], {"invented_value": "value"}
    ) == [{"value": value}]
    for wrong in (True, "12", []):
        with pytest.raises(ValueError, match="source field type mismatch"):
            parse_rows(entry, [{"invented_value": wrong}], {"invented_value": "value"})


def test_activity_wage_identity(tmp_path: Path) -> None:
    entry, _, _ = fixture(tmp_path)
    entry = replace(entry, source_id="wage_act")
    assert parse_rows(
        entry, [{"invented_value": "12"}], {"invented_value": "value"}
    ) == [{"value": "12", "table_code": "wage_act"}]


@pytest.mark.public_data
def test_added_stage_assertions_have_independent_pack_values(tmp_path: Path) -> None:
    from eii_custodian.publicdata.stage import EXPECTED

    # Document 04 section 10, PUB-62 through PUB-70; decision 0025
    # withdraws production. These literals must not come from stage.EXPECTED.
    owned = {
        "PUB-62": {
            "zone_69_2021": "429964072",
            "zone_69_2025": "1436402796",
            "ratio_2dp": "3.34",
            "sum_ratio_2dp": "1.34",
        },
        "PUB-63": {
            "populated_groups": "17",
            "mean_2020": "10084",
            "mean_2025": "11855",
            "rise": "1771",
            "rise_percent_1dp": "17.6",
            "within_groups": "38",
            "mix": "1733",
            "mix_share_1dp": "97.8",
        },
        "PUB-64": {
            "establishments": "2086",
            "employees": "41458",
            "compensation": "1308140",
            "operating_surplus": "1247422",
            "average_annual_wage": "31579",
            "output_per_employee": "152875",
            "compensation_share_1dp": "20.6",
            "operating_surplus_share_1dp": "19.7",
            "food_share_1dp": "29.3",
            "beverages_share_1dp": "5.6",
            "building_rent_share_1dp": "11.6",
            "goods_share_1dp": "40.6",
            "services_share_1dp": "16.5",
        },
        "PUB-65": {
            "italy_2dp": "8.69",
            "saudi_arabia_2dp": "11.45",
            "basket_excludes_noodles": "true",
            "valuation_basis_present": "true",
        },
        "PUB-66": {"rows_2025": "216073", "value_bn_2dp": "138.53"},
        "PUB-67": {
            "rows": "13189",
            "sum_count": "249622",
            "distinct_codes": "4755",
            "isic_prefix": "211277",
            "other_seven": "11276",
            "legacy_six": "26844",
            "other_lengths": "225",
            "al_daayen_5610101": "361",
            "national_5610101": "4782",
        },
        "PUB-68": {
            "sum_count": "161055",
            "undated": "7386",
            "july_2020": "40791",
            "june_2022": "14212",
            "september_2024": "11232",
            "dated_total": "153669",
            "combined_share_0dp": "43",
            "july_2020_bulk": "true",
            "june_2022_bulk": "true",
            "september_2024_bulk": "true",
        },
        "PUB-69": {
            "sum_count": "12533",
            "distinct_codes": "610",
            "restaurant_source_rows": "0",
            "restaurant_contract_rows": "0",
            "incompleteness_note": "openings_incomplete",
            "net_formation_built": "false",
        },
        "PUB-70": {
            "metro_2025_12": "7375367",
            "metro_2024_12": "5529167",
            "growth_0dp": "33",
        },
    }
    folder = tmp_path / "figures"
    folder.mkdir()
    for figure, expected in owned.items():
        assert EXPECTED[figure] == expected
        (folder / f"{figure}.json").write_text(json.dumps(expected))
    assert run_stage(tmp_path, required=tuple(owned)).mismatch == ""
    for figure, expected in owned.items():
        for key in expected:
            path = folder / f"{figure}.json"
            path.write_text(json.dumps({**expected, key: "planted-wrong"}))
            assert run_stage(tmp_path, required=(figure,)).mismatch == figure
            path.write_text(json.dumps(expected))
    with pytest.raises(ValueError, match="unknown required"):
        run_stage(tmp_path, required=("PLANTED",))


# Continuation fixtures use the lead-confirmed export names and invented values.
def test_confirmed_mapping_and_named_field_refusals() -> None:
    from eii_custodian.publicdata.series.parse import FIELD_MAP, confirmed_rows

    entry = next(e for e in load_registry() if e.key == "util_elec")
    row = {"year": "2021", "zone_number": "69", "value": 12}
    assert confirmed_rows(entry, [row]) == [row]
    assert FIELD_MAP["util_elec"]["value"] == ("pub_zone_utility", "value")
    assert FIELD_MAP["sec_hr_ind"]["average_annual_wage_qr"] == (
        "pub_sector_accounts",
        "value:average_annual_wage",
    )
    for bad, name in [
        ({**row, "renamed": 1}, "renamed"),
        ({k: v for k, v in row.items() if k != "value"}, "value"),
        ({**row, "value": True}, "value"),
    ]:
        with pytest.raises(ValueError, match=name):
            confirmed_rows(entry, [bad])


def test_absent_production_is_not_a_required_mapping() -> None:
    from eii_custodian.publicdata.series.parse import mapping_gaps

    assert mapping_gaps("util_elec") == ()
    for source in ("sec_hr_ind", "cus_imp_2025", "cus_imp_2019", "lic_issued"):
        assert mapping_gaps(source) == ()


def series_cache(tmp_path: Path, source: str, rows: list[dict[str, object]]):
    entry = next(e for e in load_registry() if e.key == source)
    body = json.dumps(rows).encode()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=len(rows),
        terms_sha256="",
    )
    commit_pair(tmp_path / entry.key, digest, "json", body, receipt)
    return entry, digest


@pytest.mark.public_data
def test_series_build_writes_bound_tables_and_internal_checks(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    entry, digest = series_cache(
        tmp_path,
        "util_elec",
        [
            {"year": "2021", "zone_number": "69", "value": 7},
            {"year": "2025", "zone_number": "69", "value": 24},
            {"year": "2026", "zone_number": "69", "value": 5},
            {"year": "2021", "zone_number": "70", "value": 13},
            {"year": "2025", "zone_number": "70", "value": 6},
            {"year": "2025", "zone_number": "71", "value": 10},
        ],
    )
    # 24/7 -> 3.43; (24+6+10)/(7+13) = 2, including the new zone.
    result = build_series(tmp_path, [entry], {"util_elec": digest})
    assert result["selected"] == {"util_elec": digest}
    assert result["missing"] == ()
    assert result["checks"]["PUB-62"] == {
        "zone_69_2021": "7",
        "zone_69_2025": "24",
        "ratio_2dp": "3.43",
        "sum_ratio_2dp": "2.00",
    }
    assert result["mismatch"] == "PUB-62"  # Invented figures do not match real anchors.
    path = tmp_path / "series" / "internal" / "pub_zone_utility.json"
    table = json.loads(path.read_text())
    assert table["rows"][0] == {
        "zone_code": "69",
        "period": "2021",
        "utility": "electricity",
        "value": 7,
        "unit": "kWh",
        "partial_year": False,
        "caveat_keys": [],
    }
    assert table["rows"][2]["partial_year"] is True
    assert table["row_sources"] == ["util_elec"] * 6
    assert table["method_version"] == "1"
    assert table["source_chain"][0]["sha256"] == digest
    assert not list((tmp_path / "series" / "display").glob("*.json"))


def test_method_chain_and_net_requests_refuse(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series, validate_figure

    with pytest.raises(ValueError, match="refused request: issues_minus_cancellations"):
        build_series(tmp_path, [], {}, request="issues_minus_cancellations")
    for payload in [
        {},
        {"method": "C9", "method_version": "1"},
        {"method": "C9", "source_chain": [{}]},
    ]:
        with pytest.raises(ValueError, match=r"method|source.chain"):
            validate_figure(payload)


def test_stale_display_removed_before_refusal(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    stale_files = [
        tmp_path / "series" / folder / "PUB-63.json"
        for folder in ("display", "internal", "regression")
    ]
    for stale in stale_files:
        stale.parent.mkdir(parents=True)
        stale.write_text('{"stale": true}')
    legacy = tmp_path / "figures" / "PUB-63.json"
    legacy.parent.mkdir()
    legacy.write_text('{"stale": true}')
    with pytest.raises(
        ValueError, match="selected sources must exactly match owned entries"
    ):
        build_series(tmp_path, [], {"wage_occ": "a" * 64})
    assert all(not stale.exists() for stale in stale_files)
    assert not legacy.exists()


@pytest.mark.public_data
def test_owned_missing_check_blocks_success(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    entry, digest = series_cache(tmp_path, "sec_hr_ind", [])
    result = build_series(tmp_path, [entry], {"sec_hr_ind": digest})
    assert result["mismatch"] == "PUB-64"
    assert "PUB-64" in result["missing"]


@pytest.mark.public_data
def test_fetch_build_runs_selected_cache_checks(tmp_path: Path, monkeypatch) -> None:
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.report import pass_line
    from eii_custodian.publicdata.series.figures import finish_build

    entry, digest = series_cache(tmp_path, "sec_hr_ind", [])
    observed = []

    def fetched(*args, registry_entries=None):
        return build._Fetched(
            digest, entry.fetch_host, "2026-11-14T00:00:00Z", "", ""
        ), None

    def wrapped(entries, cache, lines):
        observed.append(tuple(entries))
        return finish_build(entries, cache, lines)

    monkeypatch.setattr(build, "_fetch_row", fetched)
    monkeypatch.setattr("eii_custodian.publicdata.series.figures.finish_build", wrapped)
    result = build.run_build(
        [entry],
        lambda url: None,
        tmp_path,
        lambda: "2026-11-14T00:00:00Z",
        lambda n: None,
    )
    assert observed == [(entry,)]
    assert result.failure is not None
    assert result.failure.check == "public_data"
    assert result.failure.source_id == "PUB-64"
    assert pass_line(entry.key, digest, entry.fetch_host) in result.lines


def test_invented_shapes_cover_every_confirmed_field() -> None:
    from eii_custodian.publicdata.series.parse import FIELD_MAP, confirmed_rows

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text(),
        parse_float=Decimal,
    )
    entries = {e.source_id: e for e in load_registry()}
    assert set(fixtures) == set(FIELD_MAP)
    for source, rows in fixtures.items():
        assert confirmed_rows(entries[source], rows) == rows
        for field, value in rows[0].items():
            for bad in (
                {k: v for k, v in rows[0].items() if k != field},
                {**rows[0], field + "_renamed": value},
                {**rows[0], field: []},
            ):
                with pytest.raises(ValueError, match=field):
                    confirmed_rows(entries[source], [bad])


def test_independent_checks_and_contract_values() -> None:
    from eii_custodian.publicdata.series.figures import compute_checks, contract_rows

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text(),
        parse_float=Decimal,
    )
    # 24/7 -> 3.43; (24+6+10)/(7+13)=2.00, with one later-only zone.
    fixtures["util_elec"] = [
        dict(year=y, zone_number=z, value=v)
        for y, z, v in [
            ("2021", "69", 7),
            ("2025", "69", 24),
            ("2021", "70", 13),
            ("2025", "70", 6),
            ("2025", "71", 10),
        ]
    ]
    # Median=3, strict threshold=9. Dated=59+2+62*3=247; 59/247*100 -> 24.
    from eii_core.calc.public_series import C2_CALENDAR

    from .test_series_exact_regressions import cancellation

    fixtures["lic_cancelled"] = [
        cancellation("2020", 7, 42),
        cancellation("2022", 6, 9),
        cancellation("2024", 9, 8),
        cancellation("2020", 1, 2),
        cancellation(None, None, 9),
    ]
    other = [
        m for m in C2_CALENDAR if m not in {"2020-07", "2022-06", "2024-09", "2020-01"}
    ][:62]
    fixtures["lic_cancelled"].extend(cancellation(m[:4], int(m[5:]), 3) for m in other)
    assert compute_checks(
        {
            k: v
            for k, v in fixtures.items()
            if not k.startswith(("sec_hr_", "lic_active", "lic_issued"))
        }
    ) == {
        "PUB-62": {
            "zone_69_2021": "7",
            "zone_69_2025": "24",
            "ratio_2dp": "3.43",
            "sum_ratio_2dp": "2.00",
        },
        "PUB-63": {
            "populated_groups": "2",
            "mean_2020": "18",
            "mean_2025": "15",
            "rise": "-3",
            "rise_percent_1dp": "-17.1",
            "within_groups": "2",
            "mix": "-5",
            "mix_share_1dp": "166.7",
        },
        "PUB-65": {"valuation_basis_present": "true"},
        "PUB-66": {"rows_2025": "1", "value_bn_2dp": "2.00"},
        "PUB-68": {
            "sum_count": "256",
            "undated": "9",
            "dated_total": "247",
            "july_2020": "42",
            "june_2022": "9",
            "september_2024": "8",
            "combined_share_0dp": "24",
            "july_2020_bulk": "true",
            "june_2022_bulk": "false",
            "september_2024_bulk": "false",
        },
        "PUB-70": {"metro_2024_12": "10", "metro_2025_12": "15", "growth_0dp": "50"},
    }
    assert contract_rows("wage_occ", fixtures["wage_occ"])[0] == {
        "table_code": "wage_occ",
        "period": "2020",
        "breakdown_key": "gender=invented-a&occupation=invented-occupation",
        "indicator": "paid_workers",
        "value": 1,
        "unit": "persons",
    }
    wages = contract_rows("wage_act", fixtures["wage_act"])
    assert wages[1]["value"] == 10
    assert wages[1]["unit"] == "QAR"
    assert wages[1]["indicator"] == "monthly_average_wage"
    assert wages[1]["table_code"] == "wage_act"
    sector = contract_rows("sec_hr_ind", fixtures["sec_hr_ind"])
    assert {r["indicator"]: r["value"] for r in sector} == {
        "operating_surplus": 11,
        "compensation": 12,
        "value_added_per_worker": 13,
        "productivity_of_employee": 14,
        "services_share": 1.25,
        "goods_share": 2.5,
        "average_annual_wage": 17,
    }
    assert {r["indicator"]: r["unit"] for r in sector} == {
        "operating_surplus": "QAR_thousand",
        "compensation": "QAR_thousand",
        "value_added_per_worker": "QAR",
        "productivity_of_employee": "QAR",
        "services_share": "percent",
        "goods_share": "percent",
        "average_annual_wage": "QAR",
    }
    for source, indicator in [
        ("sec_hr_goods", "intermediate_goods:Food%20Stuff"),
        ("sec_hr_serv", "intermediate_services:Rents%20of%20Buildings"),
        ("sec_hr_size", "employees:invented-size"),
    ]:
        assert contract_rows(source, fixtures[source])[0] == {
            "activity_code": "561",
            "period": "2022",
            "indicator": indicator,
            "value": 11,
            "unit": "count" if source == "sec_hr_size" else "QAR_thousand",
        }
    transit = contract_rows("transit_monthly", fixtures["transit_monthly"])
    assert transit[0] == {
        "period": "2024-12",
        "mode": "bus",
        "riders": 1,
        "anomaly_flag": False,
    }
    assert transit[1] == {
        "period": "2024-12",
        "mode": "metro",
        "riders": 10,
        "anomaly_flag": False,
    }
    assert transit[-1] == {
        "period": "2026-01",
        "mode": "tram",
        "riders": 3,
        "anomaly_flag": True,
    }
    assert (
        contract_rows("lic_active", fixtures["lic_active"])[0]["municipality_code"]
        is None
    )


def test_reconciliations_compute_while_all_display_is_blocked(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    fixtures["cus_imp_2019"][0]["hs8"] = fixtures["cus_imp_2019"][0]["hs8"].replace(
        ".", ""
    )
    from custodian.tests.test_pub67 import FRAME, active_rows, selected_fixture

    support_entries, support_hashes = selected_fixture(tmp_path)
    fixtures["lic_active"] = active_rows()
    # S2-T08 part B, B13: an unmapped spelling refuses the build, so the
    # cancelled and issued fixture rows name a municipality of this frame.
    for source in ("lic_cancelled", "lic_issued"):
        for row in fixtures[source]:
            row["lbldy"] = FRAME[0].name_ar
    # Decimal JSON fixture numbers are decoded exactly by selected_source.
    entries, selected = [], {}
    for source, rows in fixtures.items():
        entry, digest = series_cache(tmp_path, source, rows)
        entries.append(entry)
        selected[source] = digest
    review = tmp_path / "invented-review.json"
    review.write_text(
        json.dumps(
            {
                "activities": [
                    {"activity": a, "inputs": []} for a in ("5610", "5630", "5510")
                ]
            }
        )
    )
    entries.extend(support_entries[1:])
    result = build_series(
        tmp_path,
        entries,
        selected,
        basket_review=review,
        municipalities=FRAME,
        supporting_selected={
            k: v for k, v in support_hashes.items() if k != "lic_active"
        },
    )
    evidence = json.loads(
        (tmp_path / "series/internal/reconciliations.json").read_text()
    )
    assert evidence["R1"]["status"] == "closed: not published"
    assert evidence["R1"]["blocked"].startswith("production_value absent")
    assert evidence["R1"]["matches"] == []
    assert evidence["R2"]["status"] == "reconciled: means equal, occupation table used"
    assert evidence["R2"]["years"] == [
        {
            "year": "2020",
            "wage_occ_workers": "4",
            "wage_act_workers": "4",
            "wage_occ_mean": "17.5",
            "wage_act_mean": "17.5",
            "equal_workers": True,
        },
        {
            "year": "2025",
            "wage_occ_workers": "4",
            "wage_act_workers": "4",
            "wage_occ_mean": "14.5",
            "wage_act_mean": "14.5",
            "equal_workers": True,
        },
    ]
    assert set(result["checks"]) == {f"PUB-{n}" for n in range(62, 71)}
    assert result["required"] == tuple(f"PUB-{n}" for n in range(62, 71))
    assert list((tmp_path / "series/display").iterdir()) == []
    assert len(evidence["R1"]["source_chain"]) == 4
    assert {s["sha256"] for s in evidence["R2"]["source_chain"]} == {
        selected["wage_occ"],
        selected["wage_act"],
    }


def test_evidence_stage_rejects_each_broken_chain(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series, validate_figure
    from eii_custodian.publicdata.stage import EXPECTED

    entry, digest = series_cache(
        tmp_path,
        "util_elec",
        [
            {"year": "2021", "zone_number": "69", "value": 12},
            {"year": "2025", "zone_number": "69", "value": 30},
        ],
    )
    build_series(tmp_path, [entry], {entry.key: digest})
    path = tmp_path / "series/regression/PUB-62.json"
    envelope = json.loads(path.read_text())
    validate_figure(envelope)
    for key in (
        "method",
        "method_version",
        "source_chain",
        "release_tables",
        "field_mapping",
    ):
        broken = {k: v for k, v in envelope.items() if k != key}
        path.write_text(json.dumps(broken))
        with pytest.raises(ValueError):
            run_stage(tmp_path, required=("PUB-62",), evidence=True)
    for key in envelope["source_chain"][0]:
        broken = json.loads(json.dumps(envelope))
        broken["source_chain"][0][key] = ""
        with pytest.raises(ValueError, match="source_chain"):
            validate_figure(broken)
    envelope["source_chain"][0]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="hash"):
        validate_figure(envelope)
    envelope["source_chain"][0]["sha256"] = digest
    envelope["values"] = EXPECTED["PUB-62"]
    path.write_text(json.dumps(envelope))
    assert run_stage(tmp_path, required=("PUB-62",), evidence=True).mismatch == ""


def test_duplicate_period_and_month_errors_are_reported(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import (
        build_series,
        compute_checks,
        contract_rows,
    )

    utility = {"year": "2021", "zone_number": "69", "value": 12}
    with pytest.raises(ValueError, match="duplicate utility period"):
        compute_checks({"util_elec": [utility, utility]})
    entry, digest = series_cache(tmp_path, "util_elec", [utility])
    result = build_series(tmp_path, [entry], {entry.key: digest})
    assert result["blocked"]["util_elec"] == ("regression: ('69', '2025')",)
    row = {
        "year": "2024",
        "month": "December",
        "lshhr": "invented-month",
        "public_transport_buses": 1,
        "doha_metro": 10,
        "lusail_tram": 3,
    }
    with pytest.raises(ValueError, match="duplicate transit period"):
        compute_checks({"transit_monthly": [row, row]})
    for month in ("invented-month", "0", "13"):
        with pytest.raises(ValueError, match="month"):
            contract_rows("transit_monthly", [{**row, "month": month}])
    with pytest.raises(ValueError, match="selected fetch lines"):
        run_stage(tmp_path, build_entries=[entry])


def test_finish_build_missing_and_invalid_receipts(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import finish_build

    entry = next(e for e in load_registry() if e.key == "util_elec")
    assert finish_build([], tmp_path, []) is None
    missing_lines: list[str] = []
    missing = finish_build([entry], tmp_path, missing_lines)
    assert missing is not None and missing.check == "selected_receipt"
    assert missing_lines == ["FAIL util_elec selected receipt missing"]
    refused_lines = ["PASS util_elec sha256=" + "a" * 64 + " host=invented"]
    missing_body = finish_build([entry], tmp_path, refused_lines)
    assert missing_body is not None and missing_body.check == "public_data"
    assert refused_lines[-1] == "FAIL series selected_input_refused"
    assert missing_body.observed == "selected_input_refused"


def test_display_gate_clears_stale_file_even_when_regressions_pass(
    tmp_path: Path, monkeypatch
) -> None:
    from eii_custodian.publicdata.series.figures import build_series
    from eii_custodian.publicdata.stage import StageResult

    fixture_path = Path(__file__).parent / "fixtures/series/confirmed_shapes.json"
    fixtures = json.loads(fixture_path.read_text())
    entry, digest = series_cache(tmp_path, "wage_occ", fixtures["wage_occ"])
    stale = tmp_path / "series/display/pub_wage_table.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"stale": true}')
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    result = build_series(tmp_path, [entry], {entry.key: digest})
    assert result["mismatch"] == ""
    assert not stale.exists()
    assert (tmp_path / "series/internal/pub_wage_table.json").is_file()
    assert (tmp_path / "series/regression/PUB-63.json").is_file()


def test_display_of_unaffected_table_and_fetch_success(
    tmp_path: Path, monkeypatch
) -> None:
    from eii_custodian.publicdata.series.figures import build_series, finish_build
    from eii_custodian.publicdata.stage import StageResult

    rows = [
        {"year": "2021", "zone_number": "69", "value": 12},
        {"year": "2025", "zone_number": "69", "value": 30},
    ]
    entry, digest = series_cache(tmp_path, "util_elec", rows)
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    build_series(tmp_path, [entry], {entry.key: digest})
    shown = json.loads((tmp_path / "series/display/pub_zone_utility.json").read_text())
    assert shown["rows"][0]["value"] == 12
    assert shown["row_sources"] == ["util_elec", "util_elec"]
    assert shown["source_chain"][0]["sha256"] == digest
    assert shown["release_tables"] == ["pub_zone_utility"]
    assert (
        finish_build(
            [entry], tmp_path, [f"PASS util_elec sha256={digest} host=invented"]
        )
        is None
    )


def test_finish_build_missing_selection_removes_stale_display(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import finish_build

    entry = next(e for e in load_registry() if e.key == "wage_occ")
    stale = tmp_path / "series/display/pub_wage_table.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"stale": true}')
    assert finish_build([entry], tmp_path, []) is not None
    assert not stale.exists()


def test_zero_change_and_duplicate_wage_group_refused() -> None:
    from eii_custodian.publicdata.series.figures import compute_checks

    row = {
        "year": "2020",
        "gender": "invented-a",
        "occupation": "invented-group",
        "paid_employment_workers": 2,
        "monthly_average_wage_qr": 10,
    }
    with pytest.raises(ValueError, match="zero change has no mix share"):
        compute_checks({"wage_occ": [row, {**row, "year": "2025"}]})
    with pytest.raises(ValueError, match="wage_occ duplicate wage group"):
        compute_checks({"wage_occ": [row, row]})


def test_mapping_targets_are_contract_columns_or_explicit_gaps() -> None:
    from eii_custodian.publicdata.series.parse import FIELD_MAP

    allowed = {
        "pub_licence_active": {
            "municipality_code",
            "activity_code",
            "activity_name_ar",
            "period",
            "active_count",
        },
        "pub_licence_cancelled": {
            "municipality_code",
            "activity_code",
            "period",
            "cancelled_count",
        },
        "pub_licence_issued": {
            "municipality_code",
            "activity_code",
            "period",
            "issued_count",
        },
        "pub_customs_import": {
            "tariff_code",
            "description_en",
            "description_ar",
            "origin_iso3",
            "period",
            "value_qar",
            "weight_kg",
            "quantity",
            "quantity_unit",
        },
        "pub_sector_accounts": {
            "activity_code",
            "period",
            "indicator",
            "value",
            "unit",
        },
        "pub_wage_table": {
            "table_code",
            "period",
            "breakdown_key",
            "indicator",
            "value",
            "unit",
        },
        "pub_zone_utility": {
            "zone_code",
            "period",
            "utility",
            "value",
            "unit",
            "partial_year",
        },
        "pub_transit_monthly": {"period", "mode", "riders", "anomaly_flag"},
    }
    entries = {e.source_id: e for e in load_registry()}
    for source, fields in FIELD_MAP.items():
        for table, column in fields.values():
            assert table in entries[source].release_tables
            if column.startswith("UNRESOLVED:"):
                assert column.split(":")[1] in {"municipality_code", "origin_iso3"}
            elif column.startswith("EVIDENCE_ONLY:"):
                assert column == "EVIDENCE_ONLY:activity_name_ar"
            else:
                assert column.split(":")[0] in allowed[table]


@pytest.mark.public_data
def test_default_stage_reads_internal_regressions_as_evidence(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    entry, digest = series_cache(
        tmp_path,
        "util_elec",
        [
            {"year": "2021", "zone_number": "69", "value": 12},
            {"year": "2025", "zone_number": "69", "value": 30},
        ],
    )
    build_series(tmp_path, [entry], {entry.key: digest})
    # Fetch/build's existing final stage must see the new computed evidence.
    assert run_stage(tmp_path).mismatch == "PUB-62"


@pytest.mark.public_data
@pytest.mark.parametrize(
    "source", ["sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"]
)
def test_each_restaurant_source_requires_the_complete_check(
    tmp_path: Path, source: str
) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    entry, digest = series_cache(tmp_path, source, [])
    result = build_series(tmp_path, [entry], {source: digest})
    assert result["required"] == ("PUB-64",)
    assert result["mismatch"] == "PUB-64"


def test_r1_match_records_the_confirmed_field_and_scope(tmp_path: Path) -> None:
    from eii_custodian.publicdata.series.figures import build_series

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    # A deliberately planted match in an invented activity; never a real export row.
    field = "estimates_of_intermediate_goods_value_value_in_1_000_qr"
    fixtures["sec_hr_goods"][0][field] = 8579462
    entries, selected = [], {}
    for source in ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"):
        entry, digest = series_cache(tmp_path, source, fixtures[source])
        entries.append(entry)
        selected[source] = digest
    build_series(tmp_path, entries, selected)
    report = json.loads((tmp_path / "series/internal/reconciliations.json").read_text())
    assert report["R1"]["matches"] == [
        {
            "source": "sec_hr_goods",
            "field": field,
            "year": "2022",
            "activity_scope": "invented-activity",
            "value": 8579462,
            "measure": "intermediate_goods",
            "establishments": "not on this row",
            "indicator_comparisons": [
                {
                    "activities": ["561", "561"],
                    "measure": [
                        [
                            "operating_surplus",
                            "compensation",
                            "value_added_per_worker",
                            "productivity_of_employee",
                            "services_share",
                            "goods_share",
                            "average_annual_wage",
                        ],
                        "intermediate_goods",
                    ],
                    "year": ["2022", "2022"],
                    "establishments": ["not on this row", "not on this row"],
                }
            ],
        }
    ]
    assert report["R1"]["status"] == "open"
    assert report["R1"]["blocked"] == (
        "matched figure requires signed scope resolution; no production or revenue fact"
    )
    assert list((tmp_path / "series/display").iterdir()) == []


@pytest.mark.public_data
def test_missing_frame_output_refuses_even_with_matching_numbers(
    tmp_path: Path, monkeypatch
) -> None:
    from eii_custodian.publicdata.series.figures import finish_build
    from eii_custodian.publicdata.stage import StageResult

    entry, digest = series_cache(
        tmp_path,
        "lic_cancelled",
        [
            {
                "sn_llg": "2020",
                "shhr_llg": 7,
                "lbldy": "invented-municipality",
                "rmz_lnsht_ltjry": "invented-code",
                "sm_lnsht_ltjry": "invented-activity",
                "dd_lrkhs_lmlg": 3,
            }
        ],
    )
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    lines = [f"PASS lic_cancelled sha256={digest} host=invented"]
    result = finish_build([entry], tmp_path, lines)
    assert result is not None
    assert result.source_id == "series"
    assert result.check == "public_data"
    assert result.observed == "municipality_frame_absent"
    assert lines[-1] == "FAIL series municipality_frame_not_supplied lic_cancelled"


@pytest.mark.parametrize(
    "month,expected",
    list(
        enumerate(
            (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ),
            1,
        )
    ),
)
def test_r3_source_months(month, expected):
    from eii_custodian.publicdata.series.parse import source_period

    assert source_period("transit_monthly", "2025", expected) == f"2025-{month:02}"
    for source in ("cus_imp_2025", "lic_cancelled", "lic_issued"):
        assert source_period(source, "2025", month) == f"2025-{month:02}"
        for bad in (str(month), Decimal(month), True, 0, 13):
            with pytest.raises(
                ValueError, match=source + ".*month|" + source + ".*shhr"
            ):
                source_period(source, "2025", bad)
    assert source_period("cus_imp_2019", "2019", Decimal(month)) == f"2019-{month:02}"


def test_r3_period_refusals_and_undated():
    from eii_custodian.publicdata.series.parse import source_period

    assert source_period("lic_cancelled", "", None) is None
    assert source_period("lic_cancelled", None, None) is None
    for bad in ("12", "december", "Dec", 12, None):
        with pytest.raises(ValueError, match=r"transit_monthly.*month"):
            source_period("transit_monthly", "2025", bad)
    for bad in (Decimal("1.5"), "1.0", True, Decimal(0), Decimal(13)):
        with pytest.raises(ValueError, match=r"cus_imp_2019.*lshhr_month"):
            source_period("cus_imp_2019", "2019", bad)
    with pytest.raises(ValueError, match="year"):
        source_period("transit_monthly", "25", "January")


def test_r3_customs_codes_units_and_country():
    from eii_custodian.publicdata.series.figures import contract_rows

    row = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )["cus_imp_2025"][0]
    for code, expected in (
        (int("1" * 12), "1" * 12),
        (int("1" * 11), "0" + "1" * 11),
        (1, None),
    ):
        got = contract_rows(
            "cus_imp_2025",
            [{**row, "harmonized_system_code": code, "country_of_origin": "Italy"}],
        )[0]
        assert got["tariff_code"] == expected
        assert got["origin_iso3"] == "ITA"
        assert got["quantity_unit"] == "not stated by the source"
        assert got["weight_kg"] == row["weight_in_kilograms"]
        assert got["value_qar"] == row["value_in_qatari_riyals"]
    for code in (-1, 12, int("1" * 10), int("1" * 13), "1" * 12, True):
        with pytest.raises(ValueError, match=r"cus_imp_2025.*harmonized_system_code"):
            contract_rows("cus_imp_2025", [{**row, "harmonized_system_code": code}])
    for country in (None, "invented-country", "italy"):
        assert (
            contract_rows("cus_imp_2025", [{**row, "country_of_origin": country}])[0][
                "origin_iso3"
            ]
            is None
        )


def test_r3_municipality_exact_and_no_alias():
    from eii_custodian.publicdata.series.figures import contract_rows
    from eii_custodian.publicdata.series.parse import Municipality

    row = {
        "lbldy": "بلدية تجريبية",
        "rmz_lnsht_ltjry": "invented-code",
        "lnsht_ltjry": "نشاط تجريبي",
        "dd_lrkhs_lnsht": 3,
    }
    frame = (Municipality("invented-municipality", "بلدية تجريبية"),)
    assert (
        contract_rows("lic_active", [row], municipalities=frame)[0]["municipality_code"]
        == "invented-municipality"
    )
    assert (
        contract_rows(
            "lic_active", [{**row, "lbldy": "بلدية تجريبيه"}], municipalities=frame
        )[0]["municipality_code"]
        is None
    )


def test_r3_pub64_published_fields_only():
    from eii_custodian.publicdata.series.figures import compute_checks

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text(),
        parse_float=Decimal,
    )
    from .test_series_exact_regressions import pub64_receipts

    data = {k: v for k, v in fixtures.items() if k.startswith("sec_hr_")}
    got = compute_checks(data, receipts=pub64_receipts(data))["PUB-64"]
    assert got == {
        "establishments": "12",
        "employees": "11",
        "compensation": "12",
        "operating_surplus": "11",
        "average_annual_wage": "17",
        "output_per_employee": "14",
        "compensation_share_1dp": "7792.2",
        "operating_surplus_share_1dp": "7142.9",
        "food_share_1dp": "1.7",
        "beverages_share_1dp": "0.5",
        "building_rent_share_1dp": "0.9",
        "goods_share_1dp": "2.5",
        "services_share_1dp": "1.3",
    }
    from eii_custodian.publicdata.stage import EXPECTED

    assert "production_value" not in EXPECTED["PUB-64"]


def test_r3_partial_year_caveat_and_registry():
    from eii_custodian.publicdata.series.figures import contract_rows

    for year, expected in (("2025", []), ("2026", ["partial_year_january_august"])):
        row = contract_rows(
            "util_elec", [{"year": year, "zone_number": "69", "value": 5}]
        )[0]
        assert row["caveat_keys"] == expected
    publishers = {"transit_monthly": "Ministry of Transport", "util_elec": "KAHRAMAA"}
    from eii_custodian.publicdata.series.parse import FIELD_MAP

    for entry in load_registry():
        if entry.source_id in FIELD_MAP:
            expected = publishers.get(
                entry.source_id,
                "Ministry of Commerce and Industry"
                if entry.source_id.startswith("lic_")
                else "National Planning Council",
            )
            assert entry.publisher == expected
            assert entry.licence_id == "CC-BY-4.0"


@pytest.mark.parametrize("code", ["1" * n for n in (1, 7, 9, 11, 12)])
def test_r3_hs8_lengths_refuse_with_report(tmp_path, code):
    from eii_custodian.publicdata.series.figures import build_series

    row = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )["cus_imp_2019"][0]
    entry, digest = series_cache(tmp_path, "cus_imp_2019", [{**row, "hs8": code}])
    with pytest.raises(ValueError, match="cus_imp_2019 hs8"):
        build_series(tmp_path, [entry], {entry.key: digest})
    assert json.loads((tmp_path / "series/internal/coverage.json").read_text())[
        "cus_imp_2019.hs8_lengths"
    ] == {str(len(code)): 1}
    assert list((tmp_path / "series/display").iterdir()) == []


def test_r3_hs8_valid_and_coverage(tmp_path):
    from eii_custodian.publicdata.series.figures import build_series, contract_rows

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text(),
        parse_float=Decimal,
    )
    earlier = {**fixtures["cus_imp_2019"][0], "hs8": "1" * 8}
    got = contract_rows("cus_imp_2019", [earlier])[0]
    assert got["tariff_code"] == "1" * 8
    assert got["period"] == "2019-01"
    assert got["value_qar"] == Decimal("4.5")
    assert got["weight_kg"] == Decimal("2.5")
    row = fixtures["cus_imp_2025"][0]
    # Fixtures serialised by series_cache need standard JSON numbers.
    row = json.loads(json.dumps(row, default=float))
    entry, digest = series_cache(
        tmp_path,
        "cus_imp_2025",
        [
            row,
            {**row, "harmonized_system_code": 1},
            {**row, "country_of_origin": "invented-country"},
        ],
    )
    with pytest.raises(ValueError, match="country_unmatched"):
        build_series(tmp_path, [entry], {entry.key: digest})
    coverage = json.loads((tmp_path / "series/internal/coverage.json").read_text())
    assert coverage == {
        "cus_imp_2025.code_not_stated": 1,
        "cus_imp_2025.country_not_stated": 2,
        "cus_imp_2025.country_unmatched": ["invented-country"],
    }


def test_r3_licence_periods_and_reports(tmp_path):
    from eii_custodian.publicdata.series.figures import build_series, contract_rows
    from eii_custodian.publicdata.series.parse import Municipality

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    frame = (Municipality("invented-frame-code", "بلدية تجريبية"),)
    issued = contract_rows("lic_issued", fixtures["lic_issued"], municipalities=frame)[
        0
    ]
    assert issued == {
        "period": "2025-05",
        "municipality_code": "invented-frame-code",
        "activity_code": "invented-code",
        "issued_count": 3,
        "caveat_keys": ["openings_incomplete"],
    }
    cancelled = contract_rows(
        "lic_cancelled", fixtures["lic_cancelled"], municipalities=frame
    )
    assert [r["period"] for r in cancelled] == [None, "2020-07", "2022-06", "2024-09"]
    assert [r["cancelled_count"] for r in cancelled] == [2, 3, 3, 3]
    entry, digest = series_cache(tmp_path, "lic_active", fixtures["lic_active"])
    result = build_series(tmp_path, [entry], {entry.key: digest}, municipalities=frame)
    assert result["coverage"]["lic_active.municipality_exact_match"] == []
    assert result["blocked"] == {
        "lic_active": ("regression: supporting provenance selections required",)
    }
    assert "PUB-67" not in result["checks"]
    # S2-T08 part B, B13: an unmapped spelling refuses by its word before any
    # table file, keeping the spelling in the internal coverage report only.
    from eii_custodian.publicdata.series.parse import SeriesRefused

    rows = fixtures["lic_active"] + [
        {**fixtures["lic_active"][0], "lbldy": "بلدية غير مطابقة"}
    ]
    entry, digest = series_cache(tmp_path, "lic_active", rows)
    with pytest.raises(SeriesRefused) as caught:
        build_series(tmp_path, [entry], {entry.key: digest}, municipalities=frame)
    assert caught.value.word == "unmapped_municipality_spelling"
    assert json.loads((tmp_path / "series/internal/coverage.json").read_text())[
        "lic_active.municipality_exact_match"
    ] == ["بلدية غير مطابقة"]
    assert not (tmp_path / "series/internal/pub_licence_active.json").exists()


def test_r3_reference_review_remains_explicit():
    import csv

    review = Path(__file__).resolve().parents[1] / "publicdata/review"
    with (review / "country_iso3.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows and all(r["human_reviewed"] == "false" for r in rows)
    assert not (review / "municipality_aliases.json").exists()
    assert (review / "municipality_names.csv").is_file()


def test_r3_planted_legacy_alias_is_never_read(tmp_path, monkeypatch):
    from eii_custodian.publicdata.series import parse
    from eii_custodian.publicdata.series.figures import build_series

    module = tmp_path / "src/eii_custodian/publicdata/series/parse.py"
    module.parent.mkdir(parents=True)
    review = tmp_path / "publicdata/review"
    review.mkdir(parents=True)
    monkeypatch.setattr(parse, "__file__", str(module))
    (review / "country_iso3.csv").write_text(
        "name_en,iso3\ninvented-country,SYN\n", encoding="utf-8"
    )
    (review / "country_aliases.csv").write_text(
        "name_en,iso3,reason\n", encoding="utf-8"
    )
    names = tmp_path / "invented_review"
    names.mkdir()
    (names / "municipality_names.csv").write_text(
        "name,municipality_code\nبلدية تجريبية,invented-frame-code\n", encoding="utf-8"
    )
    monkeypatch.setattr(parse, "MUNICIPALITY_NAMES_REVIEW", names)
    legacy = review / "municipality_aliases.json"
    legacy.write_text(
        json.dumps(
            [
                {
                    "source_name_ar": "بلدية تجريبيه",
                    "frame_name_ar": "بلدية تجريبية",
                    "reviewer_role": "invented-reviewer",
                    "review_date": "2026-11-14",
                }
            ]
        )
    )
    original_open = Path.open

    def refuse_legacy_read(path, *args, **kwargs):
        if path == legacy:
            raise AssertionError("legacy municipality alias file was read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse_legacy_read)
    frame = (parse.Municipality("invented-frame-code", "بلدية تجريبية"),)
    row = {
        "lbldy": "بلدية تجريبيه",
        "rmz_lnsht_ltjry": "invented-code",
        "lnsht_ltjry": "invented-name",
        "dd_lrkhs_lnsht": 7,
    }
    entry, digest = series_cache(tmp_path, "lic_active", [row])
    with pytest.raises(parse.SeriesRefused) as caught:
        build_series(tmp_path, [entry], {entry.key: digest}, municipalities=frame)
    assert caught.value.word == "unmapped_municipality_spelling"


def test_r3_exact_pub64_registry_mapping():
    from eii_custodian.publicdata.series.parse import FIELD_MAP

    registry = (
        Path(__file__).resolve().parents[1] / "publicdata/sources.yaml"
    ).read_text()
    for source in ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"):
        for field, (table, column) in FIELD_MAP[source].items():
            if column.startswith("value:"):
                assert source + "." + field + " -> " + table + "." + column in registry


def test_r3_undated_missing_year_and_frame_marker(tmp_path):
    from eii_custodian.publicdata.series.figures import build_series, contract_rows
    from eii_custodian.publicdata.series.parse import source_period

    assert source_period("lic_cancelled", None, 7) is None
    assert source_period("lic_cancelled", "", 7) is None
    row = {
        "lbldy": "invented",
        "rmz_lnsht_ltjry": "invented-code",
        "lnsht_ltjry": "invented-name",
        "dd_lrkhs_lnsht": 7,
    }
    assert contract_rows("lic_active", [row])[0]["active_count"] == 7
    entry, digest = series_cache(tmp_path, "lic_active", [row])
    result = build_series(tmp_path, [entry], {entry.key: digest})
    assert result["blocked"]["lic_active"] == ("municipality_frame_not_supplied",)


def test_r3_remaining_numeric_checks_do_not_claim_basket_or_spine_review():
    from eii_custodian.publicdata.series.figures import compute_checks

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text(),
        parse_float=Decimal,
    )
    from custodian.tests.test_pub67 import FRAME, classes

    fixtures["lic_active"][0].update(lbldy=FRAME[0].name_ar, rmz_lnsht_ltjry="561010")
    row = fixtures["cus_imp_2025"][0]
    checks = compute_checks(
        {
            "cus_imp_2025": [
                {
                    **row,
                    "country_of_origin": "Italy",
                    "value_in_qatari_riyals": 18,
                    "weight_in_kilograms": 3,
                },
                {
                    **row,
                    "country_of_origin": "Saudi Arabia",
                    "value_in_qatari_riyals": 20,
                    "weight_in_kilograms": 2,
                },
                {
                    **row,
                    "country_of_origin": "Italy",
                    "value_in_qatari_riyals": 100,
                    "weight_in_kilograms": 0,
                },
                {
                    **row,
                    "country_of_origin": "Italy",
                    "harmonized_system_code": 1,
                    "value_in_qatari_riyals": 100,
                },
            ],
            "lic_active": fixtures["lic_active"],
            "lic_issued": fixtures["lic_issued"],
        },
        isic_classes=classes(),
        municipalities=FRAME,
        activity_entry=next(e for e in load_registry() if e.key == "lic_active"),
    )
    assert checks["PUB-65"] == {
        "italy_2dp": "6.00",
        "saudi_arabia_2dp": "10.00",
        "valuation_basis_present": "true",
    }
    assert checks["PUB-67"] == {
        "rows": "1",
        "sum_count": "3",
        "distinct_codes": "1",
        "national_5610101": "0",
        "isic_prefix": "0",
        "other_seven": "0",
        "legacy_six": "3",
        "other_lengths": "0",
        "al_daayen_5610101": "0",
    }
    assert checks["PUB-69"] == {
        "sum_count": "3",
        "distinct_codes": "1",
        "restaurant_source_rows": "0",
        "restaurant_contract_rows": "0",
        "incompleteness_note": "openings_incomplete",
        "net_formation_built": "false",
    }
    # A present restaurant code must be counted, not reported as the zero anchor.
    issued = {**fixtures["lic_issued"][0], "rmz_lnsht_ltjry": "5610101"}
    assert (
        compute_checks({"lic_issued": [issued]})["PUB-69"]["restaurant_source_rows"]
        == "1"
    )


@pytest.mark.parametrize(
    "year,month", [("", 0), (None, 13), ("", "7"), ("", True), ("bad-year", None)]
)
def test_r3_undated_does_not_hide_malformed_present_field(year, month):
    from eii_custodian.publicdata.series.parse import source_period

    with pytest.raises(ValueError, match="lic_cancelled"):
        source_period("lic_cancelled", year, month)


def test_r3_customs_contract_complete_and_named_month_field():
    from eii_custodian.publicdata.series.figures import contract_rows
    from eii_custodian.publicdata.series.parse import source_period

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text(),
        parse_float=Decimal,
    )
    row = fixtures["cus_imp_2025"][0]
    assert contract_rows("cus_imp_2025", [row])[0] == {
        "period": "2025-01",
        "tariff_code": "190200000001",
        "description_en": "invented pasta",
        "description_ar": "معكرونة تجريبية",
        "origin_iso3": None,
        "quantity": Decimal("1.5"),
        "quantity_unit": "not stated by the source",
        "weight_kg": Decimal("2.5"),
        "value_qar": 2000000000,
        "valuation_basis": "not stated by the source",
    }
    with pytest.raises(ValueError) as caught:
        source_period("transit_monthly", "2025", "invented-month")
    assert str(caught.value).startswith("transit_monthly month:")


def test_r3_active_snapshot_uses_pub67_period():
    from eii_custodian.publicdata.series.figures import contract_rows

    row = {
        "lbldy": "invented",
        "rmz_lnsht_ltjry": "invented-code",
        "lnsht_ltjry": "invented-name",
        "dd_lrkhs_lnsht": 1,
    }
    assert contract_rows("lic_active", [row])[0]["period"] == "2025-05"


@pytest.mark.parametrize("body", [{"invented_value": "12.50"}, ["invented"]])
def test_selected_source_requires_rows(tmp_path, body):
    entry, _, receipt = fixture(tmp_path)
    raw = json.dumps(body).encode()
    digest = sha256_hex(raw)
    receipt.update(sha256=digest, bytes=len(raw))
    commit_pair(tmp_path / entry.key, digest, "json", raw, receipt)
    with pytest.raises(ValueError, match="source must contain rows"):
        selected_source(tmp_path, entry, digest)


def test_confirmed_registry_field_refused():
    from eii_custodian.publicdata.series.parse import confirmed_rows

    entry = next(e for e in load_registry() if e.key == "util_elec")
    entry = replace(entry, columns=(*entry.columns, ("invented_field", "string")))
    with pytest.raises(ValueError, match="util_elec registry fields: invented_field"):
        confirmed_rows(entry, [{"year": "2021", "zone_number": "69", "value": 12}])


def test_unknown_contract_source_refused():
    from eii_custodian.publicdata.series.figures import contract_rows

    with pytest.raises(
        ValueError, match="invented-source missing confirmed contract fields"
    ):
        contract_rows("invented-source", [{}])


@pytest.mark.parametrize("count", [0, 2])
def test_restaurant_indicator_requires_one_row(count):
    from eii_custodian.publicdata.series.figures import compute_checks
    from eii_custodian.publicdata.series.reconcile import R1_SOURCES

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    data = {s: fixtures[s] for s in R1_SOURCES}
    data["sec_hr_ind"] *= count
    with pytest.raises(
        ValueError, match="sec_hr_ind: one restaurant indicator row required"
    ):
        compute_checks(data)


def test_production_column_absent_from_confirmed_mapping():
    from eii_custodian.publicdata.series.parse import FIELD_MAP
    from eii_custodian.publicdata.series.reconcile import R1_SOURCES

    assert all(
        "production_value" not in field and column != "value:production_value"
        for source in R1_SOURCES
        for field, (_, column) in FIELD_MAP[source].items()
    )


@pytest.mark.parametrize(
    "source,year,month,reason",
    [
        ("lic_cancelled", "bad", None, "lic_cancelled sn_llg: four digits required"),
        ("lic_cancelled", None, 13, "lic_cancelled shhr_llg: integer month required"),
        (
            "transit_monthly",
            "bad",
            "January",
            "transit_monthly year: four digits required",
        ),
        (
            "transit_monthly",
            "2025",
            "invented",
            "transit_monthly month: English month name required",
        ),
        (
            "cus_imp_2019",
            "2019",
            Decimal("1.5"),
            "cus_imp_2019 lshhr_month: zero fraction required",
        ),
        ("cus_imp_2025", "2025", "1", "cus_imp_2025 month: integer required"),
        ("cus_imp_2025", "2025", 13, "cus_imp_2025 month: outside month range"),
    ],
)
def test_period_named_refusals(source, year, month, reason):
    from eii_custodian.publicdata.series.parse import source_period

    with pytest.raises(ValueError, match=reason):
        source_period(source, year, month)


@pytest.mark.parametrize(
    "source,code,reason",
    [
        ("cus_imp_2019", "1" * 7, "expected eight digits; lengths require review"),
        ("cus_imp_2025", "1" * 12, "integer code required"),
        ("cus_imp_2025", 12, "unexpected code length"),
    ],
)
def test_customs_code_named_refusals(source, code, reason):
    from eii_custodian.publicdata.series.parse import customs_code

    with pytest.raises(ValueError, match=reason):
        customs_code(source, code)


@pytest.mark.parametrize(
    "field,reason",
    [
        ("method", "missing method"),
        ("method_version", "missing method_version"),
        ("source_chain", "missing source_chain"),
        ("release_tables", "missing source_chain release_tables"),
        ("field_mapping", "missing source_chain field_mapping"),
        ("publisher", "incomplete source_chain"),
        ("sha256", "invalid source_chain hash"),
    ],
)
def test_figure_named_refusals(tmp_path, field, reason):
    from eii_custodian.publicdata.series.figures import validate_figure

    entry, _, receipt = fixture(tmp_path)
    envelope = {
        "method": "invented",
        "method_version": "1",
        "source_chain": [receipt],
        "release_tables": list(entry.release_tables),
        "field_mapping": {"invented": "value"},
    }
    validate_figure(envelope)
    if field in ("publisher", "sha256"):
        receipt[field] = "" if field == "publisher" else "zz"
    else:
        del envelope[field]
    with pytest.raises(ValueError, match=reason):
        validate_figure(envelope)


def test_named_mapping_gap_blocks_display(tmp_path, monkeypatch):
    from eii_custodian.publicdata.series.figures import build_series
    from eii_custodian.publicdata.stage import StageResult

    rows = [
        {"year": "2021", "zone_number": "69", "value": 12},
        {"year": "2025", "zone_number": "69", "value": 30},
    ]
    entry, digest = series_cache(tmp_path, "util_elec", rows)
    monkeypatch.setattr(
        "eii_custodian.publicdata.series.figures.mapping_gaps",
        lambda source: ("invented_mapping_gap",),
    )
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    result = build_series(tmp_path, [entry], {entry.key: digest})
    assert result["blocked"] == {"util_elec": ("invented_mapping_gap",)}
    assert not list((tmp_path / "series/display").iterdir())


def test_duplicate_field_mapping_refused(tmp_path):
    entry, _, _ = fixture(tmp_path)
    entry = replace(entry, columns=(("invented_a", "string"), ("invented_b", "string")))
    with pytest.raises(ValueError, match="incomplete or duplicate field mapping"):
        parse_rows(
            entry,
            [{"invented_a": "a", "invented_b": "b"}],
            {"invented_a": "value", "invented_b": "value"},
        )


def test_r1_size_match_records_count_and_different_scope(tmp_path):
    from eii_custodian.publicdata.series.figures import build_series
    from eii_custodian.publicdata.series.reconcile import R1_SOURCES

    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    fixtures["sec_hr_size"][0].update(
        number_of_employees=8579462, activity_code=551, year="2021"
    )
    entries, selected = [], {}
    for source in sorted(R1_SOURCES):
        entry, digest = series_cache(tmp_path, source, fixtures[source])
        entries.append(entry)
        selected[source] = digest
    build_series(tmp_path, entries, selected)
    report = json.loads(
        (tmp_path / "series/internal/reconciliations.json").read_text()
    )["R1"]
    match = report["matches"][0]
    assert match["measure"] == "employees"
    assert match["establishments"] == 12
    assert match["indicator_comparisons"][0]["activities"] == ["561", "551"]
    assert match["indicator_comparisons"][0]["year"] == ["2022", "2021"]
    assert match["indicator_comparisons"][0]["establishments"] == [
        "not on this row",
        12,
    ]
    assert report["status"] == "open"
    assert not list((tmp_path / "series/display").iterdir())


# S2-T08 part B, B13 and B15 (plan r3 section 3). Invented names and rows only.
INVENTED_FRAME_NAME = "بلدية مخترعة"
INVENTED_SPELLING = "بلدية مخترعة بصيغة أخرى"


def frame_output(cache: Path, rows=((("SYN-A", INVENTED_FRAME_NAME),))) -> None:
    from eii_custodian.publicdata.frame.municipality_output import (
        write_municipality_output,
    )

    write_municipality_output(
        cache,
        [
            {"municipality_code": code, "name_en": "invented", "name_ar": name}
            for code, name in rows
        ],
    )


def names_review(tmp_path: Path, monkeypatch, rows) -> Path:
    folder = tmp_path / "invented_review"
    folder.mkdir()
    (folder / "municipality_names.csv").write_text(
        "name,municipality_code\n" + "".join(f"{name},{code}\n" for name, code in rows),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "eii_custodian.publicdata.series.parse.MUNICIPALITY_NAMES_REVIEW", folder
    )
    return folder


def cancelled_row(spelling: str, **changes) -> dict[str, object]:
    return {
        "sn_llg": "2020",
        "shhr_llg": 7,
        "lbldy": spelling,
        "rmz_lnsht_ltjry": "invented-code",
        "sm_lnsht_ltjry": "نشاط تجريبي",
        "dd_lrkhs_lmlg": 3,
        **changes,
    }


def run_finish(tmp_path: Path, source: str, rows):
    from eii_custodian.publicdata.series.figures import finish_build

    entry, digest = series_cache(tmp_path, source, rows)
    lines = [f"PASS {entry.key} sha256={digest} host=invented"]
    return finish_build([entry], tmp_path, lines), lines


@pytest.mark.public_data
def test_reviewed_spelling_reaches_the_licence_join(tmp_path, monkeypatch):
    frame_output(tmp_path)
    names_review(tmp_path, monkeypatch, [(INVENTED_SPELLING, "SYN-A")])
    # Whitespace differs from the reviewed row: one spelling rule, normalise_name.
    spelling = INVENTED_SPELLING.replace(" ", "  ", 1)
    failure, lines = run_finish(tmp_path, "lic_cancelled", [cancelled_row(spelling)])
    # The real stage compares invented values with section 10: the figure fails.
    assert failure is not None and failure.source_id == "PUB-68"
    assert lines[-1] == "FAIL PUB-68 public_data selected-cache check"
    table = json.loads(
        (tmp_path / "series/internal/pub_licence_cancelled.json").read_text()
    )
    assert [row["municipality_code"] for row in table["rows"]] == ["SYN-A"]


@pytest.mark.public_data
def test_unmapped_spelling_is_refused_by_its_word(tmp_path, monkeypatch):
    frame_output(tmp_path)
    names_review(tmp_path, monkeypatch, [(INVENTED_SPELLING, "SYN-A")])
    failure, lines = run_finish(
        tmp_path, "lic_cancelled", [cancelled_row("بلدية لا يعرفها الملف")]
    )
    assert failure is not None
    assert lines[-1] == "FAIL series unmapped_municipality_spelling"
    assert (failure.source_id, failure.check, failure.observed) == (
        "series",
        "public_data",
        "unmapped_municipality_spelling",
    )
    assert not (tmp_path / "series/internal/pub_licence_cancelled.json").exists()
    assert list((tmp_path / "series/display").iterdir()) == []


@pytest.mark.public_data
def test_refused_names_file_is_named(tmp_path, monkeypatch):
    frame_output(tmp_path, (("SYN-A", INVENTED_FRAME_NAME), ("SYN-B", "بلدية ثانية")))
    names_review(
        tmp_path,
        monkeypatch,
        [(INVENTED_SPELLING, "SYN-A"), (INVENTED_SPELLING, "SYN-B")],
    )
    failure, lines = run_finish(
        tmp_path, "lic_cancelled", [cancelled_row(INVENTED_FRAME_NAME)]
    )
    assert failure is not None and failure.observed == "municipality_names_refused"
    assert lines[-1] == "FAIL series municipality_names_refused"


@pytest.mark.public_data
def test_reviewed_spelling_that_contradicts_the_frame_is_refused(tmp_path, monkeypatch):
    frame_output(tmp_path, (("SYN-A", INVENTED_FRAME_NAME), ("SYN-B", "بلدية ثانية")))
    names_review(tmp_path, monkeypatch, [(INVENTED_FRAME_NAME, "SYN-B")])
    failure, lines = run_finish(
        tmp_path, "lic_cancelled", [cancelled_row(INVENTED_FRAME_NAME)]
    )
    assert failure is not None and failure.observed == "municipality_names_refused"
    assert lines[-1] == "FAIL series municipality_names_refused"


@pytest.mark.public_data
def test_refusal_text_and_type_never_reach_the_line_or_record(tmp_path, monkeypatch):
    frame_output(tmp_path)
    names_review(tmp_path, monkeypatch, [(INVENTED_SPELLING, "SYN-A")])
    marker = "invented_marker_field"
    failure, lines = run_finish(
        tmp_path,
        "lic_cancelled",
        [cancelled_row(INVENTED_FRAME_NAME, **{marker: 1})],
    )
    assert failure is not None
    assert lines[-1] == "FAIL series selected_input_refused"
    fields = (failure.source_id, failure.url, failure.check, failure.expected)
    for text in (*lines, *fields, failure.observed):
        assert marker not in text and "Error" not in text
    assert failure.observed == "selected_input_refused"


def test_series_refusal_words_are_one_closed_tuple():
    from eii_custodian.publicdata.series import figures, parse

    assert figures.SERIES_REFUSALS is parse.SERIES_REFUSALS
    assert parse.SERIES_REFUSALS == (
        "municipality_frame_not_supplied",
        "unmapped_municipality_spelling",
        "municipality_names_refused",
        "selected_input_refused",
    )
    for word in parse.SERIES_REFUSALS:
        assert parse.SeriesRefused(word, "invented text").word == word
    with pytest.raises(ValueError, match=r"^series_refusal_unknown$"):
        parse.SeriesRefused("series_mapping", "invented text")


@pytest.mark.public_data
@pytest.mark.parametrize(
    "source,figure,rows",
    [
        # compute_checks needs zone 69 in 2021 and 2025: a missing year refuses.
        ("util_elec", "PUB-62", [{"year": "2021", "zone_number": "69", "value": 12}]),
        # Two rows of one month are refused as a duplicate transit period.
        (
            "transit_monthly",
            "PUB-70",
            [
                {
                    "year": "2024",
                    "month": "December",
                    "lshhr": "شهر تجريبي",
                    "public_transport_buses": 1,
                    "doha_metro": 10,
                    "lusail_tram": 3,
                }
            ]
            * 2,
        ),
        # A dated cancellation outside the C2 calendar is refused.
        (
            "lic_cancelled",
            "PUB-68",
            [cancelled_row(INVENTED_FRAME_NAME, sn_llg="2010")],
        ),
    ],
)
def test_real_stage_names_the_figure_of_a_blocked_source(
    tmp_path, monkeypatch, source, figure, rows
):
    # B15 step 1: on the real stage, with nothing replaced, a refusal of
    # compute_checks leaves the figure's regression file absent, so the stage
    # names that figure; the build never needs a series_mapping fallback.
    frame_output(tmp_path)
    names_review(tmp_path, monkeypatch, [(INVENTED_SPELLING, "SYN-A")])
    failure, lines = run_finish(tmp_path, source, rows)
    build = json.loads((tmp_path / "series/internal/build.json").read_text())
    assert build["blocked"][source][0].startswith("regression: ")
    assert build["mismatch"] == figure
    assert failure is not None and failure.source_id == figure
    assert lines[-1] == "FAIL " + figure + " public_data selected-cache check"
