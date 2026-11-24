"""Actual owned loopback child: readiness, PID binding, stop and released port."""

import http.client
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

import pytest

from operations.common import Refusal
from operations.deploy import health_probe
from operations.entry import LoopbackServer, handler
from operations.process import launch, require_owned, terminate, wait_ready


def test_one_entry_forwards_changed_identity_and_backend_then_rollback(tmp_path):
    servers = []
    threads = []

    def start(handler_class):
        server = LoopbackServer(("127.0.0.1", 0), handler_class)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        threads.append(thread)
        return server.server_address[1]

    def backend(identity):
        class Backend(BaseHTTPRequestHandler):
            def do_GET(self):
                body = identity.encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        return Backend

    first, second = "ab" * 32, "cd" * 32
    left, right = start(backend(first)), start(backend(second))
    # S3-T20: the entry requires a verified live route with a known exposure.
    selected = dict(
        backend_port=left, environment="live", entry_port=8088, exposure="loopback"
    )
    with patch("operations.entry.active_route", side_effect=lambda _: selected):
        entry = start(handler(tmp_path))

        def read():
            connection = http.client.HTTPConnection("127.0.0.1", entry, timeout=2)
            try:
                connection.request(
                    "GET", "/api/release", headers={"Host": "localhost:8088"}
                )
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()

        try:
            assert read() == (200, first.encode())
            selected["backend_port"] = right
            assert read() == (200, second.encode())
            selected["backend_port"] = left
            assert read() == (200, first.encode())
            servers[0].shutdown()
            servers[0].server_close()
            assert read() == (
                503,
                b'{"error_code":"entry_upstream_unavailable","status":"entry_refused"}',
            )
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=2)
                assert not thread.is_alive()


def test_owned_child_ready_and_shutdown_without_signalling_a_foreign_record(tmp_path):
    application = tmp_path / "INVENTED-application"
    script = application / "scripts/operations/serve.py"
    script.parent.mkdir(parents=True)
    source = Path(__file__).resolve().parents[2] / "scripts/operations"
    for name in (
        "__init__.py",
        "entry.py",
        "activation.py",
        "common.py",
        "config.py",
        "evidence.py",
    ):
        (script.parent / name).write_bytes((source / name).read_bytes())
    identity = "ab" * 32
    nonce = "operation-INVENTED-nonce"
    health = dict(
        status="ok",
        store="postgres",
        postgres="up",
        release_id=identity,
        release_hash=identity,
        parity="identical",
        ledger="local",
        local_ledger_rows=0,
        model="template",
        traffic="simulated",
        tiles="ok",
        fonts="ok",
        replays="ok",
    )
    script.write_text(
        """import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operations.entry import LoopbackServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = BODY
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
BODY = """
        + repr(json.dumps(health).encode())
        + """
LoopbackServer(("127.0.0.1", int(sys.argv[sys.argv.index("--port")+1])), Handler).serve_forever()
"""
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    state = tmp_path / "live/state"
    state.mkdir(parents=True)
    argv = (
        sys.executable,
        "-I",
        "-B",
        "-S",
        "scripts/operations/serve.py",
        "--nonce",
        nonce,
        "--environment",
        "live",
        "--port",
        str(port),
        "--release-id",
        identity,
        "--application-sha256",
        "cd" * 32,
    )
    record = launch(
        application,
        state / "process.json",
        argv,
        dict(
            {
                key: value
                for key, value in os.environ.items()
                if key in {"PATH", "HOME", "LANG", "LC_ALL"}
            },
            EII_ENVIRONMENT="live",
            EII_STATE_DIR=str(state),
        ),
        environment="live",
        nonce=nonce,
        port=port,
        release_id=identity,
        application_sha256="cd" * 32,
    )
    try:
        require_owned(record, "live")
        wait_ready(record, "live", health_probe)
        with patch("operations.process.signal.pidfd_send_signal") as signal:
            with pytest.raises(Refusal, match="process_identity_mismatch"):
                terminate(dict(record, start_ticks="INVENTED-reused-pid"), "live")
            signal.assert_not_called()
        assert health_probe(port, 1.0)["release_id"] == identity
    finally:
        terminate(record, "live")
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
