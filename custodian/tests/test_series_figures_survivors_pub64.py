"""Invented boundary cases for the PUB-64 mutation pass.

Schema extensions below are test-local declarations, with matching registry
columns. The build still validates each selected source and its receipt.
"""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_baskets import invented_review
from custodian.tests.test_public_series import series_cache
from custodian.tests.test_series_exact_regressions import pub64_build, pub64_rows
from custodian.tests.test_series_figures_survivors import _shapes
from custodian.tests.test_series_r5 import write_review

from eii_custodian.publicdata.series import figures


def _whole_text(found: object, literal: str) -> None:
    assert str(found) == literal


def test_build_preserves_compound_measure_names(tmp_path, monkeypatch):
    data = pub64_rows()
    field = "value_added_per_worker_qr"
    data["sec_hr_ind"][0][field] = 8579462
    mapping = dict(figures.FIELD_MAP["sec_hr_ind"])
    mapping[field] = ("pub_sector_accounts", "value:invented:measure")
    monkeypatch.setitem(figures.FIELD_MAP, "sec_hr_ind", mapping)

    pub64_build(tmp_path, data)

    table = json.loads(
        (tmp_path / "series/internal/pub_sector_accounts.json").read_text()
    )
    assert [row for row in table["rows"] if row["value"] == 8579462] == [
        {
            "activity_code": "561",
            "period": "2022",
            "indicator": "invented:measure",
            "value": 8579462,
            "unit": "QAR",
        }
    ]
    report = json.loads((tmp_path / "series/internal/reconciliations.json").read_text())
    assert report["R1"]["matches"] == [
        {
            "source": "sec_hr_ind",
            "field": "value_added_per_worker_qr",
            "year": "2022",
            "activity_scope": "invented-activity",
            "value": 8579462,
            "measure": "invented:measure",
            "establishments": "not on this row",
            "indicator_comparisons": [
                {
                    "activities": ["561", "561"],
                    "measure": [
                        [
                            "operating_surplus",
                            "compensation",
                            "invented:measure",
                            "productivity_of_employee",
                            "services_share",
                            "goods_share",
                            "average_annual_wage",
                        ],
                        "invented:measure",
                    ],
                    "year": ["2022", "2022"],
                    "establishments": ["not on this row", "not on this row"],
                }
            ],
        }
    ]


def test_build_compares_declared_indicator_establishments(tmp_path, monkeypatch):
    data = pub64_rows()
    data["sec_hr_ind"][0]["number_of_establishments"] = 9
    data["sec_hr_goods"][0][
        "estimates_of_intermediate_goods_value_value_in_1_000_qr"
    ] = 8579462
    mapping = dict(figures.FIELD_MAP["sec_hr_ind"])
    mapping["number_of_establishments"] = (
        "pub_sector_accounts",
        "value:establishments",
    )
    monkeypatch.setitem(figures.FIELD_MAP, "sec_hr_ind", mapping)
    entries, selected = [], {}
    for source, rows in data.items():
        entry, digest = series_cache(tmp_path, source, rows)
        if source == "sec_hr_ind":
            entry = replace(
                entry, columns=(*entry.columns, ("number_of_establishments", "integer"))
            )
        entries.append(entry)
        selected[source] = digest

    figures.build_series(tmp_path, entries, selected)

    report = json.loads((tmp_path / "series/internal/reconciliations.json").read_text())
    assert report["R1"]["matches"][0]["indicator_comparisons"] == [
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
                    "establishments",
                ],
                "intermediate_goods",
            ],
            "year": ["2022", "2022"],
            "establishments": [9, "not on this row"],
        }
    ]


def test_build_mapping_gap_uses_selected_source(tmp_path, monkeypatch):
    entry, digest = series_cache(tmp_path, "util_elec", _shapes()["util_elec"])
    monkeypatch.setattr(
        figures,
        "mapping_gaps",
        lambda source: ("invented-missing-field",) if source == "util_elec" else (),
    )
    result = figures.build_series(tmp_path, [entry], {entry.key: digest})
    assert result["blocked"] == {"util_elec": ("invented-missing-field",)}


@pytest.mark.parametrize("source", ["cus_imp_2025", "lic_active"])
@pytest.mark.parametrize(
    "extra,message",
    [
        (False, "zip() argument 2 is shorter than argument 1"),
        (True, "zip() argument 2 is longer than argument 1"),
    ],
)
def test_build_refuses_contract_cardinality_changes(
    tmp_path, monkeypatch, source, extra, message
):
    # A broken adapter must be refused before basket review or display. The
    # generated cache and receipt use invented rows. An explicit invented
    # review also isolates the path a broken guard would incorrectly reach.
    entry, digest = series_cache(tmp_path, source, _shapes()[source])
    review = invented_review()
    for activity in review["activities"]:
        activity["inputs"] = []
    review_path = write_review(tmp_path, review)
    original = figures.contract_rows

    def broken_contract(*args, **kwargs):
        converted = original(*args, **kwargs)
        return [*converted, dict(converted[0])] if extra else converted[:-1]

    monkeypatch.setattr(figures, "contract_rows", broken_contract)
    with pytest.raises(ValueError) as caught:
        figures.build_series(
            tmp_path, [entry], {entry.key: digest}, basket_review=review_path
        )
    _whole_text(caught.value, message)
    assert not list((tmp_path / "series/display").glob("*.json"))
