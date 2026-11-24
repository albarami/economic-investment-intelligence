"""S3-T20 fixtures: real live states, a counting upstream, raw entry requests.

Every state is written by the real ``activate`` over the S3-T28 promotion
fixture. The entry under test is the real handler on an ephemeral loopback
port; the only mapped value is the verified route's upstream port, which
points at the invented upstream of the case. Hosts are ``.invalid`` names.
"""

from __future__ import annotations

import http.client
import inspect
import json
import socket
import textwrap
import threading
import unittest
from collections.abc import Callable, Iterable, Sequence
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from unittest.mock import patch

import test_s3_t28_promotion as promotion_fixture
from s3_t28_support import WorkspaceCase
from test_s3_t28_controls import without_refusal

from operations import entry
from operations.activation import active_route
from operations.common import Refusal, atomic_json, encoded, sha
from operations.config import Environment

REMOTE = "entry.s3-t20.invalid"
LOCAL = "localhost:8088"
BOUND_KEYS = ("code_version", "release_id", "application_sha256")


class LiveState:
    """One live state folder, changed only through the real ``activate``."""

    def __init__(self, case: unittest.TestCase) -> None:
        self.fixture = promotion_fixture.Promotion()
        self.fixture.setUp()
        case.addCleanup(self.fixture.doCleanups)
        self.state: Path = self.fixture.state
        self.fixture.execute()  # The unbound loopback route.

    def approval(self, **changes: Any) -> dict[str, str]:
        raw = self.fixture.raw
        gate = self.fixture.root / "gate.json"
        content = dict(gate="S3", verdict="APPROVED")
        content.update({key: raw[key] for key in BOUND_KEYS})
        content.update(changes)
        gate.write_bytes(encoded(content))
        return dict(file=gate.name, sha256=sha(gate))

    def request(self, operation: str) -> dict[str, Any]:
        """Make the next request ``restart`` (loopback) or ``expose_public``."""
        raw = self.fixture.raw
        public = operation == "expose_public"
        raw.update(
            operation=operation,
            exposure="public_entry" if public else "loopback",
            previous_release_id=raw["release_id"],
            gate_approval=self.approval() if public else None,
        )
        return raw

    def expose(self, **overrides: Any) -> dict[str, Any]:
        """An authorised ``expose_public`` on the same identity and upstream."""
        self.request("expose_public")
        options: dict[str, Any] = dict(handover=lambda: None)
        options.update(overrides)
        return self.fixture.execute(**options)

    def restart(self, **overrides: Any) -> dict[str, Any]:
        """An authorised loopback operation on the same identity and upstream."""
        self.request("restart")
        return self.fixture.execute(**overrides)


class Upstream:
    """An invented loopback upstream that records every request reaching it."""

    def __init__(self, case: unittest.TestCase) -> None:
        self.requests: list[dict[str, Any]] = []
        self.answer: Callable[[BaseHTTPRequestHandler, dict[str, Any]], None] = (
            lambda handler, seen: reply(
                handler, 200, [("Content-Type", "text/plain")], b"INVENTED-page"
            )
        )
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:
                return None

            def serve(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                seen = dict(
                    method=self.command,
                    target=self.path,
                    headers=self.headers.items(),
                    body=self.rfile.read(length),
                    peer=self.client_address[0],
                )
                outer.requests.append(seen)
                self.close_connection = True
                outer.answer(self, seen)

            do_GET = do_POST = do_HEAD = do_OPTIONS = serve

        # The numeric server: the standard one asks a name service at bind.
        self.server = entry.LoopbackServer(("127.0.0.1", 0), Handler)
        self.port = int(self.server.server_address[1])
        serve_in_thread(case, self.server)

    def names(self, index: int = -1) -> set[str]:
        return {name.lower() for name, _ in self.requests[index]["headers"]}


def reply(
    handler: BaseHTTPRequestHandler,
    status: int,
    headers: Iterable[tuple[str, str]],
    body: bytes,
    *,
    length: bool = True,
) -> None:
    handler.send_response_only(status)
    for name, value in headers:
        handler.send_header(name, value)
    if length:
        handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Connection", "close")
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


def serve_in_thread(case: unittest.TestCase, server: Any) -> None:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def close() -> None:
        server.shutdown()
        server.server_close()
        thread.join(5)

    case.addCleanup(close)


def dead_port() -> int:
    """A loopback port nothing listens on (bound once, then released)."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class EntryCase(WorkspaceCase):
    def serve_entry(
        self,
        state: Path,
        host: str | None = None,
        upstream: Upstream | int | None = None,
        *,
        handler: Any = None,
    ) -> int:
        """Start the real handler; return its ephemeral loopback port."""
        backend = upstream.port if isinstance(upstream, Upstream) else upstream

        def routed(folder: Path, *rest: Any) -> Any:
            route = active_route(folder, *rest)
            if route is None or backend is None:
                return route
            return dict(route, backend_port=backend)

        mapped = patch("operations.entry.active_route", side_effect=routed)
        mapped.start()
        self.addCleanup(mapped.stop)
        made = (handler or entry.handler)(state, host)
        server = entry.LoopbackServer(("127.0.0.1", 0), made)
        serve_in_thread(self, server)
        return int(server.server_address[1])

    def refused(self, answer: bytes, reason: str, status: int | None = None) -> None:
        """The answer is exactly the entry's closed body with this reason."""
        from operations import remote

        code, headers, body = parsed(answer)
        self.assertEqual(body, remote.closed_body(reason), (code, body))
        self.assertEqual(code, remote.STATUS[reason] if status is None else status)
        self.assertIn(("connection", "close"), lowered(headers))

    def guard_red(
        self,
        function: Any,
        args: Sequence[Any],
        reason: str,
        *,
        then: str | None = None,
        line: int | None = None,
    ) -> None:
        """Delete the one raise that refuses this input; the negative goes red.

        ``then`` names the later, different refusal that decides once the guard
        is gone; ``None`` means the input is admitted. Either way the specific
        reason asserted by the negative case is no longer produced.
        """
        try:
            function(*args)
        except Refusal as refusal:
            self.assertEqual(refusal.reason, reason)
            trace = refusal.__traceback__
            while trace is not None and line is None:
                if trace.tb_frame.f_code is function.__code__:
                    line = trace.tb_lineno - function.__code__.co_firstlineno + 1
                trace = trace.tb_next
        else:
            self.fail("the production control admitted the plant")
        self.assertIsNotNone(line, "the named function must decide the refusal")
        mutant = without_refusal(function, reason, line=line)
        try:
            mutant(*args)
        except Refusal as other:
            self.assertEqual(other.reason, then)
            self.assertNotEqual(other.reason, reason)
        else:
            self.assertIsNone(then, "the mutant admitted the plant")


def edited(function: Any, old: str, new: str) -> Any:
    """A compiled copy of one function with exactly one source site changed."""
    source = textwrap.dedent(inspect.getsource(function))
    if source.count(old) != 1:
        raise AssertionError("the plant must select exactly one source site")
    namespace = dict(function.__globals__)
    exec(compile(source.replace(old, new), "<invented-plant>", "exec"), namespace)
    return namespace[function.__name__]


def health(identity: str, **changes: Any) -> bytes:
    from eii_product.api.health import Health

    document = Health(
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
    ).model_dump()
    document.update(changes)
    return encoded(document)


class Deployment:
    """The real ``deploy.up`` over one live state, on invented process seams.

    Install, store and evidence-probe steps are the S3-T28 fix-1 stubs. A
    launched API child is the invented upstream; a launched entry is the real
    ``entry.prepared`` handler in a thread, given exactly the child environment
    ``up`` passed. Loopback connections to 8088 and the upstream ports are
    mapped to those fixtures' ephemeral ports; nothing else is replaced.
    """

    def __init__(self, case: EntryCase, live: LiveState, upstream: Upstream) -> None:
        self.case, self.live, self.upstream = case, live, upstream
        self.events: list[tuple[str, int]] = []
        self.children: list[tuple[int, dict[str, str]]] = []
        self.foreign: set[int] = set()
        self.ports: dict[int, int] = {18088: upstream.port, 18089: upstream.port}
        self.servers: dict[int, Any] = {}
        self.entry_handler: Any = None
        self.healthy = True
        fixture = live.fixture
        upstream.answer = self.answer
        self.env = Environment(
            "live",
            fixture.root / "releases" / fixture.raw["release_id"],
            live.state,
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        connection = http.client.HTTPConnection
        installed = (fixture.root, dict(features=["INVENTED-finished"]))
        for target, kwargs in (
            ("operations.deploy.read_environment", dict(return_value=self.env)),
            ("operations.config.read_environment", dict(return_value=self.env)),
            ("operations.deploy.verify_peers", {}),
            ("operations.deploy.request_for", dict(side_effect=self.request)),
            ("operations.deploy.installed", dict(return_value=installed)),
            ("operations.deploy.check_stores", {}),
            ("operations.deploy.require_retained", {}),
            ("operations.deploy.staging_probe", {}),
            ("operations.process.require_owned", dict(side_effect=self.owned)),
            ("operations.process.launch", dict(side_effect=self.launch)),
            ("operations.process.terminate", dict(side_effect=self.terminate)),
            (
                "http.client.HTTPConnection",
                dict(
                    side_effect=lambda host, port, **rest: connection(
                        host, self.ports.get(port, port), **rest
                    )
                ),
            ),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            case.addCleanup(patcher.stop)
        case.addCleanup(self.close)

    def request(self, env: Any, environ: Any) -> dict[str, Any]:
        return dict(self.live.fixture.raw)

    def answer(self, handler: BaseHTTPRequestHandler, seen: dict[str, Any]) -> None:
        if seen["target"] != "/health":
            reply(handler, 200, [("Content-Type", "text/plain")], b"INVENTED-page")
        elif self.healthy:
            identity = self.live.fixture.raw["release_id"]
            reply(
                handler, 200, [("Content-Type", "application/json")], health(identity)
            )
        else:
            reply(handler, 503, [("Content-Type", "text/plain")], b"INVENTED-down")

    def owned(self, record: Any, environment: str, **rest: Any) -> None:
        if record.get("port") in self.foreign:
            raise Refusal("process_identity_mismatch")

    def launch(
        self, application: Path, path: Path, argv: Any, environ: Any, **values: Any
    ) -> dict[str, Any]:
        port = values["port"]
        record = dict(pid=17, start_ticks="123", cmdline_sha256="ab" * 32, **values)
        atomic_json(path, record)
        self.events.append(("start", port))
        self.children.append((port, dict(environ)))
        if port == 8088:
            made = (self.entry_handler or entry.prepared)(dict(environ))
            server = entry.LoopbackServer(("127.0.0.1", 0), made)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.servers[port] = (server, thread)
            self.ports[port] = int(server.server_address[1])
        return record

    def terminate(self, record: Any, environment: str) -> None:
        self.owned(record, environment)
        self.events.append(("stop", record["port"]))
        self.stop(record["port"])

    def stop(self, port: int) -> None:
        if port in self.servers:
            server, thread = self.servers.pop(port)
            server.shutdown()
            server.server_close()
            thread.join(5)
            self.ports[port] = dead_port()

    def close(self) -> None:
        for port in list(self.servers):
            self.stop(port)

    def up(self, operation: str, environ: Any = None) -> dict[str, Any]:
        from operations import deploy

        self.live.request(operation)
        self.live.fixture.bind()
        return deploy.up(dict(environ or {}))

    def down(self, environ: Any = None) -> None:
        """The real ``deploy.down``; only the record loop is the fixture's.

        ``process.down`` requires a folder named for its environment, which
        the borrowed promotion fixture does not give, so its loop is replaced
        by the same retire-each-record step over this fixture's processes.
        """
        from operations import deploy

        def retire(state: Path, environment: str, **rest: Any) -> None:
            for path in sorted(state.glob("process-*.json")):
                record = json.loads(path.read_bytes())
                if record.get("stopped") is not True:
                    self.terminate(record, environment)
                    atomic_json(path, dict(record, stopped=True))

        with patch("operations.process.down", side_effect=retire):
            deploy.down(dict(environ or {}))

    def unstopped(self, port: int = 8088) -> list[int]:
        """Running count of entry processes after each of its events."""
        kinds = [kind for kind, where in self.events if where == port]
        return [
            kinds[: index + 1].count("start") - kinds[: index + 1].count("stop")
            for index in range(len(kinds))
        ]

    def ask(self, host: str = LOCAL, origin: str | None = None) -> bytes:
        headers = [("Host", host)]
        if origin is not None:
            headers.append(("Origin", origin))
        return wire(self.ports[8088], message(headers=headers))


def message(
    method: str = "GET",
    target: str = "/",
    headers: Sequence[tuple[str, str]] = (("Host", LOCAL),),
    body: bytes = b"",
    *,
    version: str = "HTTP/1.1",
) -> bytes:
    lines = [f"{method} {target} {version}"]
    lines += [name + ": " + value for name, value in headers]
    return "\r\n".join([*lines, "", ""]).encode("latin-1") + body


def wire(
    port: int, data: bytes, *, timeout: float = 5.0, half_close: bool = False
) -> bytes:
    """Send raw bytes to the loopback port; return everything until it closes."""
    chunks = []
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
        client.sendall(data)
        if half_close:
            client.shutdown(socket.SHUT_WR)
        while chunk := client.recv(65_536):
            chunks.append(chunk)
    return b"".join(chunks)


def parsed(answer: bytes) -> tuple[int, list[tuple[str, str]], bytes]:
    head, _, body = answer.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    fields = [tuple(line.split(": ", 1)) for line in lines[1:]]
    return int(lines[0].split(" ")[1]), [(n, v) for n, v in fields], body


def lowered(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(name.lower(), value) for name, value in headers]


def reason_of(answer: bytes) -> str | None:
    """The closed reason of an entry refusal, else ``None``."""
    from operations import remote

    code, _, body = parsed(answer)
    try:
        document = json.loads(body)
    except ValueError:
        return None
    if type(document) is not dict:
        return None
    return remote.entry_reason(code, body)
