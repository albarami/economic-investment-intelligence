"""Offline selected releases, comparison lineage and tampering plants."""

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from eii_custodian.publicdata import trade_reconciliation as tr


def selection():
    return tr.Selection.from_mapping(
        {
            "confirmed": True,
            "partners": ["invented-partner", "invented-absent"],
            "years": [2020, 2021],
            "flows": ["import"],
            "scopes": ["invented-product"],
            "inputs": [
                {
                    "source_id": "cus_imp_2019",
                    "role": "portal",
                    "selected_hash": "a" * 64,
                },
                {
                    "source_id": "cus_imp_2025",
                    "role": "portal",
                    "selected_hash": "b" * 64,
                },
            ],
            "bindings": [
                {
                    "source_id": "cus_imp_2019",
                    "role": "portal",
                    "row_key": "0",
                    "partner": "invented-partner",
                    "flow": "import",
                    "year": 2020,
                    "product_scope": "invented-product",
                    "coverage_key": "invented-coverage",
                    "currency": "QAR",
                    "scale": "1",
                    "hs_revision": "unknown",
                    "classification": "unknown",
                    "evidence_sha256": "c" * 64,
                }
            ],
            "causes": [],
            "obstacles": [],
        }
    )


def portal(cache, source_id, selected):
    rows = (
        [
            {
                "period": "2020",
                "tariff_code": "invented-product",
                "origin_iso3": "invented-origin",
                "value_qar": "12.50",
                "valuation_basis": "not stated by the source",
            }
        ]
        if source_id == "cus_imp_2019"
        else []
    )
    return rows, {
        "sha256": selected,
        "publisher": "invented-publisher",
        "source_modified": "invented-version",
        "licence_basis": "owner_decision",
        "retrieved_utc": "2026-11-16T00:00:00Z",
    }


def test_selection_closed():
    p = asdict(selection())
    for plant in (
        {**p, "unknown": True},
        {**p, "years": []},
        {
            **p,
            "inputs": [
                {
                    "source_id": "fdi_projects",
                    "role": "portal",
                    "selected_hash": "a" * 64,
                }
            ],
        },
        {**p, "confirmed": False},
    ):
        with pytest.raises(ValueError):
            tr.Selection.from_mapping(plant)


def test_release_roundtrip_all_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    p = selection()
    digest = tr.build_reconciliation(tmp_path, p)
    release = tr.read_reconciliation(tmp_path, digest)
    assert len(release.inputs) == 1
    assert len(release.comparisons) == 4
    assert all(r.gap is None for r in release.comparisons)
    assert {(r.partner, r.year) for r in release.comparisons} == {
        (p, y) for p in selection().partners for y in selection().years
    }
    assert all(r.unknown_cause for r in release.comparisons)
    assert release.inputs[0].figure.value == "12.50"
    assert release.manifest["commit_allowed"] is False


@pytest.mark.parametrize("plant", ["output", "input", "binding", "cause"])
def test_reconciliation_tamper(tmp_path, monkeypatch, plant):
    monkeypatch.setattr(tr, "read_portal", portal)
    digest = tr.build_reconciliation(tmp_path, selection())
    directory = tmp_path / "trade_reconciliation"
    manifest = json.loads((directory / f"{digest}.manifest.json").read_text())
    if plant == "input":
        monkeypatch.setattr(tr, "read_portal", lambda *args: ([], {}))
    elif plant == "binding":
        manifest["selection"]["bindings"][0]["partner"] = "invented-other"
    elif plant == "cause":
        manifest["selection"]["causes"] = [{"code": "valuation", "evidence_sha256": ""}]
    else:
        data = json.loads((directory / f"{manifest['output_sha256']}.json").read_text())
        data["inputs"][0]["figure"]["value"] = "99"
        raw = json.dumps(data).encode()
        changed = hashlib.sha256(raw).hexdigest()
        (directory / f"{changed}.json").write_bytes(raw)
        manifest["output_sha256"] = changed
    raw = json.dumps(manifest).encode()
    selected = hashlib.sha256(raw).hexdigest()
    (directory / f"{selected}.manifest.json").write_bytes(raw)
    with pytest.raises(ValueError):
        tr.read_reconciliation(tmp_path, selected)


def test_unbound_row_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    with pytest.raises(ValueError, match="binding"):
        tr.build_reconciliation(tmp_path, replace(selection(), bindings=()))


def test_evidenced_causes_and_owner_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "read_portal", portal)
    data = asdict(selection())
    data["causes"] = [
        {
            "left_source": "cus_imp_2019",
            "right_source": "cus_imp_2025",
            "partner": "invented-partner",
            "year": 2020,
            "code": "publication_timing",
            "evidence_sha256": "d" * 64,
        }
    ]
    data["obstacles"] = [
        {
            "source_id": "cus_imp_2025",
            "reason": "free_plan_gap",
            "evidence_sha256": "e" * 64,
            "price_amount": None,
            "price_currency": None,
        }
    ]
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p)
    release = tr.read_reconciliation(tmp_path, digest)
    report = release.manifest["owner_report"]
    assert report["obstacles"] == data["obstacles"]
    assert report["causes"] == data["causes"]
    assert all(r.unknown_cause for r in release.comparisons)
    assert report["unknown_cause"] is True
    assert report["coverage_gaps"]


@pytest.mark.parametrize(
    "plant", ["missing_evidence", "invented_reason", "secret_price"]
)
def test_cause_obstacle_evidence_required(plant):
    data = asdict(selection())
    data["obstacles"] = [
        {
            "source_id": "cus_imp_2025",
            "reason": "registration",
            "evidence_sha256": "e" * 64,
            "price_amount": None,
            "price_currency": None,
        }
    ]
    if plant == "missing_evidence":
        data["obstacles"][0]["evidence_sha256"] = ""
    elif plant == "invented_reason":
        data["obstacles"][0]["reason"] = "invented-key-like-secret"
    else:
        data["obstacles"][0]["price_amount"] = "invented-key-like-secret"
    with pytest.raises(ValueError) as exc:
        tr.Selection.from_mapping(data)
    assert "invented-key-like-secret" not in str(exc.value)


def test_native_baci_direction_and_units(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from eii_custodian.publicdata.baci.contracts import Country, Trade

    data = asdict(selection())
    data["inputs"] = list(data["inputs"])
    data["inputs"][0] = {
        "source_id": "cepii_baci",
        "role": "baci",
        "selected_hash": "a" * 64,
    }
    data["bindings"][0].update(
        source_id="cepii_baci",
        role="baci",
        currency="invented-currency",
        hs_revision="invented-revision",
        classification="HS",
        target_code="invented-target",
        partner_code="invented-other",
    )
    item = Trade(
        "invented-version",
        "invented-revision",
        2020,
        "invented-other",
        "invented-target",
        "invented-product",
        "12.50",
        None,
        "invented-unit",
        "invented-mass",
        "invented-currency",
        "invented-basis",
        "source_missing",
        "cepii_baci",
        "f" * 64,
    )
    countries = tuple(
        Country("cepii_baci", "invented-version", c, "invented-name", None)
        for c in ("invented-target", "invented-other")
    )
    monkeypatch.setattr(tr, "read_portal", portal)
    monkeypatch.setattr(
        tr.baci_contracts,
        "read_selected",
        lambda *args: SimpleNamespace(
            trade=(item,), country=countries, source_registry={}
        ),
    )
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p)
    release = tr.read_reconciliation(tmp_path, digest)
    assert release.inputs[0].figure.unit == "invented-unit"
    data["bindings"][0]["flow"] = "export"
    data["flows"] = ["export"]
    with pytest.raises(ValueError, match="direction"):
        tr.build_reconciliation(tmp_path, tr.Selection.from_mapping(data))


def test_native_comtrade_retains_unit_not_api_price(tmp_path, monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    from eii_custodian.publicdata.comtrade.parse import TradeRow

    data = asdict(selection())
    data["inputs"] = list(data["inputs"])
    data["inputs"][0] = {
        "source_id": "un_comtrade",
        "role": "reporter",
        "selected_hash": "a" * 64,
        "publisher": "invented-publisher",
        "licence_basis": "owner_decision",
        "terms_sha256": "b" * 64,
    }
    data["bindings"][0].update(
        source_id="un_comtrade",
        role="reporter",
        currency="invented-currency",
        hs_revision="invented-revision",
        classification="invented-class",
        target_code="invented-target",
        partner_code="invented-other",
        native_flow="invented-import",
    )
    item = TradeRow(
        "un_comtrade",
        "reporter",
        "invented-target",
        "invented-other",
        "invented-second",
        "A",
        "2020",
        "invented-import",
        "invented-class",
        "invented-revision",
        "invented-product",
        2,
        "invented-customs",
        "invented-mode",
        "invented-basis",
        "invented-measure",
        Decimal("12.50"),
        "invented-unit",
        "invented-flag",
        "invented-version",
        "f" * 64,
    )
    calls = []

    def assemble(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(rows=(item,), price_currency="invented-api-currency")

    monkeypatch.setattr(tr, "assemble", assemble)
    monkeypatch.setattr(tr, "read_portal", portal)
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p, comtrade_policy=object())
    release = tr.read_reconciliation(tmp_path, digest, comtrade_policy=object())
    assert calls
    assert release.inputs[0].figure.currency == "invented-currency"
    assert release.inputs[0].figure.unit == "invented-unit"
    data["bindings"][0]["partner_code"] = "invented-wrong"
    with pytest.raises(ValueError, match="direction"):
        tr.build_reconciliation(
            tmp_path, tr.Selection.from_mapping(data), comtrade_policy=object()
        )


def test_pending_selection_and_dispatch(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.build import run_build

    assert tr.load_selection() is None
    monkeypatch.setattr(tr, "read_portal", portal)
    outcome = run_build(
        (),
        lambda _: pytest.fail("no network"),
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        reconciliation_selection=selection(),
    )
    assert outcome.failure is None
    assert "trade_reconciliation" in outcome.manifests
    assert tr.read_reconciliation(
        tmp_path, outcome.manifests["trade_reconciliation"]
    ).inputs


def test_unavailable_input_has_evidence_and_no_reader(tmp_path, monkeypatch):
    data = asdict(selection())
    data["inputs"][1]["selected_hash"] = ""
    data["obstacles"] = [
        {
            "source_id": "cus_imp_2025",
            "reason": "free_plan_gap",
            "evidence_sha256": "e" * 64,
            "price_amount": None,
            "price_currency": None,
        }
    ]

    def available(cache, source, selected):
        assert source != "cus_imp_2025"
        return portal(cache, source, selected)

    monkeypatch.setattr(tr, "read_portal", available)
    p = tr.Selection.from_mapping(data)
    digest = tr.build_reconciliation(tmp_path, p)
    result = tr.read_reconciliation(tmp_path, digest)
    assert len(result.comparisons) == 4
    assert result.manifest["owner_report"]["obstacles"][0]["reason"] == "free_plan_gap"
    data["obstacles"] = []
    with pytest.raises(ValueError):
        tr.Selection.from_mapping(data)
