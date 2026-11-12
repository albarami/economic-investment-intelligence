"""Child runner tests (P01, P02, P05-P10)."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_stubs as stubs

import preflight_proc as proc


class ChildRunner(unittest.TestCase):
    """run_child time limits, environments and the closed command table."""

    def test_real_limit_kills_sleeping_child(self) -> None:
        """P01: default limit ends a long sleep."""
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            program = stubs.write_stub(folder, "pg_isready", sleep=60.0)
            env = {"PATH": str(folder), "LANG": "C", "LC_ALL": "C"}
            start = time.monotonic()
            result = proc.run_child(
                str(program), ["-h", "h", "-p", "1", "-t", "5"], env, folder
            )
            elapsed = time.monotonic() - start
            self.assertTrue(result.timed_out)
            self.assertEqual(result.status, -9)
            self.assertGreaterEqual(elapsed, 5.0)
            self.assertLess(elapsed, 7.5)

    def test_injected_limit_kills_the_whole_group(self) -> None:
        """P02: a short limit kills the grandchild process group."""
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            pid_file = folder / "grandchild.pid"
            program = stubs.write_stub(
                folder,
                "pg_isready",
                sleep=60.0,
                grandchild=True,
                pid_file=pid_file,
            )
            env = {"PATH": str(folder)}
            proc.run_child(
                str(program),
                ["-h", "h", "-p", "1", "-t", "5"],
                env,
                folder,
                limit=0.5,
            )
            pid = int(pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.05)
                except ProcessLookupError:
                    break
            else:
                os.kill(pid, 9)
                self.fail("grandchild still alive after limit kill")

    def test_status_and_streams_are_exact(self) -> None:
        """P05: stdout, stderr and status pass through."""
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            program = stubs.write_stub(
                folder,
                "uv",
                status=3,
                stdout="out\n",
                stderr="err\n",
            )
            env = {"PATH": str(folder)}
            result = proc.run_child(
                str(program),
                ("lock", "--check", "--offline"),
                env,
                folder,
            )
            self.assertEqual(result, proc.ChildResult(3, "out\n", "err\n", False, None))

    def test_start_errors_are_named(self) -> None:
        """P06: ENOENT, EACCES and ENOEXEC."""
        labels = ["missing", "not_executable", "enoexec"]
        errors = ["ENOENT", "EACCES", "ENOEXEC"]
        ran: list[str] = []
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            for label, expected in zip(labels, errors, strict=True):
                with self.subTest(label=label):
                    ran.append(label)
                    args = ["-h", "h", "-p", "1", "-t", "5"]
                    if label == "missing":
                        program = str(folder / "pg_isready")
                    elif label == "not_executable":
                        program_path = folder / "pg_isready"
                        program_path.write_text(
                            "#!" + sys.executable + "\n", encoding="utf-8"
                        )
                        program = str(program_path)
                    else:
                        program_path = folder / "pg_isready"
                        program_path.write_text("not a program", encoding="utf-8")
                        program_path.chmod(program_path.stat().st_mode | stat.S_IXUSR)
                        program = str(program_path)
                    env = {"PATH": str(folder)}
                    result = proc.run_child(program, args, env, folder)
                    self.assertIsNone(result.status)
                    self.assertEqual(result.start_error, expected)
        self.assertEqual(ran, labels)

    def test_child_receives_exactly_its_environment(self) -> None:
        """P07: only the passed env dict reaches the child."""
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            program = stubs.write_stub(folder, "pg_isready", echo=True)
            env = {"PATH": str(folder), "LANG": "C"}
            proc.run_child(str(program), ["-h", "h", "-p", "1", "-t", "5"], env, folder)
            recorded = stubs.calls(folder)[0]["env"]
            self.assertEqual(recorded, env)

    def test_arguments_reach_the_child_literally(self) -> None:
        """P08: argv is not interpreted by a shell."""
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            program = stubs.write_stub(folder, "pg_isready")
            host = "a;touch${IFS}x"
            args = ["-h", host, "-p", "1", "-t", "5"]
            env = {"PATH": str(folder)}
            proc.run_child(str(program), args, env, folder)
            recorded = stubs.calls(folder)[0]["argv"]
            self.assertEqual(recorded, [str(program), *args])
            self.assertFalse((folder / "x").exists())

    def test_refused_commands_never_start(self) -> None:
        """P09: closed-list refusal leaves no calls log."""
        labels = [
            "docker_compose_up",
            "docker_compose_down",
            "docker_start",
            "docker_stop",
            "docker_rm",
            "docker_system_prune",
            "docker_volume_rm",
            "docker_info",
            "psql_drop",
            "pg_isready_short",
            "git_add",
            "systemctl_start",
            "npm_ci",
        ]
        commands: list[tuple[str, list[str]]] = [
            ("docker", ["compose", "up", "-d", "--wait", "db"]),
            ("docker", ["compose", "down"]),
            ("docker", ["start", "x"]),
            ("docker", ["stop", "x"]),
            ("docker", ["rm", "x"]),
            ("docker", ["system", "prune"]),
            ("docker", ["volume", "rm", "v"]),
            ("docker", ["info"]),
            ("psql", ["-c", "DROP DATABASE eii"]),
            ("pg_isready", ["-h", "h", "-p", "1"]),
            ("git", ["add", ".env"]),
            ("systemctl", ["start", "postgresql"]),
            ("npm", ["ci"]),
        ]
        ran: list[str] = []
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as tmp:
            folder = Path(tmp)
            for label, (name, args) in zip(labels, commands, strict=True):
                with self.subTest(label=label):
                    ran.append(label)
                    program = stubs.write_stub(folder, name)
                    env = {"PATH": str(folder)}
                    with self.assertRaises(proc.CommandRefused):
                        proc.run_child(str(program), args, env, folder)
                    self.assertFalse((folder / "calls.jsonl").exists())
        self.assertEqual(ran, labels)

    def test_command_table_placeholders(self) -> None:
        """P10: HOST and PORT placeholders accept or refuse sample values."""
        labels = [
            "pg_isready_ok",
            "psql_ok",
            "docker_ok",
            "git_ok",
            "cmd_ok",
            "uv_ok",
            "npm_ok",
            "port_zero",
            "port_65536",
            "port_0123",
            "port_1a",
            "host_dash",
            "host_empty",
            "host_shell",
        ]
        cases: list[tuple[str, list[str], bool]] = [
            ("pg_isready", ["-h", "db", "-p", "55440", "-t", "5"], True),
            (
                "psql",
                [
                    "-X",
                    "-w",
                    "-q",
                    "-t",
                    "-A",
                    "-F",
                    "|",
                    "-c",
                    proc.CHECK_QUERY,
                ],
                True,
            ),
            ("docker", ["info", "--format", "{{.ServerVersion}}"], True),
            ("git", ["ls-files", "--error-unmatch", ".env"], True),
            ("cmd.exe", ["/c", "ver"], True),
            ("uv", ["lock", "--check", "--offline"], True),
            ("npm", ["ls", "--package-lock-only", "--offline", "--logs-max=0"], True),
            ("pg_isready", ["-h", "h", "-p", "0", "-t", "5"], False),
            ("pg_isready", ["-h", "h", "-p", "65536", "-t", "5"], False),
            ("pg_isready", ["-h", "h", "-p", "0123", "-t", "5"], False),
            ("pg_isready", ["-h", "h", "-p", "1a", "-t", "5"], False),
            ("pg_isready", ["-h", "-x", "-p", "1", "-t", "5"], False),
            ("pg_isready", ["-h", "", "-p", "1", "-t", "5"], False),
            ("pg_isready", ["-h", "a;$(touch x)", "-p", "1", "-t", "5"], False),
        ]
        expected = [item[2] for item in cases]
        ran: list[str] = []
        for label, (name, args, want) in zip(labels, cases, strict=True):
            with self.subTest(label=label):
                ran.append(label)
                self.assertEqual(proc.command_allowed(name, args), want)
        self.assertEqual(ran, labels)
        self.assertEqual([proc.command_allowed(n, a) for n, a, _ in cases], expected)


if __name__ == "__main__":
    unittest.main()
