"""Invented native routing metadata, never a provider response."""

import json

import pytest

from eii_product.photoreal_tiles.native import NativeFailure, NativeViews, Target

BASE = "https://invented.invalid"


def tiles(uri="child.glb?session=SYN-session"):
    return json.dumps(
        {
            "asset": {"version": "1.1", "tilesetVersion": "invented"},
            "geometricError": 0,
            "root": {
                "boundingVolume": {"sphere": [0, 0, 0, 1]},
                "geometricError": 0,
                "content": {"uri": uri},
            },
        }
    ).encode()


def test_aliases_are_query_free_bound_to_one_view_and_purged():
    clock = [0.0]
    native = NativeViews(lambda: clock[0])
    native.create("SYN-view")
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    assert root.path == "/v1/3dtiles/root.json" and root.session is None
    result = json.loads(native.rewrite("SYN-view", root, tiles(), BASE))
    alias = result["root"]["content"]["uri"].removeprefix("/api/photoreal/")
    assert "?" not in alias and "tilesetVersion" not in result["asset"]
    assert b"SYN-session" not in json.dumps(result).encode()
    assert native.target("SYN-view", alias, BASE).session == "SYN-session"
    native.create("SYN-other")
    with pytest.raises(NativeFailure):
        native.target("SYN-other", alias, BASE)
    with pytest.raises(NativeFailure):
        native.target("SYN-view", "3dtiles/root.json", BASE)
    clock[0] = 10800
    with pytest.raises(NativeFailure):
        native.target("SYN-view", alias, BASE)
    assert not native.contains("SYN-view")


def tiles_with_children(count):
    body = json.loads(tiles())
    del body["root"]["content"]
    body["root"]["children"] = [
        {"content": {"uri": f"child-{index}.json"}} for index in range(count)
    ]
    return json.dumps(body).encode()


def test_alias_bound_accepts_ten_thousand_and_refuses_one_more_atomically():
    native = NativeViews()
    native.create("SYN-view")
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    result = json.loads(
        native.rewrite("SYN-view", root, tiles_with_children(10000), BASE)
    )
    aliases = native.views["SYN-view"].aliases.copy()
    assert len(result["root"]["children"]) == len(aliases) == 10000
    for child in result["root"]["children"]:
        alias = child["content"]["uri"].removeprefix("/api/photoreal/")
        assert alias in aliases
    parent = native.target("SYN-view", alias, BASE)
    with pytest.raises(NativeFailure):
        native.rewrite("SYN-view", parent, tiles("overflow.glb"), BASE)
    assert native.views["SYN-view"].aliases == aliases
    assert len(native.views["SYN-view"].aliases) == 10000


def test_view_expiry_is_measured_from_start():
    clock = [0.0]
    native = NativeViews(lambda: clock[0])
    native.create("SYN-view")
    clock[0] = 5000
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    result = json.loads(native.rewrite("SYN-view", root, tiles(), BASE))
    alias = result["root"]["content"]["uri"].removeprefix("/api/photoreal/")
    clock[0] = 15799
    assert native.target("SYN-view", alias, BASE) == Target(
        "/v1/3dtiles/child.glb", "SYN-session"
    )
    clock[0] = 15800
    with pytest.raises(NativeFailure):
        native.target("SYN-view", alias, BASE)
    assert not native.contains("SYN-view")


def test_never_started_view_is_purged_at_registration_expiry():
    clock = [0.0]
    native = NativeViews(lambda: clock[0])
    native.create("SYN-view")
    clock[0] = 10799
    assert native.contains("SYN-view")
    clock[0] = 10800
    native.purge()
    assert "SYN-view" not in native.views
    assert not native.contains("SYN-view")


def test_route_alias_overflow_disposes_view_after_counting_billable_fetch(
    tmp_path, monkeypatch
):
    from product.tests.test_map_modes import Response, invoke

    from eii_product.api import map_modes
    from eii_product.api.app import create_app

    native = NativeViews()
    monkeypatch.setattr(map_modes, "NativeViews", lambda: native)
    monkeypatch.setattr(map_modes, "read_maptile_api_key", lambda: "SYN-invented-key")
    monkeypatch.setattr(
        map_modes,
        "map_setting",
        lambda name: BASE if name == "EII_PHOTOREAL_TILE_BASE" else "",
    )
    count = tmp_path / "count"
    count.write_text("ready:0\n")
    calls = []

    def opener(request, timeout):
        calls.append(request)
        return Response(
            raw=tiles_with_children(10000) if len(calls) == 1 else tiles(),
            headers={"Content-Type": "application/json"},
        )

    app = create_app(tmp_path, opener=opener, count_path=count)
    view = json.loads(invoke(app, "/api/photoreal/views", "POST")[1])["view_id"]
    query = "view=" + view
    status, raw, headers = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200 and headers[b"cache-control"] == b"no-store"
    assert len(native.views[view].aliases) == 10000
    alias = json.loads(raw)["root"]["children"][0]["content"]["uri"]
    status, raw, headers = invoke(app, alias, query=query)
    assert status == 404 and headers[b"cache-control"] == b"no-store"
    assert raw == b'{"error":{"code":"NOT_FOUND"}}'
    assert not native.contains(view)
    assert count.read_text() == "ready:0\npending:0\nready:1\npending:1\nready:2\n"
    assert invoke(app, alias, query=query)[0] == 404
    assert len(calls) == 2
    assert count.read_text() == "ready:0\npending:0\nready:1\npending:1\nready:2\n"


@pytest.mark.parametrize(
    "uri",
    [
        "/v1/3dtiles//root.json",
        BASE + "/v1/3dtiles//root.json",
        BASE.removeprefix("https:") + "/v1/3dtiles//root.json",
        "/v1/3dtiles/a//b.glb",
        "root.json",
        "/v1/3dtiles/root.json?session=SYN-again",
        "../child.glb",
        "%2e%2e/child.glb",
        "nested/%252e%252e/child.glb",
        "//foreign.invalid/v1/3dtiles/a.glb",
        "https://" + "@".join(("SYN-user", "invented.invalid")) + "/v1/3dtiles/a.glb",
        "a.glb?key=bad",
        "a.glb?session=a&session=b",
        "a.glb#fragment",
        "a.b3dm",
        "data:invented",
        "a.glb?unknown=bad",
        "a%2fchild.glb",
        "a.glb?session=",
    ],
)
def test_native_reference_plants_fail_closed(uri):
    native = NativeViews()
    native.create("SYN-view")
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    with pytest.raises(NativeFailure):
        native.rewrite("SYN-view", root, tiles(uri), BASE)


def test_nested_parent_resolution_disposal_and_restart():
    native = NativeViews()
    native.create("SYN-view")
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    first = json.loads(
        native.rewrite(
            "SYN-view", root, tiles("nested/child.json?session=SYN-session"), BASE
        )
    )
    alias = first["root"]["content"]["uri"].removeprefix("/api/photoreal/")
    parent = native.target("SYN-view", alias, BASE)
    second = json.loads(native.rewrite("SYN-view", parent, tiles("mesh.glb"), BASE))
    alias2 = second["root"]["content"]["uri"].removeprefix("/api/photoreal/")
    target = native.target("SYN-view", alias2, BASE)
    assert target.path == "/v1/3dtiles/nested/mesh.glb"
    assert target.session == "SYN-session"
    with pytest.raises(NativeFailure):
        NativeViews().target("SYN-view", alias2, BASE)
    native.dispose("SYN-view")
    with pytest.raises(NativeFailure):
        native.target("SYN-view", alias2, BASE)


def test_route_root_once_alias_session_and_child_failure(tmp_path, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from product.tests.test_map_modes import Response, invoke

    from eii_product.api import map_modes
    from eii_product.api.app import create_app

    monkeypatch.setattr(map_modes, "read_maptile_api_key", lambda: "SYN-invented-key")
    monkeypatch.setattr(
        map_modes,
        "map_setting",
        lambda name: BASE if name == "EII_PHOTOREAL_TILE_BASE" else "",
    )
    count = tmp_path / "count"
    count.write_text("ready:0\n")
    calls = []
    fail = [False]

    def opener(request, timeout):
        calls.append(request)
        if request.full_url.split("?")[0].endswith("root.json"):
            return Response(raw=tiles(), headers={"Content-Type": "application/json"})
        return Response(
            status=503 if fail[0] else 200,
            raw=b"SYN-invented-glb",
            headers={"Content-Type": "model/gltf-binary"},
        )

    app = create_app(tmp_path, opener=opener, count_path=count)
    view = json.loads(invoke(app, "/api/photoreal/views", "POST")[1])["view_id"]
    query = "view=" + view
    status, raw, headers = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200 and headers[b"cache-control"] == b"no-store"
    assert urlsplit(calls[0].full_url).path == "/v1/3dtiles/root.json"
    alias = json.loads(raw)["root"]["content"]["uri"]
    assert invoke(app, "/api/photoreal/3dtiles/root.json", query=query)[0] == 404
    assert len(calls) == 1
    assert invoke(app, alias, query=query)[0] == 200
    assert parse_qs(urlsplit(calls[-1].full_url).query)["session"] == ["SYN-session"]
    fail[0] = True
    assert invoke(app, alias, query=query)[0] == 404
    before = len(calls)
    assert invoke(app, alias, query=query)[0] == 404
    assert len(calls) == before
    assert count.read_text().endswith("ready:2\n")


def test_session_echo_in_metadata_is_refused():
    native = NativeViews()
    native.create("SYN-view")
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    body = json.loads(tiles())
    body["asset"]["generator"] = "SYN-session"
    with pytest.raises(NativeFailure):
        native.rewrite("SYN-view", root, json.dumps(body).encode(), BASE)


def test_earlier_session_cannot_escape_in_later_metadata_or_binary():
    from eii_product.photoreal_tiles.native import Target

    native = NativeViews()
    native.create("SYN-view")
    root = native.target("SYN-view", "3dtiles/root.json", BASE)
    native.rewrite("SYN-view", root, tiles(), BASE)
    body = json.loads(tiles("next.glb?session=SYN-next"))
    body["asset"]["copyright"] = "SYN-session"
    with pytest.raises(NativeFailure):
        native.rewrite(
            "SYN-view",
            Target("/v1/3dtiles/other.json", "SYN-other"),
            json.dumps(body).encode(),
            BASE,
        )
    with pytest.raises(NativeFailure):
        native.refuse_session_echo("SYN-view", b"invented binary SYN-session")
    native.refuse_session_echo("SYN-view", b"invented clean binary")


def test_session_echo_scans_each_distinct_session_once():
    class Body(bytes):
        def __contains__(self, value):
            scanned.append(value)
            return super().__contains__(value)

    scanned = []
    native = NativeViews()
    native.create("SYN-view")
    native.views["SYN-view"].aliases = {
        "SYN-a": Target("/v1/3dtiles/a.glb", "SYN-session"),
        "SYN-b": Target("/v1/3dtiles/b.glb", "SYN-session"),
        "SYN-c": Target("/v1/3dtiles/c.glb", "SYN-other"),
        "SYN-d": Target("/v1/3dtiles/d.glb"),
    }
    native.refuse_session_echo("SYN-view", Body(b"invented body"))
    assert sorted(scanned) == [b"SYN-other", b"SYN-session"]
    for session in (b"SYN-session", b"SYN-other"):
        with pytest.raises(NativeFailure):
            native.refuse_session_echo("SYN-view", Body(session))
    with pytest.raises(NativeFailure):
        native.refuse_session_echo("SYN-missing", Body(b"invented"))


@pytest.fixture
def interrupted_route(tmp_path, monkeypatch):
    from product.tests.test_map_modes import Response, invoke

    from eii_product.api import map_modes
    from eii_product.api.app import create_app

    monkeypatch.setattr(map_modes, "read_maptile_api_key", lambda: "SYN-invented-key")
    monkeypatch.setattr(
        map_modes,
        "map_setting",
        lambda name: BASE if name == "EII_PHOTOREAL_TILE_BASE" else "",
    )
    count = tmp_path / "count"
    count.write_text("ready:0\n")
    calls = []
    failure = [None]
    closed = []

    class InterruptedResponse(Response):
        def read(self):
            if failure[0] in {"read-address", "read-context-address"}:
                from eii_product.imagery_provider.address import AddressFailure

                raise AddressFailure
            raise OSError("SYN-invented-key SYN-header-value " + BASE)

        def close(self):
            closed.append(True)

    class ManagedResponse:
        def __enter__(self):
            return InterruptedResponse(status=200)

        def __exit__(self, *args):
            closed.append(True)

    def opener(request, timeout):
        calls.append(request)
        if failure[0] == "transport":
            raise TimeoutError(request.full_url + " SYN-header-value")
        if failure[0] in {"read", "read-address"}:
            return InterruptedResponse(status=200)
        if failure[0] in {"read-context", "read-context-address"}:
            return ManagedResponse()
        return Response(raw=tiles(), headers={"Content-Type": "application/json"})

    def restart():
        return create_app(tmp_path, opener=opener, count_path=count)

    def start(app):
        status, raw, _ = invoke(app, "/api/photoreal/views", "POST")
        assert status == 200
        return "view=" + json.loads(raw)["view_id"]

    return count, calls, failure, closed, restart, start


@pytest.fixture
def exchange_errors(monkeypatch):
    import traceback

    from eii_product.photoreal_tiles.limit import Budget

    errors = []
    original = Budget.request

    def capture_request(self, limit, send, billable, step=None):
        def observed_send():
            try:
                return send()
            except Exception as error:
                errors.append("".join(traceback.format_exception(error)))
                raise

        return original(self, limit, observed_send, billable, step)

    monkeypatch.setattr(Budget, "request", capture_request)
    return errors


@pytest.mark.parametrize("target", ["root", "child"])
@pytest.mark.parametrize("managed", [False, True])
@pytest.mark.parametrize("address_failure", [False, True])
def test_route_counts_success_when_body_read_is_interrupted(
    interrupted_route, target, managed, address_failure, exchange_errors, caplog
):
    from product.tests.test_map_modes import invoke

    count, calls, failure, closed, restart, start = interrupted_route
    app = restart()
    query = start(app)
    path = "/api/photoreal/3dtiles/root.json"
    initial = 0
    if target == "child":
        status, raw, _ = invoke(app, path, query=query)
        assert status == 200
        path = json.loads(raw)["root"]["content"]["uri"]
        initial = 1
    before = count.read_text()
    failure[0] = "read-context" if managed else "read"
    if address_failure:
        failure[0] += "-address"
    status, raw, headers = invoke(app, path, query=query)
    assert status == 404
    assert headers[b"cache-control"] == b"no-store"
    assert raw == b'{"error":{"code":"NOT_FOUND"}}'
    assert closed == [True]
    assert count.read_text() == before + f"pending:{initial}\nready:{initial + 1}\n"
    assert len(exchange_errors) == 1
    for marker in ("SYN-invented-key", "SYN-header-value", BASE):
        assert (
            marker not in exchange_errors[0] + raw.decode() + str(headers) + caplog.text
        )
    for application in (app, restart()):
        state = json.loads(invoke(application, "/api/map-modes")[1])["photoreal"]
        assert state["available"] is True
        assert state["meter"]["billable_requests"] == initial + 1
        assert state["meter"]["spend_usd"] == ("0.006" if initial == 0 else "0.012")
    assert len(calls) == initial + 1


@pytest.mark.parametrize("target", ["root", "child"])
def test_route_indeterminate_exchange_stays_pending_after_restart(
    interrupted_route, target, exchange_errors, caplog
):
    from product.tests.test_map_modes import invoke

    count, calls, failure, _, restart, start = interrupted_route
    app = restart()
    query = start(app)
    other_query = start(app)
    path = "/api/photoreal/3dtiles/root.json"
    initial = 0
    if target == "child":
        status, raw, _ = invoke(app, path, query=query)
        assert status == 200
        path = json.loads(raw)["root"]["content"]["uri"]
        initial = 1
    before = count.read_text()
    failure[0] = "transport"
    status, raw, headers = invoke(app, path, query=query)
    assert status == 404
    assert headers[b"cache-control"] == b"no-store"
    assert raw == b'{"error":{"code":"NOT_FOUND"}}'
    assert count.read_text() == before + f"pending:{initial}\n"
    assert len(exchange_errors) == 1
    for marker in ("SYN-invented-key", "SYN-header-value", BASE):
        assert (
            marker not in exchange_errors[0] + raw.decode() + str(headers) + caplog.text
        )
    for application in (app, restart()):
        assert json.loads(invoke(application, "/api/map-modes")[1])["photoreal"] == {
            "available": False,
            "reason": "count_unavailable",
            "meter": None,
        }
        assert invoke(application, "/api/photoreal/views", "POST")[0] == 404
        assert invoke(application, path, query=query)[0] == 404
        other_status, _, _ = invoke(
            application, "/api/photoreal/3dtiles/root.json", query=other_query
        )
        assert other_status == 404
        assert count.read_text() == before + f"pending:{initial}\n"
        assert len(calls) == initial + 1


@pytest.mark.parametrize("code", [302, 400, 503])
def test_route_http_error_keeps_known_unbillable_treatment(
    interrupted_route, tmp_path, code
):
    from io import BytesIO
    from urllib.error import HTTPError

    from product.tests.test_map_modes import invoke

    from eii_product.api.app import create_app

    count, calls, _, _, _, start = interrupted_route
    body = BytesIO(b"SYN-error-body")

    def opener(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, code, "SYN-error", {}, body)

    app = create_app(tmp_path, opener=opener, count_path=count)
    query = start(app)
    assert invoke(app, "/api/photoreal/3dtiles/root.json", query=query)[0] == 404
    assert body.closed
    assert count.read_text() == "ready:0\npending:0\nready:0\n"
    state = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]
    assert state["available"] is True
    assert state["meter"]["billable_requests"] == 0
    assert len(calls) == 1


@pytest.mark.parametrize("target", ["root", "child"])
def test_route_redirect_resolves_unbillable_and_later_view_sends(
    interrupted_route, tmp_path, target, exchange_errors, caplog
):
    from product.tests.test_map_modes import Response, invoke

    from eii_product.api.app import create_app
    from eii_product.imagery_provider.address import AddressFailure
    from eii_product.photoreal_tiles.proxy import NoRedirect

    count, calls, _, _, _, start = interrupted_route
    redirect = [False]
    redirect_errors = []
    destination = "https://foreign.invalid/SYN-redirect-target?key=SYN-invented-key"

    def opener(request, timeout):
        calls.append(request)
        if redirect[0]:
            try:
                NoRedirect().redirect_request(
                    request,
                    None,
                    302,
                    "redirect",
                    {"Location": destination},
                    destination,
                )
            except AddressFailure as error:
                redirect_errors.append(str(error))
                raise
        return Response(raw=tiles(), headers={"Content-Type": "application/json"})

    app = create_app(tmp_path, opener=opener, count_path=count)
    query = start(app)
    path = "/api/photoreal/3dtiles/root.json"
    initial = 0
    if target == "child":
        status, raw, _ = invoke(app, path, query=query)
        assert status == 200
        path = json.loads(raw)["root"]["content"]["uri"]
        initial = 1
    before = count.read_text()
    redirect[0] = True
    status, raw, headers = invoke(app, path, query=query)
    assert status == 404
    assert headers[b"cache-control"] == b"no-store"
    assert raw == b'{"error":{"code":"NOT_FOUND"}}'
    refused_journal = before + f"pending:{initial}\nready:{initial}\n"
    assert count.read_text() == refused_journal
    assert len(calls) == initial + 1
    assert redirect_errors == ["NOT_FOUND"]
    assert exchange_errors == []
    for marker in ("SYN-invented-key", destination, "SYN-redirect-target"):
        assert (
            marker
            not in "".join(redirect_errors) + raw.decode() + str(headers) + caplog.text
        )

    restarted = create_app(tmp_path, opener=opener, count_path=count)
    for application in (app, restarted):
        state = json.loads(invoke(application, "/api/map-modes")[1])["photoreal"]
        assert state["available"] is True
        assert state["reason"] is None
        assert state["meter"]["billable_requests"] == initial
        assert state["meter"]["spend_usd"] == ("0" if initial == 0 else "0.006")
        assert count.read_text() == refused_journal
    redirect[0] = False
    later_query = start(restarted)
    assert (
        invoke(restarted, "/api/photoreal/3dtiles/root.json", query=later_query)[0]
        == 200
    )
    assert len(calls) == initial + 2
    assert (
        count.read_text()
        == refused_journal + f"pending:{initial}\nready:{initial + 1}\n"
    )


@pytest.mark.parametrize("target", ["root", "child"])
def test_route_unreadable_status_stays_pending_and_sends_nothing_further(
    interrupted_route, tmp_path, target
):
    from product.tests.test_map_modes import Response, invoke

    from eii_product.api.app import create_app

    count, calls, _, _, _, start = interrupted_route
    unreadable = [False]

    class UnreadableStatus:
        """Opener body with neither status nor getcode."""

    def opener(request, timeout):
        calls.append(request)
        if unreadable[0]:
            return UnreadableStatus()
        return Response(raw=tiles(), headers={"Content-Type": "application/json"})

    app = create_app(tmp_path, opener=opener, count_path=count)
    query = start(app)
    path = "/api/photoreal/3dtiles/root.json"
    initial = 0
    if target == "child":
        status, raw, _ = invoke(app, path, query=query)
        assert status == 200
        path = json.loads(raw)["root"]["content"]["uri"]
        initial = 1
    before = count.read_text()
    unreadable[0] = True
    status, raw, headers = invoke(app, path, query=query)
    assert status == 404
    assert headers[b"cache-control"] == b"no-store"
    assert raw == b'{"error":{"code":"NOT_FOUND"}}'
    assert count.read_text() == before + f"pending:{initial}\n"
    for application in (app, create_app(tmp_path, opener=opener, count_path=count)):
        assert json.loads(invoke(application, "/api/map-modes")[1])["photoreal"] == {
            "available": False,
            "reason": "count_unavailable",
            "meter": None,
        }
        assert invoke(application, "/api/photoreal/views", "POST")[0] == 404
        assert invoke(application, path, query=query)[0] == 404
        assert count.read_text() == before + f"pending:{initial}\n"
        assert len(calls) == initial + 1
