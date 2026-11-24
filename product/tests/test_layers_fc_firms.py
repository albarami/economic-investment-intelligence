"""The firms-per-tower route serves Public facts and refuses the rest."""

import asyncio
import json
from pathlib import Path

import pytest

from eii_core.facts import fact_id, validate_chain
from eii_product.api.app import create_app
from eii_product.api.layers import FC_CLASS_KEYS, CoverageKeyError, seal_coverage
from eii_product.register_file import read_fc_register_rows

FIXTURE = Path(__file__).parent / "fixtures" / "fc_register" / "stand_in_register.json"
_KEYS = (
    "INV-FC-ALEPH-ONE",
    "INV-FC-ALEPH-TWO",
    "INV-FC-BET-ONE",
    "INV-FC-GIMEL-ONE",
    "INV-FC-DALET-ONE",
    "INV-FC-DALET-TWO",
    "INV-FC-HE-ONE",
    "INV-FC-DISTRICT-ONE",
    "INV-FC-ZONE-FREE",
    "INV-FC-NOWHERE",
)


def _copy(tmp_path: Path) -> Path:
    dest = tmp_path / "stand_in_register.json"
    dest.write_bytes(FIXTURE.read_bytes())
    return dest


def _app(tmp_path: Path, path: Path) -> object:
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    return create_app(tiles, fc_setting_reader=lambda: str(path))


def _ok(tmp_path: Path) -> dict[str, object]:
    status, body = _get(
        _app(tmp_path, _copy(tmp_path)), "/api/layers/fc_firms_per_tower"
    )
    assert status == 200
    assert body["status"] == "ok"
    return body


def _features(body: dict[str, object]) -> list[dict[str, object]]:
    payload = body["payload"]
    assert isinstance(payload, dict)
    layers = payload["layers"]
    assert isinstance(layers, list)
    features = layers[0]["features"]
    assert isinstance(features, list)
    return features


def _named(features: list[dict[str, object]], name: str) -> dict[str, object]:
    found = [item for item in features if item["words"]["name"] == name]
    assert len(found) == 1
    return found[0]


def test_every_count_is_a_public_observed_fact_with_a_resolved_chain(
    tmp_path: Path,
) -> None:
    copy = _copy(tmp_path)
    _status, body = _get(_app(tmp_path, copy), "/api/layers/fc_firms_per_tower")
    bundle = read_fc_register_rows(str(copy))
    assert bundle is not None
    assert (
        validate_chain(
            str(bundle.lineage["lineage_id"]),
            [bundle.lineage],
            [bundle.source],
        )
        is None
    )
    facts = body["facts"]
    assert isinstance(facts, list) and facts
    assert len({fact["fact_id"] for fact in facts}) == len(facts)
    dumped = json.dumps(body)
    for key in _KEYS:
        assert key not in dumped
    for fact in facts:
        assert fact["provenance"] == "public"
        assert fact["evidence_status"] == "observed"
        assert fact["input_classes"] == ["public"]
        assert fact["unit"] == "count"
        assert fact["release_id"] == bundle.release_id
        assert (
            fact_id(
                release_id=bundle.release_id,
                metric_key="firms_per_tower",
                geography=fact["geography"],
                period=bundle.year,
                qualifiers={},
            )
            == fact["fact_id"]
        )
    district = _named(_features(body), "Invented North District")
    assert district["metric_key"] == "firms_per_tower"
    assert district["fact_id"]
    assert district["geometry_kind"] == "fill"
    assert district["subject"] == "statistic"


def test_a_planted_unresolved_lineage_is_not_emitted(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    parsed = json.loads(copy.read_text(encoding="utf-8"))
    parsed["lineage"]["transform"] = "not-a-transform"
    copy.write_text(json.dumps(parsed), encoding="utf-8")
    _status, body = _get(_app(tmp_path, copy), "/api/layers/fc_firms_per_tower")
    assert body["status"] == "NO_DATA"
    assert body["facts"] == []
    assert "payload" not in body


def test_split_kinds_on_this_layer_is_refused(tmp_path: Path) -> None:
    status, body = _get(
        _app(tmp_path, _copy(tmp_path)),
        "/api/layers/fc_firms_per_tower",
        query=b"split_kinds=age_band",
    )
    assert status == 422
    assert body["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.parametrize("plant", ("table", "method", "version", "both", "source"))
def test_a_chain_for_another_calculation_is_not_emitted(
    tmp_path: Path, plant: str
) -> None:
    copy = _copy(tmp_path)
    parsed = json.loads(copy.read_text(encoding="utf-8"))
    lineage = parsed["lineage"]
    if plant in {"table", "both"}:
        lineage["table_name"] = "pub_place"
        lineage["lineage_id"] = "lin_pub_place"
    if plant in {"method", "both"}:
        lineage["transform"] = "invented.method@v1"
    if plant == "version":
        lineage["transform"] = "eii_core.calc.firms_per_tower@invented"
    if plant == "source":
        lineage["source_id"] = "src-invented-other"
    copy.write_text(json.dumps(parsed), encoding="utf-8")
    status, body = _get(_app(tmp_path, copy), "/api/layers/fc_firms_per_tower")
    assert status == 200
    assert body == {"status": "NO_DATA", "reason": "missing_input", "facts": []}


def test_an_unknown_layer_key_is_not_found(tmp_path: Path) -> None:
    status, body = _get(_app(tmp_path, _copy(tmp_path)), "/api/layers/not_a_layer")
    assert status == 404
    assert body["error"]["code"] == "NOT_FOUND"


def test_an_unimplemented_closed_key_is_refused_with_its_fixed_reason(
    tmp_path: Path,
) -> None:
    status, body = _get(_app(tmp_path, _copy(tmp_path)), "/api/layers/night_lights")
    assert status == 501
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
    assert body["error"]["reason"] == "not_implemented"


def test_a_tower_whose_rows_all_carry_the_same_reviewed_position_is_served_with_it(
    tmp_path: Path,
) -> None:
    aleph = _named(_features(_ok(tmp_path)), "Invented Tower Aleph")
    assert aleph["position"] == [51.5, 25.3]
    assert aleph["metric_key"] == "firms_per_tower"
    assert aleph["fact_id"]


def test_a_tower_whose_rows_disagree_on_position_is_served_without_one_and_counted(
    tmp_path: Path,
) -> None:
    body = _ok(tmp_path)
    dalet = _named(_features(body), "Invented Tower Dalet")
    assert "position" not in dalet
    counts = body["coverage_report"]["counts"]
    assert counts["tower_without_position"] >= 1


def test_a_tower_whose_rows_carry_no_position_is_served_without_one_and_counted(
    tmp_path: Path,
) -> None:
    body = _ok(tmp_path)
    gimel = _named(_features(body), "Invented Tower Gimel")
    assert "position" not in gimel
    assert body["coverage_report"]["counts"]["tower_without_position"] >= 1


def test_no_position_is_invented_where_the_file_gives_none(tmp_path: Path) -> None:
    body = _ok(tmp_path)
    gimel = _named(_features(body), "Invented Tower Gimel")
    assert "position" not in gimel
    dumped = json.dumps(body)
    assert "51.8" not in dumped
    assert "25.8" not in dumped


def test_a_tower_name_that_resolves_to_no_gazetteer_place_emits_no_feature_and_is_counted(
    tmp_path: Path,
) -> None:
    body = _ok(tmp_path)
    names = [item["words"]["name"] for item in _features(body)]
    assert "Invented Tower He" not in names
    assert body["coverage_report"]["counts"]["tower_without_gazetteer_place"] == 1
    dumped = json.dumps(body)
    assert "Invented House He" not in dumped


def test_the_coverage_report_counts_each_reason_and_the_route_emits_only_ruled_keys(
    tmp_path: Path,
) -> None:
    body = _ok(tmp_path)
    counts = body["coverage_report"]["counts"]
    assert counts["zone_without_district"] == 1
    assert counts["location_unresolved"] == 1
    assert set(counts) <= {
        "zone_without_district",
        "location_unresolved",
        "tower_without_position",
        "tower_without_gazetteer_place",
    }
    notes = body["payload"]["fc_firms"]["coverage_note_keys"]
    assert notes == ["zone_without_district"]
    assert "location_unresolved" not in notes
    try:
        seal_coverage({"not_a_ruled_reason": 1})
    except CoverageKeyError as exc:
        assert str(exc) == "reason_unknown"
    else:
        raise AssertionError("unknown reason was sealed")


def test_a_district_only_count_is_a_selectable_fill_with_no_point(
    tmp_path: Path,
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["rows"] = [
        row for row in parsed["rows"] if row["row_id"] == "row-district-one"
    ]
    body = _served(tmp_path, parsed)
    features = _features(body)
    assert len(features) == 1
    feature = features[0]
    assert feature["geometry_kind"] == "fill"
    assert feature["class_id"] == "district_count"
    assert feature["class_id"] in FC_CLASS_KEYS
    assert feature["metric_key"] == "firms_per_tower"
    assert feature["fact_id"]
    assert "position" not in feature
    assert body["payload"]["fc_firms"]["breaks"] == []
    facts = body["facts"]
    assert isinstance(facts, list) and len(facts) == 1
    assert facts[0]["value"] == 1
    assert facts[0]["unit"] == "count"
    assert facts[0]["provenance"] == "public"


def test_a_band_does_not_borrow_a_lower_count_when_its_boundary_is_omitted(
    tmp_path: Path,
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    letters = "abcdefghi"
    names = (
        ("One", 1),
        ("Two", 2),
        ("Three", 3),
        ("Four", 4),
        ("Five", 5),
        ("Six", 9),
    )
    rows: list[dict[str, object]] = []
    gazetteer: list[dict[str, str]] = []
    for name, count in names:
        if name != "Six":
            gazetteer.append(
                {
                    "tower_or_building": f"Invented Tower {name}",
                    "place_code": f"place:INV-TOWER-{name.upper()}",
                }
            )
        for index in range(count):
            mark = letters[index]
            rows.append(
                {
                    "registration_key": f"INV-FC-{name.upper()}-{mark.upper()}",
                    "row_id": f"row-{name.lower()}-{mark}",
                    "tower_or_building": f"Invented Tower {name}",
                    "position_lon": "51.5",
                    "position_lat": "25.3",
                    "district_key": None,
                    "district_free_zone": False,
                    "card": {
                        "trade_name": f"Invented House {name}",
                        "activity": "Sample finance activity",
                    },
                }
            )
    parsed["rows"] = rows
    parsed["gazetteer"] = gazetteer
    parsed["districts"] = []
    body = _served(tmp_path, parsed)
    names_drawn = [item["words"]["name"] for item in _features(body)]
    assert "Invented Tower Five" in names_drawn
    assert "Invented Tower Six" not in names_drawn
    facts = body["facts"]
    assert isinstance(facts, list)
    by_id = {fact["fact_id"]: fact for fact in facts}
    five = [
        fact
        for fact in facts
        if fact["geography"]["public_code"] == "place:INV-TOWER-FIVE"
    ]
    assert len(five) == 1
    breaks = body["payload"]["fc_firms"]["breaks"]
    bound = {chip["fact_id"] for chip in breaks}
    assert five[0]["fact_id"] not in bound
    assert "band_high" not in {chip["class_id"] for chip in breaks}
    one = [
        fact
        for fact in facts
        if fact["geography"]["public_code"] == "place:INV-TOWER-ONE"
    ]
    assert len(one) == 1
    assert one[0]["fact_id"] in bound
    assert one[0]["value"] == 1
    assert all(by_id[chip["fact_id"]]["value"] != 5 for chip in breaks)


def test_a_band_stays_bound_to_its_tower_when_a_district_key_has_the_same_text(
    tmp_path: Path,
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for row in parsed["rows"]:
        if row["tower_or_building"] in ("Invented Tower Aleph", "Invented Tower Dalet"):
            row["tower_or_building"] = "INV-NORTH"
    parsed["gazetteer"] = [
        {"tower_or_building": "INV-NORTH", "place_code": "place:INV-TOWER-ALEPH"},
        *(
            item
            for item in parsed["gazetteer"]
            if item["tower_or_building"]
            not in ("Invented Tower Aleph", "Invented Tower Dalet")
        ),
    ]
    body = _served(tmp_path, parsed)
    facts = body["facts"]
    assert isinstance(facts, list)
    by_id = {fact["fact_id"]: fact for fact in facts}
    breaks = body["payload"]["fc_firms"]["breaks"]
    top = [chip for chip in breaks if chip["class_id"] == "band_mid_low"]
    assert len(top) == 1
    bound = by_id[top[0]["fact_id"]]
    assert bound["geography"]["public_code"] == "place:INV-TOWER-ALEPH"
    assert bound["value"] == 4
    assert all(
        not by_id[chip["fact_id"]]["geography"]["public_code"].startswith("district:")
        for chip in breaks
    )


_FILL_RING = [["51.4", "25.2"], ["51.6", "25.2"], ["51.6", "25.4"], ["51.4", "25.2"]]


def _tower_row(
    *,
    registration_key: str,
    row_id: str,
    tower: str,
    district_key: str | None = None,
) -> dict[str, object]:
    return {
        "registration_key": registration_key,
        "row_id": row_id,
        "tower_or_building": tower,
        "position_lon": "51.5",
        "position_lat": "25.3",
        "district_key": district_key,
        "district_free_zone": False,
        "card": {
            "trade_name": f"Invented House {row_id}",
            "activity": "Sample finance activity",
        },
    }


def _district_row(
    *, registration_key: str, row_id: str, district_key: str
) -> dict[str, object]:
    return {
        "registration_key": registration_key,
        "row_id": row_id,
        "tower_or_building": None,
        "position_lon": None,
        "position_lat": None,
        "district_key": district_key,
        "district_free_zone": False,
        "card": {
            "trade_name": f"Invented House {row_id}",
            "activity": "Sample finance activity",
        },
    }


def test_a_tower_named_like_a_district_key_keeps_its_own_feature_id(
    tmp_path: Path,
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["gazetteer"] = [
        {
            "tower_or_building": "district INV-NORTH",
            "place_code": "place:INV-TOWER-ALEPH",
        }
    ]
    parsed["districts"] = [
        {
            "district_key": "INV-NORTH",
            "name": "Invented North District",
            "ring": _FILL_RING,
        }
    ]
    parsed["rows"] = [
        _tower_row(
            registration_key="INV-FC-ALEPH-ONE",
            row_id="row-aleph-one",
            tower="district INV-NORTH",
            district_key="INV-NORTH",
        ),
        _district_row(
            registration_key="INV-FC-DISTRICT-ONE",
            row_id="row-district-one",
            district_key="INV-NORTH",
        ),
    ]
    body = _served(tmp_path, parsed)
    features = _features(body)
    tower_feature = _named(features, "district INV-NORTH")
    district_feature = _named(features, "Invented North District")
    assert tower_feature["feature_id"] != district_feature["feature_id"]
    assert str(tower_feature["feature_id"]).startswith("feat-tower-")
    assert str(district_feature["feature_id"]).startswith("feat-district-")
    companies = body["payload"]["fc_firms"]["companies"]
    assert isinstance(companies, list) and companies
    assert {row["feature_id"] for row in companies} == {tower_feature["feature_id"]}
    assert {row["row_id"] for row in companies} == {"row-aleph-one"}


def test_tower_names_differing_only_in_case_get_distinct_feature_ids(
    tmp_path: Path,
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["gazetteer"] = [
        {"tower_or_building": "Tower A", "place_code": "place:INV-TOWER-ALEPH"},
        {"tower_or_building": "tower-a", "place_code": "place:INV-TOWER-BET"},
    ]
    parsed["districts"] = []
    parsed["rows"] = [
        _tower_row(
            registration_key="INV-FC-ALEPH-ONE",
            row_id="row-aleph-one",
            tower="Tower A",
        ),
        _tower_row(
            registration_key="INV-FC-BET-ONE", row_id="row-bet-one", tower="tower-a"
        ),
    ]
    body = _served(tmp_path, parsed)
    features = _features(body)
    upper = _named(features, "Tower A")
    lower = _named(features, "tower-a")
    assert upper["feature_id"] != lower["feature_id"]


def test_district_keys_differing_only_in_case_get_distinct_feature_ids(
    tmp_path: Path,
) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["gazetteer"] = []
    parsed["districts"] = [
        {
            "district_key": "Inv-North",
            "name": "Invented North District",
            "ring": _FILL_RING,
        },
        {
            "district_key": "INV-NORTH",
            "name": "Invented South District",
            "ring": _FILL_RING,
        },
    ]
    parsed["rows"] = [
        _district_row(
            registration_key="INV-FC-DISTRICT-ONE",
            row_id="row-district-one",
            district_key="Inv-North",
        ),
        _district_row(
            registration_key="INV-FC-NOWHERE",
            row_id="row-nowhere",
            district_key="INV-NORTH",
        ),
    ]
    body = _served(tmp_path, parsed)
    features = _features(body)
    mixed = _named(features, "Invented North District")
    upper = _named(features, "Invented South District")
    assert mixed["feature_id"] != upper["feature_id"]


def test_every_feature_id_in_one_served_body_is_unique(tmp_path: Path) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for row in parsed["rows"]:
        if row["tower_or_building"] == "Invented Tower Aleph":
            row["tower_or_building"] = "district INV-NORTH"
    parsed["gazetteer"] = [
        {
            "tower_or_building": "district INV-NORTH",
            "place_code": "place:INV-TOWER-ALEPH",
        },
        *(
            item
            for item in parsed["gazetteer"]
            if item["tower_or_building"] != "Invented Tower Aleph"
        ),
    ]
    body = _served(tmp_path, parsed)
    ids = [item["feature_id"] for item in _features(body)]
    assert len(ids) > 1
    assert len(set(ids)) == len(ids)


def test_tower_name_digit_boundaries_stay_in_feature_id(tmp_path: Path) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["gazetteer"] = [
        {
            "tower_or_building": "invented tower 09az",
            "place_code": "place:INV-TOWER-ALEPH",
        }
    ]
    parsed["districts"] = []
    parsed["rows"] = [
        _tower_row(
            registration_key="INV-FC-ALEPH-ONE",
            row_id="row-aleph-one",
            tower="invented tower 09az",
        )
    ]
    body = _served(tmp_path, parsed)
    features = _features(body)
    assert len(features) == 1
    assert features[0]["feature_id"] == "feat-tower-invented~20~tower~20~09az"


def test_upper_case_and_underscore_are_escaped_in_feature_id(tmp_path: Path) -> None:
    parsed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed["gazetteer"] = [
        {
            "tower_or_building": "Invented YZ_tower",
            "place_code": "place:INV-TOWER-ALEPH",
        }
    ]
    parsed["districts"] = []
    parsed["rows"] = [
        _tower_row(
            registration_key="INV-FC-ALEPH-ONE",
            row_id="row-aleph-one",
            tower="Invented YZ_tower",
        )
    ]
    body = _served(tmp_path, parsed)
    features = _features(body)
    assert len(features) == 1
    assert features[0]["feature_id"] == "feat-tower-~49~nvented~20~~59~~5a~~5f~tower"


@pytest.mark.parametrize("value", ("1", 1.5, True))
def test_a_coverage_value_of_the_wrong_type_is_refused(value: object) -> None:
    with pytest.raises(CoverageKeyError, match="reason_unknown"):
        seal_coverage({"zone_without_district": value})


@pytest.mark.parametrize("value", (0, -1))
def test_a_coverage_value_below_one_is_refused(value: int) -> None:
    with pytest.raises(CoverageKeyError, match="reason_unknown"):
        seal_coverage({"zone_without_district": value})


def _served(tmp_path: Path, parsed: dict[str, object]) -> dict[str, object]:
    dest = tmp_path / "stand_in_register.json"
    dest.write_text(json.dumps(parsed), encoding="utf-8")
    status, body = _get(_app(tmp_path, dest), "/api/layers/fc_firms_per_tower")
    assert status == 200
    assert body["status"] == "ok"
    return body


def _get(
    app: object, path: str, *, query: bytes = b""
) -> tuple[int, dict[str, object]]:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
    }
    asyncio.run(app(scope, receive, send))
    start = next(item for item in sent if item["type"] == "http.response.start")
    raw = b"".join(
        bytes(item["body"]) if isinstance(item.get("body"), bytes) else b""
        for item in sent
        if item["type"] == "http.response.body"
    )
    status = start["status"]
    assert isinstance(status, int)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)
    return status, parsed
