"""S3-T20 entry: raw requests on the real handler over real live states.

Every refusal case changes one thing in a served request, asserts the entry's
exact closed body and proves the invented upstream was not reached.
"""

from __future__ import annotations

import gzip
import socket
import threading
import time
from collections.abc import Sequence
from functools import partial
from http.server import BaseHTTPRequestHandler
from typing import Any
from unittest.mock import patch

from s3_t20_support import (
    LOCAL,
    REMOTE,
    EntryCase,
    LiveState,
    Upstream,
    dead_port,
    edited,
    lowered,
    message,
    parsed,
    reply,
    wire,
)

from operations import entry, remote, serve
from operations.activation import active_route

HOST = b"Host: localhost:8088\r\n"
START = b"GET / HTTP/1.1\r\n"
ORIGIN = ("Origin", "https://" + REMOTE)
FORWARDING = (
    ("Forwarded", "for=192.0.2.7;proto=https"),
    ("X-Forwarded-For", "192.0.2.7"),
    ("X-Forwarded-Proto", "https"),
    ("X-Forwarded-Host", "third.s3-t20.invalid"),
)


def answered(
    status: int,
    headers: Sequence[tuple[str, str]],
    body: bytes,
    handler: BaseHTTPRequestHandler,
    seen: dict[str, Any],
) -> None:
    """An invented upstream answer, bound by ``partial`` to one case."""
    reply(handler, status, headers, body)


# One changed thing per case, on the unbound loopback entry.
FRAMING: tuple[tuple[str, bytes, str], ...] = (
    ("folded value", START + HOST + b"X-A: a\r\n b\r\n\r\n", "header_syntax_refused"),
    ("no colon", START + HOST + b"X-NoColon\r\n\r\n", "header_syntax_refused"),
    ("space in name", START + HOST + b"X Bad: v\r\n\r\n", "header_syntax_refused"),
    (
        "space before colon",
        START + b"Host : localhost:8088\r\n\r\n",
        "header_syntax_refused",
    ),
    (
        "leading space",
        START + b" Host: localhost:8088\r\n\r\n",
        "header_syntax_refused",
    ),
    ("empty name", START + HOST + b": v\r\n\r\n", "header_syntax_refused"),
    (
        "control in value",
        START + HOST + b"X-A: a\x00b\r\n\r\n",
        "header_syntax_refused",
    ),
    ("bare return", START + HOST + b"X-A: a\rb\r\n\r\n", "header_syntax_refused"),
    ("no request line words", b"GARBAGE\r\n\r\n", "request_malformed"),
    ("four words", b"GET / x HTTP/1.1\r\n" + HOST + b"\r\n", "request_malformed"),
    ("version 0.9", b"GET /\r\n", "request_malformed"),
    ("version 2.0", b"GET / HTTP/2.0\r\n" + HOST + b"\r\n", "request_malformed"),
    ("version 1.2", b"GET / HTTP/1.2\r\n" + HOST + b"\r\n", "request_malformed"),
    (
        "line one byte over the limit, complete",
        b"GET /" + b"a" * (entry.LINE_LIMIT - 15) + b" HTTP/1.1\r\n" + HOST + b"\r\n",
        "request_malformed",
    ),
    (
        "line over the limit",
        b"GET /" + b"a" * (entry.LINE_LIMIT + 1) + b" HTTP/1.1\r\n" + HOST + b"\r\n",
        "request_malformed",
    ),
    (
        "too many headers",
        START + HOST + b"".join(b"X-%d: v\r\n" % i for i in range(101)) + b"\r\n",
        "request_malformed",
    ),
    ("unknown method", b"BREW / HTTP/1.1\r\n" + HOST + b"\r\n", "method_refused"),
    (
        "connect",
        b"CONNECT localhost:8088 HTTP/1.1\r\n" + HOST + b"\r\n",
        "method_refused",
    ),
    ("put", b"PUT / HTTP/1.1\r\n" + HOST + b"\r\n", "method_refused"),
    ("no host", START + b"\r\n", "host_header_invalid"),
    ("two hosts", START + HOST + HOST + b"\r\n", "host_header_invalid"),
    (
        "two origins",
        START + HOST + b"Origin: http://localhost:8088\r\n" * 2 + b"\r\n",
        "origin_header_invalid",
    ),
    (
        "absolute form",
        b"GET http://third.s3-t20.invalid/ HTTP/1.1\r\n" + HOST + b"\r\n",
        "target_form_refused",
    ),
    (
        "asterisk form",
        b"OPTIONS * HTTP/1.1\r\n" + HOST + b"\r\n",
        "target_form_refused",
    ),
    (
        "dot segment",
        b"GET /a/../b HTTP/1.1\r\n" + HOST + b"\r\n",
        "target_path_refused",
    ),
    (
        "encoded slash",
        b"GET /a%2Fb HTTP/1.1\r\n" + HOST + b"\r\n",
        "target_path_refused",
    ),
    ("empty segment", b"GET //a HTTP/1.1\r\n" + HOST + b"\r\n", "target_path_refused"),
    (
        "raw non-ASCII",
        "GET /café HTTP/1.1\r\n".encode() + HOST + b"\r\n",
        "target_path_refused",
    ),
    (
        "transfer encoding",
        START + HOST + b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
        "transfer_encoding_refused",
    ),
    (
        "two lengths",
        START + HOST + b"Content-Length: 0\r\nContent-Length: 0\r\n\r\n",
        "content_length_invalid",
    ),
    (
        "body on GET",
        START + HOST + b"Content-Length: 2\r\n\r\nab",
        "request_body_refused",
    ),
)


def post(headers: Sequence[tuple[str, str]], body: bytes, length: str | None) -> bytes:
    sent = [("Host", LOCAL), ("Origin", "http://" + LOCAL), *headers]
    if length is not None:
        sent.append(("Content-Length", length))
    return message("POST", "/api/x", sent, body)


def cookies(answer: bytes) -> list[str]:
    return [value for name, value in lowered(parsed(answer)[1]) if name == "set-cookie"]


def field(answer: bytes, wanted: str) -> list[str]:
    return [value for name, value in lowered(parsed(answer)[1]) if name == wanted]


class Loopback(EntryCase):
    """Row 4: an unbound state and an entry started without a host."""

    def setUp(self) -> None:
        super().setUp()
        self.live = LiveState(self)
        self.upstream = Upstream(self)
        self.port = self.serve_entry(self.live.state, None, self.upstream)

    def test_served_request_is_rebuilt(self) -> None:
        answer = wire(self.port, message("GET", "/a%41/b?x=%2F&y=1"))
        self.assertEqual(parsed(answer)[0], 200)
        seen = self.upstream.requests[-1]
        self.assertEqual((seen["method"], seen["target"]), ("GET", "/aA/b?x=%2F&y=1"))
        body = b"{}" * 10
        answer = wire(self.port, post([], body, str(len(body))))
        self.assertEqual(parsed(answer)[0], 200)
        seen = self.upstream.requests[-1]
        self.assertEqual((seen["method"], seen["body"]), ("POST", body))

    def test_request_line_at_the_limit_is_served(self) -> None:
        line = b"GET /" + b"a" * (entry.LINE_LIMIT - 16) + b" HTTP/1.1\r\n"
        self.assertEqual(len(line), entry.LINE_LIMIT)
        self.assertEqual(parsed(wire(self.port, line + HOST + b"\r\n"))[0], 200)
        self.assertEqual(len(self.upstream.requests), 1)

    def test_each_framing_refusal_reaches_no_upstream(self) -> None:
        for label, data, reason in FRAMING:
            with self.subTest(label=label):
                self.refused(wire(self.port, data, half_close=True), reason)
        self.assertEqual(self.upstream.requests, [])

    def test_body_refusals(self) -> None:
        limit = remote.BODY_LIMIT
        for label, data, reason in (
            ("no length", post([], b"", None), "content_length_invalid"),
            ("signed", post([], b"", "+0"), "content_length_invalid"),
            ("over the limit", post([], b"", str(limit + 1)), "request_body_too_large"),
            ("short body", post([], b"ab", "5"), "request_body_incomplete"),
            (
                "no origin",
                message("POST", "/api/x", [("Host", LOCAL), ("Content-Length", "0")]),
                "origin_refused",
            ),
        ):
            with self.subTest(label=label):
                self.refused(wire(self.port, data, half_close=True), reason)
        self.assertEqual(self.upstream.requests, [])
        answer = wire(self.port, post([], b"a" * limit, str(limit)))
        self.assertEqual(parsed(answer)[0], 200)
        self.assertEqual(len(self.upstream.requests[-1]["body"]), limit)

    def test_silent_client_times_out(self) -> None:
        with patch("operations.remote.READ_SECONDS", 0.3):
            port = self.serve_entry(self.live.state, None, self.upstream)
        for label, data in (
            ("request line", b"GET / HT"),
            ("headers", START + HOST),
            ("body", post([], b"ab", "5")),
        ):
            with self.subTest(label=label):
                self.refused(wire(port, data), "request_read_timeout")
        self.assertEqual(self.upstream.requests, [])
        self.assertEqual(remote.READ_SECONDS, 10.0)

    def test_one_request_per_connection(self) -> None:
        answer = wire(self.port, message("GET", "/one") + message("GET", "/two"))
        self.assertEqual(answer.count(b"HTTP/1.1 "), 1)
        self.assertEqual(field(answer, "connection"), ["close"])
        self.assertEqual([seen["target"] for seen in self.upstream.requests], ["/one"])

    def test_refusal_shape(self) -> None:
        answer = wire(self.port, message("HEAD", "/a%2Fb"))
        code, headers, body = parsed(answer)
        self.assertEqual((code, body), (400, b""))
        self.assertIn(("cache-control", "no-store"), lowered(headers))
        self.assertIn(("connection", "close"), lowered(headers))
        answer = wire(self.port, message("GET", "/a%2Fb?secret=INVENTED-echo"))
        self.assertNotIn(b"INVENTED-echo", answer)
        self.assertEqual(field(answer, "content-type"), ["application/json"])

    def test_third_host_refused(self) -> None:
        for host in (
            REMOTE,
            "third.s3-t20.invalid",
            "127.0.0.1:8088",
            "[::1]:8088",
            "LOCALHOST:8088",
            "localhost",
            "localhost:8088.",
        ):
            with self.subTest(host=host):
                self.refused(
                    wire(self.port, message(headers=[("Host", host)])), "host_refused"
                )
        self.assertEqual(self.upstream.requests, [])

    def test_presenter_refused_on_entry_socket_with_localhost_host(self) -> None:
        # The upstream answers as if EII_PRESENTER were on; nothing reaches it.
        for target, extra in (
            ("/api/presenter/state", []),
            ("/api/%50resenter/state", []),
            ("/api/release", [("X-EII-Presenter-Token", "INVENTED")]),
        ):
            for method in ("GET", "POST"):
                headers = [("Host", LOCAL), ("Origin", "http://" + LOCAL), *extra]
                if method == "POST":
                    headers.append(("Content-Length", "0"))
                with self.subTest(target=target, method=method):
                    self.refused(
                        wire(self.port, message(method, target, headers)),
                        "presenter_remote_refused",
                    )
        self.assertEqual(self.upstream.requests, [])

    def test_upstream_down_and_route_unavailable(self) -> None:
        port = self.serve_entry(self.live.state, None, dead_port())
        self.refused(wire(port, message()), "entry_upstream_unavailable")
        empty = self.root / "empty-state"
        empty.mkdir()
        self.refused(
            wire(self.serve_entry(empty, None, self.upstream), message()),
            "entry_route_unavailable",
        )
        real = active_route(self.live.state)
        assert real is not None
        for label, planted in (
            ("staging", dict(real, environment="staging")),
            ("other entry port", dict(real, entry_port=8089)),
            ("unknown exposure", dict(real, exposure="public")),
            ("no exposure", {k: v for k, v in real.items() if k != "exposure"}),
        ):
            with (
                self.subTest(label=label),
                patch("operations.entry.active_route", return_value=planted),
            ):
                self.refused(wire(self.port, message()), "entry_route_unavailable")
        log = self.live.state / "promotions.jsonl"
        log.write_bytes(log.read_bytes().replace(b'"lead"', b'"LEAD"', 1))
        self.refused(wire(self.port, message()), "entry_route_unavailable")
        self.assertEqual(self.upstream.requests, [])

    def test_loopback_cookies_unchanged(self) -> None:
        self.upstream.answer = lambda handler, seen: reply(
            handler, 200, [("Set-Cookie", "a=b; Path=/"), ("Set-Cookie", "c=d")], b"ok"
        )
        self.assertEqual(cookies(wire(self.port, message())), ["a=b; Path=/", "c=d"])


class Public(EntryCase):
    """Row 1: a public route and an entry holding the validated host."""

    def setUp(self) -> None:
        super().setUp()
        self.live = LiveState(self)
        self.live.expose()
        self.upstream = Upstream(self)
        self.port = self.serve_entry(self.live.state, REMOTE, self.upstream)

    def get(self, *extra: tuple[str, str], target: str = "/", port: int = 0) -> bytes:
        return wire(
            port or self.port, message("GET", target, [("Host", REMOTE), *extra])
        )

    def test_both_host_forms_served(self) -> None:
        for host in (LOCAL, REMOTE, REMOTE + ":443"):
            with self.subTest(host=host):
                answer = wire(self.port, message(headers=[("Host", host)]))
                self.assertEqual(parsed(answer)[0], 200)
        self.assertEqual(len(self.upstream.requests), 3)

    def test_third_host_refused(self) -> None:
        for host in (
            "third.s3-t20.invalid",
            REMOTE + ":8443",
            REMOTE + ".",
            "127.0.0.1:8088",
        ):
            with self.subTest(host=host):
                self.refused(
                    wire(self.port, message(headers=[("Host", host)])), "host_refused"
                )
        self.assertEqual(self.upstream.requests, [])

    def test_third_origin_refused(self) -> None:
        for origin in (
            "https://third.s3-t20.invalid",
            "http://" + REMOTE,
            "http://" + LOCAL,
            "null",
        ):
            for method in ("GET", "POST"):
                headers = [
                    ("Host", REMOTE),
                    ("Origin", origin),
                    ("Content-Length", "0"),
                ]
                with self.subTest(origin=origin, method=method):
                    self.refused(
                        wire(
                            self.port,
                            message(
                                method, "/api/x", headers[: 2 + (method == "POST")]
                            ),
                        ),
                        "origin_refused",
                    )
        self.assertEqual(self.upstream.requests, [])
        accepted = [("Host", REMOTE), ORIGIN, ("Content-Length", "0")]
        self.assertEqual(
            parsed(wire(self.port, message("POST", "/api/x", accepted)))[0], 200
        )

    def test_presenter_refused_through_remote_host(self) -> None:
        for host in (REMOTE, REMOTE + ":443", LOCAL):
            for target, extra in (
                ("/api/presenter/state", []),
                ("/api/PRESENTER/state", []),
                ("/api/release", [("x-eii-presenter-token", "INVENTED")]),
            ):
                with self.subTest(host=host, target=target):
                    self.refused(
                        wire(
                            self.port, message("GET", target, [("Host", host), *extra])
                        ),
                        "presenter_remote_refused",
                    )
        self.assertEqual(self.upstream.requests, [])

    def planted(self, function: Any, old: str, new: str) -> int:
        """An entry whose one named rule was changed at one source site."""
        mutant = edited(function, old, new)
        patcher = patch("operations.remote." + function.__name__, mutant)
        patcher.start()
        self.addCleanup(patcher.stop)
        return self.serve_entry(self.live.state, REMOTE, self.upstream)

    def test_cookie_without_secure_fails(self) -> None:
        sent = [
            "eii_session=INVENTED; HttpOnly; SameSite=Strict; Path=/",
            "second=INVENTED; SameSite=Lax",
            "third=INVENTED; samesite=strict; secure",
        ]
        self.upstream.answer = lambda handler, seen: reply(
            handler, 200, [("Set-Cookie", value) for value in sent], b"ok"
        )

        def insecure(answer: bytes) -> list[str]:
            return [c for c in cookies(answer) if "secure" not in c.lower().split("; ")]

        answer = self.get()
        self.assertEqual(len(cookies(answer)), 3)
        self.assertEqual(insecure(answer), [])
        # Plant: the entry stops adding Secure; the same check finds the cookies.
        port = self.planted(
            remote.response_cookies,
            'cookie if "secure" in attributes else cookie + "; Secure"',
            "cookie",
        )
        self.assertEqual(insecure(self.get(port=port)), sent[:2])

    def test_cookie_without_samesite_fails(self) -> None:
        good = "eii_session=INVENTED; HttpOnly; SameSite=Strict; Path=/"
        for bad in (
            "planted=INVENTED; Secure",
            "planted=INVENTED; SameSite=None; Secure",
        ):
            pair = [("Set-Cookie", good), ("Set-Cookie", bad)]
            self.upstream.answer = partial(answered, 200, pair, b"ok")
            with self.subTest(bad=bad):
                answer = self.get()
                self.refused(answer, "cookie_policy_refused")
                self.assertEqual(cookies(answer), [])
        # Plant: the SameSite guard alone is removed; the cookie crosses.
        port = self.planted(
            remote.response_cookies, 'raise Refusal("cookie_policy_refused")', "pass"
        )
        self.assertEqual(len(cookies(self.get(port=port))), 2)

    def test_gzip_negotiated_and_equal_after_decompression(self) -> None:
        page = ("<p>INVENTED " * 400).encode()
        self.upstream.answer = lambda handler, seen: reply(
            handler, 200, [("Content-Type", "text/html; charset=utf-8")], page
        )
        packed = self.get(("Accept-Encoding", "br, gzip"))
        self.assertEqual(field(packed, "content-encoding"), ["gzip"])
        self.assertLess(len(parsed(packed)[2]), len(page))
        self.assertEqual(gzip.decompress(parsed(packed)[2]), page)
        plain = self.get()
        self.assertEqual(field(plain, "content-encoding"), [])
        self.assertEqual(parsed(plain)[2], page)
        refused = self.get(("Accept-Encoding", "gzip;q=0"))
        self.assertEqual(parsed(refused)[2], page)

    def test_gzip_length_and_vary(self) -> None:
        page = b"body { color: black }" * 200
        self.upstream.answer = lambda handler, seen: reply(
            handler, 200, [("Content-Type", "text/css"), ("Vary", "Cookie")], page
        )
        answer = self.get(("Accept-Encoding", "gzip"))
        self.assertEqual(field(answer, "content-length"), [str(len(parsed(answer)[2]))])
        self.assertEqual(field(answer, "vary"), ["Cookie, Accept-Encoding"])
        self.assertEqual(self.get(("Accept-Encoding", "gzip")), answer)

    def test_no_gzip_for_stream_range_or_encoded(self) -> None:
        page = b"INVENTED " * 400
        asked = ("Accept-Encoding", "gzip")
        for label, status, headers, extra in (
            ("stream", 200, [("Content-Type", "text/event-stream")], ()),
            (
                "range",
                206,
                [("Content-Type", "text/html"), ("Content-Range", "bytes 0-3599/3600")],
                (("Range", "bytes=0-3599"),),
            ),
            (
                "range asked",
                200,
                [("Content-Type", "text/html")],
                (("Range", "bytes=0-"),),
            ),
            (
                "encoded",
                200,
                [("Content-Type", "text/html"), ("Content-Encoding", "br")],
                (),
            ),
            ("tile", 200, [("Content-Type", "application/x-protobuf")], ()),
            ("missing", 404, [("Content-Type", "text/html")], ()),
        ):
            self.upstream.answer = partial(answered, status, headers, page)
            with self.subTest(label=label):
                answer = self.get(asked, *extra)
                self.assertEqual(parsed(answer)[0], status)
                self.assertNotIn("gzip", field(answer, "content-encoding"))
                self.assertEqual(parsed(answer)[2], page)

    def test_stream_first_frame_before_second(self) -> None:
        first, second = b"event: one\ndata: 1\n\n", b"event: two\ndata: 2\n\n"
        release = threading.Event()

        def answer(handler: BaseHTTPRequestHandler, seen: dict[str, Any]) -> None:
            handler.send_response_only(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.wfile.write(first)
            handler.wfile.flush()
            release.wait(10)
            handler.wfile.write(second)

        self.upstream.answer = answer
        sent = message(headers=[("Host", REMOTE), ("Accept-Encoding", "gzip")])
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as client:
            client.sendall(sent)
            seen = b""
            while first not in seen:
                chunk = client.recv(65_536)
                self.assertTrue(chunk, "the entry closed before the first frame")
                seen += chunk
            # The first frame arrived while the upstream still holds the second.
            self.assertNotIn(second, seen)
            self.assertFalse(release.is_set())
            release.set()
            while chunk := client.recv(65_536):
                seen += chunk
        self.assertTrue(seen.endswith(first + second))
        self.assertEqual(field(seen, "content-length"), [])

    def test_entry_strips_forwarding_headers(self) -> None:
        dropped = {name.lower() for name, _ in FORWARDING}
        self.assertEqual(parsed(self.get(*FORWARDING, ("X-Kept", "1")))[0], 200)
        self.assertEqual(self.upstream.names() & dropped, set())
        self.assertIn("x-kept", self.upstream.names())
        nominated = self.get(("Connection", "X-Kept, close"), ("X-Kept", "1"))
        self.assertEqual(parsed(nominated)[0], 200)
        self.assertNotIn("x-kept", self.upstream.names())
        # Plant: the entry's drop of forwarding headers alone is removed.
        port = self.planted(
            remote.forward_headers,
            ' and not name.lower().startswith("x-forwarded-")',
            "",
        )
        self.get(*FORWARDING, port=port)
        self.assertEqual(
            self.upstream.names() & dropped,
            {"x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"},
        )


class Server(EntryCase):
    """D2, second half: no entry in the path; the server trusts no proxy header."""

    def observed(self, options: dict[str, Any]) -> tuple[Any, Any]:
        import uvicorn

        seen: list[tuple[Any, Any]] = []

        async def application(scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] != "http":
                return
            seen.append((scope["client"][0], scope["scheme"]))
            await send(dict(type="http.response.start", status=200, headers=[]))
            await send(dict(type="http.response.body", body=b"ok"))

        server = uvicorn.Server(uvicorn.Config(application, **options))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        def stop() -> None:
            server.should_exit = True
            thread.join(10)

        self.addCleanup(stop)
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(server.started)
        sent = [
            ("Host", LOCAL),
            ("X-Forwarded-For", "192.0.2.7"),
            ("X-Forwarded-Proto", "https"),
        ]
        answer = wire(
            options["port"], message(headers=[*sent, ("Connection", "close")])
        )
        self.assertEqual(parsed(answer)[0], 200)
        return seen[-1]

    def test_server_ignores_forwarding_headers(self) -> None:
        options = serve.server_options(dead_port())
        self.assertIs(options["proxy_headers"], False)
        self.assertEqual(options["host"], "127.0.0.1")
        self.assertEqual(self.observed(options), ("127.0.0.1", "http"))
        # Plant: the explicit off option alone is removed.
        mutant = edited(serve.server_options, "proxy_headers=False,", "")
        planted = mutant(dead_port())
        self.assertNotIn("proxy_headers", planted)
        self.assertEqual(self.observed(planted), ("192.0.2.7", "https"))
