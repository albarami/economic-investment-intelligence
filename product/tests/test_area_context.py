"""Trusted routing configuration and one session-aware context factory."""

from types import SimpleNamespace

import pytest

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


def test_sources_context_and_cookie_only(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    source = RoutingSource.from_tiles(tmp_path)
    assert source.tile_folder == tmp_path and source.call is None
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
            RoutingSource.from_tiles(tmp_path / "absent")
        elif kind == "no-config":
            RoutingSource.from_tiles(tmp_path)
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


def test_checked_release_path_rules(tmp_path):
    root = tmp_path / "release"
    tiles = root / "artefacts" / "routing"
    tiles.mkdir(parents=True)
    (tiles / "config.json").write_text("{}")
    checked = CheckedRelease(root, {"artefacts": [{"path": "artefacts/routing/"}]}, {})
    assert routing_from_release(checked).tile_folder == tiles.resolve()
    for entries in (
        [],
        [{"path": "/routing/"}],
        [{"path": "artefacts/../routing/"}],
        [{"path": "artefacts/routing/"}] * 2,
    ):
        with pytest.raises(ConfigError, match=r"^routing_tiles$"):
            routing_from_release(CheckedRelease(root, {"artefacts": entries}, {}))
    (tiles / "config.json").unlink()
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(checked)
    tiles.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "config.json").write_text("{}")
    tiles.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ConfigError, match=r"^routing_tiles$"):
        routing_from_release(checked)
