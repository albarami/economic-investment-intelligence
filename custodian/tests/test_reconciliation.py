"""Invented reconciliation fixtures; no fetched records."""

import hashlib
import json
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from eii_custodian.publicdata.series.reconcile import (
    R1_SOURCES,
    Resolution,
    RestaurantObservation,
    closure_status,
    emit_fact,
    restaurant_evidence,
    wage_evidence,
)


def test_open_lineage_emits_no_fact() -> None:
    assert (
        emit_fact({"value": "invented"}, ("sec_hr_ind",), {"sec_hr_ind": "open"}, ())
        is None
    )


def test_closure_needs_record_and_bound_signoff(tmp_path: Path) -> None:
    record, note = tmp_path / "invented.md", tmp_path / "signoff.json"
    resolution = Resolution(record, note, frozenset({"sec_hr_goods"}))
    assert closure_status(resolution) == "open"
    record.write_text("Invented decision only.")
    assert closure_status(resolution) == "open"
    payload = {
        "approved": True,
        "reviewer_role": "owner-delegated advisor",
        "record": record.name,
        "record_sha256": hashlib.sha256(record.read_bytes()).hexdigest(),
        "sources": ["sec_hr_goods"],
    }
    note.write_text(json.dumps(payload))
    assert closure_status(resolution) == "resolved:invented"
    fact = {"value": "invented"}
    assert (
        emit_fact(
            fact,
            ("sec_hr_goods",),
            {"sec_hr_goods": "resolved:invented"},
            (resolution,),
        )
        == fact
    )
    for field, value in [
        ("approved", False),
        ("reviewer_role", "builder"),
        ("record", "other.md"),
        ("record_sha256", "bad"),
        ("sources", []),
    ]:
        note.write_text(json.dumps({**payload, field: value}))
        assert closure_status(resolution) == "open", field
    note.write_text(json.dumps(payload))
    record.unlink()
    assert closure_status(resolution) == "open"


def test_transitive_and_unknown_lineages_blocked() -> None:
    fact = {"value": "invented"}
    assert emit_fact(fact, (), {}, ()) is None
    assert emit_fact(fact, ("missing",), {}, ()) is None
    assert emit_fact(fact, ("sec_hr_goods",), {"sec_hr_goods": "none"}, ()) is None
    assert (
        emit_fact(
            fact, ("other", "sec_hr_size"), {"other": "none", "sec_hr_size": "open"}, ()
        )
        is None
    )
    assert emit_fact(fact, ("other",), {"other": "resolved:missing"}, ()) is None
    assert emit_fact(fact, ("other",), {"other": "none"}, ()) == fact


def test_restaurant_match_in_other_table_compares_all_axes() -> None:
    production = RestaurantObservation(
        "sec_hr_ind",
        "invented_output",
        D(80),
        "561",
        "production",
        "2022",
        "invented_sample_a",
    )
    revenue = RestaurantObservation(
        "sec_hr_goods",
        "invented_sales",
        D(100),
        "55+56",
        "revenue",
        "2021",
        "invented_sample_b",
    )
    evidence = restaurant_evidence(
        [production, revenue], production, D(100), R1_SOURCES
    )
    assert evidence["matches"] == [
        {
            "source": "sec_hr_goods",
            "field": "invented_sales",
            "value": "100",
            "activities": ("561", "55+56"),
            "measure": ("production", "revenue"),
            "year": ("2022", "2021"),
            "establishments": ("invented_sample_a", "invented_sample_b"),
        }
    ]
    assert evidence["item"] == "R1"
    assert evidence["status"] == "open"
    assert "proposed_measure" not in evidence
    assert "production_value" not in json.dumps(evidence)
    assert evidence["sources"] == sorted(R1_SOURCES)
    assert (
        emit_fact(
            {"derived": "invented"},
            evidence["sources"],
            dict.fromkeys(R1_SOURCES, "open"),
            (),
        )
        is None
    )
    no_match = restaurant_evidence([production], production, D(100), R1_SOURCES)
    assert no_match["matches"] == []
    assert no_match["proposed_table"] == "sec_hr_ind"
    assert no_match["revenue_display"] is False
    with pytest.raises(ValueError, match="all hotels"):
        restaurant_evidence([], production, D(100), frozenset({"sec_hr_ind"}))
    with pytest.raises(ValueError, match="unrecorded"):
        restaurant_evidence(
            [replace(revenue, source="other")], production, D(100), R1_SOURCES
        )


def test_wage_means_every_shared_year_with_discrepancies_preserved() -> None:
    tables = {
        "wage_occ": {
            "2020": {"a": (D(3), D(10)), "b": (D(1), D(30))},
            "2023": {"a": (D(4), D(20))},
            "2025": {"a": (D(9), D(40))},
        },
        "wage_act": {"2020": {"x": (D(4), D(12))}, "2023": {"x": (D(4), D(18))}},
    }
    assert wage_evidence(tables, ["2020", "2023"])["years"] == [
        {
            "year": "2020",
            "wage_occ_workers": "4",
            "wage_act_workers": "4",
            "wage_occ_mean": "15",
            "wage_act_mean": "12",
            "equal_workers": True,
        },
        {
            "year": "2023",
            "wage_occ_workers": "4",
            "wage_act_workers": "4",
            "wage_occ_mean": "20",
            "wage_act_mean": "18",
            "equal_workers": True,
        },
    ]
    report = wage_evidence(tables, ["2020", "2023"])
    assert report["item"] == "R2"
    assert report["sources"] == ["wage_act", "wage_occ"]
    assert report["status"] == "reconciled: tables differ, occupation table used"
    tables["wage_act"]["2023"]["x"] = (D(5), D(18))
    assert wage_evidence(tables, ["2020", "2023"])["years"][1]["equal_workers"] is False
    with pytest.raises(ValueError, match="shared years"):
        wage_evidence(tables, ["2020"])
    with pytest.raises(ValueError, match="identities"):
        wage_evidence({"wrong": tables["wage_occ"]}, [])


def test_reconciliation_dependencies_are_complete() -> None:
    from eii_custodian.publicdata.series.reconcile import R2_SOURCES

    assert R1_SOURCES == {"sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"}
    assert R2_SOURCES == {"wage_occ", "wage_act"}


def test_missing_resolution_explicitly_returns_false(tmp_path: Path) -> None:
    assert (
        Resolution(
            tmp_path / "absent.md", tmp_path / "absent.json", frozenset()
        ).approved()
        is False
    )


@pytest.mark.parametrize(
    "workers,mean,status",
    [
        (4, "17.50", "reconciled: means equal, occupation table used"),
        (4, "18", "reconciled: tables differ, occupation table used"),
        (5, "17.5", "open: worker totals differ"),
    ],
)
def test_wage_status_describes_observed_means_and_totals(workers, mean, status):
    tables = {
        "wage_occ": {"2020": {"a": (D(4), D("17.5"))}},
        "wage_act": {"2020": {"a": (D(workers), D(mean))}},
    }
    assert wage_evidence(tables, ["2020"])["status"] == status
