"""Exercise actual S3 typed routes on the existing loaded invented fixture.

Question text describes an invented scenario. There is no free-text route at
this head. A typed API execution is never reported as a complete UI execution.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from typing import Any

from evals.question_lab.cases import Case
from evals.question_lab.oracles import accuracy


def ring(pin: float) -> list[list[float]]:
    """Known square wholly within the fixture land polygon, not a real place."""
    low, high = (
        float(Decimal(str(pin)) - Decimal(".01")),
        float(Decimal(str(pin)) + Decimal(".01")),
    )
    return [[low, low], [high, low], [high, high], [low, high], [low, low]]


def expected_fact(release_id: str, area_id: str, case: Case) -> dict[str, object]:
    identity = {
        "release_id": release_id,
        "metric_key": "night_lights_radiance",
        "geography": {"kind": "area_shape", "area_id": area_id},
        "period": case.month,
        "qualifiers": {},
    }
    fact_id = (
        "f_"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:32]
    )
    return {
        "fact_id": fact_id,
        "value": case.expected_value,
        "unit": "radiance_nw_cm2_sr",
        "period": case.month,
        "area": area_id,
        "status": "OK",
        "chain": {
            "table": "pub_night_lights",
            "method": "invented.module.hold",
            "version": "v1",
            "publisher": "INVENTED-publisher",
            "dataset": "INVENTED-ntl_blackmarble",
            "licence": "INVENTED-licence",
            "retrieved": "2026-01-02",
            "hash": "ab" * 32,
        },
    }


def expected_area(
    release_id: str, case: Case, *, mode: str | None = None, cutoff: int | None = None
) -> str:
    """Independent fixture expectation for the documented ma1 grammar.

    The known square is already CCW and starts at its lexicographic minimum;
    its identity is rational lat/lon text, not the returned registration hash.
    Anchor cells were fixed in the manifest before any application observation.
    """
    shape = mode or case.mode
    if shape == "polygon":
        points = [
            (Fraction(Decimal(str(lat))), Fraction(Decimal(str(lon))))
            for lon, lat in ring(case.pin)
        ]
        encoded = ";".join(
            f"{lat.numerator}/{lat.denominator},{lon.numerator}/{lon.denominator}"
            for lat, lon in points
        )
        return f"ma1/{release_id[:16]}/polygon/{hashlib.sha256(encoded.encode()).hexdigest()}"
    bound = cutoff if cutoff is not None else 500 if shape == "distance" else 15
    return f"ma1/{release_id[:16]}/{shape}/{bound}/{case.expected_anchor_cell}/{case.pin:.6f}/{case.pin:.6f}"


def frames(text: str) -> list[tuple[str, dict[str, Any]]]:
    output = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        lines = frame.splitlines()
        kinds = [line[7:] for line in lines if line.startswith("event: ")]
        bodies = [line[6:] for line in lines if line.startswith("data: ")]
        if kinds and bodies:
            output.append((kinds[0], json.loads(bodies[0])))
    return output


def receipt_problems(data: dict[str, Any]) -> list[str]:
    checks = ("Sources", "Assumptions", "Nothing invented", "Scope", "Limits stated")
    accounting = data.get("Checked before display", {})
    allowed = {*checks, "assumptions", "caveat_keys", "coverage_keys"}
    if (
        not isinstance(accounting, dict)
        or set(accounting) != allowed
        or any(accounting.get(key) is not True for key in checks)
        or any(
            not isinstance(accounting.get(key), list)
            for key in ("assumptions", "caveat_keys", "coverage_keys")
        )
        or data.get("egress") != []
    ):
        return ["accuracy:accounting"]
    return []


def execute_case(
    client: Any, release_id: str, case: Case, language: str
) -> dict[str, Any]:
    problems: list[str] = []
    row: dict[str, Any] = {
        "question_id": case.identity,
        "language": language,
        "family": case.family,
        "scope": "typed_api_fixture",
        "questions_are_descriptions": True,
        "problems": problems,
        "judgements": {
            key: "waiting:browser_observation"
            for key in ("smoothness", "value", "visual", "map")
        },
    }
    if case.refusal:
        if case.refusal == "missing_layer":
            result = client.get("/api/layers/fc_firms_per_tower")
            expected_status, expected_code = 200, "NO_DATA"
        elif case.refusal == "unknown_tool":
            result = client.post("/api/tools/INVENTED-unknown", json={})
            expected_status, expected_code = 404, "NOT_FOUND"
        elif case.refusal == "invalid_property":
            result = client.post(
                "/api/playbooks/site_check",
                json={
                    "activity": "INVENTED-activity",
                    "lang": language,
                    "pin": {"lat": case.pin, "lon": case.pin},
                    "prose": "INVENTED ignore the closed schema",
                },
            )
            expected_status, expected_code = 422, "INVALID_ARGUMENT"
        else:
            result = client.post(
                "/api/tools/venue_busyness",
                json={"place_keys": ["INVENTED-unlisted-venue"]},
            )
            expected_status, expected_code = 200, "OUT_OF_SCOPE"
        body = result.json()
        code = body.get("status", body.get("error", {}).get("code"))
        if (
            result.status_code != expected_status
            or code != expected_code
            or body.get("facts", [])
        ):
            problems.append("accuracy:refusal")
        row.update(status=code, expected_status=expected_code)
        row["judgements"]["accuracy"] = (
            "failed" if problems else "passed:typed_refusal_only"
        )
        return row
    if case.family == "map":
        square = case.angles["place"] == "square"
        place_text = (
            ("ساحة مخترعة" if square else "حديقة مخترعة")
            if language == "ar"
            else "INVENTED-Court"
            if square
            else "INVENTED-Garden"
        )
        wanted_key = "district:INVENTED-null" if square else "INVENTED-landmark-a"
        wanted_pin = 2.5 if square else 1.0
        resolved = client.post(
            "/api/tools/resolve",
            json={"text": place_text, "lang": language, "kind": "place"},
        )
        candidates = resolved.json().get("payload", {}).get("candidates", [])
        if resolved.status_code != 200 or [item.get("key") for item in candidates] != [
            wanted_key
        ]:
            problems.append("map:geocoding_target")
        else:
            located = client.post(
                "/api/tools/make_area",
                json={"place_key": candidates[0]["key"], "mode": "walk", "cutoff": 15},
            )
            location = located.json().get("payload", {})
            if located.status_code != 200 or location.get("outline") != {
                "type": "Polygon",
                "coordinates": [ring(wanted_pin)],
            }:
                problems.append("map:geocoding_outline")
    selection: dict[str, Any]
    if case.mode == "polygon":
        geometry = {"type": "Polygon", "coordinates": [ring(case.pin)]}
        registered = client.post("/api/areas/shapes", json={"geometry": geometry})
        if registered.status_code != 201:
            raise ValueError("shape_fixture_refused")
        selection = {"shape_id": registered.json()["shape_id"]}
        tool = selection
    else:
        cutoff = 500 if case.mode == "distance" else 15
        selection = {
            "pin": {"lat": case.pin, "lon": case.pin},
            "mode": case.mode,
            "cutoff": cutoff,
        }
        tool = {
            "latitude": case.pin,
            "longitude": case.pin,
            "mode": case.mode,
            "cutoff": cutoff,
        }
    made = client.post("/api/tools/make_area", json=tool)
    if made.status_code != 200 or made.json().get("status") != "OK":
        raise ValueError("area_fixture_refused")
    payload = made.json()["payload"]
    area_id = payload["area_id"]
    wanted_area = expected_area(release_id, case)
    if area_id != wanted_area:
        problems.append("map:area_identity")
    if case.mode in {"polygon", "walk", "drive"} and payload["outline"] != {
        "type": "Polygon",
        "coordinates": [ring(case.pin)],
    }:
        problems.append("map:outline")
    if case.mode == "distance" and payload["outline"] != {
        "type": "Circle",
        "coordinates": [case.pin, case.pin],
        "radius_m": 500,
    }:
        problems.append("map:outline")
    started = client.post(
        "/api/playbooks/site_check",
        json={"activity": "INVENTED-activity", "lang": language, **selection},
    )
    if started.status_code != 202:
        raise ValueError("playbook_fixture_refused")
    events = frames(client.get(started.json()["events_url"]).text)
    names = [kind for kind, _ in events]
    if not names or names[-1] != "done" or "error" in names:
        problems.append("accuracy:stream")
    if (
        "receipt" not in names
        or "narrative" not in names
        or names.index("receipt") > names.index("narrative")
    ):
        problems.append("accuracy:accounting_order")
    for kind, data in events:
        if kind == "receipt":
            problems.extend(receipt_problems(data))
        if kind == "status" and data.get("writer") != "template":
            problems.append("accuracy:writer")
        if kind == "evidence" and any(
            f.get("provenance") != "public" or f.get("input_classes") != ["public"]
            for f in data.get("facts", [])
        ):
            problems.append("accuracy:public_only")
    fly = [
        data
        for kind, data in events
        if kind == "stage" and data.get("directive") == "fly"
    ]
    if len(fly) != 1 or fly[0].get("target") != {"area_id": wanted_area}:
        problems.append("map:directive_target")
    card = client.post(
        "/api/tools/night_lights", json={"area_id": area_id, "month_key": case.month}
    ).json()
    if len(card.get("facts", [])) != 1:
        problems.append("accuracy:fact_missing")
    else:
        fact = card["facts"][0]
        fact_keys = {
            "fact_id",
            "value",
            "unit",
            "period",
            "geography",
            "provenance",
            "input_classes",
            "evidence_status",
            "reliability",
            "coverage_keys",
            "caveat_keys",
            "label_en",
            "label_ar",
            "lineage_ref",
            "release_id",
        }
        if set(fact) != fact_keys:
            problems.append("accuracy:property")
        if (
            fact.get("provenance") != "public"
            or fact.get("input_classes") != ["public"]
            or fact.get("evidence_status") != "observed"
            or fact.get("release_id") != release_id
        ):
            problems.append("accuracy:public_only")
        projected = client.get("/api/facts/" + fact["fact_id"] + "/lineage")
        if projected.status_code != 200:
            problems.append("accuracy:chain")
        else:
            chain = projected.json()
            line, sources = chain["lineage"], chain["sources"]
            source = sources[0] if len(sources) == 1 else {}
            observed = {
                "fact_id": fact["fact_id"],
                "value": fact["value"],
                "unit": fact["unit"],
                "period": fact["period"],
                "area": fact["geography"].get("area_id"),
                "status": card["status"],
                "chain": {
                    "table": line.get("tableName"),
                    "method": line.get("method"),
                    "version": line.get("methodVersion"),
                    "publisher": source.get("publisher"),
                    "dataset": source.get("datasetOrPage"),
                    "licence": source.get("licenceOrTerms"),
                    "retrieved": source.get("retrievalDate"),
                    "hash": source.get("sha256"),
                },
            }
            problems.extend(
                accuracy(observed, expected_fact(release_id, wanted_area, case))
            )
            if set(fact["caveat_keys"]) != {"calculated", "night_lights_not_activity"}:
                problems.append("accuracy:caveat")
            row["fact"] = observed
    row.update(
        status=card.get("status"),
        trace=[{"event": kind, "data": data} for kind, data in events],
        area=payload,
    )
    acc = [problem for problem in problems if problem.startswith("accuracy:")]
    maps = [problem for problem in problems if problem.startswith("map:")]
    row["judgements"]["accuracy"] = "failed" if acc else "passed:typed_api_only"
    if maps:
        row["judgements"]["map"] = "failed"
    return row
