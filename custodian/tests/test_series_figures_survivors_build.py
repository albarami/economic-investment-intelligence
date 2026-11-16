"""Selected build reports, default review routing and reconciliation boundaries."""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_baskets import invented_review
from custodian.tests.test_public_series import series_cache
from custodian.tests.test_series_figures_survivors import _shapes, _whole_text
from custodian.tests.test_series_r5 import source_rows

from eii_custodian.publicdata.series import figures
from eii_custodian.publicdata.series.reconcile import Resolution
from eii_custodian.publicdata.stage import StageResult


def test_default_review_path_is_resolved(tmp_path, monkeypatch):
    # Redirect only the module location: no installed real basket lines read.
    module = tmp_path / "src/eii_custodian/publicdata/series/figures.py"
    module.parent.mkdir(parents=True)
    review = tmp_path / "publicdata/review/baskets.yaml"
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps(invented_review()), encoding="utf-8")
    monkeypatch.setattr(figures, "__file__", str(module))
    assert figures.basket_exclusion_review(source_rows()) is True


def test_selected_sources_whole_refusal(tmp_path):
    with pytest.raises(ValueError) as caught:
        figures.build_series(tmp_path, [], {"invented": "invented"})
    _whole_text(caught.value, "selected sources must exactly match owned entries")


def test_unmatched_country_whole_refusal(tmp_path):
    row = dict(_shapes()["cus_imp_2025"][0], country_of_origin="SYN-country")
    entry, digest = series_cache(tmp_path, "cus_imp_2025", [row])
    with pytest.raises(ValueError) as caught:
        figures.build_series(tmp_path, [entry], {entry.key: digest})
    _whole_text(caught.value, "cus_imp_2025 country_unmatched: ['SYN-country']")


def test_historical_lengths_accumulate(tmp_path):
    row = dict(_shapes()["cus_imp_2019"][0], hs8="1" * 8)
    entry, digest = series_cache(tmp_path, "cus_imp_2019", [row, row])
    result = figures.build_series(tmp_path, [entry], {entry.key: digest})
    assert result["coverage"]["cus_imp_2019.hs8_lengths"] == {"8": 2}


def test_only_shared_wage_years_are_reported(tmp_path):
    shapes = _shapes()
    shapes["wage_act"].append(dict(shapes["wage_act"][0], year="2023"))
    entries, selected = [], {}
    for source in ("wage_occ", "wage_act"):
        entry, digest = series_cache(tmp_path, source, shapes[source])
        entries.append(entry)
        selected[source] = digest
    figures.build_series(tmp_path, entries, selected)
    report = json.loads((tmp_path / "series/internal/reconciliations.json").read_text())
    assert report["R2"]["years"] == [
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


def test_restaurant_evidence_requires_both_axes(tmp_path):
    shapes = _shapes()
    shapes["sec_hr_goods"][0][
        "estimates_of_intermediate_goods_value_value_in_1_000_qr"
    ] = 8579462
    row = shapes["sec_hr_ind"][0]
    shapes["sec_hr_ind"].extend([dict(row, activity_code=551), dict(row, year="2021")])
    entries, selected = [], {}
    for source in ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"):
        entry, digest = series_cache(tmp_path, source, shapes[source])
        entries.append(entry)
        selected[source] = digest
    result = figures.build_series(tmp_path, entries, selected)
    report = json.loads((tmp_path / "series/internal/reconciliations.json").read_text())
    comparisons = report["R1"]["matches"][0]["indicator_comparisons"]
    assert len(comparisons) == 1
    assert comparisons[0]["activities"] == ["561", "561"]
    assert comparisons[0]["year"] == ["2022", "2022"]
    assert result["checks"]["PUB-64"]["employees"] == "11"


def test_mapping_gap_and_regression_are_both_retained(tmp_path, monkeypatch):
    entry, digest = series_cache(tmp_path, "util_elec", [_shapes()["util_elec"][0]])
    monkeypatch.setattr(figures, "mapping_gaps", lambda source: ("invented-gap",))
    result = figures.build_series(tmp_path, [entry], {entry.key: digest})
    assert result["blocked"] == {
        "util_elec": ("invented-gap", "regression: ('69', '2025')")
    }


def test_blocked_first_table_does_not_stop_unaffected_display(tmp_path, monkeypatch):
    shapes = _shapes()
    entries, selected = [], {}
    for source in ("lic_active", "util_elec"):
        entry, digest = series_cache(tmp_path, source, shapes[source])
        entries.append(entry)
        selected[source] = digest
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    result = figures.build_series(tmp_path, entries, selected)
    assert result["blocked"] == {"lic_active": ("municipality_frame_not_supplied",)}
    assert (tmp_path / "series/display/pub_zone_utility.json").is_file()
    assert not (tmp_path / "series/display/pub_licence_active.json").exists()


def test_resolution_sequence_reaches_display_gate(tmp_path, monkeypatch):
    entry, digest = series_cache(tmp_path, "sec_hr_goods", _shapes()["sec_hr_goods"])
    entry = replace(entry, reconciliation="resolved:invented")
    resolution = Resolution(
        tmp_path / "absent.md", tmp_path / "absent.json", frozenset({"sec_hr_goods"})
    )
    monkeypatch.setattr(
        "eii_custodian.publicdata.stage.run_stage", lambda *a, **k: StageResult((), "")
    )
    figures.build_series(
        tmp_path, [entry], {entry.key: digest}, resolutions=(resolution,)
    )
    assert not (tmp_path / "series/display/pub_sector_accounts.json").exists()


def test_build_report_complete_at_owned_path(tmp_path):
    entry, digest = series_cache(tmp_path, "util_elec", _shapes()["util_elec"])
    figures.build_series(tmp_path, [entry], {entry.key: digest})
    assert json.loads((tmp_path / "series/internal/build.json").read_text()) == {
        "selected": {"util_elec": digest},
        "coverage": {},
        "checks": {
            "PUB-62": {
                "zone_69_2021": "12",
                "zone_69_2025": "30",
                "ratio_2dp": "2.50",
                "sum_ratio_2dp": "2.50",
            }
        },
        "blocked": {},
        "required": ["PUB-62"],
        "mismatch": "PUB-62",
        "missing": [],
    }


def test_unprefixed_mapping_match_keeps_whole_measure(tmp_path):
    shapes = _shapes()
    # This invented numeric activity value has a mapping without a colon.
    # The evidence scan visits every numeric field, not just value: targets.
    shapes["sec_hr_size"].append(dict(shapes["sec_hr_size"][0], activity_code=8579462))
    entries, selected = [], {}
    for source in ("sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"):
        entry, digest = series_cache(tmp_path, source, shapes[source])
        entries.append(entry)
        selected[source] = digest
    figures.build_series(tmp_path, entries, selected)
    report = json.loads((tmp_path / "series/internal/reconciliations.json").read_text())
    match = report["R1"]["matches"][0]
    assert match["field"] == "activity_code"
    assert match["measure"] == "activity_code"
    assert match["indicator_comparisons"][0]["measure"][1] == "activity_code"


def test_series_stage_does_not_read_unowned_legacy_figure(tmp_path):
    legacy = tmp_path / "figures/PUB-72.json"
    legacy.parent.mkdir()
    legacy.write_text('{"invented": "mismatch"}', encoding="utf-8")
    result = figures.build_series(tmp_path, [], {})
    assert result["mismatch"] == ""
    assert result["missing"] == (
        "PUB-62",
        "PUB-63",
        "PUB-64",
        "PUB-65",
        "PUB-66",
        "PUB-67",
        "PUB-68",
        "PUB-69",
        "PUB-70",
        "PUB-71",
        "PUB-72",
        "PUB-73",
    )
    assert legacy.read_text() == '{"invented": "mismatch"}'
