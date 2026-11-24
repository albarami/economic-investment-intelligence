"""Trusted routing configuration and one session-aware context factory."""

import json
from types import SimpleNamespace

import pytest
from product.tests.test_routing_extract import extract as extract
from routing_release_fixture import TILES

from eii_product.api.app import create_app
from eii_product.api.area_context import (
    AreaContextFactory,
    RoutingSource,
    routing_from_release,
)
from eii_product.api.session_store import SessionStore
from eii_product.config import ConfigError
from eii_product.store.release_check import CheckedRelease
from eii_product.tools.routing import RoutingTilesUnavailable


def call(*args):
    return ((0, 0), (0, 1), (1, 1), (0, 0))


def test_sources_context_and_cookie_only(tmp_path, extract):
    source = RoutingSource.from_tiles(extract[0] / TILES, extract[0])
    config = json.loads((source.tile_folder / "config.json").read_bytes())
    assert config["mjolnir"]["tile_extract"] == str((extract[0] / TILES).resolve())
    assert source.call is None
    factory = AreaContextFactory("ab" * 32, RoutingSource.from_call(call))
    sessions = SessionStore()
    held = sessions.admit(None)
    request = SimpleNamespace(
        cookies={"eii_session": held.key},
        app=SimpleNamespace(state=SimpleNamespace(sessions=sessions)),
    )
    context = factory.dependency(request)
    assert context.shapes is held.shapes
    assert context.routing is call
    assert factory.for_playbook("INVENTED-book").playbook_key == "INVENTED-book"
    assert factory.for_session(held.shapes).playbook_key == "site_check"
    assert sessions.count == 1
    request.cookies = {"eii_session": "INVENTED-unknown", "routing": "INVENTED-path"}
    assert factory.dependency(request).routing is call
    assert sessions.count == 1
    with pytest.raises(RoutingTilesUnavailable):
        AreaContextFactory("ab" * 32, None).for_session(held.shapes).routing(
            "walk", 5, 0, 0
        )


@pytest.mark.parametrize(
    "kind", ["missing", "no-config", "both", "neither", "bad-call", "bad-app"]
)
def test_source_refusals(tmp_path, kind):
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        if kind == "missing":
            RoutingSource.from_tiles(tmp_path / "absent", tmp_path)
        elif kind == "no-config":
            RoutingSource.from_tiles(tmp_path, tmp_path)
        elif kind == "both":
            RoutingSource(tile_folder=tmp_path, call=call)
        elif kind == "neither":
            RoutingSource()
        elif kind == "bad-call":
            RoutingSource.from_call("INVENTED-path")
        else:
            create_app(
                tmp_path, routing="INVENTED-path", fc_setting_reader=lambda: None
            )


def test_checked_release_path_rules(extract):
    root, reference = extract
    checked = CheckedRelease(root, {"artefacts": [reference]}, {})
    source = routing_from_release(checked)
    config = json.loads((source.tile_folder / "config.json").read_bytes())
    assert config["mjolnir"]["tile_extract"] == str((root / TILES).resolve())
    for entries in (
        [],
        [{"path": "/routing/"}],
        [{"path": "artefacts/../routing/"}],
        [reference] * 2,
    ):
        with pytest.raises(ConfigError, match=r"^routing_tiles$"):
            routing_from_release(CheckedRelease(root, {"artefacts": entries}, {}))
