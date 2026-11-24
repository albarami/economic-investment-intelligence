"""One loopback entry. Every request resolves a durably authorised route."""

from __future__ import annotations

import http.client
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations.activation import active_route

HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


class LoopbackServer(ThreadingHTTPServer):
    """Bind the numeric local address without the HTTP server's FQDN lookup."""

    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        self.server_name = str(self.server_address[0])
        self.server_port = int(self.server_address[1])


def handler(state: Path) -> type[BaseHTTPRequestHandler]:
    class Entry(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            # No URL, request body, address or upstream exception is logged.
            return None

        def forward(self) -> None:
            if self.headers.get("Host", "").split(":", 1)[0] not in {
                "localhost",
                "127.0.0.1",
            }:
                self.send_error(403)
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {
                "http://localhost:8088",
                "http://127.0.0.1:8088",
            }:
                self.send_error(403)
                return
            connection = None
            sent = False
            try:
                route = active_route(state)
                if route is None:
                    raise ValueError
                connection = http.client.HTTPConnection(
                    "127.0.0.1", route["backend_port"], timeout=5
                )
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or self.headers.get("Transfer-Encoding"):
                    self.send_error(400)
                    return
                body = self.rfile.read(length) if length else None
                headers = {
                    k: v for k, v in self.headers.items() if k.lower() not in HOP
                }
                connection.request(self.command, self.path, body, headers)
                response = connection.getresponse()
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in HOP:
                        self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                sent = True
                self.close_connection = True
                while chunk := response.read1(65536):
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except Exception:
                # Once headers are sent, a broken stream is closed, never replaced.
                if not sent:
                    self.send_error(503)
                self.close_connection = True
            finally:
                if connection is not None:
                    connection.close()

        do_GET = forward
        do_POST = forward
        do_HEAD = forward
        do_OPTIONS = forward

    return Entry


def main() -> int:
    # Arguments carry the owned-process nonce, never a host or credential.
    del sys.argv[1:]
    from operations.common import Refusal
    from operations.config import read_environment

    env = read_environment(
        {key: value for key, value in os.environ.items() if key != "EII_STORE"}
    )
    state = env.state
    route = active_route(state)
    if (
        env.name != "live"
        or route is None
        or route["environment"] != "live"
        or route["entry_port"] != 8088
    ):
        raise Refusal("activation_target_mismatch")
    if route["exposure"] != "loopback":
        raise Refusal("public_entry_requires_s3_t20")
    server = LoopbackServer(("127.0.0.1", 8088), handler(state))
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
