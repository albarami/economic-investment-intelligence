"""The remote-check command on invented fixtures: no host is resolved or reached.

The positive control is the real entry handler over a public route written by
the real ``activate``, in front of an invented upstream, reached through an
injected opener and resolver under an invented ``.invalid`` name, with an
injected browser result file. Every other case changes one input.
"""

from __future__ import annotations

import contextlib
import copy
import http.client
import io
import itertools
import json
import re
import ssl
import sys
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st
from s3_t20_support import REMOTE, EntryCase, LiveState, Upstream, dead_port, reply
from s3_t28_support import IDENTITY, ROOT
from test_s3_t28_controls import without_refusal

import remote_check_browser
from commands import remote_check as command
from eii_core.reason_codes import CODES
from operations import remote, remote_check
from operations.common import Refusal, encoded
from operations.remote_check import Frames, Limits, Outcome

REAL_LAUNCH = remote_check_browser.launch
DEFAULT_OPENER = remote_check.default_opener
ANSWER = "0a1b2c3d-e4f5-4a6b-8c7d-9e0f1a2b3c4d"
EVENTS = "/api/answers/" + ANSWER + "/events"
FACT = "f_" + "ab" * 16
ADDRESS = "203.0.113.7"  # A documentation address; no test connects to it.
HEALTH: dict[str, Any] = dict(
    status="ok",
    store="postgres",
    postgres="up",
    release_id=IDENTITY,
    release_hash=IDENTITY,
    parity="identical",
    ledger="local",
    local_ledger_rows=0,
    model="template",
    traffic="simulated",
    tiles="ok",
    fonts="ok",
    replays="ok",
)
FRAMES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("plan_step", {"step": "INVENTED-step"}),
    ("stage", {"directive": "INVENTED-directive"}),
    ("evidence", {"tool": "night_lights", "facts": [{"fact_id": FACT}]}),
    ("receipt", {"Checked before display": {"Sources": True}, "egress": []}),
    ("status", {"writer": "template", "status": "OK"}),
    ("narrative", {"key": "INVENTED-claim"}),
    ("done", {"answer_id": ANSWER, "brief": {"key": "INVENTED-brief"}}),
)
STATUSES = dict(start_page_en=200, start_page_ar=200, card=202, map_style=200, tile=206)
RESULT: dict[str, Any] = dict(
    schema="remote_check_browser.v1",
    items={name: dict(status=code, reason=None) for name, code in STATUSES.items()},
    events_path=EVENTS,
)
ALL_PASS = {
    "health": "PASS health: HTTP 200",
    "start_page_en": "PASS start page (en): HTTP 200",
    "start_page_ar": "PASS start page (ar): HTTP 200",
    "card": "PASS card with fact chip: HTTP 202",
    "map_style": "PASS map style: HTTP 200",
    "tile": "PASS tile: HTTP 206",
    "stream": "PASS streamed answer: HTTP 200",
}
BROWSER = ("start_page_en", "start_page_ar", "card", "map_style", "tile")
# The six closed sentences, written out here so a changed one is red.
PASSED = "every item passed"
NOT_AUTHORISED = "the entry answered and public exposure is not authorised"
NOT_SERVING = "the entry answered and the product is not serving"
ENTRY_REFUSED = "the entry answered and refused the check's request"
UNDECIDED = (
    "the tunnel or the product is down, and the responses cannot establish which"
)
NEUTRAL = "the failed items above failed on content, or the browser could not run"
ROUND_3_SENTENCE = (
    "the entry and the product answered, and the items above failed on "
    "content or the browser could not run"
)
HOSTILE: tuple[Any, ...] = ({"toString": None}, 7, None, [])
DOCUMENT_13 = ROOT / "docs/13_DEPLOYMENT_AND_OPERATIONS.md"


def frame(identity: object, kind: object, data: object) -> str:
    return f"id: {identity}\r\nevent: {kind}\r\ndata: {data}\r\n\r\n"


def stream(frames: Any = FRAMES, tail: str = "") -> bytes:
    text = "".join(
        frame(index + 1, kind, json.dumps(data, separators=(",", ":")))
        for index, (kind, data) in enumerate(frames)
    )
    return (text + tail).encode()


def no_status(label: str, reason: str) -> str:
    return f"FAIL {label}: no HTTP status was received: {reason}"


def failed(label: str, status: int, reason: str) -> str:
    return f"FAIL {label}: HTTP {status}: {reason}"


def leaves(value: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if isinstance(value, dict) and value:
        return [leaf for key in value for leaf in leaves(value[key], (*path, key))]
    if isinstance(value, list) and value:
        return [
            leaf for i, item in enumerate(value) for leaf in leaves(item, (*path, i))
        ]
    return [path]


def replaced(value: Any, path: tuple[Any, ...], hostile: Any) -> Any:
    changed = copy.deepcopy(value)
    holder = changed
    for key in path[:-1]:
        holder = holder[key]
    holder[path[-1]] = copy.deepcopy(hostile)
    return changed


def decided(function: Any, *args: Any) -> str | None:
    try:
        function(*args)
    except Refusal as refusal:
        return refusal.reason
    return None


def fed(body: bytes, cuts: Any = ()) -> str | None:
    """The stream reader's decision on a whole body, fed in the given pieces."""
    frames = Frames()
    edges = [0, *sorted(min(cut, len(body)) for cut in cuts), len(body)]
    try:
        for start, end in itertools.pairwise(edges):
            frames.feed(body[start:end])
        frames.end()
    except Refusal as refusal:
        return refusal.reason
    return None


SEAMS = [
    patch(target, side_effect=AssertionError("INVENTED-default-seam"))
    for target in (
        "operations.remote_check.system_addresses",
        "operations.remote_check.default_opener",
        "remote_check_browser.launch",
    )
]


def setUpModule() -> None:
    """No test of this file resolves a name, opens a connection or starts a child."""
    for seam in SEAMS:
        seam.start()


def tearDownModule() -> None:
    for seam in SEAMS:
        seam.stop()


class CheckCase(EntryCase):
    """The positive control and its one-input changes."""

    def setUp(self) -> None:
        super().setUp()
        (self.root / "web/node_modules/playwright").mkdir(parents=True)
        (self.root / "web/node_modules/playwright/cli.js").write_bytes(b"")
        (self.root / "data/tools/playwright").mkdir(parents=True)
        self.health: Any = dict(HEALTH)
        self.result: Any = copy.deepcopy(RESULT)
        self.body = stream()
        self.code: int | None = 0
        self.plan: dict[str, Any] = {}
        self.ports: dict[int, int] = {}
        self.opened: list[tuple[str, str, float]] = []
        self.launched: list[tuple[Any, ...]] = []
        self.upstream = Upstream(self)
        self.upstream.answer = self.answer
        self.live = LiveState(self)
        self.live.expose()
        self.port = self.serve_entry(self.live.state, REMOTE, self.upstream)
        self.environ = {"EII_REMOTE_HOST": REMOTE, "PATH": "/INVENTED/bin"}

    def answer(self, handler: Any, seen: dict[str, Any]) -> None:
        path = seen["target"]
        if path in self.plan:
            self.plan[path](handler)
        elif path == "/health":
            reply(
                handler,
                200,
                [("Content-Type", "application/json")],
                self.health if type(self.health) is bytes else encoded(self.health),
            )
        elif path == EVENTS:
            self.events(handler)
        else:
            reply(handler, 404, [], b"")

    def events(self, handler: Any, **changes: Any) -> None:
        headers = [("Content-Type", "text/event-stream; charset=utf-8")]
        options: dict[str, Any] = dict(length=False)
        options.update(changes)
        reply(handler, 200, headers + options.pop("extra", []), self.body, **options)

    def opener(self, address: str, host: str, timeout: float) -> Any:
        self.opened.append((address, host, timeout))
        port = self.ports.get(len(self.opened), self.port)
        return http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)

    def launch(self, argv: Any, cwd: Path, env: Any, seconds: float) -> int | None:
        self.launched.append((tuple(argv), cwd, dict(env), seconds))
        if self.result is not None:
            raw = self.result if type(self.result) is bytes else encoded(self.result)
            Path(env["EII_REMOTE_CHECK_RESULT"]).write_bytes(raw)
        return self.code

    def check(self, **options: Any) -> tuple[int, list[str], str]:
        out, err = io.StringIO(), io.StringIO()
        settings_: dict[str, Any] = dict(
            resolve=lambda _: [ADDRESS], opener=self.opener, launch=self.launch
        )
        environ = options.pop("environ", self.environ)
        args = options.pop("args", [])
        settings_.update(options)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = command.run(self.root, environ, args, **settings_)
        # The host is never part of any line, a refusal included.
        self.assertNotIn(REMOTE, out.getvalue() + err.getvalue())
        self.assertNotIn(ADDRESS, out.getvalue() + err.getvalue())
        return code, out.getvalue().splitlines(), err.getvalue()

    def expect(self, changed: dict[str, str], closing: str, **options: Any) -> None:
        """Exit 1; only the named item lines differ from the positive control."""
        code, lines, err = self.check(**options)
        wanted = [changed.get(name, line) for name, line in ALL_PASS.items()]
        self.assertEqual(lines, [*wanted, "remote-check: " + closing])
        self.assertEqual((code, err), (1, ""))

    def before_request(self, reason: str, **options: Any) -> None:
        code, lines, err = self.check(**options)
        self.assertEqual((code, lines), (2, []))
        self.assertEqual(err, f"FAIL remote-check: {reason}\n")
        self.assertEqual(
            (self.opened, self.launched, self.upstream.requests), ([], [], [])
        )

    def browser_down(self, reason: str, **options: Any) -> None:
        """List E: all five browser items fail alike and the stream is withheld."""
        changed = {
            name: no_status(remote_check.LABELS[name], reason) for name in BROWSER
        }
        changed["stream"] = no_status("streamed answer", "stream_answer_unavailable")
        self.expect(changed, NEUTRAL, **options)
        self.assertEqual(len(self.opened), 1)

    def direct(self, call: int) -> None:
        """Point one item's connection at the invented upstream itself."""
        self.ports[call] = self.upstream.port

    def fast(self, read: float, item: float) -> None:
        limits = Limits(read=read, item=item)
        seam = patch("operations.remote_check.Limits", lambda: limits)
        seam.start()
        self.addCleanup(seam.stop)


class Control(CheckCase):
    def test_check_all_pass(self) -> None:
        code, lines, err = self.check()
        self.assertEqual(lines, [*ALL_PASS.values(), "remote-check: " + PASSED])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            [seen["target"] for seen in self.upstream.requests], ["/health", EVENTS]
        )
        self.assertEqual(
            self.opened, [(ADDRESS, REMOTE, remote_check.CONNECT_SECONDS)] * 2
        )
        ((argv, cwd, env, seconds),) = self.launched
        self.assertEqual(
            argv,
            (
                "node",
                "node_modules/playwright/cli.js",
                "test",
                "--config",
                "playwright.remote-check.config.ts",
            ),
        )
        self.assertEqual((cwd, seconds), (self.root / "web", 180.0))
        self.assertEqual(
            set(env),
            {
                "PATH",
                "TMPDIR",
                "PLAYWRIGHT_BROWSERS_PATH",
                "EII_REMOTE_CHECK_ORIGIN",
                "EII_REMOTE_CHECK_RESULT",
            },
        )
        self.assertEqual(env["EII_REMOTE_CHECK_ORIGIN"], "https://" + REMOTE)
        self.assertEqual(
            env["PLAYWRIGHT_BROWSERS_PATH"], str(self.root / "data/tools/playwright")
        )
        # The fresh folder of the result file is removed with everything in it.
        self.assertFalse(Path(env["EII_REMOTE_CHECK_RESULT"]).parent.exists())

    def test_child_environment_is_closed(self) -> None:
        self.check(environ=dict(self.environ, INVENTED_SECRET="INVENTED", HOME="/x"))
        self.assertEqual(
            sorted(self.launched[0][2]),
            [
                "EII_REMOTE_CHECK_ORIGIN",
                "EII_REMOTE_CHECK_RESULT",
                "HOME",
                "PATH",
                "PLAYWRIGHT_BROWSERS_PATH",
                "TMPDIR",
            ],
        )

    def test_any_argument_refused(self) -> None:
        for args in (["--help"], ["extra"], [""], ["remote-check"], ["a", "b"]):
            with self.subTest(args=args):
                code, lines, err = self.check(args=args)
                self.assertEqual((code, lines), (2, []))
                self.assertIn("usage", err)
                self.assertEqual((self.opened, self.launched), ([], []))

    def test_host_never_printed(self) -> None:
        # Every ``check`` of this file asserts it; these are the three kinds.
        self.before_request("remote_host_invalid", environ={"EII_REMOTE_HOST": "x"})
        self.assertEqual(self.check()[0], 0)
        self.plan["/health"] = lambda handler: reply(handler, 500, [], b"")
        self.assertEqual(self.check()[0], 1)

    def test_unexpected_fault_prints_one_closed_line(self) -> None:
        def broken(*_: Any) -> Any:
            raise RuntimeError("INVENTED " + REMOTE)

        with patch("operations.remote_check.check", broken):
            code, lines, err = self.check()
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(err, "FAIL remote-check: operation_failed\n")


class BeforeAnyRequest(CheckCase):
    """List A: exit 2, no opener call, no child and no item line."""

    def test_host_missing_before_request(self) -> None:
        for environ in ({}, {"EII_REMOTE_HOST": ""}):
            with self.subTest(environ=environ):
                self.before_request("remote_host_missing", environ=environ)

    def test_host_invalid_before_request(self) -> None:
        for value in (
            "https://" + REMOTE,
            REMOTE + ":443",
            REMOTE + "/path",
            "203.0.113.7",
            "[2001:db8::7]",
            REMOTE + ".",
            "localhost",
            "entry.localhost",
            "single",
            REMOTE.upper(),
        ):
            with self.subTest(value=value):
                self.before_request(
                    "remote_host_invalid", environ={"EII_REMOTE_HOST": value}
                )

    def test_host_unresolved_before_request(self) -> None:
        def raising(_: str) -> list[str]:
            raise OSError("INVENTED-resolver")

        for resolve in (lambda _: [], raising, lambda _: ["INVENTED-not-an-address"]):
            with self.subTest(resolve=resolve):
                self.before_request("remote_host_unresolved", resolve=resolve)

    def test_host_loopback_before_request(self) -> None:
        for addresses in (
            ["127.0.0.1"],
            ["::1"],
            [ADDRESS, "127.0.0.1", "2001:db8::7"],
            ["127.9.9.9"],
            ["::ffff:127.0.0.1"],
            ["::ffff:0.0.0.0"],
            ["0.0.0.0"],
            ["::"],
        ):
            with self.subTest(addresses=addresses):
                self.before_request(
                    "remote_host_loopback", resolve=lambda _, a=addresses: a
                )

    def test_address_checked_is_the_address_used(self) -> None:
        self.check(resolve=lambda _: ["2001:db8::7", ADDRESS])
        self.assertEqual({call[0] for call in self.opened}, {"2001:db8::7"})


class Transport(CheckCase):
    """List B: each case on the Health item and again on the stream item."""

    ITEMS = (
        (1, "health", "health", "/health"),
        (2, "stream", "streamed answer", EVENTS),
    )

    def closing_for(self, name: str, reason: str) -> str:
        return UNDECIDED if name == "health" else NEUTRAL

    def test_no_response(self) -> None:
        quiet = Upstream(self)
        quiet.answer = lambda handler, seen: None
        for call, name, label, _ in self.ITEMS:
            for port in (dead_port(), quiet.port):
                with self.subTest(item=name, port=port):
                    self.opened.clear()
                    self.ports = {call: port}
                    self.expect(
                        {name: no_status(label, "no_response")},
                        self.closing_for(name, "no_response"),
                    )

    def test_tls_failed(self) -> None:
        class Unverified(http.client.HTTPConnection):
            def connect(self) -> None:
                raise ssl.SSLCertVerificationError("INVENTED-certificate " + REMOTE)

        for call, name, label, _ in self.ITEMS:
            with self.subTest(item=name):
                self.opened.clear()

                def opener(
                    address: str, host: str, timeout: float, c: int = call
                ) -> Any:
                    made = self.opener(address, host, timeout)
                    return Unverified("127.0.0.1", 1) if len(self.opened) == c else made

                self.expect(
                    {name: no_status(label, "tls_failed")},
                    self.closing_for(name, "tls_failed"),
                    opener=opener,
                )

    def test_default_context_verifies_certificates(self) -> None:
        context = remote_check.verified_context()
        self.assertIs(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        opener = DEFAULT_OPENER  # The module's own; ``setUp`` replaced the name.
        made = opener(ADDRESS, REMOTE, 5.0)
        self.assertEqual((made.address, made.host, made.port), (ADDRESS, REMOTE, 443))
        self.assertIs(made.tls.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(made.tls.check_hostname)

        def unverified() -> ssl.SSLContext:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context

        def name_unchecked() -> ssl.SSLContext:
            context = ssl.create_default_context()
            context.check_hostname = False
            return context

        for plant in (unverified, name_unchecked):
            with (
                self.subTest(plant=plant.__name__),
                patch("operations.remote_check.verified_context", plant),
            ):
                self.guard_red(opener, (ADDRESS, REMOTE, 5.0), "tls_failed")

    def test_redirect_refused(self) -> None:
        other = Upstream(self)
        target = f"http://127.0.0.1:{other.port}/health"
        for _, name, label, path in self.ITEMS:
            for status in (301, 302, 307, 308):
                with self.subTest(item=name, status=status):
                    self.upstream.requests.clear()
                    self.plan = {
                        path: lambda handler, s=status: reply(
                            handler, s, [("Location", target)], b""
                        )
                    }
                    self.expect(
                        {name: failed(label, status, "redirect_refused")}, NEUTRAL
                    )
                    asked = [seen["target"] for seen in self.upstream.requests]
                    self.assertEqual(asked.count(path), 1)
                    self.assertEqual(other.requests, [])

    def test_response_timeout(self) -> None:
        self.fast(read=0.3, item=0.9)

        def stalled(handler: Any) -> None:
            time.sleep(0.6)

        def headed(handler: Any) -> None:
            handler.send_response_only(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.end_headers()
            handler.wfile.flush()

        def silent_body(handler: Any) -> None:
            headed(handler)
            time.sleep(0.6)

        def trickled(handler: Any) -> None:
            headed(handler)
            with contextlib.suppress(OSError):  # The reader has left by its bound.
                for _ in range(8):
                    handler.wfile.write(b" ")
                    handler.wfile.flush()
                    time.sleep(0.15)

        for call, name, label, path in self.ITEMS:
            for plant, line in (
                (stalled, no_status(label, "response_timeout")),
                (silent_body, failed(label, 200, "response_timeout")),
                (trickled, failed(label, 200, "response_timeout")),
            ):
                with self.subTest(item=name, plant=plant.__name__):
                    self.opened.clear()
                    self.direct(call)
                    self.plan = {path: plant}
                    self.expect(
                        {name: line}, self.closing_for(name, "response_timeout")
                    )

    def test_response_too_large(self) -> None:
        document = encoded(HEALTH)
        filler = len(stream()) + len(frame(8, "narrative", '""'))
        for extra, lines in ((0, None), (1, "response_too_large")):
            self.health = document + b" " * (
                remote_check.HEALTH_BYTES - len(document) + extra
            )
            with self.subTest(item="health", extra=extra):
                if lines is None:
                    self.assertEqual(self.check()[0], 0)
                else:
                    self.expect({"health": failed("health", 200, lines)}, NEUTRAL)
        self.health = dict(HEALTH)
        for extra, lines in ((0, None), (1, "response_too_large")):
            padding = "x" * (remote_check.STREAM_BYTES - filler + extra)
            frames = [*FRAMES[:-1], ("narrative", padding), FRAMES[-1]]
            self.body = stream(frames)
            self.assertEqual(len(self.body), remote_check.STREAM_BYTES + extra)
            with self.subTest(item="stream", extra=extra):
                if lines is None:
                    self.assertEqual(self.check()[0], 0)
                else:
                    self.expect(
                        {"stream": failed("streamed answer", 200, lines)}, NEUTRAL
                    )

    def test_status_unexpected(self) -> None:
        shaped = b'{"error_code":"INVENTED_reason","status":"entry_refused"}'
        for _, name, label, path in self.ITEMS:
            for status, body in (
                (404, b""),
                (500, b"INVENTED"),
                (503, shaped),
                (204, b""),
            ):
                with self.subTest(item=name, status=status):
                    self.plan = {
                        path: lambda handler, s=status, b=body: reply(handler, s, [], b)
                    }
                    self.expect(
                        {name: failed(label, status, "status_unexpected")},
                        self.closing_for(name, "status_unexpected"),
                    )

    def test_product_down_fail_on_loopback(self) -> None:
        self.port = self.serve_entry(self.live.state, REMOTE, dead_port())
        reason = "entry_upstream_unavailable"
        self.expect(
            {
                "health": failed("health", 503, reason),
                "stream": failed("streamed answer", 503, reason),
            },
            NOT_SERVING,
        )
        self.assertEqual(self.upstream.requests, [])

    def test_entry_route_unavailable_reported(self) -> None:
        (self.live.state / "route.json").unlink()
        reason = "entry_route_unavailable"
        self.expect(
            {
                "health": failed("health", 503, reason),
                "stream": failed("streamed answer", 503, reason),
            },
            NOT_SERVING,
        )
        self.assertEqual(self.upstream.requests, [])

    def test_not_exposed_reported(self) -> None:
        self.live.restart()
        reason = "remote_exposure_required"
        self.expect(
            {
                "health": failed("health", 503, reason),
                "stream": failed("streamed answer", 503, reason),
            },
            NOT_AUTHORISED,
        )
        self.assertEqual(self.upstream.requests, [])

    def test_entry_reason_passed_through(self) -> None:
        def sentence(reason: str) -> str:
            if reason == "remote_exposure_required":
                return NOT_AUTHORISED
            if reason in {"entry_upstream_unavailable", "entry_route_unavailable"}:
                return NOT_SERVING
            return ENTRY_REFUSED

        self.assertGreaterEqual(len(remote.ENTRY_REASONS), 21)
        for call, name, label, path in self.ITEMS:
            for reason in sorted(remote.ENTRY_REASONS):
                with self.subTest(item=name, reason=reason):
                    self.opened.clear()
                    self.direct(call)
                    status = remote.STATUS[reason]
                    self.plan = {
                        path: lambda handler, s=status, r=reason: reply(
                            handler, s, [], remote.closed_body(r)
                        )
                    }
                    self.expect({name: failed(label, status, reason)}, sentence(reason))

    def test_entry_refusing_the_host_is_reported(self) -> None:
        self.port = self.serve_entry(
            self.live.state, "other.s3-t20.invalid", self.upstream
        )
        self.expect(
            {
                "health": failed("health", 403, "host_refused"),
                "stream": failed("streamed answer", 403, "host_refused"),
            },
            ENTRY_REFUSED,
        )
        self.assertEqual(self.upstream.requests, [])


class HealthContent(CheckCase):
    """List C."""

    def test_health_malformed(self) -> None:
        removed = {key: value for key, value in HEALTH.items() if key != "fonts"}
        for name, body in (
            ("not-json", b"INVENTED"),
            ("not-object", b"[]"),
            ("key-removed", encoded(removed)),
            ("key-added", encoded(dict(HEALTH, INVENTED="x"))),
            ("wrong-type", encoded(dict(HEALTH, local_ledger_rows="0"))),
            ("boolean-integer", encoded(dict(HEALTH, local_ledger_rows=True))),
            ("negative", encoded(dict(HEALTH, local_ledger_rows=-1))),
            ("repeated-key", encoded(HEALTH)[:-1] + b',"status":"ok"}'),
            ("constant", encoded(HEALTH).replace(b":0,", b":NaN,")),
            ("not-utf-8", b"\xff\xfe"),
            ("empty", b""),
            ("nested-past-the-interpreter-limit", b"[" * 60_000),
        ):
            with self.subTest(case=name):
                self.health = body
                self.expect(
                    {"health": failed("health", 200, "health_malformed")}, NEUTRAL
                )

    def test_health_not_ok(self) -> None:
        self.health = dict(HEALTH, status="degraded", tiles="missing")
        self.expect({"health": failed("health", 200, "health_not_ok")}, NEUTRAL)

    def test_health_guards_red_when_deleted(self) -> None:
        self.guard_red(
            remote_check.health_rule, (b"[]",), "health_malformed", then="health_not_ok"
        )
        degraded = encoded(dict(HEALTH, status="degraded"))
        self.guard_red(remote_check.health_rule, (degraded,), "health_not_ok")


class StreamContent(CheckCase):
    """List D."""

    def stream_fails(self, reason: str, status: int = 200) -> None:
        self.expect({"stream": failed("streamed answer", status, reason)}, NEUTRAL)

    def test_stream_answer_unavailable(self) -> None:
        # R3-F2: a null events path is valid; only the stream item is withheld.
        self.result["events_path"] = None
        self.expect(
            {"stream": no_status("streamed answer", "stream_answer_unavailable")},
            NEUTRAL,
        )
        self.assertEqual(len(self.opened), 1)
        self.assertEqual(
            [seen["target"] for seen in self.upstream.requests], ["/health"]
        )

    def test_stream_type_invalid(self) -> None:
        for kind in ("application/json", "text/plain", "text/event-streams", None):
            with self.subTest(kind=kind):
                headers = [] if kind is None else [("Content-Type", kind)]
                self.plan = {
                    EVENTS: lambda handler, h=headers: reply(
                        handler, 200, h, self.body, length=False
                    )
                }
                self.stream_fails("stream_type_invalid")

    def test_stream_length_fixed(self) -> None:
        self.plan = {EVENTS: lambda handler: self.events(handler, length=True)}
        self.stream_fails("stream_length_fixed")

    def test_stream_encoded(self) -> None:
        for coding in ("gzip", "identity"):
            with self.subTest(coding=coding):
                extra = [("Content-Encoding", coding)]
                self.plan = {
                    EVENTS: lambda handler, e=extra: self.events(handler, extra=e)
                }
                self.stream_fails("stream_encoded")

    def test_stream_frame_malformed(self) -> None:
        head, done = stream(FRAMES[:-1]).decode(), frame(7, "done", "{}")
        for name, plant in (
            ("no-event-line", "id: 9\r\ndata: {}\r\n\r\n"),
            (
                "two-event-lines",
                "id: 9\r\nevent: stage\r\nevent: stage\r\ndata: {}\r\n\r\n",
            ),
            ("no-data-line", "id: 9\r\nevent: stage\r\n\r\n"),
            ("unknown-kind", frame(9, "INVENTED", "{}")),
            ("kind-in-another-case", frame(9, "Stage", "{}")),
            ("not-json", frame(9, "narrative", "{")),
            ("constant", frame(9, "narrative", "NaN")),
            ("not-an-object", frame(9, "stage", "7")),
            ("list-not-object", frame(9, "stage", "[]")),
            ("no-id-line", "event: stage\r\ndata: {}\r\n\r\n"),
            ("id-not-digits", frame("x", "stage", "{}")),
            ("unknown-line", "id: 9\r\nevent: stage\r\nretry: 5\r\ndata: {}\r\n\r\n"),
            ("comment-only", ": INVENTED\r\n\r\n"),
            ("not-utf-8", "\udcff"),
        ):
            with self.subTest(case=name):
                self.body = (head + plant + done).encode("utf-8", "surrogateescape")
                self.stream_fails("stream_frame_malformed")

    def test_stream_order_invalid(self) -> None:
        for name, body in (
            ("frame-after-done", stream() + frame(8, "narrative", "{}").encode()),
            ("malformed-after-done", stream() + b"INVENTED\r\n\r\n"),
            ("repeated-id", stream().replace(b"id: 2\r\n", b"id: 1\r\n")),
        ):
            with self.subTest(case=name):
                self.body = body
                self.stream_fails("stream_order_invalid")

    def test_stream_error_event(self) -> None:
        self.body = stream([*FRAMES[:3], ("error", {"error_code": "INVENTED"})])
        self.stream_fails("stream_error_event")

    def test_stream_truncated(self) -> None:
        for name, body in (
            ("before-done", stream(FRAMES[:-1])),
            ("empty", b""),
            ("inside-a-frame-after-done", stream(tail="id: 9\r\nevent: narr")),
            ("inside-a-character-after-done", stream() + b"\xe2\x82"),
        ):
            with self.subTest(case=name):
                self.body = body
                self.stream_fails("stream_truncated")

    def test_stream_guards_red_when_deleted(self) -> None:
        head = remote_check.stream_head
        self.guard_red(head, ("text/plain", None, None), "stream_type_invalid")
        self.guard_red(head, ("text/event-stream", "7", None), "stream_length_fixed")
        self.guard_red(head, ("text/event-stream", None, "gzip"), "stream_encoded")
        block = frame(9, "stage", "{}").strip().replace("\r\n", "\n")
        self.guard_red(Frames.frame, (Frames(done=True), block), "stream_order_invalid")
        self.guard_red(
            Frames.frame, (Frames(seen={"9"}), block), "stream_order_invalid"
        )
        error = block.replace("stage", "error")
        self.guard_red(Frames.frame, (Frames(), error), "stream_error_event")
        self.guard_red(Frames.end, (Frames(),), "stream_truncated")
        self.guard_red(
            Frames.end, (Frames(done=True, pending="id: 9"),), "stream_truncated"
        )
        redirect = (302, "https://other.invalid/", lambda: b"")
        self.guard_red(
            remote_check.other_status,
            redirect,
            "redirect_refused",
            then="status_unexpected",
        )
        self.guard_red(
            remote_check.other_status, (404, None, lambda: b""), "status_unexpected"
        )
        self.guard_red(
            remote_check.resolved, (REMOTE, lambda _: ["::1"]), "remote_host_loopback"
        )


class Browser(CheckCase):
    """Lists E and F."""

    def test_browser_unavailable(self) -> None:
        cli = self.root / "web/node_modules/playwright/cli.js"
        browsers = self.root / "data/tools/playwright"

        def absent(*_: Any) -> int:
            raise FileNotFoundError("INVENTED-node")

        cli.unlink()
        self.browser_down("browser_unavailable")
        self.assertEqual(self.launched, [])
        cli.write_bytes(b"")
        browsers.rmdir()
        self.opened.clear()
        self.browser_down("browser_unavailable")
        self.assertEqual(self.launched, [])
        browsers.mkdir()
        self.opened.clear()
        self.browser_down("browser_unavailable", launch=absent)

    def test_browser_timeout(self) -> None:
        self.code = None
        self.browser_down("browser_timeout")

    def test_browser_failed(self) -> None:
        for code in (1, 3, -9):
            with self.subTest(code=code):
                self.opened.clear()
                self.code = code
                self.browser_down("browser_failed")

    def test_browser_result_missing(self) -> None:
        self.result = None
        self.browser_down("browser_result_missing")

    def test_browser_result_invalid(self) -> None:
        def item(name: str, **values: Any) -> Any:
            return replaced(
                RESULT, ("items", name), dict(RESULT["items"][name], **values)
            )

        valid = encoded(RESULT)
        without = {key: value for key, value in RESULT.items() if key != "events_path"}
        fewer = replaced(
            RESULT,
            ("items",),
            {k: v for k, v in RESULT["items"].items() if k != "tile"},
        )
        cases: list[tuple[str, Any]] = [
            (
                "over-the-size-bound",
                valid + b" " * (remote_check.RESULT_BYTES + 1 - len(valid)),
            ),
            ("not-json", b"INVENTED-PLANT"),
            ("repeated-key", valid[:-1] + b',"schema":"remote_check_browser.v1"}'),
            ("another-schema", dict(RESULT, schema="remote_check_browser.v2")),
            ("key-missing", without),
            ("key-added", dict(RESULT, INVENTED="INVENTED-PLANT")),
            ("item-missing", fewer),
            (
                "item-added",
                replaced(RESULT, ("items", "INVENTED"), dict(status=200, reason=None)),
            ),
            ("item-key-added", item("tile", INVENTED=1)),
            ("status-boolean", item("tile", status=True)),
            ("status-string", item("tile", status="206")),
            ("status-below", item("tile", status=99)),
            ("status-above", item("tile", status=600)),
            ("reason-of-another-item", item("card", reason="tile_not_rendered")),
            ("reason-unknown", item("card", reason="INVENTED-PLANT")),
            ("null-reason-null-status", item("card", status=None)),
            (
                "path-other-origin",
                dict(RESULT, events_path="https://other.invalid" + EVENTS),
            ),
            ("path-upper-case", dict(RESULT, events_path="/api/answers/AB/events")),
            ("path-traversal", dict(RESULT, events_path="/api/answers/../events")),
            ("path-trailing-line", dict(RESULT, events_path=EVENTS + "\n")),
            ("not-an-object", []),
        ]
        for name, plant in cases:
            with self.subTest(case=name):
                self.opened.clear()
                self.result = plant
                self.browser_down("browser_result_invalid")
        # The boundary: a file of exactly the bound is read whole and passes.
        self.result = valid + b" " * (remote_check.RESULT_BYTES - len(valid))
        self.assertEqual(self.check()[0], 0)

    def test_browser_reason_printed(self) -> None:
        total = 0
        for name, reasons in remote_check.ITEM_REASONS.items():
            label = remote_check.LABELS[name]
            for reason in reasons:
                for status in (STATUSES[name], 404, None):
                    with self.subTest(item=name, reason=reason, status=status):
                        self.result = replaced(
                            RESULT, ("items", name), dict(status=status, reason=reason)
                        )
                        line = (
                            no_status(label, reason)
                            if status is None
                            else failed(label, status, reason)
                        )
                        self.expect({name: line}, NEUTRAL)
                        total += 1
        self.assertEqual(total, 29 * 3)

    def test_unlisted_browse_refusal_is_browser_failed(self) -> None:
        def browse() -> bytes:
            raise Refusal("INVENTED_reason")

        outcomes, path = remote_check.browser_items(browse)
        self.assertIsNone(path)
        self.assertEqual(list(outcomes), list(BROWSER))
        self.assertEqual(set(outcomes.values()), {Outcome(None, "browser_failed")})

    def test_failed_card_without_events_path(self) -> None:
        self.result["items"]["card"] = dict(status=429, reason="card_playbook_refused")
        self.result["events_path"] = None
        self.expect(
            {
                "card": failed("card with fact chip", 429, "card_playbook_refused"),
                "stream": no_status("streamed answer", "stream_answer_unavailable"),
            },
            NEUTRAL,
        )

    def test_launcher_bounds_its_child(self) -> None:
        python = (sys.executable, "-I", "-B", "-c")
        env = {"HOME": str(self.root)}  # An unset home makes a local lookup.
        marker = self.root / "INVENTED-late"
        touch = f"import time, pathlib; time.sleep(1.2); pathlib.Path({str(marker)!r}).touch()"
        # The child starts a child of its own, and both outlive the bound.
        late = f"import subprocess, sys; subprocess.run([*{python!r}, {touch!r}])"
        self.assertEqual(
            REAL_LAUNCH((*python, "raise SystemExit(3)"), self.root, env, 5), 3
        )
        started = time.monotonic()
        self.assertIsNone(REAL_LAUNCH((*python, late), self.root, env, 0.4))
        self.assertLess(time.monotonic() - started, 1.0)
        time.sleep(1.4)
        self.assertFalse(marker.exists(), "a process of the child outlived its bound")
        with self.assertRaises(FileNotFoundError):
            REAL_LAUNCH(("INVENTED-no-such-program",), self.root, env, 1)


class ClosingLine(unittest.TestCase):
    """List G and R3-F3."""

    HEALTH_FAILURES = (
        ("no_response", None, UNDECIDED),
        ("tls_failed", None, UNDECIDED),
        ("response_timeout", None, UNDECIDED),
        ("response_timeout", 200, UNDECIDED),
        ("status_unexpected", 404, UNDECIDED),
        ("redirect_refused", 302, NEUTRAL),
        ("response_too_large", 200, NEUTRAL),
        ("health_malformed", 200, NEUTRAL),
        ("health_not_ok", 200, NEUTRAL),
    )

    def outcomes(self, **changed: Outcome) -> dict[str, Outcome]:
        made = {name: Outcome(200, None) for name in remote_check.LABELS}
        made.update(changed)
        return made

    def browser_unavailable(self, health: Outcome) -> dict[str, Outcome]:
        down = {name: Outcome(None, "browser_unavailable") for name in BROWSER}
        return self.outcomes(
            health=health, stream=Outcome(None, "stream_answer_unavailable"), **down
        )

    def test_closing_line(self) -> None:
        def entry(reason: str) -> Outcome:
            return Outcome(remote.STATUS[reason], reason, entry=True)

        exposure = entry("remote_exposure_required")
        upstream, route = (
            entry("entry_" + x + "_unavailable") for x in ("upstream", "route")
        )
        refused, silent = entry("host_refused"), Outcome(None, "no_response")
        content = Outcome(202, "card_missing")
        for name, changed, sentence in (
            ("1", {}, PASSED),
            ("2", dict(health=exposure), NOT_AUTHORISED),
            ("2-stream", dict(stream=exposure), NOT_AUTHORISED),
            ("3-upstream", dict(health=upstream), NOT_SERVING),
            ("3-route", dict(health=route), NOT_SERVING),
            ("4", dict(health=refused), ENTRY_REFUSED),
            ("5", dict(health=silent), UNDECIDED),
            ("6", dict(card=content), NEUTRAL),
            ("2-before-3", dict(health=upstream, stream=exposure), NOT_AUTHORISED),
            ("3-before-4", dict(health=refused, stream=route), NOT_SERVING),
            ("4-before-5", dict(health=silent, stream=refused), ENTRY_REFUSED),
            ("5-before-6", dict(health=silent, card=content), UNDECIDED),
        ):
            with self.subTest(case=name):
                outcomes = self.outcomes(**changed)
                self.assertEqual(remote_check.closing(outcomes), sentence)
                self.assertEqual(
                    remote_check.lines(outcomes)[-1], "remote-check: " + sentence
                )
        self.assertEqual(
            remote_check.SENTENCES,
            (PASSED, NOT_AUTHORISED, NOT_SERVING, ENTRY_REFUSED, UNDECIDED, NEUTRAL),
        )

    def test_an_unrecognised_body_is_never_an_entry_answer(self) -> None:
        # The same reason word without the exact entry body claims nothing.
        outcomes = self.outcomes(health=Outcome(503, "remote_exposure_required"))
        self.assertEqual(remote_check.closing(outcomes), NEUTRAL)

    def fallback_table(self) -> None:
        for reason, status, sentence in self.HEALTH_FAILURES:
            outcomes = self.browser_unavailable(Outcome(status, reason))
            line = remote_check.closing(outcomes)
            # R3-F3: no entry body was received, so nothing "answered".
            self.assertNotRegex(line, r"answer", (reason, status))
            self.assertEqual(line, sentence, (reason, status))

    def test_fallback_closing_line_claims_no_answer(self) -> None:
        self.fallback_table()
        reasons = {reason for reason, _, _ in self.HEALTH_FAILURES}
        self.assertEqual(
            reasons,
            {
                "no_response",
                "tls_failed",
                "redirect_refused",
                "response_timeout",
                "response_too_large",
                "status_unexpected",
                "health_malformed",
                "health_not_ok",
            },
        )

    def test_planted_availability_assertion_turns_red(self) -> None:
        planted = (*remote_check.SENTENCES[:5], ROUND_3_SENTENCE)
        with patch.object(remote_check, "SENTENCES", planted):
            result = unittest.TestResult()
            unittest.FunctionTestCase(self.fallback_table).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("redirect_refused", result.failures[0][1])

    @settings(deadline=None, max_examples=300)
    @given(
        health=st.sampled_from(
            [
                None,
                *sorted(remote_check.UNDECIDED),
                "health_malformed",
                "redirect_refused",
            ]
        ),
        entry=st.lists(st.sampled_from(sorted(remote.ENTRY_REASONS)), max_size=2),
        browser=st.sampled_from([None, "browser_failed", "card_missing"]),
    )
    def test_closing_line_matches_its_six_row_oracle(
        self, health: str | None, entry: list[str], browser: str | None
    ) -> None:
        outcomes = self.outcomes(
            health=Outcome(None, health), card=Outcome(None, browser)
        )
        for name, reason in zip(("health", "stream"), entry, strict=False):
            outcomes[name] = Outcome(503, reason, entry=True)
        reasons = [outcome.reason for outcome in outcomes.values()]
        if all(reason is None for reason in reasons):
            wanted = PASSED
        elif "remote_exposure_required" in entry:
            wanted = NOT_AUTHORISED
        elif {"entry_upstream_unavailable", "entry_route_unavailable"} & set(entry):
            wanted = NOT_SERVING
        elif entry:
            wanted = ENTRY_REFUSED
        elif health in {
            "no_response",
            "tls_failed",
            "response_timeout",
            "status_unexpected",
        }:
            wanted = UNDECIDED
        else:
            wanted = NEUTRAL
        line = remote_check.closing(outcomes)
        self.assertEqual(line, wanted)
        self.assertEqual("answered" in line, bool(entry))


class HostileLeaves(CheckCase):
    """R3-F2: every leaf and four hostile values, each judged by its own domain."""

    def test_health_leaves_follow_the_health_domain(self) -> None:
        count = 0
        for path in leaves(HEALTH):
            for hostile in HOSTILE:
                body = encoded(replaced(HEALTH, path, hostile))
                # The one valid substitution: a non-negative row count.
                valid = path == ("local_ledger_rows",) and hostile == 7
                with self.subTest(path=path, hostile=hostile):
                    self.assertEqual(
                        decided(remote_check.health_rule, body),
                        None if valid else "health_malformed",
                    )
                    count += 1
        self.assertEqual(count, 13 * 4)

    def test_local_ledger_rows_seven_stays_valid(self) -> None:
        self.health = dict(HEALTH, local_ledger_rows=7)
        code, lines, _ = self.check()
        self.assertEqual((code, lines[0]), (0, "PASS health: HTTP 200"))

    def test_entry_body_leaves_are_never_an_entry_answer(self) -> None:
        document = json.loads(remote.closed_body("entry_upstream_unavailable"))
        for path in leaves(document):
            for hostile in HOSTILE:
                body = encoded(replaced(document, path, hostile))
                with self.subTest(path=path, hostile=hostile):
                    self.assertEqual(
                        decided(remote_check.other_status, 503, None, lambda b=body: b),
                        "status_unexpected",
                    )

    def frame_cases(self) -> Any:
        for index, (kind, data) in enumerate((*FRAMES, ("error", {"error_code": "X"}))):
            base = [*FRAMES[:1], (kind, data)] if kind == "error" else list(FRAMES)
            at = 1 if kind == "error" else index
            record = dict(id=str(at + 1), event=kind, data=data)
            for path in leaves(record):
                for hostile in HOSTILE:
                    yield kind, base, at, path, replaced(record, path, hostile)

    def frame_expectation(
        self, kind: str, at: int, total: int, path: Any, hostile: Any
    ) -> str | None:
        """The reader contract, by field: id, kind, data, then data's own leaves."""
        unchanged = "stream_error_event" if kind == "error" else None
        text = json.dumps(hostile)
        if path == ("id",):
            if not text.isdigit():
                return "stream_frame_malformed"
            others = {str(i + 1) for i in range(total)} - {str(at + 1)}
            return "stream_order_invalid" if text in others else unchanged
        if path == ("event",):
            return "stream_frame_malformed"
        if path == ("data",):
            valid = kind == "narrative" or isinstance(hostile, dict)
            return unchanged if valid else "stream_frame_malformed"
        return unchanged  # Inside data the reader checks presence and shape only.

    def test_frame_leaves_follow_the_reader_contract(self) -> None:
        count = 0
        for kind, base, at, path, record in self.frame_cases():
            hostile = record
            for key in path:
                hostile = hostile[key]
            text = "".join(
                frame(
                    json.dumps(record["id"])
                    if (i == at and path == ("id",))
                    else i + 1,
                    json.dumps(record["event"])
                    if (i == at and path == ("event",))
                    else k,
                    json.dumps(record["data"] if i == at else d, separators=(",", ":")),
                )
                for i, (k, d) in enumerate(base)
            )
            wanted = self.frame_expectation(kind, at, len(base), path, hostile)
            with self.subTest(kind=kind, path=path, hostile=hostile):
                self.assertEqual(fed(text.encode()), wanted)
                count += 1
        self.assertGreaterEqual(count, 8 * 3 * 4)

    def result_fixtures(self) -> dict[str, dict[str, Any]]:
        failing = copy.deepcopy(RESULT)
        for name, reasons in remote_check.ITEM_REASONS.items():
            failing["items"][name] = dict(status=404, reason=reasons[0])
        return dict(passing=copy.deepcopy(RESULT), failing=failing)

    def test_result_leaves_follow_the_result_schema(self) -> None:
        count = 0
        for kind, fixture in self.result_fixtures().items():
            for path in leaves(fixture):
                for hostile in HOSTILE:
                    # Valid by the schema: a null events path; a null reason
                    # beside an integer status (a pass); a null status beside
                    # a reason (a failure that received no response).
                    valid = hostile is None and (
                        path == ("events_path",)
                        or path[-1] == "reason"
                        or (path[-1] == "status" and kind == "failing")
                    )
                    raw = encoded(replaced(fixture, path, hostile))
                    with self.subTest(fixture=kind, path=path, hostile=hostile):
                        self.assertEqual(
                            decided(remote_check.browser_result, raw),
                            None if valid else "browser_result_invalid",
                        )
                        count += 1
        self.assertEqual(count, 2 * 12 * 4)

    def test_null_reason_on_a_successful_item_is_a_no_op(self) -> None:
        for name in BROWSER:
            self.result = replaced(RESULT, ("items", name, "reason"), None)
            self.assertEqual(self.result, RESULT)
            code, lines, _ = self.check()
            self.assertEqual((code, lines[:-1]), (0, list(ALL_PASS.values())))

    def test_null_events_path_keeps_browser_items_valid(self) -> None:
        self.result = replaced(RESULT, ("events_path",), None)
        outcomes, path = remote_check.browser_result(encoded(self.result))
        self.assertIsNone(path)
        self.assertEqual({o.reason for o in outcomes.values()}, {None})
        code, lines, _ = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(lines[1:6], list(ALL_PASS.values())[1:6])
        self.assertEqual(
            lines[6], no_status("streamed answer", "stream_answer_unavailable")
        )

    def test_hostile_leaf_never_passes_a_failed_item_through_the_command(self) -> None:
        self.result = replaced(RESULT, ("items", "card", "status"), {"toString": None})
        self.browser_down("browser_result_invalid")


class Frames_(unittest.TestCase):
    KIND = st.sampled_from([*sorted(remote_check.KINDS), "INVENTED"])
    IDENTITY = st.sampled_from(["1", "2", "3", "4", "07", "x", ""])
    DATA = st.sampled_from(["{}", '{"a":[1]}', "7", "null", "[]", '"s"', "{", "NaN"])

    @staticmethod
    def oracle(frames: list[tuple[str, str, str]], tail: str) -> str | None:
        def refuse(_: str) -> Any:
            raise ValueError

        seen: set[str] = set()
        done = False
        for identity, kind, text in frames:
            if done:
                return "stream_order_invalid"
            try:
                data = json.loads(text, parse_constant=refuse)
            except ValueError:
                return "stream_frame_malformed"
            if (
                kind not in remote_check.KINDS
                or not (identity.isascii() and identity.isdigit())
                or (kind != "narrative" and not isinstance(data, dict))
            ):
                return "stream_frame_malformed"
            if identity in seen:
                return "stream_order_invalid"
            if kind == "error":
                return "stream_error_event"
            seen.add(identity)
            done = kind == "done"
        return None if done and not tail.strip() else "stream_truncated"

    @settings(deadline=None, max_examples=500)
    @given(
        frames=st.lists(st.tuples(IDENTITY, KIND, DATA), max_size=6),
        tail=st.sampled_from(
            ["", "\r\n", "id: 9", "id: 9\r\nevent: done\r\ndata: {}\r\n"]
        ),
        cuts=st.lists(st.integers(min_value=0, max_value=400), max_size=5),
        newline=st.sampled_from(["\r\n", "\n"]),
    )
    def test_frames_match_the_oracle_however_they_are_cut(
        self,
        frames: list[tuple[str, str, str]],
        tail: str,
        cuts: list[int],
        newline: str,
    ) -> None:
        text = "".join(frame(*one) for one in frames) + tail
        body = text.replace("\r\n", newline).encode()
        wanted = self.oracle(frames, tail)
        self.assertEqual(fed(body), wanted)
        self.assertEqual(fed(body, cuts), wanted)


class Records(unittest.TestCase):
    def test_check_reasons_closed(self) -> None:
        carried = {
            reason for group in remote_check.ITEM_REASONS.values() for reason in group
        }
        carried |= set(remote_check.BROWSER_REASONS) | set(remote.ENTRY_REASONS)
        carried |= {"stream_answer_unavailable", "response_timeout", "tls_failed"}
        carried |= {"no_response", "operation_failed"}
        for path in (
            "scripts/operations/remote_check.py",
            "scripts/commands/remote_check.py",
        ):
            carried |= set(
                re.findall(r'Refusal\(\s*"([a-z_0-9]+)"', (ROOT / path).read_text())
            )
        self.assertGreater(len(carried), 60)
        self.assertEqual(carried - set(CODES), set())
        planted = carried | {"INVENTED_reason"}
        self.assertEqual(planted - set(CODES), {"INVENTED_reason"})

    def test_item_reasons_equal_the_runner_lists(self) -> None:
        text = (ROOT / "web/tests/remote-check/decide.ts").read_text()
        page = text[
            text.index("const PAGE_REASONS") : text.index("export const ITEM_REASONS")
        ]
        items = text[text.index("export const ITEM_REASONS") :]
        items = items[: items.index("} as const;")]
        quoted = re.compile(r"'([a-z_]+)'")
        listed = remote_check.ITEM_REASONS
        self.assertEqual(tuple(quoted.findall(page)), listed["start_page_en"])
        self.assertEqual(
            tuple(quoted.findall(items)),
            (*listed["card"], *listed["map_style"], *listed["tile"]),
        )
        self.assertEqual(list(listed), re.findall(r"^  ([a-z_]+):", items, re.M))
        self.assertIn("RESULT_SCHEMA = '" + remote_check.RESULT_SCHEMA + "'", text)
        self.assertIn("STEP_MS = 15_000", text)
        self.assertEqual(remote_check.BROWSER_STEP_SECONDS, 15.0)

    def test_bounds_equal_document_13(self) -> None:
        text = DOCUMENT_13.read_text()
        for name, unit in (
            ("CONNECT_SECONDS", "seconds"),
            ("READ_SECONDS", "seconds"),
            ("ITEM_SECONDS", "seconds"),
            ("HEALTH_BYTES", "bytes"),
            ("STREAM_BYTES", "bytes"),
            ("BROWSER_SECONDS", "seconds"),
            ("BROWSER_STEP_SECONDS", "seconds"),
            ("RESULT_BYTES", "bytes"),
        ):
            with self.subTest(bound=name):
                rows = re.findall(rf"\| `{name}` \| ([0-9,]+) {unit} \|", text)
                self.assertEqual(len(rows), 1, "document 13 holds this bound once")
                self.assertEqual(
                    int(rows[0].replace(",", "")), getattr(remote_check, name)
                )
        self.assertEqual(
            (
                Limits().connect,
                Limits().read,
                Limits().item,
                Limits().health,
                Limits().stream,
            ),
            (5.0, 10.0, 30.0, 65_536, 1_048_576),
        )

    def test_closing_sentences_equal_document_13(self) -> None:
        text = DOCUMENT_13.read_text()
        for sentence in remote_check.SENTENCES:
            with self.subTest(sentence=sentence):
                self.assertEqual(text.count("`remote-check: " + sentence + "`"), 1)
        self.assertNotIn(ROUND_3_SENTENCE, text)

    def test_reader_never_follows_a_redirect_or_reads_a_setting(self) -> None:
        source = (ROOT / "scripts/operations/remote_check.py").read_text()
        for word in ("urllib", "os.environ", "getenv", "print(", "subprocess"):
            self.assertNotIn(word, source)
        without = without_refusal(remote_check.other_status, "redirect_refused")
        with self.assertRaisesRegex(Refusal, "status_unexpected"):
            without(302, "https://other.invalid/", lambda: b"")


if __name__ == "__main__":
    unittest.main()
