"""Specific negative cases and hostile leaf replacements for the reason boundary."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from product.tests.test_fc_register_read import FIXTURE

from eii_core.reason_codes import CODES
from eii_core.reasons import reason
from eii_product.api import playbooks, public_layers, results
from eii_product.register_file import RegisterRefusal, _read_path
from eii_product.tools import public_context_tools, resolve, routing, sector_facts


@pytest.mark.parametrize(
    "fault,expected",
    [
        (ValueError("source_missing"), "source_missing"),
        (ValueError("INVENTED path SELECT"), "operation_failed"),
        (KeyError("INVENTED private"), "input_key_missing"),
        (TimeoutError("INVENTED private"), "operation_timeout"),
    ],
)
def test_closed_body_and_log(fault, expected, capsys):
    response = results.error_response(fault)
    error = json.loads(response.body)["error"]
    log = json.loads(capsys.readouterr().out)
    assert error["message_key"] == log["error_code"] == expected
    assert log["error_id"] == error["error_id"]
    assert "INVENTED" not in json.dumps(error) + json.dumps(log)


@pytest.mark.parametrize("method", ["accepted_ring", "_isochrone", "network_distance"])
@pytest.mark.parametrize(
    "fault,expected",
    [
        (ValueError("coordinate_range"), "coordinate_range"),
        (OSError("INVENTED private"), "operation_os_error"),
        (KeyError("INVENTED private"), "input_key_missing"),
    ],
)
def test_routing_handlers(method, fault, expected, tmp_path):
    if method == "accepted_ring" and isinstance(fault, OSError):
        with patch.object(routing, "_coordinate_pairs", side_effect=fault):
            with pytest.raises(OSError, match=r"^INVENTED private$"):
                routing.accepted_ring(())
        return
    actor = Mock()
    actor.isochrone.side_effect = actor.matrix.side_effect = fault
    with (
        patch("valhalla.Actor", return_value=actor),
        patch.object(routing, "_ready", return_value=True),
        patch.object(routing, "_coordinate_pairs", side_effect=fault),
    ):
        with pytest.raises(
            routing.RoutingTilesUnavailable, match=r"^" + expected + "$"
        ) as caught:
            if method == "accepted_ring":
                routing.accepted_ring(())
            elif method == "_isochrone":
                routing._isochrone(tmp_path, "walk", 5, 1, 1)
            else:
                routing.network_distance(tmp_path, "walk", (1, 1), (1, 1))
    assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize(
    "refs,expected", [([], "missing_input"), (["a", "b"], "lineage_ambiguous")]
)
def test_lineage_count(refs, expected):
    from product.tests.test_reason_part_b import lineage_reader
    from product.tests.test_tools_http import CardStore

    store = CardStore()
    with patch.object(
        public_context_tools, "read", side_effect=lineage_reader(store, bool(refs))
    ):
        with pytest.raises(ValueError, match="^" + expected + "$"):
            public_context_tools.chain(store, "pub_place")


def test_lineage_validation_keeps_specific_failure():
    from product.tests.test_tools_http import CardStore

    with patch.object(
        public_context_tools, "validate_chain", return_value="source_missing"
    ):
        with pytest.raises(ValueError, match=r"^source_missing$"):
            public_context_tools.chain(CardStore(), "pub_place")


@pytest.mark.parametrize("fault", ["source_missing", "chain_refused"])
def test_layer_chain_withheld(fault):
    from product.tests.test_tools_http import CardStore

    store = CardStore()
    ctx = public_layers.LayerRead(store, "public_places")
    bound = public_context_tools.chain(store, "pub_place")
    with (
        patch.object(public_layers, "chain", return_value=bound),
        patch.object(public_layers, "validate_chain", return_value=fault),
    ):
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
    assert ctx.response([])["payload"]["withheld"] == [{"reason_key": fault}]


def test_layer_unknown_source_withheld():
    from product.tests.test_tools_http import CardStore

    store = CardStore()
    ctx = public_layers.LayerRead(store, "public_places")
    bound = public_context_tools.chain(store, "pub_place")
    with (
        patch.object(public_layers, "chain", return_value=bound),
        patch.object(public_layers, "validate_chain", return_value=None),
    ):
        assert (
            ctx.fact(
                "pub_place",
                "place_listing",
                "INVENTED",
                "published_text",
                "published",
                "place:INVENTED",
                source_id="INVENTED-unknown",
            )
            is None
        )
    assert ctx.response([])["payload"]["withheld"] == [{"reason_key": "source_missing"}]


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (*path, key))
    elif isinstance(value, list):
        for key, child in enumerate(value):
            yield from leaves(child, (*path, key))
    else:
        yield path


@pytest.mark.parametrize("hostile", [{"toString": None}, 7, None, []])
def test_every_register_leaf_has_closed_outcome(tmp_path, hostile):
    clean = json.loads(FIXTURE.read_text())
    for path in leaves(clean):
        body = deepcopy(clean)
        parent = body
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = hostile
        target = tmp_path / "INVENTED.json"
        target.write_text(json.dumps(body))
        try:
            _read_path(str(target), hashlib.sha256(target.read_bytes()).hexdigest())
        except RegisterRefusal as error:
            assert error.reason in CODES
            assert error.reason.startswith("register_")
            assert str(target) not in str(error)


@given(st.sampled_from(sorted(CODES)))
def test_api_projection_preserves_every_closed_code(code):
    response = results.error_response(ValueError(code))
    assert response.status_code == 500
    assert json.loads(response.body)["error"]["message_key"] == code


@pytest.mark.parametrize("kind", ["place", "activity"])
@pytest.mark.parametrize("value", [None, {"toString": None}, 7, []])
def test_candidate_payload_leaf_refusal(value, kind):
    valid = {
        "kind": "place",
        "key": "INVENTED",
        "label_en": "INVENTED",
        "label_ar": "INVENTED",
        "source": "gazetteer",
        "match": "exact",
    }
    if kind == "activity":
        valid.update(
            kind="activity",
            source="activity_spine",
            commerce_code="INVENTED",
            isic_class="INVENTED",
            place_category="INVENTED",
            not_mappable=False,
        )
    for key in valid:
        with pytest.raises(resolve.PayloadError, match=r"^INVALID_ARGUMENT$"):
            resolve.require_candidate({**valid, key: value})


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("activity", "bad input", "activity"),
        ("geography", "bad", "geography"),
        (
            "scenario_inputs",
            {"monthly_rent": 1, "seats": 1, "average_bill": 1},
            "scenario",
        ),
    ],
)
def test_sector_field_diagnostics(key, value, expected):
    args = {
        "activity": "INVENTED",
        "topic": "licences",
        "geography": "national",
        key: value,
    }
    with pytest.raises(ValueError, match=r"^" + expected + "$"):
        sector_facts.sector_facts(None, args)


def test_explicit_message_key_does_not_admit_exception_text(capsys):
    response = playbooks.refusal(
        500, "INTERNAL", message_key="INVENTED private path SELECT"
    )
    assert json.loads(response.body)["error"]["message_key"] == "operation_failed"
    assert "INVENTED" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "field,value",
    [
        ("activity", None),
        ("topic", "INVENTED"),
        ("geography", []),
        ("scenario_inputs", {"toString": None}),
    ],
)
def test_schema_field_reason(field, value):
    args = {
        "activity": "INVENTED",
        "topic": "unit_economics",
        "geography": "national",
        field: value,
    }
    with pytest.raises(ValueError, match="^" + field + "$"):
        sector_facts.sector_facts(None, args)


@pytest.mark.parametrize("status", ["INVALID_ARGUMENT", "NO_DATA"])
def test_resolver_adapter_retains_reason(status):
    from eii_product.api import tools

    outcome = resolve.ResolveResult(
        "resolve", status, "candidate_numeral", "ab" * 32, None
    )
    with patch.object(tools, "resolve", return_value=outcome):
        if status == "INVALID_ARGUMENT":
            with pytest.raises(ValueError, match=r"^candidate_numeral$"):
                tools._resolved(SimpleNamespace(release_id="ab" * 32), {}, None)
        else:
            assert (
                tools._resolved(SimpleNamespace(release_id="ab" * 32), {}, None).reason
                == "candidate_numeral"
            )


@pytest.mark.parametrize(
    "stack,span,expected",
    [
        ("INVENTED", "0-255.pbf", "font_stack_refused"),
        ("Noto Sans Medium", "bad", "font_span_refused"),
        ("Noto Sans Medium", "1-256.pbf", "font_range_refused"),
    ],
)
def test_font_reasons(tmp_path, stack, span, expected):
    from eii_product.api.frontend import _font_path

    with pytest.raises(ValueError, match="^" + expected + "$"):
        _font_path(tmp_path, stack, span)


def test_asset_escape_and_missing(tmp_path):
    from eii_product.api.frontend import _inside

    with pytest.raises(ValueError, match=r"^asset_path_refused$"):
        _inside(tmp_path, "../INVENTED")
    with pytest.raises(ValueError, match=r"^asset_missing$"):
        _inside(tmp_path, "INVENTED")


def test_snapshot_refuses_withheld_points():
    def withheld(store, key):
        ctx = public_layers.LayerRead(SimpleNamespace(release_id="ab" * 32), key)
        ctx.withheld.append({"reason_key": "source_missing"})
        return ctx.response([])

    with patch.object(public_layers, "read_layer", side_effect=withheld):
        with pytest.raises(ValueError, match=r"^source_missing$"):
            public_layers.public_point_snapshot(None)


def test_population_withheld_reason():
    from product.tests.test_reason_part_b import card_area
    from product.tests.test_tools_http import CardStore

    from eii_core.calc.facts import NoData

    store = CardStore()
    context, area_id = card_area(store)
    bands = public_context_tools.read(store, "population_age_sex_bands")
    with patch.object(
        public_context_tools,
        "read_population_age_sex",
        return_value=NoData("missing_input"),
    ):
        result = public_context_tools.run_card(
            store, "population_age_sex", {"area_id": area_id, "split": "none"}, context
        )
    assert result.reason == "missing_input"
    assert result.payload == {
        "entries": [{"status": "NO_DATA", "reason_key": "missing_input"} for _ in bands]
    }
    assert result.facts == ()


def test_catalogue_read_parser_exception_is_distinct(tmp_path):
    import yaml

    from eii_product.assistant.catalogue import load

    path = tmp_path / "claims.yaml"
    path.write_text("{}")
    with patch.object(
        yaml, "safe_load", side_effect=yaml.YAMLError("INVENTED private")
    ):
        assert load._read(path, "claims.yaml").rule_code == "yaml_invalid"


def test_satellite_metadata_transport_reason():
    from eii_product.imagery_provider.address import AddressFailure
    from eii_product.photoreal_tiles.proxy import satellite_credit

    with pytest.raises(AddressFailure, match=r"^operation_timeout$"):
        satellite_credit(
            Mock(side_effect=TimeoutError("INVENTED private")),
            "https://tiles.invalid",
            "INVENTED-key",
        )


def test_imagery_tile_http_reason():
    from fastapi import FastAPI
    from product.tests.public_http_support import Client

    from eii_product.api.gis_imagery import imagery_router

    app = FastAPI()
    app.include_router(
        imagery_router(
            SimpleNamespace(tile=Mock(side_effect=ValueError("input_key_missing")))
        )
    )
    response = Client(app).get("/api/gis-imagery/2026-03/0/0/0")
    assert response.status_code == 422
    assert response.json()["error"]["message_key"] == "input_key_missing"


def test_invalid_outcome_keeps_reason_and_writes_no_ledger(tmp_path):
    from contextlib import closing

    from eii_product.ledger.local import LocalLedger

    with closing(LocalLedger(tmp_path / "ledger.sqlite")) as ledger:
        response = results.respond(
            lambda: results.PublicResult(
                "resolve", "INVALID_ARGUMENT", "ab" * 32, reason="candidate_numeral"
            ),
            ledger=ledger,
            engine="embedded",
            arguments={},
        )
        assert response.status_code == 422
        assert json.loads(response.body)["error"]["message_key"] == "candidate_numeral"
        assert ledger.rows() == []


def test_font_symlink_is_path_refused(tmp_path):
    from eii_product.api.frontend import _font_path

    fonts = tmp_path / "fonts"
    fonts.mkdir()
    target = tmp_path / "INVENTED"
    target.mkdir()
    (target / "0-255.pbf").write_bytes(b"INVENTED")
    (fonts / "Noto Sans Medium").symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match=r"^asset_path_refused$"):
        _font_path(fonts, "Noto Sans Medium", "0-255.pbf")


@pytest.mark.parametrize("value", ["INVENTED", 1.5, True])
def test_bad_release_coordinate_is_withheld(value):
    with pytest.raises(resolve.PayloadError, match=r"^coordinate_invalid$"):
        resolve._coordinate(value)


def test_missing_release_keys_and_geometry_are_withheld():
    from eii_product.store.protocol import QueryResult

    with pytest.raises(resolve.PayloadError, match=r"^candidate_key_missing$"):
        resolve._places(QueryResult(("place_key",), ((None,),)))
    with pytest.raises(resolve.PayloadError, match=r"^candidate_code_missing$"):
        resolve._activities(
            ({"node_type": "activity", "node_id": "INVENTED", "code": None},), ()
        )
    with pytest.raises(resolve.PayloadError, match=r"^geometry_refused$"):
        resolve._land(QueryResult(("geometry",), ((None,),)))
    with patch.object(
        resolve,
        "decode_geometry",
        side_effect=resolve.GeometryTextError("geometry text refused"),
    ):
        with pytest.raises(resolve.PayloadError, match=r"^geometry text refused$"):
            resolve._land(QueryResult(("geometry",), (("INVENTED",),)))


def test_bad_located_coordinate_keeps_inner_reason():
    with patch.object(
        resolve, "exact_point", side_effect=ValueError("coordinate_range")
    ):
        with pytest.raises(resolve.PayloadError, match=r"^coordinate_range$"):
            resolve._located(SimpleNamespace(latitude=1, longitude=1), ())


def test_employee_total_ambiguity():
    from product.tests.sector_fixture import norm_rows, release_store, with_lineage

    original = sector_facts._read

    def read(store, name, **params):
        rows = original(store, name, **params)
        return [*rows, rows[0]] if name == "account_employees" else rows

    with release_store(with_lineage(norm_rows())) as store:
        ctx = sector_facts.Context(
            store,
            sector_facts.Inputs(
                activity="SYN-restaurant", topic="unit_economics", geography="national"
            ),
        )
        with patch.object(sector_facts, "_read", side_effect=read):
            sector_facts._norms(ctx)
    assert ctx.blocks[0]["reason_key"] == "employee_total_ambiguous"
    assert ctx.blocks[0]["fact_ids"] == []


@pytest.mark.parametrize(
    "fault,expected",
    [
        (ValueError("source_missing"), "source_missing"),
        (ValueError("INVENTED private"), "response_unavailable"),
    ],
)
def test_billable_failure_constructor_keeps_closed_reason(fault, expected):
    from eii_product.photoreal_tiles.limit import BillableFailure

    assert reason(BillableFailure(str(fault))) == expected


@pytest.mark.parametrize(
    "fault,expected",
    [
        (OSError("INVENTED private"), "operation_os_error"),
        (ValueError("source_missing"), "source_missing"),
    ],
)
def test_budget_count_preserves_reason(tmp_path, fault, expected):
    from eii_product.photoreal_tiles.limit import Budget, BudgetFailure

    with patch.object(Path, "open", side_effect=fault):
        with pytest.raises(BudgetFailure, match="^" + expected + "$"):
            Budget(tmp_path / "count").count()


@pytest.mark.parametrize(
    "fault,status,expected",
    [
        (TimeoutError("INVENTED private"), 504, "operation_timeout"),
        (ValueError("routing_tiles"), 500, "routing_tiles"),
    ],
)
def test_playbook_timeout_and_configuration(fault, status, expected, tmp_path):
    from product.tests.test_reason_part_b import playbook_failure

    assert (
        playbook_failure("D38", tmp_path, fault=fault, expected_status=status)
        == expected
    )


def test_imagery_manifest_missing_field_reason(tmp_path):
    from hashlib import sha256

    from product.tests.test_released_imagery import released_fixture

    from eii_product.api.gis_imagery import ReleasedImagery

    folder, identity = released_fixture(tmp_path)
    original = folder / (identity + ".json")
    manifest = json.loads(original.read_bytes())
    manifest.pop("version")
    body = json.dumps(manifest).encode()
    digest = sha256(body).hexdigest()
    (folder / (digest + ".json")).write_bytes(body)
    with pytest.raises(ValueError, match=r"^input_key_missing$"):
        ReleasedImagery(folder, digest)


def test_bad_release_location_keeps_no_data_status():
    store = SimpleNamespace(release_id="ab" * 32)
    with patch.object(
        resolve, "_matched", side_effect=resolve.DataRefusal("coordinate_range")
    ):
        outcome = resolve.resolve(
            store, {"text": "INVENTED", "lang": "en", "kind": "place"}, Mock()
        )
    assert outcome.status == "NO_DATA"
    assert outcome.reason == "coordinate_range"
    assert outcome.payload is None


def test_unknown_field_cannot_select_another_closed_reason():
    args = {
        "activity": "INVENTED",
        "topic": "unit_economics",
        "geography": "national",
        "source_missing": "INVENTED",
    }
    with pytest.raises(ValueError, match=r"^INVALID_ARGUMENT$"):
        sector_facts.sector_facts(None, args)


@given(st.sampled_from(sorted(CODES - sector_facts.Inputs.model_fields.keys())))
def test_unknown_field_reason_is_not_chosen_by_input_key(field):
    args = {
        "activity": "INVENTED",
        "topic": "unit_economics",
        "geography": "national",
        field: "INVENTED",
    }
    with pytest.raises(ValueError, match=r"^INVALID_ARGUMENT$"):
        sector_facts.sector_facts(None, args)
