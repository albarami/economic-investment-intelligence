"""The address route, the imagery adapter, and the sinks that exist on this base."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path

import pytest
from product.tests.sector_fixture import repository_path

from eii_product.api.app import create_app
from eii_product.config import read_esri_api_key
from eii_product.imagery_provider.address import (
    MAX_LOCATIONS,
    REQUEST_TIMEOUT_S,
    AddressFailure,
    AddressHit,
    live_transport,
    parse_candidates,
)

LABEL = "SYN-lane"
KEY = "SYN-imagery-key"
VENDOR = "SYN-vendor-said"
NEEDLES = (LABEL, KEY, VENDOR)


def test_config_reads_only_the_one_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ESRI_API_KEY", raising=False)
    assert read_esri_api_key() is None
    monkeypatch.setenv("ESRI_API_KEY", "")
    assert read_esri_api_key() is None
    monkeypatch.setenv("ESRI_API_KEY", KEY)
    assert read_esri_api_key() == KEY
    root = repository_path("product/src/eii_product", __file__)
    hits = [
        path.name
        for path in root.rglob("*.py")
        if "ESRI_API_KEY" in path.read_text(encoding="utf-8")
    ]
    assert hits == ["config.py"]


def test_create_app_keeps_tiles_and_mounts_the_route(tmp_path: Path) -> None:
    calls: list[object] = []

    def opener(*args: object, **kwargs: object) -> object:
        calls.append(args)
        raise OSError("opened")

    app = create_app(tmp_path, opener=opener)
    paths = _route_paths(app)
    assert "/api/address-search" in paths
    assert "/tiles/{name}" in paths
    assert calls == []
    folder = repository_path("product/src/eii_product/imagery_provider", __file__)
    names = sorted(path.name for path in folder.iterdir() if path.name != "__pycache__")
    assert names == ["__init__.py", "address.py"]
    for name in ("address.py", "address_search.py"):
        text = list(repository_path("product/src/eii_product", __file__).rglob(name))
        assert text
        for path in text:
            source = path.read_text(encoding="utf-8")
            assert "pytest" not in source


def test_tests_do_not_call_the_provider(tmp_path: Path) -> None:
    calls: list[object] = []

    def opener(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        raise OSError("opened")

    absent = create_app(tmp_path, key_reader=lambda: None, opener=opener)
    status, body, _log = _invoke(absent, {"text": LABEL, "lang": "en"})
    assert status == 404
    assert calls == []
    offline = create_app(
        tmp_path,
        key_reader=lambda: KEY,
        offline_reader=lambda: True,
        opener=opener,
    )
    status, body, _log = _invoke(offline, {"text": LABEL, "lang": "en"})
    assert status == 404
    assert KEY not in json.dumps(body)
    assert calls == []
    send = live_transport(opener)
    with pytest.raises(AddressFailure):
        send(LABEL, "en", KEY)
    assert calls != []


def test_the_live_request_is_a_form_post_and_drops_the_score() -> None:
    seen: list[object] = []

    def opener(request: object, timeout: float) -> object:
        seen.append((request, timeout))
        return _Body(200, _provider((LABEL, 1.5, 2.5, 1), ("SYN-other", 3.5, 4.5, 99)))

    send = live_transport(opener)
    hits = send(LABEL, "ar", KEY)
    request, timeout = seen[0]
    assert timeout == REQUEST_TIMEOUT_S
    assert request.method == "POST"
    assert request.full_url.endswith("findAddressCandidates")
    assert "token" not in request.full_url
    assert LABEL not in request.full_url
    form = request.data.decode("utf-8")
    assert "token=" + KEY in form
    assert "SingleLine=" + LABEL in form
    assert "f=json" in form
    assert "maxLocations=5" in form
    assert "langCode=ar" in form
    assert [hit.label for hit in hits] == [LABEL, "SYN-other"]
    assert hits[0] == AddressHit(LABEL, 1.5, 2.5)
    assert not hasattr(hits[0], "score")
    crowded = {
        "candidates": [
            {"address": f"SYN-{name}", "location": {"x": 1.5, "y": 2.5}, "score": index}
            for index, name in enumerate(("f", "e", "d", "c", "b", "a"))
        ]
    }
    parsed = parse_candidates(crowded)
    assert len(parsed) == MAX_LOCATIONS
    assert [hit.label for hit in parsed] == [
        "SYN-f",
        "SYN-e",
        "SYN-d",
        "SYN-c",
        "SYN-b",
    ]
    with pytest.raises(AddressFailure):
        parse_candidates(
            {"candidates": [{"address": LABEL, "location": {"x": 200, "y": 0}}]}
        )
    with pytest.raises(AddressFailure):
        parse_candidates(
            {
                "candidates": [
                    {"address": LABEL, "location": {"x": float("nan"), "y": 0}}
                ]
            }
        )
    with pytest.raises(AddressFailure):
        parse_candidates({"message": VENDOR})


def test_the_route_returns_the_label_and_point(tmp_path: Path) -> None:
    def transport(text: str, lang: str, key: str) -> tuple[AddressHit, ...]:
        assert text == LABEL and lang == "en" and key == KEY
        return (AddressHit(LABEL, 1.5, 2.5),)

    app = create_app(
        tmp_path,
        key_reader=lambda: KEY,
        offline_reader=lambda: False,
        transport_factory=lambda opener: transport,
    )
    status, body, log = _invoke(app, {"text": LABEL, "lang": "en"})
    assert status == 200
    assert body == {
        "results": [{"label": LABEL, "point": {"longitude": 1.5, "latitude": 2.5}}]
    }
    assert "score" not in json.dumps(body)
    assert KEY not in json.dumps(body)
    assert LABEL not in log
    assert KEY not in log
    record = json.loads(log)
    assert set(record) == {
        "ts",
        "level",
        "event",
        "answer_id",
        "seat_key",
        "tool",
        "engine",
        "release_id",
        "status",
        "duration_ms",
        "error_code",
        "error_id",
    }


def test_failures_are_not_found_without_provider_text(tmp_path: Path) -> None:
    def empty(text: str, lang: str, key: str) -> tuple[AddressHit, ...]:
        del text, lang, key
        return ()

    app = create_app(
        tmp_path,
        key_reader=lambda: KEY,
        transport_factory=lambda opener: empty,
    )
    status, body, log = _invoke(app, {"text": LABEL, "lang": "en"})
    assert status == 404
    assert set(body["error"]) == {"code", "message_key", "error_id"}
    assert body["error"]["code"] == "NOT_FOUND"
    assert VENDOR not in json.dumps(body)
    assert KEY not in log

    def broken(text: str, lang: str, key: str) -> tuple[AddressHit, ...]:
        del text, lang, key
        raise AddressFailure

    failed = create_app(
        tmp_path,
        key_reader=lambda: KEY,
        transport_factory=lambda opener: broken,
    )
    status, body, _log = _invoke(failed, {"text": LABEL, "lang": "ar"})
    assert status == 404
    assert VENDOR not in json.dumps(body)
    status, body, _log = _invoke(app, {"text": LABEL, "lang": "en", "extra": 1})
    assert status == 422
    assert body["error"]["code"] == "INVALID_ARGUMENT"
    assert KEY not in json.dumps(body)


def test_an_unexpected_transport_error_is_a_closed_not_found(tmp_path: Path) -> None:
    detail = f"{KEY} {LABEL} {VENDOR}"

    def transport(text: str, lang: str, key: str) -> tuple[AddressHit, ...]:
        del text, lang, key
        raise RuntimeError(detail)

    app = create_app(
        tmp_path,
        key_reader=lambda: KEY,
        offline_reader=lambda: False,
        transport_factory=lambda opener: transport,
    )
    status, body, log = _invoke(app, {"text": LABEL, "lang": "en"})
    assert status == 404
    dumped = json.dumps(body)
    assert body["error"]["code"] == "NOT_FOUND"
    assert set(body["error"]) == {"code", "message_key", "error_id"}
    record = json.loads(log)
    assert set(record) == {
        "ts",
        "level",
        "event",
        "answer_id",
        "seat_key",
        "tool",
        "engine",
        "release_id",
        "status",
        "duration_ms",
        "error_code",
        "error_id",
    }
    for needle in (KEY, LABEL, VENDOR):
        assert needle not in dumped
        assert needle not in log


def test_a_non_200_provider_body_stays_out_of_the_refusal(tmp_path: Path) -> None:
    echo = f"{KEY}|{LABEL}|{VENDOR}".encode()

    class _Echo:
        status = 503

        def read(self) -> bytes:
            return echo

        def close(self) -> None:
            return None

    def opener(request: object, timeout: float) -> object:
        del request, timeout
        return _Echo()

    app = create_app(
        tmp_path,
        key_reader=lambda: KEY,
        offline_reader=lambda: False,
        opener=opener,
    )
    status, body, log = _invoke(app, {"text": LABEL, "lang": "en"})
    assert status == 404
    dumped = json.dumps(body)
    assert body["error"]["code"] == "NOT_FOUND"
    for needle in (KEY, LABEL, VENDOR):
        assert needle not in dumped
        assert needle not in log


def test_address_result_is_not_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    temporary = tmp_path / "tmp"
    temporary.mkdir()
    monkeypatch.setenv("TMPDIR", str(temporary))

    def transport(text: str, lang: str, key: str) -> tuple[AddressHit, ...]:
        del text, lang, key
        return (AddressHit(LABEL, 1.5, 2.5),)

    app = create_app(
        tmp_path / "tiles",
        key_reader=lambda: KEY,
        transport_factory=lambda opener: transport,
    )
    (tmp_path / "tiles").mkdir()
    status, _body, log = _invoke(app, {"text": LABEL, "lang": "en"})
    assert status == 200
    assert _scan(tmp_path, log) == []
    planted = tmp_path / "plant.txt"
    planted.write_text(LABEL, encoding="utf-8")
    assert _scan(tmp_path, "") != []
    planted.unlink()
    database = sqlite3.connect(tmp_path / "plant.sqlite")
    database.execute("CREATE TABLE plant (label TEXT)")
    database.execute("INSERT INTO plant VALUES (?)", (LABEL,))
    database.commit()
    database.close()
    assert any(LABEL in hit for hit in _scan(tmp_path, ""))
    assert any(KEY in hit for hit in _scan(tmp_path, f"key={KEY}"))


class _Body:
    def __init__(self, status: int, payload: dict[str, object]) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def close(self) -> None:
        return None


def _provider(*rows: tuple) -> dict[str, object]:
    candidates = []
    for address, longitude, latitude, score in rows:
        candidates.append(
            {
                "address": address,
                "location": {"x": longitude, "y": latitude},
                "score": score,
                "attributes": {"note": VENDOR},
                "extent": {"xmin": 0},
            }
        )
    return {"spatialReference": {"wkid": 4326}, "candidates": candidates}


def _invoke(app: object, payload: dict[str, object]) -> tuple[int, dict, str]:
    handler = _Capture()
    logger = logging.getLogger("eii.address_search")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    sent: list[dict] = []
    delivered = False

    async def receive() -> dict:
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {
            "type": "http.request",
            "body": json.dumps(payload).encode("utf-8"),
            "more_body": False,
        }

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/address-search",
        "raw_path": b"/api/address-search",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
    }
    try:
        asyncio.run(app(scope, receive, send))
    finally:
        logger.removeHandler(handler)
    status = next(
        item["status"] for item in sent if item["type"] == "http.response.start"
    )
    raw = b"".join(
        item.get("body", b"") for item in sent if item["type"] == "http.response.body"
    )
    return status, json.loads(raw), "\n".join(handler.lines)


def _route_paths(application: object) -> set[str]:
    paths: set[str] = set()
    pending = list(getattr(application, "routes", ()))
    while pending:
        route = pending.pop()
        original = getattr(route, "original_router", None)
        if original is not None:
            pending.extend(original.routes)
            continue
        nested = getattr(route, "routes", None)
        if nested:
            pending.extend(nested)
        path = getattr(route, "path", None)
        if path is not None:
            paths.add(path)
    return paths


def _scan(folder: Path, log_text: str) -> list[str]:
    found: list[str] = []
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        for needle in NEEDLES:
            if needle.encode("utf-8") in data:
                found.append(f"{path.name}:{needle}")
    for needle in NEEDLES:
        if needle in log_text:
            found.append(f"log:{needle}")
    return found


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())
