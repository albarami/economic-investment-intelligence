"""S3-T20 pure rules: one negative per refusal, guard deletions and properties.

Each negative changes one input of a valid call and asserts the specific
closed reason; ``guard_red`` then deletes that one raise in a compiled copy and
proves the negative no longer holds. Hosts are invented ``.invalid`` names.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from urllib.parse import quote

from hypothesis import given, settings
from hypothesis import strategies as st
from s3_t20_support import LOCAL, REMOTE, EntryCase, LiveState
from s3_t28_support import ROOT

from operations import entry, remote
from operations.common import Refusal

VALID = [("Host", REMOTE), ("Accept", "text/html")]
POST = [("Host", REMOTE), ("Origin", "https://" + REMOTE), ("Content-Length", "2")]

HOSTS_INVALID = (
    "entry",
    "localhost",
    "entry.localhost",
    REMOTE + ":443",
    "https://" + REMOTE,
    REMOTE + "/path",
    REMOTE + ".",
    "Entry.s3-t20.invalid",
    "127.0.0.1",
    "192.0.2.7",
    "[::1]",
    "a..invalid",
    "-a.invalid",
    "a-.invalid",
    "a_b.invalid",
    "a b.invalid",
    "*.s3-t20.invalid",
    "a" * 64 + ".invalid",
    ".".join(["a" * 60] * 5) + ".invalid",
    "entry.s3-t20.invalid\n",
)
HOST_FORMS_REFUSED = (
    "third.s3-t20.invalid",
    "127.0.0.1:8088",
    "127.0.0.1",
    "[::1]:8088",
    "[::ffff:127.0.0.1]:8088",
    "LOCALHOST:8088",
    "localhost:8088.",
    "localhost.:8088",
    "localhost",
    "localhost:80",
    "localhost:8089",
    REMOTE.upper(),
    REMOTE + ".",
    REMOTE + ":8443",
    REMOTE + ":80",
    " " + REMOTE,
    "",
)
# Each non-origin form, with what decides once the form guard alone is deleted.
TARGET_FORMS = (
    ("*", "target_path_refused"),
    ("http://third.s3-t20.invalid/", "target_path_refused"),
    ("third.s3-t20.invalid:443", None),
    ("api/release", None),
    ("", "target_path_refused"),
)
PATHS_REFUSED = (
    "/a%2Fb",
    "/a%2fb",
    "/a%5Cb",
    "/a%2Eb",
    "/%2e%2e/a",
    "/a%25b",
    "/a%00b",
    "/a%1Fb",
    "/a%7Fb",
    "/a%C2%85b",
    "/a%FFb",
    "/a%zz",
    "/a%2",
    "/a%",
    "/a#b",
    "//a",
    "/a//b",
    "/a/",
    "/.",
    "/..",
    "/a/../b",
    "/a/./b",
    "/a\\b",
    "/a b",
    "/a\tb",
    "/a\x7fb",
    "/café",
    "/a?b c",
    "/a?b#c",
    "/a?bé",
    "/a?b\x00",
)
TARGETS_SERVED = (
    ("/", "/", "/"),
    ("/?lang=ar&theme=dark", "/", "/?lang=ar&theme=dark"),
    ("/a%20b", "/a b", "/a%20b"),
    ("/a%41", "/aA", "/aA"),
    ("/caf%C3%A9", "/café", "/caf%C3%A9"),
    ("/fonts/A%20B,C%20D/0-255.pbf", "/fonts/A B,C D/0-255.pbf", None),
    ("/a.b/c..d?x=%2F", "/a.b/c..d", "/a.b/c..d?x=%2F"),
    ("/a?", "/a", "/a?"),
)


def reason_of(function: Any, *args: Any) -> str | None:
    try:
        function(*args)
    except Refusal as refusal:
        return refusal.reason
    return None


def listener_sites(sources: dict[str, str]) -> dict[str, list[str]]:
    """Every reference to a server class, bind or serve call in the sources."""
    wanted = {"bind", "listen", "create_server", "serve_forever", "server_bind"}
    found: dict[str, list[str]] = {}
    for name, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Attribute | ast.Name):
                continue
            text = ast.unparse(node)
            last = text.rsplit(".", 1)[-1]
            if last in wanted or last.endswith("Server") or text == "uvicorn.run":
                found.setdefault(name, []).append(text)
    return {name: sorted(texts) for name, texts in found.items()}


class Host(EntryCase):
    def test_remote_host_forms(self) -> None:
        self.assertEqual(remote.remote_host(REMOTE), REMOTE)
        self.guard_red(
            remote.remote_host, ("",), "remote_host_missing", then="remote_host_invalid"
        )
        for value in HOSTS_INVALID:
            with self.subTest(value=value):
                self.guard_red(remote.remote_host, (value,), "remote_host_invalid")

    def test_second_public_port_refused(self) -> None:
        # A host value that names a port can never widen the one entry.
        for value in (REMOTE + ":8443", REMOTE + ":8088", "localhost:9000"):
            with self.subTest(value=value):
                self.assertEqual(
                    reason_of(remote.remote_host, value), "remote_host_invalid"
                )
        # Another entry port is refused by the real activation.
        live = LiveState(self)
        live.fixture.raw.update(entry_port=8090)
        with self.assertRaises(Refusal) as caught:
            live.restart()
        self.assertEqual(caught.exception.reason, "activation_target_mismatch")
        # The operation sources hold exactly the known listeners.
        folder = ROOT / "scripts/operations"
        sources = {path.name: path.read_text() for path in sorted(folder.glob("*.py"))}
        expected = {
            "development.py": ["uvicorn.run"],
            "entry.py": [
                "LoopbackServer",
                "TCPServer",
                "TCPServer.server_bind",
                "ThreadingHTTPServer",
                "server.serve_forever",
            ],
            "serve.py": ["uvicorn.run"],
        }
        self.assertEqual(listener_sites(sources), expected)
        planted = dict(sources)
        planted["entry.py"] += (
            "\n\ndef second() -> None:\n"
            '    LoopbackServer(("127.0.0.1", 8090), handler(Path("."))).serve_forever()\n'
        )
        self.assertNotEqual(listener_sites(planted), expected)
        tree = ast.parse(sources["entry.py"])
        binds = [
            ast.unparse(node.args[0])
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "LoopbackServer"
        ]
        self.assertEqual(binds, ["('127.0.0.1', 8088)"])

    def test_non_loopback_bind_refused(self) -> None:
        from operations import serve

        for name in ("0.0.0.0", "::", "localhost", "192.0.2.7"):
            with self.subTest(name=name), self.assertRaises(Refusal) as caught:
                entry.prepared({"EII_ENVIRONMENT": "live", "EII_LISTEN_HOST": name})
            self.assertEqual(caught.exception.reason, "host_not_loopback")
        self.assertEqual(serve.server_options(18088)["host"], "127.0.0.1")

    def test_entry_start_holds_host_only_on_public_route(self) -> None:
        self.assertIsNone(remote.entry_host("loopback", ""))
        self.assertEqual(remote.entry_host("public_entry", REMOTE), REMOTE)
        self.assertEqual(remote.entry_host("loopback", REMOTE), REMOTE)
        self.assertEqual(
            reason_of(remote.entry_host, "public_entry", ""), "remote_host_missing"
        )
        self.assertEqual(
            reason_of(remote.entry_host, "loopback", REMOTE + ":443"),
            "remote_host_invalid",
        )
        child = {"EII_ENVIRONMENT": "live"}
        self.assertEqual(remote.entry_environment(child, "loopback", REMOTE), child)
        self.assertEqual(
            remote.entry_environment(child, "public_entry", REMOTE),
            dict(child, EII_REMOTE_HOST=REMOTE),
        )
        self.assertEqual(
            reason_of(remote.entry_environment, child, "public_entry", ""),
            "remote_host_missing",
        )
        rest, raw = remote.take_host(dict(child, EII_REMOTE_HOST=REMOTE))
        self.assertEqual((rest, raw), (child, REMOTE))
        self.assertEqual(remote.take_host(child), (child, ""))


class Admission(EntryCase):
    def test_four_rows_each_guard_alone(self) -> None:
        self.assertIsNone(reason_of(remote.admission, "public_entry", True, True))
        self.assertIsNone(reason_of(remote.admission, "loopback", False, False))
        for args, reason in (
            (("public_entry", True, False), "remote_host_missing"),
            (("loopback", True, False), "remote_exposure_required"),
            (("loopback", False, True), "remote_exposure_required"),
            (("public", False, False), "entry_route_unavailable"),
            ((None, False, False), "entry_route_unavailable"),
        ):
            with self.subTest(args=args):
                self.guard_red(remote.admission, args, reason)

    def test_expected_answer_follows_the_table(self) -> None:
        self.assertIsNone(remote.expected_answer("public_entry", True))
        self.assertIsNone(remote.expected_answer("loopback", False))
        self.assertEqual(
            remote.expected_answer("loopback", True), "remote_exposure_required"
        )
        self.assertEqual(
            remote.expected_answer("other", True), "entry_route_unavailable"
        )

    @settings(max_examples=200, deadline=None)
    @given(
        exposure=st.sampled_from(
            ["public_entry", "loopback", "", "PUBLIC_ENTRY", None]
        ),
        is_bound=st.booleans(),
        host_held=st.booleans(),
    )
    def test_admission_equals_four_row_oracle(
        self, exposure: Any, is_bound: bool, host_held: bool
    ) -> None:
        if exposure == "public_entry":
            oracle = None if host_held else "remote_host_missing"
        elif exposure == "loopback":
            oracle = "remote_exposure_required" if is_bound or host_held else None
        else:
            oracle = "entry_route_unavailable"
        self.assertEqual(
            reason_of(remote.admission, exposure, is_bound, host_held), oracle
        )

    def test_closed_body_and_recognition(self) -> None:
        self.guard_red(remote.closed_body, ("INVENTED",), "entry_route_unavailable")
        for reason, status in remote.STATUS.items():
            body = remote.closed_body(reason)
            self.assertEqual(remote.entry_reason(status, body), reason)
            self.assertIsNone(remote.entry_reason(status + 1, body))
            self.assertIsNone(remote.entry_reason(status, body + b"\n"))
            self.assertIsNone(
                remote.entry_reason(status, body.replace(b'":"', b'": "'))
            )
        self.assertIsNone(remote.entry_reason(503, b""))
        self.assertIsNone(
            remote.entry_reason(
                503, b'{"error_code":"startup_not_ready","status":"entry_refused"}'
            )
        )


class Request(EntryCase):
    def test_valid_forms(self) -> None:
        for host in (LOCAL, REMOTE, REMOTE + ":443"):
            forward = remote.rebuild("GET", "/api/release", [("Host", host)], REMOTE)
            self.assertEqual((forward.path, forward.length), ("/api/release", 0))
        forward = remote.rebuild("POST", "/api/x", POST, REMOTE)
        self.assertEqual(forward.length, 2)
        local = [("Host", LOCAL), ("Origin", "http://" + LOCAL)]
        self.assertEqual(remote.rebuild("GET", "/", local, None).target, "/")

    def test_method_refused(self) -> None:
        for method in ("PUT", "DELETE", "PATCH", "CONNECT", "TRACE", "get", ""):
            with self.subTest(method=method):
                self.guard_red(
                    remote.rebuild, (method, "/", POST[:2], REMOTE), "method_refused"
                )

    def test_header_syntax_refused(self) -> None:
        for name, value in (
            ("X Bad", "v"),
            ("", "v"),
            ("X-Bad:", "v"),
            ("naïve", "v"),
            ("X-A", "a\x00b"),
            ("X-A", "a\rb"),
            ("X-A", "a\nb"),
            ("X-A", "a\r\n b"),
            ("X-A", "a\x7fb"),
            ("X-A", "aĀb"),
        ):
            with self.subTest(name=name, value=value):
                self.guard_red(
                    remote.header_rule,
                    ([*VALID, (name, value)],),
                    "header_syntax_refused",
                )
        self.assertIsNone(reason_of(remote.header_rule, [("X-A", "a\tb é")]))

    def test_host_rule(self) -> None:
        for values in ([], [REMOTE, REMOTE], [LOCAL, REMOTE]):
            with self.subTest(values=values):
                self.assertEqual(
                    reason_of(remote.host_rule, values, REMOTE), "host_header_invalid"
                )
        self.guard_red(
            remote.host_rule, ([REMOTE, REMOTE], REMOTE), "host_header_invalid"
        )
        for value in HOST_FORMS_REFUSED:
            with self.subTest(value=value):
                self.guard_red(remote.host_rule, ([value], REMOTE), "host_refused")
        # Without a held remote name only the loopback form is served.
        self.guard_red(remote.host_rule, ([REMOTE], None), "host_refused")
        self.guard_red(remote.host_rule, ([REMOTE + ":443"], None), "host_refused")
        for value in (LOCAL, REMOTE, REMOTE + ":443"):
            self.assertEqual(remote.host_rule([value], REMOTE), value)

    def test_origin_rule(self) -> None:
        matching = "https://" + REMOTE
        self.guard_red(
            remote.origin_rule,
            ([matching, matching], "GET", REMOTE),
            "origin_header_invalid",
        )
        self.guard_red(remote.origin_rule, ([], "POST", REMOTE), "origin_refused")
        for host, origin in (
            (REMOTE, "https://third.s3-t20.invalid"),
            (REMOTE, "http://" + REMOTE),
            (REMOTE, matching + ":443"),
            (REMOTE, matching + "/"),
            (REMOTE, "http://" + LOCAL),
            (REMOTE, "null"),
            (REMOTE, ""),
            (REMOTE + ":443", matching + ":443"),
            (LOCAL, "https://" + LOCAL),
            (LOCAL, "http://localhost"),
            (LOCAL, "http://127.0.0.1:8088"),
            (LOCAL, matching),
        ):
            for method in ("GET", "POST"):
                with self.subTest(host=host, origin=origin, method=method):
                    self.guard_red(
                        remote.origin_rule, ([origin], method, host), "origin_refused"
                    )
        for method in sorted(remote.SAFE_METHODS):
            self.assertIsNone(reason_of(remote.origin_rule, [], method, REMOTE))
        self.assertIsNone(
            reason_of(remote.origin_rule, [matching], "POST", REMOTE + ":443")
        )
        self.assertIsNone(
            reason_of(remote.origin_rule, ["http://" + LOCAL], "POST", LOCAL)
        )

    def test_target_rules(self) -> None:
        for target, then in TARGET_FORMS:
            with self.subTest(target=target):
                self.guard_red(
                    remote.canonical_target, (target,), "target_form_refused", then=then
                )
        for target in PATHS_REFUSED:
            with self.subTest(target=target):
                self.assertEqual(
                    reason_of(remote.canonical_target, target), "target_path_refused"
                )
        for target, path, forward in TARGETS_SERVED:
            with self.subTest(target=target):
                self.assertEqual(
                    remote.canonical_target(target), (path, forward or target)
                )

    def test_presenter_rule(self) -> None:
        for target in (
            "/api/presenter/state",
            "/api/PRESENTER/state",
            "/api/%70resenter/state",
            "/api/pre%73enter",
            "/presenter",
            "/a/b/Presenter/c?x=1",
        ):
            with self.subTest(target=target):
                self.assertEqual(
                    reason_of(remote.rebuild, "GET", target, VALID, REMOTE),
                    "presenter_remote_refused",
                )
        self.guard_red(
            remote.presenter_rule,
            ("/api/presenter/state", VALID),
            "presenter_remote_refused",
        )
        for name in (
            "X-EII-Presenter-Token",
            "x-eii-presenter-token",
            "X-EII-PRESENTER-TOKEN",
        ):
            with self.subTest(name=name):
                self.guard_red(
                    remote.presenter_rule,
                    ("/api/release", [*VALID, (name, "INVENTED")]),
                    "presenter_remote_refused",
                )
        for target in ("/api/presenters", "/api/presenter-notes", "/api/a?presenter=1"):
            self.assertIsNone(reason_of(remote.rebuild, "GET", target, VALID, REMOTE))

    def test_body_rules(self) -> None:
        from eii_product.api.shapes import BODY_LIMIT

        self.assertEqual(remote.BODY_LIMIT, BODY_LIMIT)
        base = [("Host", REMOTE), ("Origin", "https://" + REMOTE)]
        cases: tuple[tuple[str, list[tuple[str, str]], str], ...] = (
            (
                "POST",
                [*POST, ("Transfer-Encoding", "chunked")],
                "transfer_encoding_refused",
            ),
            (
                "POST",
                [*POST, ("Transfer-Encoding", "identity")],
                "transfer_encoding_refused",
            ),
            ("GET", [*VALID, ("Transfer-Encoding", "")], "transfer_encoding_refused"),
            ("POST", [*POST, ("Content-Length", "2")], "content_length_invalid"),
            ("POST", base, "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "1a")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "-1")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "+1")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "0x10")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "1 2")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "\u0661")], "content_length_invalid"),
            ("POST", [*base, ("Content-Length", "1" * 10)], "content_length_invalid"),
            ("GET", [*VALID, ("Content-Length", "1")], "request_body_refused"),
            ("HEAD", [*VALID, ("Content-Length", "65537")], "request_body_refused"),
            ("POST", [*base, ("Content-Length", "65537")], "request_body_too_large"),
            (
                "POST",
                [*base, ("Content-Length", "999999999")],
                "request_body_too_large",
            ),
        )
        for method, headers, reason in cases:
            with self.subTest(method=method, headers=headers[2:]):
                self.assertEqual(reason_of(remote.body_length, method, headers), reason)
        self.guard_red(remote.body_length, cases[0][:2], "transfer_encoding_refused")
        self.guard_red(remote.body_length, cases[3][:2], "content_length_invalid")
        self.guard_red(
            remote.body_length,
            cases[4][:2],
            "content_length_invalid",
        )
        self.guard_red(remote.body_length, cases[13][:2], "request_body_refused")
        self.guard_red(remote.body_length, cases[15][:2], "request_body_too_large")
        for method, value, length in (
            ("POST", "65536", 65536),
            ("POST", "0", 0),
            ("POST", "007", 7),
            ("GET", "0", 0),
        ):
            headers = [*base, ("Content-Length", value)]
            self.assertEqual(remote.body_length(method, headers), length)
        self.assertEqual(remote.body_length("GET", VALID), 0)

    def test_forwarding_headers_dropped(self) -> None:
        headers = [
            ("Host", REMOTE),
            ("Accept", "text/html"),
            ("Connection", "X-Secret, keep-alive"),
            ("X-Secret", "INVENTED"),
            ("Keep-Alive", "timeout=5"),
            ("Upgrade", "websocket"),
            ("TE", "trailers"),
            ("Proxy-Authorization", "INVENTED"),
            ("Forwarded", "for=192.0.2.7"),
            ("X-Forwarded-For", "192.0.2.7"),
            ("X-Forwarded-Proto", "https"),
            ("X-Forwarded-Host", "third.s3-t20.invalid"),
            ("x-forwarded-port", "443"),
            ("Content-Length", "0"),
            ("Cookie", "eii_session=INVENTED"),
        ]
        self.assertEqual(
            remote.forward_headers(headers),
            [
                ("Host", REMOTE),
                ("Accept", "text/html"),
                ("Cookie", "eii_session=INVENTED"),
            ],
        )


class Response(EntryCase):
    def test_cookie_rules(self) -> None:
        good = "eii_session=INVENTED; HttpOnly; SameSite=Strict; Path=/"
        self.assertEqual(remote.response_cookies([good], True), [good + "; Secure"])
        kept = "a=secure; Secure; SameSite=Lax"
        self.assertEqual(remote.response_cookies([kept], True), [kept])
        for bad in (
            "a=b; HttpOnly; Path=/",
            "a=b; Secure",
            "a=b; SameSite=None; Secure",
            "a=b; SameSite",
            "a=b; SameSite=",
            "a=samesite=strict",
            "a=b; SameSite=Strict2",
        ):
            with self.subTest(bad=bad):
                self.guard_red(
                    remote.response_cookies,
                    ([good, bad], True),
                    "cookie_policy_refused",
                )
        # Loopback exposure leaves S3-T08 A15 unchanged.
        self.assertEqual(remote.response_cookies([good, "a=b"], False), [good, "a=b"])
        relayed = remote.relay_headers(
            [
                ("Content-Type", "text/html"),
                ("Set-Cookie", good),
                ("Connection", "keep-alive"),
                ("Transfer-Encoding", "chunked"),
                ("set-cookie", kept),
            ],
            True,
        )
        self.assertEqual(
            relayed,
            [
                ("Content-Type", "text/html"),
                ("Set-Cookie", good + "; Secure"),
                ("Set-Cookie", kept),
            ],
        )

    def test_gzip_negotiation_forms(self) -> None:
        for value, accepted in (
            ("gzip", True),
            ("GZIP", True),
            ("br, gzip;q=0.5", True),
            ("deflate, gzip ; q=1.000", True),
            ("gzip;q=0", False),
            ("gzip;q=0.000", False),
            ("gzip;q=2", False),
            ("gzip;q=0.5555", False),
            ("gzip;q=", False),
            ("gzip;x=1", False),
            ("xgzip", False),
            ("identity", False),
            ("*", False),
            ("", False),
        ):
            with self.subTest(value=value):
                self.assertEqual(remote.accepts_gzip([value]), accepted)
        self.assertFalse(remote.accepts_gzip([]))

    def test_gzip_only_for_complete_listed_text(self) -> None:
        asked = [("Host", REMOTE), ("Accept-Encoding", "gzip")]
        forward = remote.rebuild("GET", "/", asked, REMOTE)
        answer = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", "9")]
        self.assertTrue(remote.gzip_wanted(forward, 200, answer))

        def swapped(name: str, value: str | None) -> list[tuple[str, str]]:
            kept = [item for item in answer if item[0] != name]
            return kept if value is None else [*kept, (name, value)]

        ranged = remote.rebuild("GET", "/", [*asked, ("Range", "bytes=0-1")], REMOTE)
        plain = remote.rebuild("GET", "/", [("Host", REMOTE)], REMOTE)
        head = remote.rebuild("HEAD", "/", asked, REMOTE)
        for label, args in (
            ("head", (head, 200, answer)),
            ("partial", (forward, 206, answer)),
            ("missing", (forward, 404, answer)),
            ("not-accepted", (plain, 200, answer)),
            ("range", (ranged, 200, answer)),
            ("encoded", (forward, 200, [*answer, ("Content-Encoding", "br")])),
            (
                "content-range",
                (forward, 200, [*answer, ("Content-Range", "bytes 0-8/9")]),
            ),
            ("stream", (forward, 200, swapped("Content-Type", "text/event-stream"))),
            (
                "binary",
                (forward, 200, swapped("Content-Type", "application/x-protobuf")),
            ),
            ("two-types", (forward, 200, [*answer, ("Content-Type", "text/css")])),
            ("no-type", (forward, 200, swapped("Content-Type", None))),
            ("no-length", (forward, 200, swapped("Content-Length", None))),
            ("empty", (forward, 200, swapped("Content-Length", "0"))),
            ("two-lengths", (forward, 200, [*answer, ("Content-Length", "9")])),
            ("bad-length", (forward, 200, swapped("Content-Length", "9x"))),
            (
                "over-cap",
                (forward, 200, swapped("Content-Length", str(remote.GZIP_LIMIT + 1))),
            ),
        ):
            with self.subTest(label=label):
                self.assertFalse(remote.gzip_wanted(*args))
        self.assertTrue(
            remote.gzip_wanted(
                forward, 200, swapped("Content-Length", str(remote.GZIP_LIMIT))
            )
        )
        self.assertEqual(
            remote.gzip_headers([*answer, ("Vary", "Cookie")], 4),
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Encoding", "gzip"),
                ("Content-Length", "4"),
                ("Vary", "Cookie, Accept-Encoding"),
            ],
        )


SEGMENT = st.text(
    st.characters(
        blacklist_characters="/\\%",
        blacklist_categories=("Cc", "Cs"),
        max_codepoint=0x2FFF,
    ),
    min_size=1,
    max_size=8,
).filter(lambda text: text not in {".", ".."})
HOST_VALUES = st.one_of(
    st.sampled_from([LOCAL, REMOTE, REMOTE + ":443", *HOST_FORMS_REFUSED]),
    st.text(st.characters(min_codepoint=0x21, max_codepoint=0x7E), max_size=20),
)


def spelled(text: str, choices: list[int]) -> str:
    """One spelling of a segment: each letter literal, other case or escaped."""
    parts = []
    for char, choice in zip(text, choices, strict=True):
        if choice == 0:
            parts.append(char)
        elif choice == 1:
            parts.append(char.swapcase())
        else:
            parts.append(f"%{ord(char.swapcase() if choice == 3 else char):02X}")
    return "".join(parts)


class Properties(EntryCase):
    @settings(max_examples=300, deadline=None)
    @given(segments=st.lists(SEGMENT, min_size=1, max_size=4))
    def test_any_encoding_of_a_path_has_one_canonical_form(
        self, segments: list[str]
    ) -> None:
        target = "/" + "/".join(quote(item, safe="") for item in segments)
        path, forward = remote.canonical_target(target)
        self.assertEqual(path, "/" + "/".join(segments))
        self.assertEqual(remote.canonical_target(forward), (path, forward))

    @settings(max_examples=400, deadline=None)
    @given(target=st.text(max_size=24))
    def test_any_target_is_refused_or_canonical(self, target: str) -> None:
        try:
            path, forward = remote.canonical_target(target)
        except Refusal as refusal:
            self.assertIn(
                refusal.reason, {"target_form_refused", "target_path_refused"}
            )
            return
        self.assertTrue(forward.isascii() and forward.startswith("/"))
        self.assertNotIn("//", path)
        self.assertFalse({".", ".."} & set(path.split("/")))
        self.assertEqual(remote.canonical_target(forward), (path, forward))

    @settings(max_examples=300, deadline=None)
    @given(
        choices=st.lists(st.integers(0, 3), min_size=9, max_size=9),
        before=st.lists(st.sampled_from(["api", "a", "v1"]), max_size=2),
        after=st.lists(st.sampled_from(["state", "x.y", "0"]), max_size=2),
        host=st.sampled_from([LOCAL, REMOTE, REMOTE + ":443"]),
        method=st.sampled_from(["GET", "HEAD", "OPTIONS"]),
    )
    def test_no_spelling_of_a_presenter_path_is_rebuilt_for_any_host(
        self,
        choices: list[int],
        before: list[str],
        after: list[str],
        host: str,
        method: str,
    ) -> None:
        target = "/" + "/".join([*before, spelled("presenter", choices), *after])
        self.assertEqual(
            reason_of(remote.rebuild, method, target, [("Host", host)], REMOTE),
            "presenter_remote_refused",
        )

    @settings(max_examples=400, deadline=None)
    @given(
        hosts=st.lists(HOST_VALUES, max_size=2),
        origins=st.lists(
            st.sampled_from(
                [
                    "https://" + REMOTE,
                    "http://" + LOCAL,
                    "null",
                    "https://third.s3-t20.invalid",
                ]
            ),
            max_size=2,
        ),
        method=st.sampled_from(["GET", "POST", "HEAD", "OPTIONS", "PUT"]),
        held=st.booleans(),
    )
    def test_host_and_origin_admit_exactly_the_closed_forms(
        self, hosts: list[str], origins: list[str], method: str, held: bool
    ) -> None:
        headers = [("Host", value) for value in hosts]
        headers += [("Origin", value) for value in origins]
        if method == "POST":
            headers.append(("Content-Length", "0"))
        remote_name = REMOTE if held else None
        admitted = {LOCAL} | ({REMOTE, REMOTE + ":443"} if held else set())
        if method not in remote.METHODS:
            oracle: str | None = "method_refused"
        elif len(hosts) != 1:
            oracle = "host_header_invalid"
        elif hosts[0] not in admitted:
            oracle = "host_refused"
        elif len(origins) > 1:
            oracle = "origin_header_invalid"
        elif not origins:
            oracle = None if method in remote.SAFE_METHODS else "origin_refused"
        else:
            own = "http://" + LOCAL if hosts[0] == LOCAL else "https://" + REMOTE
            oracle = None if origins[0] == own else "origin_refused"
        self.assertEqual(
            reason_of(remote.rebuild, method, "/api/release", headers, remote_name),
            oracle,
        )

    @settings(max_examples=200, deadline=None)
    @given(
        length=st.one_of(
            st.integers(-5, 70_000).map(str),
            st.sampled_from(["65535", "65536", "65537", "", "1e3", " 1", "1 "]),
        )
    )
    def test_body_length_boundary(self, length: str) -> None:
        headers = [
            ("Host", REMOTE),
            ("Origin", "https://" + REMOTE),
            ("Content-Length", length),
        ]
        plain = length.isascii() and length.isdigit() and len(length) <= 9
        if not plain:
            oracle: str | None = "content_length_invalid"
        elif int(length) > 65_536:
            oracle = "request_body_too_large"
        else:
            oracle = None
        self.assertEqual(reason_of(remote.body_length, "POST", headers), oracle)


class Bound(EntryCase):
    def test_binding_is_read_from_the_verified_log(self) -> None:
        live = LiveState(self)
        self.assertFalse(remote.bound(live.state))
        live.expose()
        self.assertTrue(remote.bound(live.state))
        live.restart()
        # P never returns to false inside one state.
        self.assertTrue(remote.bound(live.state))
        log = Path(live.state) / "promotions.jsonl"
        log.write_bytes(log.read_bytes().replace(b"public_entry", b"loopback", 1))
        with self.assertRaises(Refusal) as caught:
            remote.bound(live.state)
        self.assertEqual(caught.exception.reason, "promotion_log_mismatch")
