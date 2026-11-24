"""Actual loaded S3 API controls and independent wire-corruption plants."""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Match the offline eval tests under the runner's safe-path Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.question_lab.api import execute_case, frames
from evals.question_lab.cases import load_cases

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def service(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Any, str]]:
    # Same real loader/embedded path as the command, no public cache or live DB.
    builder = import_module("product.tests.public_opening_server").build_fixture_app
    app, store, ledger = builder(tmp_path_factory.mktemp("lab-api"), ROOT / "web/dist")
    try:
        yield app, store.release_id
    finally:
        ledger.close()
        store.close()


class CorruptingClient:
    def __init__(self, app: Any, plant: str) -> None:
        self.base = import_module("product.tests.public_http_support").Client(app)
        self.plant = plant

    def refusal(self, result: Any) -> Any:
        body = copy.deepcopy(result.json())
        if self.plant == "refusal_facts":
            body["facts"] = [{"fact_id": "INVENTED-forbidden-refusal-fact"}]
        return SimpleNamespace(
            status_code=503 if self.plant == "refusal_status" else result.status_code,
            json=lambda: body,
        )

    def other_area(self) -> str:
        return str(
            self.base.post(
                "/api/tools/make_area",
                json={"latitude": 1.5, "longitude": 1.5, "mode": "walk", "cutoff": 15},
            ).json()["payload"]["area_id"]
        )

    def post(self, path: str, *, json: dict[str, Any]) -> Any:
        result = self.base.post(path, json=json)
        if self.plant.startswith("refusal_"):
            return self.refusal(result)
        if path == "/api/tools/make_area" and self.plant in {
            "area_identity",
            "outline",
            "geocode_outline",
        }:
            body = copy.deepcopy(result.json())
            if self.plant == "area_identity":
                body["payload"]["area_id"] = self.other_area()
            elif self.plant == "outline" or "place_key" in json:
                body["payload"]["outline"]["coordinates"][0][0][0] += 0.001
            return SimpleNamespace(status_code=result.status_code, json=lambda: body)
        if path == "/api/tools/resolve" and self.plant == "geocode_key":
            body = copy.deepcopy(result.json())
            body["payload"]["candidates"][0]["key"] = "district:INVENTED-null"
            return SimpleNamespace(status_code=result.status_code, json=lambda: body)
        if path == "/api/tools/night_lights" and self.plant in {
            "figure",
            "identity",
            "caveat",
            "evidence_status",
            "fact_property",
            "fact_missing",
        }:
            body = copy.deepcopy(result.json())
            if self.plant == "figure":
                body["facts"][0]["value"] = 99
            elif self.plant == "caveat":
                body["facts"][0]["caveat_keys"].remove("night_lights_not_activity")
            elif self.plant == "evidence_status":
                body["facts"][0]["evidence_status"] = "inferred"
            elif self.plant == "fact_property":
                body["facts"][0]["prose"] = "INVENTED-model-text"
            elif self.plant == "fact_missing":
                body["facts"] = []
            else:
                other = self.base.post(
                    "/api/tools/make_area",
                    json={
                        "latitude": 1.5,
                        "longitude": 1.5,
                        "mode": "walk",
                        "cutoff": 15,
                    },
                ).json()["payload"]["area_id"]
                valid = self.base.post(
                    "/api/tools/night_lights",
                    json={"area_id": other, "month_key": "2026-03"},
                ).json()["facts"][0]
                body["facts"][0]["fact_id"] = valid["fact_id"]
            return SimpleNamespace(status_code=result.status_code, json=lambda: body)
        return result

    def get(self, path: str) -> Any:
        result = self.base.get(path)
        if self.plant.startswith("refusal_"):
            return self.refusal(result)
        if path.endswith("/lineage") and self.plant == "chain":
            body = copy.deepcopy(result.json())
            body["lineage"]["methodVersion"] = ""
            return SimpleNamespace(status_code=result.status_code, json=lambda: body)
        if path.endswith("/events") and self.plant in {
            "map",
            "accounting",
            "model",
            "stream_error",
            "receipt_after_narrative",
        }:
            changed = []
            events = frames(result.text)
            if self.plant == "stream_error":
                events.append(("error", {"code": "INVENTED-error"}))
            elif self.plant == "receipt_after_narrative":
                receipt = next(event for event in events if event[0] == "receipt")
                events.remove(receipt)
                events.insert(
                    next(i for i, event in enumerate(events) if event[0] == "narrative")
                    + 1,
                    receipt,
                )
            for kind, data in events:
                if (
                    self.plant == "map"
                    and kind == "stage"
                    and data.get("directive") == "fly"
                ):
                    other = self.base.post(
                        "/api/tools/make_area",
                        json={
                            "latitude": 1.5,
                            "longitude": 1.5,
                            "mode": "walk",
                            "cutoff": 15,
                        },
                    ).json()["payload"]["area_id"]
                    data["target"] = {"area_id": other}
                if self.plant == "accounting" and kind == "receipt":
                    data["Checked before display"]["Sources"] = False
                if self.plant == "model" and kind == "status":
                    data["writer"] = "model"
                changed.append(f"event: {kind}\r\ndata: {json.dumps(data)}\r\n\r\n")
            return SimpleNamespace(
                status_code=result.status_code, text="".join(changed)
            )
        return result


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize(
    "plant,diagnostic",
    [
        ("control", None),
        ("figure", "accuracy:value"),
        ("identity", "accuracy:fact_id"),
        ("chain", "accuracy:chain"),
        ("map", "map:directive_target"),
        ("accounting", "accuracy:accounting"),
        ("model", "accuracy:writer"),
        ("geocode_control", None),
        ("geocode_key", "map:geocoding_target"),
        ("area_identity", "map:area_identity"),
        ("outline", "map:outline"),
        ("geocode_outline", "map:geocoding_outline"),
        ("caveat", "accuracy:caveat"),
        ("evidence_status", "accuracy:public_only"),
        ("fact_property", "accuracy:property"),
        ("fact_missing", "accuracy:fact_missing"),
        ("stream_error", "accuracy:stream"),
        ("receipt_after_narrative", "accuracy:accounting_order"),
    ],
)
def test_actual_loaded_path_controls_and_plants(
    service: tuple[Any, str], language: str, plant: str, diagnostic: str | None
) -> None:
    app, release_id = service
    if plant.startswith("geocode"):
        case = next(
            case
            for case in load_cases(ROOT)
            if case.family == "map" and case.angles["place"] == "garden"
        )
    else:
        case = next(
            case
            for case in load_cases(ROOT)
            if case.family == "flagship" and case.mode == "walk"
        )
    result = execute_case(CorruptingClient(app, plant), release_id, case, language)
    if diagnostic is None:
        assert result["problems"] == []
    else:
        assert diagnostic in result["problems"]
    if plant in {"map", "geocode_key"}:
        assert result["judgements"]["map"] == "failed"
        assert result["judgements"]["accuracy"] == "passed:typed_api_only"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize(
    "kind", ["missing_layer", "unknown_tool", "invalid_property", "unlisted_venue"]
)
@pytest.mark.parametrize("plant", ["control", "refusal_facts", "refusal_status"])
def test_refusal_controls_and_plants(
    service: tuple[Any, str], language: str, kind: str, plant: str
) -> None:
    app, release_id = service
    case = next(case for case in load_cases(ROOT) if case.refusal == kind)
    result = execute_case(CorruptingClient(app, plant), release_id, case, language)
    if plant == "control":
        assert result["problems"] == []
        assert result["judgements"]["accuracy"] == "passed:typed_refusal_only"
    else:
        assert "accuracy:refusal" in result["problems"]
        assert result["judgements"]["accuracy"] == "failed"
