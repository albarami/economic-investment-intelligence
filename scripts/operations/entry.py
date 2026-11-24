"""One loopback entry. Every request resolves a durably authorised route."""

from __future__ import annotations

import gzip
import http.client
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer
from typing import Any

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations.activation import active_route

LINE_LIMIT = 65_536  # bytes of one request line.
CHUNK = 65_536  # bytes of one relayed read.


class LoopbackServer(ThreadingHTTPServer):
    """Bind the numeric local address without the HTTP server's FQDN lookup."""

    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        self.server_name = str(self.server_address[0])
        self.server_port = int(self.server_address[1])


def handler(state: Path, host: str | None = None) -> type[BaseHTTPRequestHandler]:
    # The rules load here, so a process that only binds needs this file alone.
    from operations import remote
    from operations.common import Refusal

    class Entry(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = remote.READ_SECONDS

        def log_message(self, format: str, *args: object) -> None:
            # No URL, request body, address or upstream exception is logged.
            return None

        def head(self, status: int, headers: Sequence[tuple[str, str]]) -> None:
            """Every answer is one response on a connection that then closes."""
            phrase = HTTPStatus(status).phrase if status in set(HTTPStatus) else ""
            lines = [f"HTTP/1.1 {status} {phrase}"]
            lines += [name + ": " + value for name, value in headers]
            lines += ["Connection: close", "", ""]
            self.wfile.write("\r\n".join(lines).encode("latin-1"))

        def refuse(self, reason: str) -> None:
            """The entry's one closed body; nothing of the request is echoed."""
            body = remote.closed_body(reason)
            self.head(
                remote.STATUS[reason],
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store"),
                ],
            )
            if getattr(self, "command", None) != "HEAD":
                self.wfile.write(body)

        def send_error(
            self, code: int, message: str | None = None, explain: str | None = None
        ) -> None:
            # The standard library's own parse failures use the same writer.
            self.refuse("request_malformed")

        def handle_one_request(self) -> None:
            try:
                self.receive()
            except TimeoutError:
                self.silent(lambda: self.refuse("request_read_timeout"))
            except OSError:
                pass  # The client left; there is nobody to answer.
            finally:
                # One request per connection, whatever was or was not answered.
                self.close_connection = True

        def silent(self, write: Callable[[], None]) -> None:
            try:
                write()
            except OSError:
                pass

        def receive(self) -> None:
            self.raw_requestline = self.rfile.readline(LINE_LIMIT + 1)
            if not self.raw_requestline:
                return
            if len(self.raw_requestline) > LINE_LIMIT:
                self.refuse("request_malformed")
            elif self.parse_request():
                self.relay()

        def admit(self) -> Mapping[str, Any]:
            """Section 2: decided before Host, Origin or the target is read."""
            try:
                route = active_route(state)
                if (
                    route is None
                    or route["environment"] != "live"
                    or route["entry_port"] != 8088
                ):
                    raise Refusal("entry_route_unavailable")
                exposure, is_bound = route["exposure"], remote.bound(state)
            except Exception:
                raise Refusal("entry_route_unavailable") from None
            remote.admission(exposure, is_bound, host is not None)
            return route

        def rebuilt(self) -> Any:
            """Section 3: the one validated form; only it is sent upstream."""
            if self.request_version not in {"HTTP/1.0", "HTTP/1.1"}:
                raise Refusal("request_malformed")
            if self.headers.defects or self.headers.get_payload():
                raise Refusal("header_syntax_refused")
            target = self.requestline.split()[1]
            return remote.rebuild(self.command, target, self.headers.items(), host)

        def body(self, length: int) -> bytes:
            data = self.rfile.read(length) if length else b""
            if len(data) != length:
                raise Refusal("request_body_incomplete")
            return data

        def relay(self) -> None:
            try:
                route = self.admit()
                forward = self.rebuilt()
                body = self.body(forward.length)
            except Refusal as refusal:
                self.refuse(refusal.reason)
                return
            connection = http.client.HTTPConnection(
                "127.0.0.1", route["backend_port"], timeout=5
            )
            try:
                self.exchange(connection, route, forward, body)
            finally:
                connection.close()

        def exchange(
            self,
            connection: http.client.HTTPConnection,
            route: Mapping[str, Any],
            forward: Any,
            body: bytes,
        ) -> None:
            try:
                connection.putrequest(
                    forward.method,
                    forward.target,
                    skip_host=True,
                    skip_accept_encoding=True,
                )
                for name, value in forward.headers:
                    connection.putheader(name, value)
                if forward.method == "POST":
                    connection.putheader("Content-Length", str(forward.length))
                connection.endheaders(body or None)
                response = connection.getresponse()
                headers = remote.relay_headers(
                    response.getheaders(), route["exposure"] == "public_entry"
                )
                packed = (
                    gzip.compress(response.read(), mtime=0)
                    if remote.gzip_wanted(forward, response.status, headers)
                    else None
                )
            except Refusal as refusal:
                self.refuse(refusal.reason)
                return
            except Exception:
                self.refuse("entry_upstream_unavailable")
                return
            if packed is not None:
                self.head(response.status, remote.gzip_headers(headers, len(packed)))
                self.wfile.write(packed)
                return
            self.head(response.status, headers)
            self.stream(response)

        def stream(self, response: http.client.HTTPResponse) -> None:
            # Once headers are sent, a broken stream is closed, never replaced.
            try:
                while chunk := response.read1(CHUNK):
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except Exception:
                return

    return Entry


def prepared(environ: Mapping[str, str]) -> type[BaseHTTPRequestHandler]:
    """Read the environment and the verified route; return what this entry serves."""
    from operations import remote
    from operations.common import Refusal
    from operations.config import read_environment

    environ, raw_host = remote.take_host(
        {key: value for key, value in environ.items() if key != "EII_STORE"}
    )
    env = read_environment(environ)
    route = active_route(env.state)
    if (
        env.name != "live"
        or route is None
        or route["environment"] != "live"
        or route["entry_port"] != 8088
    ):
        raise Refusal("activation_target_mismatch")
    # A public route without a validated host never starts (remote_host_missing).
    return handler(env.state, remote.entry_host(route["exposure"], raw_host))


def main() -> int:
    # Arguments carry the owned-process nonce, never a host or credential.
    del sys.argv[1:]
    server = LoopbackServer(("127.0.0.1", 8088), prepared(os.environ))
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
