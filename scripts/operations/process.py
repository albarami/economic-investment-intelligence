"""Owned detached process lifecycle. Database executables are never admitted."""

from __future__ import annotations

import hashlib
import os
import select
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from operations.common import Refusal, atomic_json, read_json

READY_SECONDS = 5.0
PROCESS_SCRIPTS = frozenset(
    {"scripts/operations/serve.py", "scripts/operations/entry.py"}
)


def boot_id() -> str:
    """Kernel boot identity makes a previous-boot PID unambiguously stale."""
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if not value:
            raise Refusal("process_identity_mismatch")
        return value
    except OSError:
        raise Refusal("process_identity_mismatch") from None


def require_command(argv: Sequence[str]) -> None:
    if (
        len(argv) < 5
        or argv[0] != sys.executable
        or tuple(argv[1:4]) != ("-I", "-B", "-S")
        or argv[4] not in PROCESS_SCRIPTS
    ):
        raise Refusal("operation_command_refused", 1)


def identity(pid: int, *, proc_root: Path = Path("/proc")) -> tuple[str, str]:
    try:
        folder = proc_root / str(pid)
        if folder.stat().st_uid != os.getuid():
            raise Refusal("process_identity_mismatch")
        stat_text = (folder / "stat").read_text()
        # comm is parenthesised and can itself hold spaces or parentheses.
        fields = stat_text.rsplit(") ", 1)[1].split()
        raw_ticks = fields[19]
        ticks = "ticks:" + ":".join(
            raw_ticks[offset : offset + 3] for offset in range(0, len(raw_ticks), 3)
        )
        command = (folder / "cmdline").read_bytes()
        if not command:
            raise Refusal("process_identity_mismatch")
        return ticks, hashlib.sha256(command).hexdigest()
    except (OSError, ValueError, IndexError):
        raise Refusal("process_identity_mismatch") from None


def require_owned(
    record: Mapping[str, Any], environment: str, *, proc_root: Path = Path("/proc")
) -> None:
    if (
        record.get("environment") != environment
        or type(record.get("pid")) is not int
        or record["pid"] <= 1
        or (record.get("boot_id") is not None and record["boot_id"] != boot_id())
    ):
        raise Refusal("process_identity_mismatch")
    ticks, command = identity(record["pid"], proc_root=proc_root)
    if ticks != record.get("start_ticks") or command != record.get("cmdline_sha256"):
        raise Refusal("process_identity_mismatch")
    try:
        cmdline = (proc_root / str(record["pid"]) / "cmdline").read_bytes().split(b"\0")
    except OSError:
        raise Refusal("process_identity_mismatch") from None
    try:
        nonce = cmdline[cmdline.index(b"--nonce") + 1]
        actual_environment = cmdline[cmdline.index(b"--environment") + 1]
        actual_port = cmdline[cmdline.index(b"--port") + 1]
    except (ValueError, IndexError):
        raise Refusal("process_identity_mismatch") from None
    if (
        not record.get("nonce")
        or nonce != str(record["nonce"]).encode()
        or actual_environment != environment.encode()
        or actual_port != str(record.get("port")).encode()
    ):
        raise Refusal("process_identity_mismatch")


def launch(
    application: Path,
    state: Path,
    argv: Sequence[str],
    environ: Mapping[str, str],
    *,
    environment: str,
    nonce: str,
    port: int,
    release_id: str,
    application_sha256: str,
) -> dict[str, Any]:
    require_command(argv)
    required = {"--nonce": nonce, "--environment": environment, "--port": str(port)}
    if argv[4] == "scripts/operations/serve.py":
        required.update(
            {"--release-id": release_id, "--application-sha256": application_sha256}
        )
    tail = argv[5:]
    if (
        len(tail) != len(required) * 2
        or {tail[i]: tail[i + 1] for i in range(0, len(tail), 2)} != required
    ):
        raise Refusal("process_identity_mismatch")
    if (
        not environ.get("EII_STATE_DIR")
        or state.parent.resolve() != Path(environ["EII_STATE_DIR"]).resolve()
        or environ.get("EII_ENVIRONMENT") != environment
    ):
        raise Refusal("cross_environment_write")
    # No inherited streams, descriptors, credential arguments, logs or shell.
    child = subprocess.Popen(
        list(argv),
        cwd=application,
        env=dict(environ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )
    try:
        ticks, command = identity(child.pid)
        record = dict(
            pid=child.pid,
            boot_id=boot_id(),
            start_ticks=ticks,
            cmdline_sha256=command,
            nonce=nonce,
            environment=environment,
            port=port,
            release_id=release_id,
            application_sha256=application_sha256,
        )
        atomic_json(state, record)
        return record
    except BaseException:
        # Popen is an unreaped child here: its PID cannot have been reused.
        child.terminate()
        child.wait(timeout=READY_SECONDS)
        raise


def terminate(record: Mapping[str, Any], environment: str) -> None:
    pid = record.get("pid")
    if type(pid) is not int or pid <= 1:
        raise Refusal("process_identity_mismatch")
    try:
        descriptor = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        require_owned(record, environment)
        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        poller = select.poll()
        poller.register(descriptor, select.POLLIN)
        if not poller.poll(int(READY_SECONDS * 1000)):
            raise Refusal("process_shutdown_failed", 1)
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
    finally:
        os.close(descriptor)


def wait_ready(record: Mapping[str, Any], environment: str, probe: Any) -> None:
    # A bounded readiness poll is not a retry of a failed gate/build/test.
    deadline = time.monotonic() + READY_SECONDS
    while time.monotonic() < deadline:
        require_owned(record, environment)
        result = probe(
            record["port"], min(1.0, max(0.001, deadline - time.monotonic()))
        )
        if result is not None:
            if (
                result.get("status") != "ok"
                or result.get("release_id") != record["release_id"]
                or result.get("release_hash") != record["release_id"]
            ):
                raise Refusal("startup_not_ready")
            return
        time.sleep(0.02)
    raise Refusal("startup_not_ready")


def process_record(state: Path, port: int) -> Path:
    return state / ("process-" + str(port) + ".json")


def down(state: Path, environment: str) -> None:
    # State, releases, databases, journals and ledger are retained.
    if state.name != "state" or state.parent.name != environment:
        raise Refusal("cross_environment_write")
    if not state.is_dir():
        return
    failures = []
    current_boot = boot_id()
    for path in sorted(state.glob("process-*.json")):
        try:
            record = read_json(path, "process_identity_mismatch")
            if record.get("stopped") is not True:
                if not (
                    type(record.get("boot_id")) is str
                    and record["boot_id"] != current_boot
                ):
                    try:
                        terminate(record, environment)
                    except Refusal as failure:
                        if (
                            failure.reason == "process_identity_mismatch"
                            and record.get("boot_id") == current_boot
                            and record.get("environment") == environment
                            and type(record.get("pid")) is int
                            and record["pid"] > 1
                            and type(record.get("start_ticks")) is str
                        ):
                            try:
                                other_user = (
                                    Path(f"/proc/{record['pid']}").stat().st_uid
                                    != os.getuid()
                                )
                            except OSError:
                                raise failure from None
                            ticks = None if other_user else identity(record["pid"])[0]
                            if other_user or ticks != record["start_ticks"]:
                                # The recorded process is gone. Retire its
                                # record without signalling the reused PID,
                                # and still report the ownership refusal.
                                atomic_json(path, dict(record, stopped=True))
                        raise
                atomic_json(path, dict(record, stopped=True))
        except Refusal as failure:
            failures.append(failure)
    if failures:
        raise failures[0]
