"""Whole invented production sequence, with a descendant syscall tripwire."""

import ctypes
import errno
import json
import signal
import subprocess
import sys
import unittest
from typing import Any
from unittest.mock import call, patch

import s3_t28_network as network
from s3_t28_network import trace
from s3_t28_support import ROOT, WorkspaceCase


class Network(WorkspaceCase):
    def test_n4_caller_child_remains_owned_and_keeps_its_failure_status(self) -> None:
        wrapper = f"""
import json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, {str(ROOT / "scripts/tests")!r})
from s3_t28_network import trace
reader, writer = os.pipe()
child = subprocess.Popen(
    (sys.executable, '-I', '-B', '-c',
     'import os, sys; os.read(int(sys.argv[1]), 1); sys.exit(3)', str(reader)),
    pass_fds=(reader,),
)
os.close(reader)
try:
    started = time.monotonic()
    result = trace((sys.executable, '-I', '-B', '-c', 'pass'), Path({str(self.root)!r}))
    elapsed = time.monotonic() - started
    assert result == (0, [], ''), result
    assert elapsed < 1, elapsed
    assert child.poll() is None, 'INVENTED-caller-child-reaped'
finally:
    os.close(writer)
    status = child.wait(timeout=1)
assert status == 3, status
print(json.dumps(dict(status=status, trace_seconds=elapsed)))
"""
        value = self.bounded_wrapper(wrapper)
        self.assertEqual(value["status"], 3)
        self.assertLess(value["trace_seconds"], 1)

    def test_n4_exited_caller_child_keeps_its_failure_status(self) -> None:
        wrapper = f"""
import json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "scripts/tests")!r})
from s3_t28_network import trace
child = subprocess.Popen((sys.executable, '-I', '-B', '-c', 'raise SystemExit(3)'))
try:
    event = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)
    assert event.si_status == 3, event
    assert trace((sys.executable, '-I', '-B', '-c', 'pass'), Path({str(self.root)!r})) == (0, [], '')
finally:
    status = child.wait(timeout=1)
assert status == 3, status
print(json.dumps(dict(status=status)))
"""
        self.assertEqual(self.bounded_wrapper(wrapper), dict(status=3))

    def test_n4_json_pipe_preserves_large_output_and_nonzero_exit(self) -> None:
        wrapper = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "scripts/tests")!r})
from s3_t28_network import trace
code, attempts, output = trace(
    (sys.executable, '-I', '-B', '-c', "print('INVENTED' * 16384); raise SystemExit(3)"),
    Path({str(self.root)!r}),
)
assert (code, attempts) == (3, []), (code, attempts)
assert output == 'INVENTED' * 16384 + '\\n'
print(json.dumps(dict(complete=True)))
"""
        self.assertEqual(self.bounded_wrapper(wrapper), dict(complete=True))

    def test_n4_json_pipe_reraises_os_and_non_os_errors(self) -> None:
        wrapper = f"""
import errno, json, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "scripts/tests")!r})
import s3_t28_network as network
for error in (OSError(errno.EIO, 'INVENTED-inspection-failed'), RuntimeError('INVENTED-tracer-failed')):
    def fail(*args):
        raise error
    network._trace = fail
    expected = OSError if isinstance(error, OSError) else AssertionError
    try:
        network.trace(('INVENTED-unused',), Path({str(self.root)!r}))
    except expected as received:
        assert received.args == error.args, received.args
    else:
        raise AssertionError('INVENTED-missing-tracer-error')
print(json.dumps(dict(reraised=True)))
"""
        self.assertEqual(self.bounded_wrapper(wrapper), dict(reraised=True))

    def bounded_wrapper(self, wrapper: str) -> dict[str, Any]:
        result = subprocess.run(
            (sys.executable, "-I", "-B", "-c", wrapper),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value: dict[str, Any] = json.loads(result.stdout)
        return value

    def bounded_thread_trace(
        self, program: str, *, inspection_failure: bool = False
    ) -> dict[str, Any]:
        # Isolate the tracer too: EXITKILL kills only its own tracees if the
        # unchanged five-second process bound catches a cleanup regression.
        wrapper = f"""
import errno, json, os, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "scripts/tests")!r})
import s3_t28_network as network
failure = {inspection_failure!r}
if failure:
    def fail_inspection(*args):
        raise OSError(errno.EIO, 'INVENTED-inspection-failed')
    network.socket_name = fail_inspection
try:
    code, attempts, output = network.trace(
        (sys.executable, '-I', '-B', '-c', {program!r}), Path({str(self.root)!r})
    )
except OSError as error:
    assert failure and error.errno == errno.EIO
    try:
        os.waitpid(-1, network.WALL)
    except ChildProcessError:
        print(json.dumps(dict(reaped=True)))
    else:
        raise AssertionError('INVENTED-unreaped-tracee')
else:
    assert not failure, 'INVENTED-missing-inspection-failure'
    assert code == 0, output
    print(json.dumps(dict(attempts=attempts)))
"""
        result = subprocess.run(
            (sys.executable, "-I", "-B", "-c", wrapper),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value: dict[str, Any] = json.loads(result.stdout)
        return value

    def test_n2_owned_bind_and_listen_in_worker_thread(self) -> None:
        result = self.bounded_thread_trace("""
import socket, threading
completed = []
with socket.socket() as server, socket.socket() as client:
    def serve():
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        completed.append(True)
    worker = threading.Thread(target=serve)
    worker.start()
    worker.join()
    assert completed == [True]
    client.connect(server.getsockname())
    with server.accept()[0] as accepted:
        client.sendall(b'INVENTED')
        assert accepted.recv(8) == b'INVENTED'
""")
        self.assertEqual(result, dict(attempts=[]))

    def test_n2_listen_without_bind_in_worker_thread_is_recorded(self) -> None:
        result = self.bounded_thread_trace("""
import errno, socket, threading
completed = []
def serve():
    with socket.socket() as server:
        try:
            server.listen(1)
        except OSError as error:
            assert error.errno == errno.EPERM
            completed.append(True)
worker = threading.Thread(target=serve)
worker.start()
worker.join()
assert completed == [True]
""")
        self.assertEqual(result, dict(attempts=["listen"]))

    def test_n2_thread_inspection_failure_reaps_all_within_existing_bound(self) -> None:
        result = self.bounded_thread_trace(
            """
import socket, threading
with socket.socket() as server:
    worker = threading.Thread(target=lambda: server.bind(('127.0.0.1', 0)))
    worker.start()
    worker.join()
""",
            inspection_failure=True,
        )
        self.assertEqual(result, dict(reaped=True))

    def test_n2_cleanup_waits_for_any_tracee_until_no_children_remain(self) -> None:
        # Linux cannot report the leader zombie until its traced thread is
        # reaped. Model that ordering explicitly so a per-ID wait cannot pass
        # merely because a native set happened to enumerate the thread first.
        leader, thread = 16, 17
        resumes = []

        def ptrace(
            request: int, pid: int, address: Any = None, data: Any = None
        ) -> int:
            if request == 0x4201:
                ctypes.cast(data, ctypes.POINTER(ctypes.c_ulonglong))[0] = thread
            if request == network.SYSCALL:
                resumes.append(pid)
                if len(resumes) == 2:
                    raise OSError(errno.EIO, "INVENTED-tracer-failed")
            return 0

        events = iter(
            (
                (leader, signal.SIGSTOP << 8 | 0x7F),
                (leader, 3 << 16 | signal.SIGTRAP << 8 | 0x7F),
                (thread, signal.SIGKILL),
                (leader, signal.SIGKILL),
            )
        )

        def waitpid(pid: int, options: int) -> tuple[int, int]:
            if resumes:
                self.assertEqual((pid, options), (-1, network.WALL))
            try:
                return next(events)
            except StopIteration:
                raise ChildProcessError from None

        with (
            patch("s3_t28_network.os.fork", return_value=leader),
            patch.object(network, "ptrace", side_effect=ptrace),
            patch("s3_t28_network.os.kill") as kill,
            patch("s3_t28_network.os.waitpid", side_effect=waitpid) as wait,
            self.assertRaisesRegex(OSError, "INVENTED-tracer-failed"),
        ):
            network._trace(("INVENTED-unused",), -1, self.root)
        self.assertCountEqual(
            kill.call_args_list,
            [call(leader, signal.SIGKILL), call(thread, signal.SIGKILL)],
        )
        self.assertEqual(
            wait.call_args_list,
            [call(leader, 0), *[call(-1, network.WALL)] * 4],
        )

    def test_local_resolver_other_loopback_and_unix_relays_are_recorded(self) -> None:
        for family, target, expected in (
            ("AF_INET", ("127.0.0.53", 53), "dns"),
            ("AF_INET", ("127.0.0.1", 53), "dns"),
            ("AF_INET", ("127.10.20.30", 9), "connect"),
            ("AF_INET", ("127.0.0.1", 9), "connect"),
            ("AF_INET6", ("::1", 9), "connect"),
            ("AF_UNIX", "/run/INVENTED-session-bus.sock", "unix-relay"),
            ("AF_UNIX", "\0INVENTED-session-bus", "unix-relay"),
        ):
            with self.subTest(family=family, target=target):
                attempts = self.run_traced(
                    "import socket\n"
                    + f"with socket.socket(socket.{family}, socket.SOCK_DGRAM) as channel:\n"
                    + "    try:\n"
                    + f"        channel.connect({target!r})\n"
                    + "    except OSError:\n        pass\n"
                )
                self.assertEqual(attempts, [expected])
                with self.assertRaises(AssertionError):
                    self.assertEqual(attempts, [], "local relay is an attempt")

    def test_listen_without_bind_is_recorded(self) -> None:
        attempts = self.run_traced(
            "import socket\n"
            "with socket.socket() as channel:\n"
            "    try:\n        channel.listen(1)\n"
            "    except OSError:\n        pass\n"
        )
        self.assertEqual(attempts, ["listen"])

    def test_unspecified_family_cannot_hide_a_wildcard_bind(self) -> None:
        attempts = self.run_traced("""
import ctypes, socket
libc = ctypes.CDLL(None)
with socket.socket() as channel:
    raw = bytes(16)  # AF_UNSPEC plus INADDR_ANY is accepted by Linux bind.
    libc.bind(channel.fileno(), raw, len(raw))
""")
        self.assertEqual(attempts, ["connect"])

        disconnect = self.run_traced("""
import ctypes, socket
libc = ctypes.CDLL(None)
with socket.socket(type=socket.SOCK_DGRAM) as server, socket.socket(type=socket.SOCK_DGRAM) as client:
    server.bind(('127.0.0.1', 0))
    client.connect(server.getsockname())
    raw = bytes(16)
    assert libc.connect(client.fileno(), raw, len(raw)) == 0
""")
        self.assertEqual(disconnect, [])

    def test_only_test_owned_loopback_ports_and_unix_paths_are_admitted(self) -> None:
        attempts = self.run_traced(
            "import os, socket\n"
            "from pathlib import Path\n"
            + f"root = Path({str(self.root)!r})\n"
            + "os.chdir(root)\n"
            + "for family, host in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):\n"
            + "    with socket.socket(family) as server, socket.socket(family) as client:\n"
            + "        server.bind((host, 0))\n"
            + "        server.listen(1)\n"
            + "        client.connect(server.getsockname())\n"
            + "with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as client:\n"
            + "    server.bind('owned.sock')\n"
            + "    server.listen(1)\n"
            + "    client.connect('owned.sock')\n"
        )
        self.assertEqual(attempts, [])

    def sequence(self, hook: str = "lambda step: None") -> str:
        return (
            "import subprocess, sys, unittest\n"
            + "sys.path[:0] = "
            + repr(
                [
                    str(ROOT / p)
                    for p in ("scripts/tests", "scripts", "core/src", "product/src")
                ]
            )
            + "\nfrom test_s3_t28_runbook import Runbook\n"
            + "case = Runbook('test_dispatch_build_stage_promote_rollback_handover_and_down')\n"
            + "case.operation_hook = "
            + hook
            + "\n"
            + "suite = unittest.TestSuite([case])\n"
            + "result = unittest.TextTestRunner().run(suite)\n"
            + "assert result.testsRun == 1 and result.wasSuccessful()\n"
        )

    def run_traced(self, program: str) -> list[str]:
        code, attempts, output = trace(
            (sys.executable, "-I", "-B", "-c", program), self.root
        )
        self.assertEqual(code, 0, output)
        return attempts

    def test_complete_production_dispatch_sequence_has_zero_outbound_attempts(
        self,
    ) -> None:
        attempts = self.run_traced(self.sequence())
        self.assertEqual(attempts, [])

    def test_caught_native_outbound_in_exec_child_still_turns_assertion_red(
        self,
    ) -> None:
        native = """
import ctypes, socket
libc = ctypes.CDLL(None)
sock = socket.socket()
raw = bytes([2, 0, 0, 80, 192, 0, 2, 1]) + bytes(8)
assert libc.connect(sock.fileno(), raw, len(raw)) == -1
sock.close()
"""
        hook = (
            "lambda step: subprocess.run([sys.executable, '-I', '-B', '-c', "
            + repr(native)
            + "], check=True) if step == 'live_stop' else None"
        )
        attempts = self.run_traced(self.sequence(hook))
        self.assertEqual(attempts, ["connect"])

        def production_assertion() -> None:
            self.assertEqual(attempts, [], "outbound attempt, even when caught")

        result = unittest.TestResult()
        unittest.FunctionTestCase(production_assertion).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("outbound attempt", result.failures[0][1])

    def test_each_stream_datagram_message_and_thread_attempt_is_observed(self) -> None:
        attempts = self.run_traced("""
import ctypes, errno, socket, threading
for operation in ('connect', 'connect_ex', 'sendto', 'sendmsg'):
    with socket.socket(type=socket.SOCK_DGRAM) as channel:
        try:
            if operation == 'connect':
                channel.connect(('192.0.2.1', 80))
            elif operation == 'connect_ex':
                assert channel.connect_ex(('192.0.2.1', 80)) == errno.EPERM
            elif operation == 'sendto':
                channel.sendto(b'INVENTED', ('192.0.2.1', 80))
            else:
                channel.sendmsg([b'INVENTED'], [], 0, ('192.0.2.1', 80))
        except OSError as error:
            assert error.errno == errno.EPERM
def native():
    libc = ctypes.CDLL(None, use_errno=True)
    with socket.socket() as channel:
        raw = bytes([2, 0, 0, 80, 192, 0, 2, 1]) + bytes(8)
        assert libc.connect(channel.fileno(), raw, len(raw)) == -1
        assert ctypes.get_errno() == errno.EPERM
worker = threading.Thread(target=native)
worker.start()
worker.join()
""")
        self.assertEqual(
            attempts, ["connect", "connect", "sendto", "sendmsg", "connect"]
        )

    def test_native_message_batch_and_untraced_child_cannot_escape(self) -> None:
        attempts = self.run_traced("""
import ctypes as c
import errno, socket
class IOVec(c.Structure):
    _fields_ = [('base', c.c_void_p), ('length', c.c_size_t)]
class Header(c.Structure):
    _fields_ = [('name', c.c_void_p), ('namelen', c.c_uint), ('iov', c.POINTER(IOVec)), ('iovlen', c.c_size_t), ('control', c.c_void_p), ('controllen', c.c_size_t), ('flags', c.c_int)]
class Message(c.Structure):
    _fields_ = [('header', Header), ('length', c.c_uint)]
libc = c.CDLL(None, use_errno=True)
name = c.create_string_buffer(bytes([2, 0, 0, 80, 192, 0, 2, 1]) + bytes(8))
body = c.create_string_buffer(b'INVENTED')
iov = IOVec(c.cast(body, c.c_void_p), 8)
message = Message(Header(c.cast(name, c.c_void_p), 16, c.pointer(iov), 1, None, 0, 0), 0)
assert c.sizeof(message) == 64
with socket.socket(type=socket.SOCK_DGRAM) as channel:
    assert libc.sendmmsg(channel.fileno(), c.byref(message), 1, 0) == -1
    assert c.get_errno() == errno.EPERM
# CLONE_UNTRACED would evade the ptrace descendant attachment. Refuse before
# a child is created. io_uring could hide socket work behind asynchronous IO.
assert libc.syscall(56, 0x800000 | 17, 0, 0, 0, 0) == -1
assert c.get_errno() == errno.EPERM
assert libc.syscall(425, 1, 0) == -1
assert c.get_errno() == errno.EPERM
""")
        self.assertEqual(
            attempts,
            ["sendmmsg", "untraced-child-refused", "unsupported-network-transport"],
        )
