"""Exact API contracts on the imported, invented register stand-in."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from product.tests.test_fc_register_read import _copy
from product.tests.test_layers_fc_firms import FIXTURE, _get, _ok, _served

from eii_core.calc.firms_per_tower import TowerCount
from eii_product.api import layers
from eii_product.register_file import (
    RegisterBundle,
    RegisterRefusal,
    read_fc_register_rows,
)


def _document() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _bundle(tmp_path: Path) -> RegisterBundle:
    bundle = read_fc_register_rows(str(_copy(tmp_path)))
    assert bundle is not None
    return bundle


def _message(error: Exception, expected: str) -> None:
    assert str(error) == expected


@pytest.mark.parametrize(
    ("path", "query", "status", "body"),
    [
        ("invented_absent", b"", 404, {"error": {"code": "NOT_FOUND"}}),
        (
            "night_lights",
            b"",
            501,
            {"error": {"code": "NOT_IMPLEMENTED", "reason": "not_implemented"}},
        ),
        (
            "fc_firms_per_tower",
            b"invented=value",
            422,
            {"error": {"code": "INVALID_ARGUMENT"}},
        ),
        (
            "invented_absent",
            b"invented=value",
            422,
            {"error": {"code": "INVALID_ARGUMENT"}},
        ),
    ],
)
def test_refusal_contract(path: str, query: bytes, status: int, body: object) -> None:
    app = FastAPI()
    app.include_router(layers.build_layer_router(None))
    assert _get(app, "/api/layers/" + path, query=query) == (status, body)


@pytest.mark.parametrize("reason", ["read_refused", "row_shape", "path_refused"])
def test_reader_refusal_contract(reason: str) -> None:
    def refuse(setting: str) -> None:
        assert setting == "invented-setting"
        raise RegisterRefusal(reason)

    app = FastAPI()
    app.include_router(layers.build_layer_router("invented-setting", refuse))
    if reason == "read_refused":
        assert _get(app, "/api/layers/fc_firms_per_tower") == (
            200,
            {"status": "NO_DATA", "reason": "read_refused", "facts": []},
        )
    else:
        with pytest.raises(RegisterRefusal) as caught:
            _get(app, "/api/layers/fc_firms_per_tower")
        _message(caught.value, reason)


@pytest.mark.parametrize("kind", ["unset", "absent", "broken"])
def test_missing_input_contract(tmp_path: Path, kind: str) -> None:
    bundle = _bundle(tmp_path)
    broken = replace(bundle, lineage={**bundle.lineage, "transform": "invented-broken"})
    calls: list[str] = []

    def reader(setting: str) -> RegisterBundle | None:
        calls.append(setting)
        return broken if kind == "broken" else None

    app = FastAPI()
    app.include_router(
        layers.build_layer_router(
            None if kind == "unset" else "invented-setting", reader
        )
    )
    assert _get(app, "/api/layers/fc_firms_per_tower") == (
        200,
        {"status": "NO_DATA", "reason": "missing_input", "facts": []},
    )
    assert calls == ([] if kind == "unset" else ["invented-setting"])


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.5, None])
def test_coverage_refusals(value: Any) -> None:
    with pytest.raises(layers.CoverageKeyError) as caught:
        layers.seal_coverage({"tower_without_position": value})
    _message(caught.value, "reason_unknown")


def test_coverage_minimum_and_unknown_key() -> None:
    assert layers.seal_coverage({}) == {}
    assert layers.seal_coverage({"tower_without_position": 1}) == {
        "tower_without_position": 1
    }
    with pytest.raises(layers.CoverageKeyError) as caught:
        layers.seal_coverage({"invented_reason": 1})
    _message(caught.value, "reason_unknown")


def test_missing_towers_do_not_stop_later_counts(tmp_path: Path) -> None:
    parsed = _document()
    parsed["gazetteer"] = parsed["gazetteer"][2:]
    body = _served(tmp_path, parsed)
    assert body["coverage_report"] == {
        "counts": {
            "tower_without_position": 2,
            "zone_without_district": 1,
            "location_unresolved": 1,
            "tower_without_gazetteer_place": 3,
        }
    }
    assert [f["geography"]["public_code"] for f in body["facts"]] == [
        "place:INV-TOWER-GIMEL",
        "place:INV-TOWER-DALET",
        "district:INV-NORTH",
    ]
    assert [f["value"] for f in body["facts"]] == [1, 2, 1]


def test_missing_district_does_not_stop_later_district(tmp_path: Path) -> None:
    parsed = _document()
    district = parsed["rows"][7]
    missing = {
        **district,
        "district_key": "INV-MISSING",
        "registration_key": "INV-FC-MISSING",
        "row_id": "row-missing",
    }
    parsed["rows"] = [missing, district]
    body = _served(tmp_path, parsed)
    assert [f["geography"]["public_code"] for f in body["facts"]] == [
        "district:INV-NORTH"
    ]
    assert [f["value"] for f in body["facts"]] == [1]


def test_no_emitted_geography_has_empty_chain_and_legend(tmp_path: Path) -> None:
    parsed = _document()
    parsed["gazetteer"] = []
    parsed["districts"] = []
    body = _served(tmp_path, parsed)
    assert body["facts"] == []
    payload = body["payload"]
    assert payload["layers"] == [
        {
            "key": "fc_firms_per_tower",
            "visible": True,
            "source_chain_fact_id": "",
            "source_id": "src-fc-stand-in",
            "features": [],
        }
    ]
    assert payload["count_fact_ids"] == []
    assert payload["count_facts"] == []
    assert payload["fc_firms"] == {
        "direction": "higher",
        "companies": [],
        "coverage_note_keys": ["zone_without_district"],
        "breaks": [],
        "no_data": True,
    }
    assert body["coverage_report"]["counts"]["tower_without_gazetteer_place"] == 5


def test_missing_lower_break_keeps_later_break(tmp_path: Path) -> None:
    parsed = _document()
    parsed["gazetteer"] = [parsed["gazetteer"][0], parsed["gazetteer"][3]]
    body = _served(tmp_path, parsed)
    facts = body["facts"]
    assert [f["value"] for f in facts] == [2, 2, 1]
    assert body["payload"]["fc_firms"]["breaks"] == [
        {"class_id": "band_mid_low", "fact_id": facts[1]["fact_id"]}
    ]


def test_default_reader_and_exact_success_contract(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(layers.build_layer_router(str(_copy(tmp_path))))
    status, body = _get(app, "/api/layers/fc_firms_per_tower")
    assert status == 200
    assert set(body) == {"status", "facts", "coverage_report", "payload"}
    assert body["status"] == "ok"
    assert [f["value"] for f in body["facts"]] == [2, 1, 1, 2, 1]
    assert [f["geography"]["public_code"] for f in body["facts"]] == [
        "place:INV-TOWER-ALEPH",
        "place:INV-TOWER-BET",
        "place:INV-TOWER-GIMEL",
        "place:INV-TOWER-DALET",
        "district:INV-NORTH",
    ]
    for fact in body["facts"]:
        assert fact["reliability"] == "low_count"
        assert fact["label_en"] == "Firms registered here"
        assert fact["label_ar"] == "الشركات المسجلة هنا"
        assert fact["coverage_keys"] == []
        assert fact["caveat_keys"] == ["calculated"]
        assert fact["period"] == "2024"
        assert fact["lineage_ref"] == "lin_pub_register_company"
    payload = body["payload"]
    assert set(payload) == {
        "layers",
        "sources",
        "count_fact_ids",
        "count_facts",
        "fc_firms",
    }
    assert payload["sources"] == [
        {
            "sourceId": "src-fc-stand-in",
            "attribution": [
                {"kind": "plain", "text": "Sample financial centre register page"}
            ],
            "retrievalDate": "2026-01-15",
            "publisher": [{"kind": "plain", "text": "Sample Register Publisher"}],
            "datasetOrPage": "Sample financial centre register page",
            "licenceOrTerms": "Terms recorded for this sample",
        }
    ]
    assert len(payload["layers"]) == 1
    layer = payload["layers"][0]
    assert set(layer) == {
        "key",
        "visible",
        "source_chain_fact_id",
        "source_id",
        "features",
    }
    assert layer["key"] == "fc_firms_per_tower"
    assert layer["visible"] is True
    assert layer["source_id"] == "src-fc-stand-in"
    assert layer["source_chain_fact_id"] == body["facts"][0]["fact_id"]
    bound = body["facts"][3]["fact_id"]
    assert payload["count_fact_ids"] == [bound]
    assert payload["count_facts"] == [{"fact_id": bound, "year": "2024"}]
    assert set(payload["fc_firms"]) == {
        "direction",
        "companies",
        "coverage_note_keys",
        "breaks",
        "no_data",
    }
    assert payload["fc_firms"]["direction"] == "higher"
    assert payload["fc_firms"]["no_data"] is True
    assert payload["fc_firms"]["breaks"] == [
        {"class_id": "band_mid_low", "fact_id": bound}
    ]


def test_exact_tower_and_district_features(tmp_path: Path) -> None:
    body = _ok(tmp_path)
    facts = body["facts"]
    features = body["payload"]["layers"][0]["features"]
    assert features[0] == {
        "feature_id": "feat-tower-~49~nvented~20~~54~ower~20~~41~leph",
        "metric_key": "firms_per_tower",
        "provenance": "public",
        "subject": "place",
        "geometry_kind": "point",
        "class_id": "band_mid_low",
        "fact_id": facts[0]["fact_id"],
        "geography_code": "place:INV-TOWER-ALEPH",
        "place_key": "INV-TOWER-ALEPH",
        "words": {"name": "Invented Tower Aleph"},
        "position": [51.5, 25.3],
    }
    assert features[4] == {
        "feature_id": "feat-district-~49~~4e~~56~~2d~~4e~~4f~~52~~54~~48~",
        "metric_key": "firms_per_tower",
        "provenance": "public",
        "subject": "statistic",
        "geometry_kind": "fill",
        "class_id": "band_low",
        "fact_id": facts[4]["fact_id"],
        "geography_code": "district:INV-NORTH",
        "words": {"name": "Invented North District"},
        "ring": [[51.4, 25.2], [51.6, 25.2], [51.6, 25.4], [51.4, 25.2]],
    }


def test_exact_company_cards_and_order(tmp_path: Path) -> None:
    body = _ok(tmp_path)
    companies = body["payload"]["fc_firms"]["companies"]
    assert [(r["feature_id"], r["row_id"]) for r in companies] == [
        ("feat-tower-~49~nvented~20~~54~ower~20~~41~leph", "row-aleph-one"),
        ("feat-tower-~49~nvented~20~~54~ower~20~~41~leph", "row-aleph-two"),
        ("feat-tower-~49~nvented~20~~54~ower~20~~42~et", "row-bet-one"),
        ("feat-tower-~49~nvented~20~~54~ower~20~~47~imel", "row-gimel-one"),
        ("feat-tower-~49~nvented~20~~54~ower~20~~44~alet", "row-dalet-one"),
        ("feat-tower-~49~nvented~20~~54~ower~20~~44~alet", "row-dalet-two"),
    ]
    assert [r["fields"] for r in companies] == [
        [
            {"key": "trade_name", "text": name},
            {"key": "activity", "text": "Sample finance activity"},
        ]
        for name in [
            "Invented House Aleph",
            "Invented House Aleph Two",
            "Invented House Bet",
            "Invented House Gimel",
            "Invented House Dalet",
            "Invented House Dalet Two",
        ]
    ]
    assert all(set(row) == {"feature_id", "row_id", "fields"} for row in companies)


@pytest.mark.parametrize(
    ("status", "position"),
    [("agree", None), ("disagree", ("1.2", "3.4")), ("none", ("1.2", "3.4"))],
)
def test_position_requires_both_agreement_and_coordinates(
    tmp_path: Path, status: str, position: tuple[str, str] | None
) -> None:
    # The calculator normalises these pairs; direct construction exercises the
    # feature adapter's independent guard on its dataclass input.
    bundle = _bundle(tmp_path)
    tower = TowerCount("Invented Tower Aleph", 1, "band_low", position, status, ())
    feature = layers._tower_feature(
        tower,
        bundle.gazetteer["Invented Tower Aleph"],
        "invented-fact",
        "invented-feature",
    )
    assert "position" not in feature


def test_empty_rows_have_no_counts_or_notes(tmp_path: Path) -> None:
    # The file reader refuses empty rows in _rows; the adapter also accepts an
    # injected RegisterBundle whose row tuple is empty.
    body = layers._serve(replace(_bundle(tmp_path), rows=()))
    assert body["facts"] == []
    assert body["coverage_report"] == {"counts": {}}
    assert body["payload"]["fc_firms"] == {
        "direction": "higher",
        "companies": [],
        "coverage_note_keys": [],
        "breaks": [],
        "no_data": False,
    }


def test_retrieval_without_isoformat_is_empty(tmp_path: Path) -> None:
    # _source converts file dates to date objects. The Mapping-valued adapter
    # input also permits text, so exercise its explicit fallback directly.
    bundle = _bundle(tmp_path)
    body = layers._serve(
        replace(bundle, source={**bundle.source, "retrieved_on": "invented-date"})
    )
    assert body["payload"]["sources"][0]["retrievalDate"] == ""
