"""S3-T10 template/accounting and chosen-area fixture; never live parity."""

import json
import sys
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

# Match the offline eval tests under the runner's safe-path Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from product.tests import public_opening_server
from product.tests.public_opening_server import build_fixture_app

from eii_product.assistant.playbooks.engine import execute
from eii_product.assistant.playbooks.models import Bundle
from eii_product.ledger.local import LocalLedger
from eii_product.photoreal_tiles.limit import Budget
from eii_product.store.embedded import EmbeddedStore

Service = tuple[Any, LocalLedger, EmbeddedStore, list[object]]


def test_opening_fixture_keeps_budget_inside_work(tmp_path: Path) -> None:
    with patch("eii_product.api.map_modes.Budget", wraps=Budget) as budget:
        _app, store, ledger = build_fixture_app(tmp_path, Path("web/dist"))
    try:
        assert budget.call_count == 1
        assert budget.call_args.args == (tmp_path / "photoreal-count.log",)
    finally:
        ledger.close()
        store.close()


def test_opening_fixture_pins_no_provider(tmp_path: Path) -> None:
    with patch.object(public_opening_server, "create_app") as create:
        _app, store, ledger = build_fixture_app(tmp_path, Path("web/dist"))
    try:
        pins = create.call_args.kwargs
        assert {
            "key_reader",
            "offline_reader",
            "transport_factory",
            "opener",
        } <= pins.keys()
        assert pins["key_reader"]() is None
        assert pins["offline_reader"]() is True
        assert pins["transport_factory"] is pins["opener"]
        marker = tmp_path / "egress-attempts.txt"
        assert not marker.exists()
        for callback in (pins["transport_factory"], pins["opener"]):
            with pytest.raises(AssertionError, match=r"^provider_attempt$"):
                callback()
            assert marker.exists()
        assert marker.read_text() == "provider_attempt\nprovider_attempt\n"
    finally:
        ledger.close()
        store.close()


@pytest.mark.parametrize("server_error", [False, True])
def test_opening_fixture_main_binds_only_loopback_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server_error: bool
) -> None:
    app, store, ledger = Mock(), Mock(), Mock()
    monkeypatch.setattr(
        "sys.argv",
        ["opening", "--work", str(tmp_path), "--port", "1234", "--web", "web/dist"],
    )
    with (
        patch.object(
            public_opening_server,
            "build_fixture_app",
            return_value=(app, store, ledger),
        ) as build,
        patch("product.tests.public_opening_server.uvicorn.run") as run,
    ):
        if server_error:
            run.side_effect = RuntimeError("INVENTED-server-failure")
            with pytest.raises(RuntimeError, match="INVENTED-server-failure"):
                public_opening_server.main()
        else:
            public_opening_server.main()
        build.assert_called_once_with(tmp_path, Path("web/dist"))
        run.assert_called_once_with(
            app, host="127.0.0.1", port=1234, log_level="error", access_log=False
        )
        ledger.close.assert_called_once_with()
        store.close.assert_called_once_with()


@pytest.fixture(scope="module")
def service(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Service]:
    work = tmp_path_factory.mktemp("opening")
    app, store, ledger = build_fixture_app(work, Path("web/dist"))
    try:
        yield (
            import_module("product.tests.public_http_support").Client(app),
            ledger,
            store,
            [],
        )
    finally:
        ledger.close()
        store.close()


@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize("selection", ["polygon", "distance", "walk", "drive"])
def test_opening_story_preserves_area_and_uses_templates(
    service: Service, lang: str, selection: str
) -> None:
    client, ledger, store, _ = service
    if selection == "polygon":
        registered = client.post(
            "/api/areas/shapes",
            json=import_module("product.tests.test_shapes_http").polygon(),
        )
        assert registered.status_code == 201
        area = {"shape_id": registered.json()["shape_id"]}
        tool = area
    else:
        cutoff = 500 if selection == "distance" else 15
        area = {"pin": {"lat": 1, "lon": 1}, "mode": selection, "cutoff": cutoff}
        tool = {"latitude": 1, "longitude": 1, "mode": selection, "cutoff": cutoff}
    expected = client.post("/api/tools/make_area", json=tool).json()["payload"]
    bundles = []

    def capture(*args: Any, **kwargs: Any) -> Bundle:
        result = execute(*args, **kwargs)
        bundles.append(result)
        return result

    with patch("eii_product.api.playbooks.execute", side_effect=capture):
        started = client.post(
            "/api/playbooks/site_check",
            json={"activity": "INVENTED-activity", "lang": lang, **area},
        )
        assert started.status_code == 202
        events = client.get(started.json()["events_url"]).text
    frames = [
        (part.split("event: ")[1].split("\r\n")[0], json.loads(part.split("data: ")[1]))
        for part in events.split("\r\n\r\n")
        if "event: " in part
    ]
    kinds = [kind for kind, _ in frames]
    assert kinds[-1] == "done"
    assert "error" not in kinds
    assert kinds.index("receipt") < kinds.index("narrative")
    receipt = next(data for kind, data in frames if kind == "receipt")
    assert receipt["egress"] == []
    assert all(
        receipt["Checked before display"][key] is True
        for key in (
            "Sources",
            "Assumptions",
            "Nothing invented",
            "Scope",
            "Limits stated",
        )
    )
    assert (
        next(data for kind, data in frames if kind == "status")["writer"] == "template"
    )
    assert bundles[0].area_roles["headline"] == expected["area_id"]
    for kind, data in frames:
        if kind == "evidence":
            for fact in data["facts"]:
                assert fact["provenance"] == "public"
                assert fact["input_classes"] == ["public"]
                assert fact["release_id"] == store.release_id
    assert ledger.rows()
