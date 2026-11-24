"""S3-T20 admission, handover and first-exposure order on production paths.

States are written by the real ``activate``; where the entry process is part
of the case the real ``deploy.up`` runs on invented process seams and the
entry is the real ``entry.prepared`` handler. Hosts are ``.invalid`` names.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import re
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler
from typing import Any
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st
from s3_t20_support import (
    LOCAL,
    REMOTE,
    Deployment,
    EntryCase,
    LiveState,
    Upstream,
    edited,
    message,
    parsed,
    reason_of,
    wire,
)
from s3_t28_network import trace
from s3_t28_support import ROOT, WorkspaceCase

import preflight
from commands.main import main
from operations import deploy, entry, remote
from operations.activation import active_route, entries
from operations.common import Refusal
from operations.runbook import FIRST_EXPOSURE, require_tunnel_start

CLOSED = "remote_exposure_required"
FOUR = (
    (LOCAL, None),
    (LOCAL, "http://" + LOCAL),
    (REMOTE, None),
    (REMOTE, "https://" + REMOTE),
)


ADMISSION = remote.admission
P_ROW = '    if is_bound:\n        raise Refusal("remote_exposure_required")\n'
H_ROW = '    if host_held:\n        raise Refusal("remote_exposure_required")\n'


def loopback_rows_removed(exposure: object, is_bound: bool, host_held: bool) -> None:
    """The planted admission: both loopback refusals deleted, nothing else."""
    try:
        ADMISSION(exposure, is_bound, host_held)
    except Refusal as refusal:
        if refusal.reason != CLOSED:
            raise


class Admission(EntryCase):
    def setUp(self) -> None:
        super().setUp()
        self.live = LiveState(self)
        self.upstream = Upstream(self)

    def four(self, port: int) -> list[str | None]:
        answers = []
        for host, origin in FOUR:
            headers = [("Host", host)] + ([("Origin", origin)] if origin else [])
            answers.append(reason_of(wire(port, message(headers=headers))))
        return answers

    def test_exposure_never_depends_on_host(self) -> None:
        self.live.expose()
        port = self.serve_entry(self.live.state, REMOTE, self.upstream)
        for host in (LOCAL, REMOTE):
            answer = wire(port, message(headers=[("Host", host)]))
            self.assertEqual(parsed(answer)[0], 200)
        self.assertEqual(len(self.upstream.requests), 2)
        # One thing changes: a real authorised loopback operation. The
        # handler, its host and the upstream are untouched.
        self.assertEqual(self.live.restart()["exposure"], "loopback")
        self.assertEqual(self.four(port), [CLOSED] * 4)
        self.assertEqual(len(self.upstream.requests), 2)
        # Plant: the loopback rows' refusal alone is deleted; localhost relays.
        with patch("operations.remote.admission", loopback_rows_removed):
            planted = self.four(port)
        self.assertEqual(planted[:2], [None, None])
        self.assertGreater(len(self.upstream.requests), 2)

    def test_bound_state_closes_hostless_entry(self) -> None:
        self.live.expose()
        self.live.restart()
        port = self.serve_entry(self.live.state, None, self.upstream)
        self.assertEqual(self.four(port), [CLOSED] * 4)
        self.assertEqual(self.upstream.requests, [])
        # Plant: P leaves the row and H stays; the reboot case relays.
        self.guard_red(remote.admission, ("loopback", True, False), CLOSED)
        with patch("operations.remote.admission", edited(ADMISSION, P_ROW, "")):
            self.assertEqual(self.four(port)[:2], [None, None])
        self.assertEqual(len(self.upstream.requests), 2)

    def test_host_holding_entry_closes_without_binding(self) -> None:
        self.assertFalse(remote.bound(self.live.state))
        port = self.serve_entry(self.live.state, REMOTE, self.upstream)
        self.assertEqual(self.four(port), [CLOSED] * 4)
        self.assertEqual(self.upstream.requests, [])
        # Plant: H leaves the row and P stays; the host-holding entry relays.
        self.guard_red(remote.admission, ("loopback", False, True), CLOSED)
        with patch("operations.remote.admission", edited(ADMISSION, H_ROW, "")):
            self.assertEqual(self.four(port), [None] * 4)
        self.assertEqual(len(self.upstream.requests), 4)

    def test_unbound_state_keeps_loopback_entry(self) -> None:
        port = self.serve_entry(self.live.state, None, self.upstream)
        self.assertEqual(self.four(port), [None, None, "host_refused", "host_refused"])
        self.assertEqual(len(self.upstream.requests), 2)

    def test_hostless_entry_on_public_route_refused(self) -> None:
        self.live.expose()
        port = self.serve_entry(self.live.state, None, self.upstream)
        self.assertEqual(self.four(port), ["remote_host_missing"] * 4)
        self.assertEqual(self.upstream.requests, [])

    def test_failed_exposure_leaves_state_bound(self) -> None:
        port = self.serve_entry(self.live.state, None, self.upstream)
        before = active_route(self.live.state)

        def fail(*args: Any) -> None:
            raise Refusal("startup_not_ready")

        with self.assertRaises(Refusal) as caught:
            self.live.expose(ready=fail)
        self.assertEqual(caught.exception.reason, "startup_not_ready")
        self.assertEqual(active_route(self.live.state), before)
        self.assertTrue(remote.bound(self.live.state))
        self.assertEqual(self.four(port), [CLOSED] * 4)
        self.assertEqual(self.upstream.requests, [])

    def test_refused_exposure_appends_nothing(self) -> None:
        port = self.serve_entry(self.live.state, None, self.upstream)
        before = (entries(self.live.state), active_route(self.live.state))
        raw = self.live.fixture.raw
        changes: tuple[tuple[str, Callable[[], None]], ...] = (
            ("missing approval", lambda: raw.update(gate_approval=None)),
            (
                "stale approval",
                lambda: raw.update(
                    gate_approval=self.live.approval(release_id="bb" * 32)
                ),
            ),
            (
                "rejected approval",
                lambda: raw.update(
                    gate_approval=self.live.approval(verdict="REJECTED")
                ),
            ),
            (
                "another gate",
                lambda: raw.update(gate_approval=self.live.approval(gate="S2")),
            ),
        )
        for label, change in changes:
            self.live.request("expose_public")
            change()
            with self.subTest(label=label), self.assertRaises(Refusal) as caught:
                self.live.fixture.execute(handover=lambda: None)
            self.assertEqual(caught.exception.reason, "public_gate_approval_required")
        self.assertEqual(
            (entries(self.live.state), active_route(self.live.state)), before
        )
        self.assertFalse(remote.bound(self.live.state))
        self.assertEqual(self.four(port)[:2], [None, None])

    def test_admission_on_the_wire_equals_four_row_oracle(self) -> None:
        """E, P and H alone decide the table; caller input never selects a row."""
        doors: dict[tuple[str, bool, bool], tuple[int, Upstream]] = {}
        for exposure, was_bound in (
            ("loopback", False),
            ("loopback", True),
            ("public_entry", True),
        ):
            live = LiveState(self)
            if was_bound:
                live.expose()
            if exposure == "loopback" and was_bound:
                live.restart()
            self.assertEqual(remote.bound(live.state), was_bound)
            for held in (False, True):
                upstream = Upstream(self)
                port = self.serve_entry(live.state, REMOTE if held else None, upstream)
                doors[exposure, was_bound, held] = port, upstream

        @settings(max_examples=200, deadline=None)
        @given(
            door=st.sampled_from(sorted(doors)),
            host=st.sampled_from(
                [LOCAL, REMOTE, REMOTE + ":443", "third.s3-t20.invalid", ""]
            ),
            origin=st.sampled_from(
                [None, "http://" + LOCAL, "https://" + REMOTE, "null"]
            ),
            method=st.sampled_from(["GET", "POST", "PUT"]),
            target=st.sampled_from(
                ["/", "/api/release", "/api/presenter/state", "/a/../b"]
            ),
        )
        def check(
            door: tuple[str, bool, bool],
            host: str,
            origin: str | None,
            method: str,
            target: str,
        ) -> None:
            (exposure, was_bound, held), (port, upstream) = door, doors[door]
            headers = [("Host", host)] + ([("Origin", origin)] if origin else [])
            if method == "POST":
                headers.append(("Content-Length", "0"))
            seen = len(upstream.requests)
            answer = reason_of(wire(port, message(method, target, headers)))
            if exposure == "public_entry":
                row = None if held else "remote_host_missing"
            else:
                row = CLOSED if was_bound or held else None
            if row is not None:
                self.assertEqual(answer, row)
                self.assertEqual(len(upstream.requests), seen)
            else:
                self.assertNotIn(answer, {CLOSED, "remote_host_missing"})

        check()


class Handover(EntryCase):
    def setUp(self) -> None:
        super().setUp()
        self.live = LiveState(self)
        self.upstream = Upstream(self)
        self.dep = Deployment(self, self.live, self.upstream)

    def pages(self) -> int:
        return sum(seen["target"] != "/health" for seen in self.upstream.requests)

    def test_authorised_exposure_replaces_the_entry(self) -> None:
        self.dep.up("restart")
        self.assertEqual(self.dep.events, [("start", 18088), ("start", 8088)])
        self.dep.up("expose_public", {remote.HOST_NAME: REMOTE})
        self.assertEqual(self.dep.events[2:], [("stop", 8088), ("start", 8088)])
        self.assertEqual(self.dep.unstopped(), [1, 0, 1])
        for host in (LOCAL, REMOTE):
            self.assertEqual(parsed(self.dep.ask(host))[0], 200)
        # Repeated exposure: still one owned listener, on the new name.
        other = "second.s3-t20.invalid"
        self.dep.up("expose_public", {remote.HOST_NAME: other})
        self.assertEqual(self.dep.unstopped(), [1, 0, 1, 0, 1])
        self.assertEqual(parsed(self.dep.ask(other))[0], 200)
        self.refused(self.dep.ask(REMOTE), "host_refused")
        hosts = [(port, env.get(remote.HOST_NAME)) for port, env in self.dep.children]
        self.assertEqual(
            hosts, [(18088, None), (8088, None), (8088, REMOTE), (8088, other)]
        )

    def test_loopback_start_never_gives_entry_the_host(self) -> None:
        self.dep.up("restart", {remote.HOST_NAME: REMOTE})
        self.assertEqual([port for port, _ in self.dep.children], [18088, 8088])
        for _, environ in self.dep.children:
            self.assertNotIn(remote.HOST_NAME, environ)
        self.assertEqual(parsed(self.dep.ask())[0], 200)
        self.refused(self.dep.ask(REMOTE), "host_refused")
        # Plant: the entry child receives the host on a loopback route.
        self.dep.down()
        with (
            patch(
                "operations.remote.entry_environment",
                lambda child, exposure, raw: {**child, remote.HOST_NAME: raw},
            ),
            self.assertRaises(Refusal) as caught,
        ):
            self.dep.up("restart", {remote.HOST_NAME: REMOTE})
        # Even then H closes the door, so readiness itself fails closed.
        self.assertEqual(caught.exception.reason, "startup_not_ready")
        self.assertEqual(self.dep.children[-1][1].get(remote.HOST_NAME), REMOTE)

    def test_entry_readiness_on_closed_door(self) -> None:
        self.dep.up("restart")
        self.dep.up("expose_public", {remote.HOST_NAME: REMOTE})
        # The earlier host-holding entry stays and answers the closed body.
        self.dep.up("restart")
        self.assertEqual(self.dep.unstopped(), [1, 0, 1])
        self.refused(self.dep.ask(), CLOSED)
        # After down, a new hostless entry starts on the bound state.
        self.dep.down({remote.HOST_NAME: REMOTE})
        self.dep.up("restart")
        self.assertNotIn(remote.HOST_NAME, self.dep.children[-1][1])
        self.refused(self.dep.ask(REMOTE), CLOSED)
        events = len(self.dep.events)
        # Plant: an entry that still relays health is not ready.
        self.dep.down()
        self.dep.entry_handler = lambda environ: relaying(self.live)
        with self.assertRaises(Refusal) as caught:
            self.dep.up("restart")
        self.assertEqual(caught.exception.reason, "startup_not_ready")
        self.assertEqual(self.dep.events[events:][-1], ("stop", 8088))
        # Plant: an entry that answers nothing is not ready either.
        self.dep.down()
        self.dep.entry_handler = lambda environ: Silent
        with self.assertRaises(Refusal) as caught:
            self.dep.up("restart")
        self.assertEqual(caught.exception.reason, "startup_not_ready")
        self.assertEqual(self.dep.events[-1], ("stop", 8088))

    def test_failed_exposure_through_up_leaves_closed_door(self) -> None:
        self.dep.up("restart")
        count = len(entries(self.live.state))
        # A missing or invalid host appends nothing and changes no process.
        for value, reason in (
            ("", "remote_host_missing"),
            (REMOTE + ":443", "remote_host_invalid"),
        ):
            with self.subTest(value=value), self.assertRaises(Refusal) as caught:
                self.dep.up("expose_public", {remote.HOST_NAME: value} if value else {})
            self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(len(entries(self.live.state)), count)
        self.assertEqual(self.dep.unstopped(), [1])
        self.assertEqual(parsed(self.dep.ask())[0], 200)
        # Readiness fails after the authorisation was appended.
        self.dep.healthy = False
        self.dep.terminate(dict(port=18088), "live")
        (self.live.state / "process-18088.json").unlink()
        with self.assertRaises(Refusal) as caught:
            self.dep.up("expose_public", {remote.HOST_NAME: REMOTE})
        self.assertEqual(caught.exception.reason, "startup_not_ready")
        self.assertEqual(len(entries(self.live.state)), count + 1)
        self.assertEqual(route_of(self.live)["exposure"], "loopback")
        self.assertEqual(self.dep.unstopped(), [1])
        before = self.pages()
        self.refused(self.dep.ask(), CLOSED)
        self.refused(self.dep.ask(REMOTE), CLOSED)
        self.assertEqual(self.pages(), before)

    def test_foreign_entry_process_is_never_signalled(self) -> None:
        self.dep.up("restart")
        self.dep.foreign.add(8088)
        with self.assertRaises(Refusal) as caught:
            self.dep.up("expose_public", {remote.HOST_NAME: REMOTE})
        self.assertEqual(caught.exception.reason, "process_identity_mismatch")
        self.assertNotIn(("stop", 8088), self.dep.events)
        self.assertEqual(self.dep.unstopped(), [1])
        # The route switched; the hostless entry left running is closed.
        self.refused(self.dep.ask(REMOTE), "remote_host_missing")
        self.refused(self.dep.ask(), "remote_host_missing")

    def test_entry_start_rules(self) -> None:
        """What the entry process itself refuses or holds when it starts."""
        self.dep.up("restart")
        route = route_of(self.live)
        for label, planted in (
            ("no route", None),
            ("staging route", dict(route, environment="staging")),
            ("another entry port", dict(route, entry_port=8090)),
        ):
            with (
                self.subTest(label=label),
                patch("operations.entry.active_route", return_value=planted),
                self.assertRaises(Refusal) as caught,
            ):
                entry.prepared({})
            self.assertEqual(caught.exception.reason, "activation_target_mismatch")
        # Unbound loopback route: no host is held, with or without the name.
        hostless = self.serve_entry(
            self.live.state, None, self.upstream, handler=lambda *_: entry.prepared({})
        )
        self.assertEqual(reason_of(wire(hostless, message())), None)
        holding = self.serve_entry(
            self.live.state,
            None,
            self.upstream,
            handler=lambda *_: entry.prepared({remote.HOST_NAME: REMOTE}),
        )
        self.refused(wire(holding, message()), CLOSED)
        # Public route: the entry never starts without a valid host.
        self.dep.up("expose_public", {remote.HOST_NAME: REMOTE})
        for value, reason in (
            ("", "remote_host_missing"),
            (REMOTE + ":443", "remote_host_invalid"),
            ("localhost", "remote_host_invalid"),
        ):
            with self.subTest(value=value), self.assertRaises(Refusal) as caught:
                entry.prepared({remote.HOST_NAME: value} if value else {})
            self.assertEqual(caught.exception.reason, reason)

    def test_down_never_refuses_the_host(self) -> None:
        self.dep.up("restart")
        settings = {remote.HOST_NAME: REMOTE, "EII_ENVIRONMENT": "live"}
        with patch(
            "operations.deploy.read_environment", return_value=self.dep.env
        ) as read:
            self.dep.down(settings)
        read.assert_called_once_with({"EII_ENVIRONMENT": "live"})
        self.assertEqual(self.dep.unstopped(), [1, 0])
        # Plant: the stop reads the settings as given, host included.
        with (
            patch(
                "operations.deploy.read_environment", return_value=self.dep.env
            ) as read,
            patch("operations.process.down"),
        ):
            edited(deploy.down, "remote.take_host(environ)[0]", "environ")(settings)
        read.assert_called_once_with(settings)


def route_of(live: LiveState) -> dict[str, Any]:
    route = active_route(live.state)
    assert route is not None
    return route


def relaying(live: LiveState) -> Any:
    """A planted entry whose admission table refuses nothing."""

    class Relaying(entry.handler(live.state, None)):  # type: ignore[misc]
        def admit(self) -> Any:
            with patch("operations.remote.admission", lambda *args: None):
                return super().admit()

    return Relaying


class Silent(BaseHTTPRequestHandler):
    """A planted entry that accepts a connection and answers nothing."""

    def handle(self) -> None:
        return None


class Tripwire(WorkspaceCase):
    def test_planted_relay_makes_no_outbound_attempt(self) -> None:
        """The deciding test, its plant included, under the syscall tripwire."""
        paths = [
            str(ROOT / part)
            for part in ("scripts/tests", "scripts", "core/src", "product/src")
        ]
        program = (
            "import sys, unittest\n"
            f"sys.path[:0] = {paths!r}\n"
            "from test_s3_t20_handover import Admission\n"
            "case = Admission('test_exposure_never_depends_on_host')\n"
            "result = unittest.TextTestRunner().run(unittest.TestSuite([case]))\n"
            "assert result.testsRun == 1 and result.wasSuccessful()\n"
        )
        code, attempts, output = trace(
            (sys.executable, "-I", "-B", "-c", program), self.root
        )
        self.assertEqual(code, 0, output)
        self.assertEqual(attempts, [])


class Tunnel:
    """A stub of the lead's tunnel: a counter, never a process or a socket."""

    def __init__(self, rows: list[dict[str, Any]], state: str) -> None:
        self.rows, self.state, self.starts = rows, state, 0

    def stop(self) -> None:
        self.rows.append(dict(step="tunnel_stopped", state=self.state, exit_code=0))

    def start(self) -> None:
        require_tunnel_start(self.rows, self.state)
        self.starts += 1


class FirstExposure(EntryCase):
    """R3-F1: the checked order of document 13's first-exposure steps."""

    def setUp(self) -> None:
        super().setUp()
        self.rows: list[dict[str, Any]] = []
        self.live = LiveState(self)
        self.upstream = Upstream(self)
        self.dep = Deployment(self, self.live, self.upstream)
        self.state = self.label(self.live)
        self.tunnel = Tunnel(self.rows, self.state)
        ready = patch(
            "preflight.run_preflight",
            side_effect=lambda *a, **k: preflight.Report((), "postgres", 0),
        )
        ready.start()
        self.addCleanup(ready.stop)

    @staticmethod
    def label(live: LiveState) -> str:
        return hashlib.sha256(str(live.state).encode()).hexdigest()

    def command(self, step: str, host: str | None = None) -> int:
        """One ``./eii up`` through the real dispatcher; its row is recorded."""
        self.live.request("restart" if step == "live_start" else "expose_public")
        self.live.fixture.bind()
        environ = {
            "EII_ENVIRONMENT": "live",
            "EII_RELEASE_DIR": str(self.dep.env.release),
        }
        if host is not None:
            environ[remote.HOST_NAME] = host
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            code = main(["up"], environ, self.root)
        self.errors = errors.getvalue()
        self.rows.append(dict(step=step, state=self.state, exit_code=code))
        return code

    def refused_start(self, reason: str, then: str | None = None) -> None:
        """The stub start is refused; with that one guard deleted it is not.

        ``then`` names the next check that still closes the start when the
        deleted guard was not the only one this record fails.
        """
        with self.assertRaises(Refusal) as caught:
            self.tunnel.start()
        self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(self.tunnel.starts, 0)
        self.guard_red(
            require_tunnel_start, (list(self.rows), self.state), reason, then=then
        )

    def test_documented_order_permits_the_start(self) -> None:
        self.tunnel.stop()
        self.assertEqual(self.command("live_start"), 0, self.errors)
        # The unbound listener relays localhost: this is why the tunnel waits.
        self.assertEqual(parsed(self.dep.ask())[0], 200)
        self.assertEqual(self.command("handover", REMOTE), 0, self.errors)
        self.tunnel.start()
        self.assertEqual(self.tunnel.starts, 1)
        self.assertEqual(parsed(self.dep.ask(REMOTE))[0], 200)
        self.assertEqual([row["step"] for row in self.rows], list(FIRST_EXPOSURE))

    def test_early_start_refused(self) -> None:
        self.tunnel.stop()
        self.refused_start(
            "tunnel_start_before_exposure", "tunnel_start_after_failed_exposure"
        )

    def test_reordered_start_refused(self) -> None:
        self.tunnel.stop()
        self.assertEqual(self.command("live_start"), 0, self.errors)
        self.refused_start(
            "tunnel_start_before_exposure", "tunnel_start_after_failed_exposure"
        )
        self.assertEqual(self.command("handover", REMOTE), 0, self.errors)
        self.tunnel.start()
        self.assertEqual(self.tunnel.starts, 1)

    def test_omitted_stop_refused(self) -> None:
        self.assertEqual(self.command("live_start"), 0, self.errors)
        self.assertEqual(self.command("handover", REMOTE), 0, self.errors)
        self.refused_start("tunnel_stop_missing")

    def test_failed_exposure_then_start_refused(self) -> None:
        self.tunnel.stop()
        self.assertEqual(self.command("live_start"), 0, self.errors)
        self.dep.healthy = False
        self.dep.terminate(dict(port=18088), "live")
        (self.live.state / "process-18088.json").unlink()
        self.assertNotEqual(self.command("handover", REMOTE), 0)
        self.assertIn("startup_not_ready", self.errors)
        self.refused_start("tunnel_start_after_failed_exposure")
        # The failed exposure left the state bound and 8088 a closed door.
        self.refused(self.dep.ask(), CLOSED)
        # A later successful exposure permits the start again.
        self.dep.healthy = True
        self.assertEqual(self.command("handover", REMOTE), 0, self.errors)
        self.tunnel.start()
        self.assertEqual(self.tunnel.starts, 1)

    def test_missing_loopback_start_refused(self) -> None:
        self.tunnel.stop()
        self.assertEqual(self.command("handover", REMOTE), 0, self.errors)
        self.refused_start("runbook_step_missing")

    def test_new_state_folder_starts_again(self) -> None:
        self.tunnel.stop()
        self.assertEqual(self.command("live_start"), 0, self.errors)
        self.assertEqual(self.command("handover", REMOTE), 0, self.errors)
        self.tunnel.start()
        # A new live state folder is unbound: the first state's record does
        # not cover it, and its own record must begin with the tunnel stopped.
        fresh = LiveState(self)
        self.assertFalse(remote.bound(fresh.state))
        other = Tunnel(self.rows, self.label(fresh))
        for step in ("live_start", "handover"):
            with self.assertRaises(Refusal) as caught:
                other.start()
            self.assertEqual(caught.exception.reason, "tunnel_stop_missing")
            self.rows.append(dict(step=step, state=other.state, exit_code=0))
        with self.assertRaises(Refusal) as caught:
            other.start()
        self.assertEqual(caught.exception.reason, "tunnel_stop_missing")
        self.assertEqual(other.starts, 0)
        del self.rows[-2:]
        other.stop()
        self.rows.append(dict(step="live_start", state=other.state, exit_code=0))
        self.rows.append(dict(step="handover", state=other.state, exit_code=0))
        other.start()
        self.assertEqual(other.starts, 1)

    def test_malformed_record_refused(self) -> None:
        good = dict(step="tunnel_stopped", state=self.state, exit_code=0)
        for label, row in (
            ("unknown step", dict(good, step="tunnel_started")),
            ("boolean exit", dict(good, exit_code=False)),
            ("text exit", dict(good, exit_code="0")),
            ("short state", dict(good, state="ab")),
            ("state not text", dict(good, state=7)),
            ("extra key", dict(good, note="INVENTED")),
            ("missing key", dict(step="tunnel_stopped", state=self.state)),
        ):
            with self.subTest(label=label):
                with self.assertRaises(Refusal) as caught:
                    require_tunnel_start([good, row], self.state)
                self.assertEqual(caught.exception.reason, "runbook_result_invalid")
        # Guard deleted: the unknown step is no longer refused as malformed.
        self.guard_red(
            require_tunnel_start,
            ([dict(good, step="tunnel_started")], self.state),
            "runbook_result_invalid",
            then="tunnel_stop_missing",
        )

    @settings(max_examples=400, deadline=None)
    @given(
        record=st.lists(
            st.tuples(st.sampled_from(FIRST_EXPOSURE), st.sampled_from([0, 1, 4])),
            max_size=8,
        )
    )
    def test_start_permission_equals_the_order_oracle(
        self, record: list[tuple[str, int]]
    ) -> None:
        letters = {"tunnel_stopped": "s", "live_start": "l", "handover": "h"}
        text = "".join(
            letters[step].upper() if code == 0 else letters[step]
            for step, code in record
        )
        if not text.startswith("S"):
            oracle: str | None = "tunnel_stop_missing"
        elif not re.search("[Hh]", text):
            oracle = "tunnel_start_before_exposure"
        elif re.search("h[^Hh]*$", text):
            oracle = "tunnel_start_after_failed_exposure"
        elif not re.search("L.*H[^Hh]*$", text):
            oracle = "runbook_step_missing"
        else:
            oracle = None
        rows = [
            dict(step=step, state=self.state, exit_code=code) for step, code in record
        ]
        other = [dict(step="handover", state="cd" * 32, exit_code=0)]
        try:
            require_tunnel_start(other + rows + other, self.state)
        except Refusal as refusal:
            self.assertEqual(refusal.reason, oracle)
        else:
            self.assertIsNone(oracle)
