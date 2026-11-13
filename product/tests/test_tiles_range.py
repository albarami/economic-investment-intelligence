"""HTTP byte-range tests for the tile spike API."""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

from eii_product.api.app import create_app
from eii_product.api.tiles import build_router

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "tiles"
SPIKE_PATH = FIXTURE_DIR / "spike.tile"
PINNED_SPIKE_SIZE = 2048
PINNED_SPIKE_SHA256 = "9321e6f1ce8c82770c4e45387f972cf8d1b57278c45cd63f4a817b4d1808a3de"
SPIKE_BYTES = SPIKE_PATH.read_bytes()
SPIKE_SIZE = PINNED_SPIKE_SIZE


def _route_paths(application: FastAPI) -> set[str]:
    paths: set[str] = set()
    pending = list(application.routes)
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


def _request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, headers=headers or {})
    response = conn.getresponse()
    body = response.read()
    header_map = {k.lower(): v for k, v in response.getheaders()}
    conn.close()
    return response.status, header_map, body


@pytest.fixture(scope="module")
def tile_server() -> Iterator[int]:
    app = create_app(FIXTURE_DIR)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = Config(app, host="127.0.0.1", port=port, log_level="error")
    server = Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            status, _, _ = _request(port, "GET", "/tiles")
            if status == 200:
                break
        except (TimeoutError, OSError, http.client.HTTPException):
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("tile server did not answer on /tiles")

    yield port

    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive()


def test_full_request_returns_the_pinned_fixture(tile_server: int) -> None:
    on_disk = SPIKE_PATH.read_bytes()
    assert len(on_disk) == PINNED_SPIKE_SIZE
    assert hashlib.sha256(on_disk).hexdigest() == PINNED_SPIKE_SHA256

    status, headers, body = _request(tile_server, "GET", "/tiles/spike.tile")
    assert status == 200
    assert headers.get("content-type", "").startswith("application/octet-stream")
    assert headers.get("content-length") == str(SPIKE_SIZE)
    assert headers.get("accept-ranges") == "bytes"
    assert body == on_disk
    assert hashlib.sha256(body).hexdigest() == PINNED_SPIKE_SHA256


def test_valid_ranges_return_the_expected_bytes(tile_server: int) -> None:
    cases: list[tuple[str, str, str, bytes]] = [
        ("bytes=0-0", "bytes 0-0/2048", "1", SPIKE_BYTES[0:1]),
        ("bytes=10-19", "bytes 10-19/2048", "10", SPIKE_BYTES[10:20]),
        ("bytes=2047-2047", "bytes 2047-2047/2048", "1", SPIKE_BYTES[2047:2048]),
        ("bytes=100-", "bytes 100-2047/2048", str(SPIKE_SIZE - 100), SPIKE_BYTES[100:]),
        ("bytes=-16", "bytes 2032-2047/2048", "16", SPIKE_BYTES[-16:]),
        ("bytes=2000-3000", "bytes 2000-2047/2048", "48", SPIKE_BYTES[2000:]),
    ]
    # Valid multi-range request (RFC 9110); the server answers 206 with two parts.
    status, headers, body = _request(
        tile_server,
        "GET",
        "/tiles/spike.tile",
        headers={"Range": "bytes=0-1,4-5"},
    )
    assert status == 206
    assert headers.get("content-type", "").startswith("multipart/byteranges")
    assert b"bytes 0-1/2048" in body
    assert b"bytes 4-5/2048" in body
    assert SPIKE_BYTES[0:2] in body
    assert SPIKE_BYTES[4:6] in body

    for range_header, content_range, length, expected in cases:
        status, headers, body = _request(
            tile_server,
            "GET",
            "/tiles/spike.tile",
            headers={"Range": range_header},
        )
        assert status == 206, range_header
        assert headers.get("content-range") == content_range
        assert headers.get("content-length") == length
        assert body == expected


def test_invalid_ranges_fail_safely_and_the_server_survives(tile_server: int) -> None:
    status, headers, body = _request(
        tile_server,
        "GET",
        "/tiles/spike.tile",
        headers={"Range": f"bytes={SPIKE_SIZE}-"},
    )
    assert status == 416
    assert headers.get("content-range") == f"bytes */{SPIKE_SIZE}"
    assert SPIKE_BYTES[:32] not in body

    for bad in ("bytes=abc", "bytes=9-2"):
        status, _, body = _request(
            tile_server,
            "GET",
            "/tiles/spike.tile",
            headers={"Range": bad},
        )
        assert status == 400, bad
        assert SPIKE_BYTES[:32] not in body

        ok_status, _, ok_body = _request(tile_server, "GET", "/tiles/spike.tile")
        assert ok_status == 200
        assert ok_body == SPIKE_BYTES

    ok_status, _, ok_body = _request(tile_server, "GET", "/tiles/spike.tile")
    assert ok_status == 200
    assert ok_body == SPIKE_BYTES


def test_regular_files_with_invalid_tile_names_return_404(tile_server: int) -> None:
    """Names outside the closed tile form must not be served."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    with tempfile.TemporaryDirectory() as tmp:
        tile_dir = Path(tmp)
        (tile_dir / "spike.tile").write_bytes(SPIKE_BYTES)
        secret_upper = b"synth-upper-case-payload"
        (tile_dir / "Upper.tile").write_bytes(secret_upper)
        secret_other_end = b"synth-wrong-suffix-payload"
        (tile_dir / "otherend.txt").write_bytes(secret_other_end)

        config = Config(
            create_app(tile_dir),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
        server = Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    probe_status, _, _ = _request(port, "GET", "/tiles/spike.tile")
                    if probe_status == 200:
                        break
                except (TimeoutError, OSError):
                    time.sleep(0.05)
            else:
                raise RuntimeError("invalid-name server did not start")

            for path in ("/tiles/Upper.tile", "/tiles/otherend.txt"):
                status, _, body = _request(port, "GET", path)
                assert status == 404, path
                assert secret_upper not in body
                assert secret_other_end not in body
                assert SPIKE_BYTES[:32] not in body
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def test_a_tile_named_directory_returns_404_not_5xx(tile_server: int) -> None:
    """A directory whose name matches the tile suffix must answer 404."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    with tempfile.TemporaryDirectory() as tmp:
        tile_dir = Path(tmp)
        (tile_dir / "spike.tile").write_bytes(SPIKE_BYTES)
        folder_name = "synthdir.tile"
        (tile_dir / folder_name).mkdir()
        (tile_dir / folder_name / "inner.bin").write_bytes(b"nested-bytes")

        config = Config(
            create_app(tile_dir),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
        server = Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    probe_status, _, _ = _request(port, "GET", "/tiles/spike.tile")
                    if probe_status == 200:
                        break
                except (TimeoutError, OSError):
                    time.sleep(0.05)
            else:
                raise RuntimeError("folder tile server did not start")

            status, _, body = _request(port, "GET", f"/tiles/{folder_name}")
            assert status == 404
            assert status < 500
            assert b"nested-bytes" not in body
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def test_requests_outside_the_tile_directory_are_refused(tile_server: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        outside = Path(tmp) / "outside.txt"
        outside.write_text("secret-outside", encoding="ascii")
        secret = outside.read_bytes()

        for path in (
            "/tiles/..%2Foutside.txt",
            "/tiles/..%2F..%2Fetc%2Fpasswd",
            "/tiles/%2Ftmp%2Fevil.tile",
        ):
            status, _, body = _request(tile_server, "GET", path)
            assert status == 404
            assert secret not in body

        with tempfile.TemporaryDirectory() as link_tmp:
            tile_dir = Path(link_tmp)
            (tile_dir / "spike.tile").write_bytes(SPIKE_BYTES)
            link = tile_dir / "link.tile"
            link.symlink_to(outside)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            config = Config(
                create_app(tile_dir),
                host="127.0.0.1",
                port=port,
                log_level="error",
            )
            server = Server(config)
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    try:
                        status, _, body = _request(port, "GET", "/tiles/link.tile")
                        if status in (200, 404):
                            break
                    except (TimeoutError, OSError):
                        time.sleep(0.05)
                else:
                    raise RuntimeError("link server did not start")
                assert status == 404
                assert secret not in body
            finally:
                server.should_exit = True
                thread.join(timeout=5)


def _response_has_forbidden_headers(status: int, headers: dict[str, str]) -> None:
    assert "access-control-allow-origin" not in headers
    assert "location" not in headers
    for value in headers.values():
        assert "://" not in value


def test_the_api_app_serves_the_tile_and_the_status(tile_server: int) -> None:
    status, headers, body = _request(tile_server, "GET", "/tiles/spike.tile")
    assert status == 200
    _response_has_forbidden_headers(status, headers)

    status, headers, body = _request(tile_server, "GET", "/tiles")
    assert status == 200
    payload = json.loads(body.decode("utf-8"))
    assert payload["tiles"] == "ok"
    assert not any(ch.isdigit() for ch in payload["tiles"])
    _response_has_forbidden_headers(status, headers)

    with tempfile.TemporaryDirectory() as tmp:
        tile_dir = Path(tmp)
        (tile_dir / "spike.tile").write_bytes(b"x")
        cors_app = FastAPI(docs_url=None, redoc_url=None)
        cors_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET"],
        )
        cors_app.include_router(build_router(tile_dir))
        paths = _route_paths(cors_app)
        assert "/tiles/{name}" in paths
        assert "/tiles" in paths

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        config = Config(cors_app, host="127.0.0.1", port=port, log_level="error")
        server = Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    st, hdrs, _ = _request(
                        port,
                        "GET",
                        "/tiles/spike.tile",
                        headers={"Origin": "http://cross-origin.invalid"},
                    )
                    if st == 200:
                        break
                except (TimeoutError, OSError):
                    time.sleep(0.05)
            else:
                raise RuntimeError("cors server did not start")
            assert hdrs.get("access-control-allow-origin") == "*"
            with pytest.raises(AssertionError):
                _response_has_forbidden_headers(st, hdrs)
        finally:
            server.should_exit = True
            thread.join(timeout=5)

    paths = _route_paths(create_app(FIXTURE_DIR))
    assert "/tiles/{name}" in paths
    assert "/tiles" in paths
