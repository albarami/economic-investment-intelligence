"""One inner-refusal plant per Part-B D row, through its actual outer boundary."""

import json
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from hypothesis import given
from hypothesis import strategies as st
from product.tests.public_http_support import Client
from product.tests.test_public_playbook import catalogue

from eii_core.calc.facts import NoData
from eii_core.reasons import reason
from eii_product.api import layers, playbooks, public_layers, release, results
from eii_product.assistant.catalogue import load
from eii_product.ledger.local import LocalLedger
from eii_product.register_file import RegisterRefusal
from eii_product.store.protocol import StoreRefusal
from eii_product.tools import (
    make_area,
    public_context_tools,
    resolve,
    routing,
    sector_facts,
)

RELEASE = "ab" * 32
STORE = SimpleNamespace(release_id=RELEASE)


def api_code(response):
    return json.loads(response.body)["error"]["message_key"]


def layer_failure(row):
    if row == "D19":

        def read(month):
            raise ValueError("metric_unbound")

        router = layers.build_layer_router(None, public_readers={"public_places": read})
        path = "/api/layers/public_places"
    else:
        router = layers.build_layer_router(
            "INVENTED", rows_reader=Mock(side_effect=RegisterRefusal("path_refused"))
        )
        path = "/api/layers/fc_firms_per_tower"
    app = FastAPI()
    app.include_router(router)
    response = Client(app).get(path)
    assert response.status_code == 500
    return response.json()["error"]["message_key"]


def playbook_failure(row, tmp_path, fault=None, expected_status=None):
    app = FastAPI()
    with closing(LocalLedger(tmp_path / "ledger.sqlite")) as ledger:
        app.include_router(playbooks.build_router(STORE, ledger, catalogue()))
        target = "load_playbook" if row == "D37" else "execute"
        fault = fault or (
            ValueError("unknown_question")
            if row == "D37"
            else StoreRefusal("STORE_UNAVAILABLE")
        )
        with patch.object(playbooks, target, side_effect=fault):
            response = Client(app).post(
                "/api/playbooks/site_check",
                json={
                    "activity": "INVENTED",
                    "lang": "en",
                    "pin": {"lat": 1, "lon": 1},
                },
            )
    assert response.status_code == (expected_status or (404 if row == "D37" else 503))
    return response.json()["error"]["message_key"]


def layer_withheld(row):
    ctx = public_layers.LayerRead(STORE, "company_points")
    with patch.object(public_layers, "chain", side_effect=ValueError("source_missing")):
        if row == "D23":
            body = public_layers.company_points(ctx)
        else:
            assert (
                ctx.fact(
                    "pub_place",
                    "place_listing",
                    "INVENTED",
                    "published_text",
                    "published",
                    "place:INVENTED",
                )
                is None
            )
            body = ctx.response([])
    assert body["facts"] == []
    return body["payload"]["withheld"][0]["reason_key"]


def lineage_reader(store, ambiguous):
    original = public_context_tools.read
    lines = original(store, "public_lineage_for_table", table_name="pub_place")
    changed = (
        [
            *lines,
            *({**line, "lineage_id": line["lineage_id"] + "_other"} for line in lines),
        ]
        if ambiguous
        else []
    )

    def read(source, name, **params):
        return (
            changed
            if name == "public_lineage_for_table"
            else original(source, name, **params)
        )

    return read


def card_area(store):
    from eii_product.api.area_context import AreaContextFactory

    context = AreaContextFactory(store.release_id, None).for_playbook("site_check")
    area = make_area.make_area(
        store,
        {"latitude": 1, "longitude": 1, "mode": "distance", "cutoff": 500},
        context,
    )
    assert area.status == "OK"
    return context, area.payload["area_id"]


def context_failure(row):
    from product.tests.test_tools_http import CardStore

    store = CardStore()
    if row == "D25":
        with patch.object(
            public_context_tools, "read", side_effect=lineage_reader(store, True)
        ):
            with pytest.raises(ValueError) as caught:
                public_context_tools.chain(store, "pub_place")
        return reason(caught.value)
    context, area_id = card_area(store)
    month = public_context_tools.read(store, "layer_night_lights_months")[0]["period"]
    with patch.object(
        public_context_tools, "read_night_lights", return_value=NoData("missing_input")
    ):
        result = public_context_tools.run_card(
            store, "night_lights", {"area_id": area_id, "month_key": month}, context
        )
    assert result.status == "NO_DATA" and not result.facts
    return result.reason


def sector_failure(row):
    from product.tests.sector_fixture import norm_rows, release_store, with_lineage
    from product.tests.test_tools_http import CardStore

    from eii_core.facts import Fact

    if row == "D45":
        store = CardStore()
        ctx = sector_facts.Context(
            store,
            sector_facts.Inputs(
                activity="INVENTED", topic="unit_economics", geography="national"
            ),
        )
        fact = Fact.model_validate(
            public_layers.read_layer(store, "public_places")["facts"][0]
        )
        ctx.chains[fact.lineage_ref] = (
            store.tables["fact_lineage"],
            store.tables["source_registry"],
        )
        ctx.block("unit_economics", [fact.model_copy(update={"value": None})])
    else:
        with release_store(with_lineage(norm_rows())) as store:
            ctx = sector_facts.Context(
                store,
                sector_facts.Inputs(
                    activity="SYN-restaurant",
                    topic="unit_economics",
                    geography="national",
                ),
            )
            with patch.object(ctx, "measure", side_effect=ValueError("source_missing")):
                sector_facts._norms(ctx)
    return ctx.blocks[0]["reason_key"]


def api_plant(row, tmp_path):
    if row in {"D18", "D47"}:
        fault = ValueError("chain_refused" if row == "D18" else "row_citation_missing")
        if row == "D18":
            return api_code(results.error_response(fault))
        with closing(LocalLedger(tmp_path / "ledger.sqlite")) as ledger:
            return api_code(
                results.respond(
                    lambda: results.PublicResult("night_lights", "OK", RELEASE),
                    ledger=ledger,
                    engine="embedded",
                    arguments={},
                    prepare=Mock(side_effect=fault),
                )
            )
    if row in {"D19", "D20"}:
        return layer_failure(row)
    if row == "D21":
        from eii_product.register_file import _year

        with pytest.raises(RegisterRefusal) as caught:
            _year("INVENTED")
        return reason(caught.value)
    if row in {"D22", "D23"}:
        return layer_withheld(row)
    if row == "D24":
        with patch.object(
            public_layers, "read_layer", side_effect=ValueError("metric_unbound")
        ):
            with pytest.raises(ValueError) as caught:
                public_layers.public_point_snapshot(STORE)
        return api_code(results.error_response(caught.value))
    if row in {"D25", "D26"}:
        return context_failure(row)
    if row == "D27":
        with patch.object(
            release, "check_release", side_effect=ValueError("digest_mismatch")
        ):
            with pytest.raises(ValueError) as caught:
                release.MountedRelease(STORE, Path("INVENTED"))
        return reason(caught.value)
    if row == "D28":
        from eii_product.api.map_modes import refuse

        response = refuse("offline")
        assert response.status_code == 404
        return api_code(response)
    if row == "D29":
        from eii_product.api import map_modes

        app = FastAPI()
        app.include_router(
            map_modes.build_router(
                lambda: "INVENTED-key",
                lambda: False,
                Mock(side_effect=TimeoutError("INVENTED private text")),
                tmp_path / "count",
            )
        )
        with (
            patch.object(
                map_modes, "map_setting", return_value="https://tiles.invalid"
            ),
            patch.object(map_modes, "satellite_credit", return_value="INVENTED-credit"),
        ):
            response = Client(app).get("/api/imagery/tiles/0/0/0")
        assert response.status_code == 404
        assert "x-eii-error-code" not in response.headers
        return response.json()["error"]["message_key"]
    if row == "D30":
        from eii_product.api.frontend import build_router

        app = FastAPI()
        app.include_router(build_router(tmp_path, tmp_path))
        response = Client(app).get("/fonts/INVENTED/0-255.pbf")
        assert response.status_code == 404
        return response.json()["error"]["message_key"]
    return tool_plant(row, tmp_path)


def tool_plant(row, tmp_path):
    if row == "D31":
        from product.tests.test_released_imagery import released_fixture

        from eii_product.api.gis_imagery import ReleasedImagery

        folder, identity = released_fixture(tmp_path)
        imagery = ReleasedImagery(folder, identity)
        key = next(iter(imagery.tiles))
        imagery.tiles[key].pop("object_sha256")
        date, level, line, column = key.split("/")
        with pytest.raises(ValueError) as caught:
            imagery.tile(date, int(level), int(line), int(column))
        return reason(caught.value)
    if row in {"D37", "D38"}:
        return playbook_failure(row, tmp_path)
    if row == "D39":
        with patch.object(
            make_area,
            "_checked",
            side_effect=make_area.GeometryTextError(make_area.GEOMETRY_REFUSED),
        ):
            with pytest.raises(ValueError) as caught:
                make_area.make_area(
                    STORE,
                    {"latitude": 1, "longitude": 1, "mode": "distance", "cutoff": 500},
                    SimpleNamespace(
                        release_mode="public_only",
                        playbook_key="site_check",
                        hour_keys=frozenset(),
                        day_keys=frozenset(),
                    ),
                )
        return api_code(results.error_response(caught.value))
    if row == "D40":
        with patch.object(
            routing, "_coordinate_pairs", side_effect=ValueError("coordinate_range")
        ):
            with pytest.raises(routing.RoutingTilesUnavailable) as caught:
                routing.accepted_ring(())
        return reason(caught.value)
    if row == "D41":
        from eii_product.api.area_context import RoutingSource

        with (
            patch.object(Path, "is_file", return_value=True),
            patch(
                "eii_product.api.area_context._check_extract",
                side_effect=ValueError("geometry_refused"),
            ),
        ):
            with pytest.raises(Exception) as caught:
                RoutingSource.from_tiles(tmp_path / "tiles.tar", tmp_path)
        return reason(caught.value)
    if row in {"D42", "D43"}:
        context = Mock()
        if row == "D42":
            with patch.object(
                resolve,
                "_matched",
                side_effect=resolve.PayloadError("candidate_numeral"),
            ):
                outcome = resolve.resolve(
                    STORE, {"text": "INVENTED", "lang": "en", "kind": "place"}, context
                )
        else:
            context.index_for.side_effect = resolve.PayloadError("geometry_refused")
            outcome = resolve.resolve(
                STORE, {"text": "INVENTED", "lang": "en", "kind": "place"}, context
            )
        assert outcome.payload is None
        return outcome.reason
    if row in {"D44", "D45"}:
        return sector_failure(row)
    if row == "D46":
        with pytest.raises(ValueError) as caught:
            sector_facts.sector_facts(
                STORE,
                {"activity": "INVENTED", "topic": "unit_economics", "geography": "bad"},
            )
        return reason(caught.value)
    if row == "D53":
        path = tmp_path / "claims.yaml"
        path.write_text("claims: [")
        return load._read(path, "claims.yaml").rule_code
    raise AssertionError(row)


CASES = [
    ("D18", "chain_refused"),
    ("D19", "metric_unbound"),
    ("D20", "path_refused"),
    ("D21", "register_year_invalid"),
    ("D22", "source_missing"),
    ("D23", "source_missing"),
    ("D24", "metric_unbound"),
    ("D25", "lineage_ambiguous"),
    ("D26", "missing_input"),
    ("D27", "digest_mismatch"),
    ("D28", "offline"),
    ("D29", "operation_timeout"),
    ("D30", "font_stack_refused"),
    ("D31", "input_key_missing"),
    ("D37", "unknown_question"),
    ("D38", "STORE_UNAVAILABLE"),
    ("D39", "geometry text refused"),
    ("D40", "coordinate_range"),
    ("D41", "geometry_refused"),
    ("D42", "candidate_numeral"),
    ("D43", "geometry_refused"),
    ("D44", "source_missing"),
    ("D45", "fact_invalid"),
    ("D46", "geography"),
    ("D47", "row_citation_missing"),
    ("D53", "yaml_invalid"),
]


@pytest.mark.parametrize("row,expected", CASES, ids=[r for r, _ in CASES])
def test_part_b_inner_reason(row, expected, tmp_path):
    assert api_plant(row, tmp_path) == expected


@given(
    st.text().filter(
        lambda value: value not in {"chain_refused", "row_citation_missing"}
    )
)
def test_response_never_interpolates_unknown_text(value):
    from eii_core.reason_codes import CODES

    response = results.error_response(ValueError(value))
    error = json.loads(response.body)["error"]
    assert error["message_key"] in CODES or error["message_key"] == "internal"
    assert set(error) == {"code", "message_key", "error_id"}
