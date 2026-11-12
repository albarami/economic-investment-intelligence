"""Mount modes, environment and descriptor swaps inside the sandbox."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import sandbox_check
import sandbox_launch as launch

pytestmark = pytest.mark.sandbox
MODES = [
    "write_cache",
    "write_vault",
    "write_root",
    "write_usr",
    "write_tmp",
    "write_venv",
    "write_code",
    "write_interpreter",
    "write_inside",
]
MODE_LINES = [
    "write_cache error OSError EROFS",
    "write_vault ok",
    "write_root error OSError EROFS",
    "write_usr error OSError EROFS",
    "write_tmp ok",
    "write_venv error OSError EROFS",
    "write_code error OSError EROFS",
    "write_interpreter error OSError EROFS",
    "write_inside error OSError EROFS",
]


class MountRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        support.require_environment(cls)

    def test_filesystem_modes_in_both_profiles(self) -> None:
        leftover = Path("/tmp/probe-write")
        if leftover.exists():
            self.fail(
                f"/tmp/probe-write was left on the host before the test: {leftover.stat().st_size} bytes"
            )
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            config = support.probe_config(fx, port, abstract, hidden=[])
            for profile in ("build-world", "build-release"):
                self.assertEqual(
                    support.run_inside(profile, fx, config, MODES), MODE_LINES
                )
            self.assertEqual(
                (fx.root / "data" / "vault" / "b1" / "v.txt").read_bytes(), b"x"
            )
            self.assertFalse((fx.root / "data" / "public_cache" / "new.txt").exists())
            self.assertFalse(leftover.exists())
            interpreter = launch.interpreter_for(launch.current_venv())
            for folder in (
                launch.current_venv(),
                interpreter.real,
                fx.root / "core" / "src",
                fx.root / "custodian" / "src",
                fx.root / "scripts" / "sandbox_inside",
            ):
                self.assertFalse((folder / "eii-probe-write").exists(), folder)

    def test_environment_names_and_values(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            config = support.probe_config(fx, port, abstract, hidden=[])
            venv = launch.current_venv()
            for profile in ("build-world", "build-release"):
                result = launch.run_in_sandbox(
                    profile,
                    fx.layout(profile),
                    launch.python_command(
                        "-c",
                        "import json, os; print(json.dumps(dict(os.environ), sort_keys=True))",
                    ),
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "EII_SANDBOX_PROFILE": profile,
                        "HOME": "/tmp",
                        "PATH": str(venv / "bin"),
                        "PWD": "/tmp",
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                )
                lines = support.run_inside(profile, fx, config, ["env", "profile"])
                self.assertEqual(
                    lines,
                    [
                        "env EII_SANDBOX_PROFILE,HOME,PATH,PWD,PYTHONDONTWRITEBYTECODE",
                        f"profile {profile}",
                    ],
                )

    def test_hostile_surroundings_do_not_reach_the_sandbox(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            planted = Path(tmp) / "planted"
            planted.mkdir()
            (planted / "sitecustomize.py").write_text(
                "import os\nos._exit(97)\n", encoding="utf-8"
            )
            config = support.probe_config(fx, port, abstract, hidden=[])
            self.assertFalse(_open(1000))
            handle = os.open(fx.outside / "sentinel.txt", os.O_RDONLY)
            try:
                if handle != 1000:
                    os.dup2(handle, 1000)
                    os.close(handle)
                    handle = 1000
                self.assertTrue(_open(1000))
                hostile = {
                    "PYTHONPATH": str(planted),
                    "LD_PRELOAD": "/nonexistent/hook.so",
                    "HOME": "/tmp/hostile-home",
                    "XDG_CONFIG_HOME": "/tmp/hostile-config",
                    "PATH": "/nonexistent",
                    "EII_PLANTED_SECRET": "planted-value-1234",
                }
                with patch.dict(os.environ, hostile, clear=False):
                    lines = support.run_inside(
                        "build-world", fx, config, ["env", "fds", "profile"]
                    )
                    self.assertEqual(
                        lines,
                        [
                            "env EII_SANDBOX_PROFILE,HOME,PATH,PWD,PYTHONDONTWRITEBYTECODE",
                            "fds none",
                            "profile build-world",
                        ],
                    )
                    command = launch.python_command(
                        str(fx.root / support.PROBE_REL), config, "env"
                    )
                    parent = dict(os.environ)
                    parent.pop("LD_PRELOAD", None)
                    with support.sandbox_argv(fx, "build-world", command) as (
                        argv,
                        descriptors,
                    ):
                        leaked = support.run_argv(
                            support.mutate(argv, "no-clearenv", fx), descriptors, parent
                        )
                    self.assertIn("EII_PLANTED_SECRET", leaked[0])
            finally:
                if _open(1000):
                    os.close(1000)
            tooth = subprocess.run(
                [str(launch.current_venv() / "bin" / "python"), "-c", "print('ran')"],
                env={"PYTHONPATH": str(planted), "PATH": "/usr/bin"},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(tooth.returncode, 97)
            command = launch.python_command(
                str(fx.root / support.PROBE_REL), config, "fds"
            )
            with support.sandbox_argv(fx, "build-world", command) as (
                argv,
                descriptors,
            ):
                kept = os.open(fx.outside / "sentinel.txt", os.O_RDONLY)
                try:
                    if kept != 1000:
                        os.dup2(kept, 1000)
                        os.close(kept)
                        kept = 1000
                    lines = support.run_argv(argv, descriptors, {}, extra=(1000,))
                finally:
                    if _open(1000):
                        os.close(1000)
            self.assertEqual(lines, ["fds 1000"])

    def test_exit_statuses_and_setup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fx = support.make_fixture(tmp)
            layout = fx.layout("build-world")
            done = launch.run_in_sandbox(
                "build-world",
                layout,
                launch.python_command("-c", "import sys; sys.exit(7)"),
            )
            self.assertEqual((done.returncode, done.stdout, done.stderr), (7, "", ""))
            done = launch.run_in_sandbox(
                "build-world",
                layout,
                launch.python_command(
                    "-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"
                ),
            )
            self.assertEqual(done.returncode, 137)
            done = launch.run_in_sandbox(
                "build-world",
                layout,
                launch.python_command(
                    "-c", "import sys; print('x', file=sys.stderr); sys.exit(1)"
                ),
            )
            self.assertEqual(done.returncode, 1)
            self.assertEqual(done.stderr, "x\n")
            with self.assertRaises(launch.SandboxSetupError) as caught:
                launch.run_in_sandbox("build-world", layout, ["/nonexistent/python"])
            self.assertEqual(
                str(caught.exception),
                "could not enter the sandbox build-world: bwrap: execvp /nonexistent/python: No such file or directory",
            )

    def test_timeout_kills_the_process_group(self) -> None:
        marker = "eii-timeout-" + os.urandom(4).hex()
        with tempfile.TemporaryDirectory() as tmp:
            fx = support.make_fixture(tmp)
            command = launch.python_command("-c", "import time; time.sleep(30)")
            command.append(marker)
            started = time.monotonic()
            with self.assertRaises(launch.SandboxTimeout) as caught:
                launch.run_in_sandbox(
                    "build-world", fx.layout("build-world"), command, timeout=1.0
                )
            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual(
                str(caught.exception),
                "sandbox build-world timed out after 1 s; the process group was killed",
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and support.marker_processes(marker):
                time.sleep(0.05)
            self.assertEqual(support.marker_processes(marker), [])

    def test_die_with_parent(self) -> None:
        marker = "eii-die-" + os.urandom(4).hex()
        with tempfile.TemporaryDirectory() as tmp:
            fx = support.make_fixture(tmp)
            payload = json.dumps(
                {
                    "root": str(fx.root),
                    "scenario": str(fx.scenario),
                    "venv": str(launch.current_venv()),
                }
            )
            driver = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    support.DIE_DRIVER,
                    str(support.ROOT / "scripts"),
                    payload,
                    marker,
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if any(
                        pid != driver.pid for pid in support.marker_processes(marker)
                    ):
                        break
                    time.sleep(0.05)
                else:
                    self.fail("sandbox did not start")
                os.kill(driver.pid, signal.SIGKILL)
            finally:
                driver.wait(timeout=5)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if not [
                    pid for pid in support.marker_processes(marker) if pid != driver.pid
                ]:
                    return
                time.sleep(0.05)
            self.fail("a sandboxed process outlived its driver")

    def test_check_commands_have_teeth(self) -> None:
        self.assertEqual(sandbox_check.check_bubblewrap(), [])
        out, err = __import__("io").StringIO(), __import__("io").StringIO()
        with patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
            status = sandbox_check.main(["check"])
        self.assertEqual(status, 0)
        self.assertEqual(err.getvalue(), "")
        self.assertRegex(
            out.getvalue().splitlines()[0], r"bubblewrap [0-9]+\.[0-9]+\.[0-9]+"
        )
        self.assertEqual(out.getvalue().splitlines()[-1], "sandbox: OK")
        real = launch.build_argv

        def drop_net(*args: Any, **kwargs: Any) -> list[str]:
            built: list[str] = real(*args, **kwargs)
            return [token for token in built if token != "--unshare-net"]

        with patch.object(launch, "build_argv", drop_net):
            inside = (
                "standard output ['read_outside error FileNotFoundError ENOENT', "
                "'tcp_loopback ok', 'unix_abstract ok'], expected "
                "['read_outside error FileNotFoundError ENOENT', "
                "'tcp_loopback error ConnectionRefusedError ECONNREFUSED', "
                "'unix_abstract error ConnectionRefusedError ECONNREFUSED']"
            )
            self.assertEqual(
                sandbox_check.check_bubblewrap(),
                [f"profile build-world: {inside}", f"profile build-release: {inside}"],
            )

    def test_swapped_source_is_not_mounted(self) -> None:
        labels = []
        for kind in ("rename", "link", "scenario"):
            labels.append(kind)
            with (
                tempfile.TemporaryDirectory() as tmp,
                sandbox_check.listeners() as (port, abstract),
            ):
                fx = support.make_fixture(tmp)
                if kind == "scenario":
                    attempts = ["read_scenario", "write_scenario", "fds"]
                    expected = [
                        "read_scenario ok",
                        "write_scenario error OSError EROFS",
                        "fds none",
                    ]
                    hidden: list[str] = []
                else:
                    attempts = ["read_cache", "write_vault", "hidden", "fds"]
                    hidden = [
                        str(fx.root / "data" / "public_cache" / "swapped.txt"),
                        str(fx.root / "data" / "vault" / "b1" / "swapped.txt"),
                    ]
                    expected = [
                        "read_cache ok",
                        "write_vault ok",
                        "hidden 0 error FileNotFoundError ENOENT",
                        "hidden 1 error FileNotFoundError ENOENT",
                        "fds none",
                    ]
                config = support.probe_config(fx, port, abstract, hidden=hidden)
                real = subprocess.Popen

                def wrapped(
                    *args: object,
                    fx: support.Fixture = fx,
                    kind: str = kind,
                    real: Callable[..., subprocess.Popen[str]] = real,
                    **kwargs: object,
                ) -> subprocess.Popen[str]:
                    support.swap_source(fx, kind)
                    return real(*args, **kwargs)

                with patch.object(
                    support.exposed(launch, "subprocess"), "Popen", wrapped
                ):
                    lines = support.run_inside("build-world", fx, config, attempts)
                self.assertEqual(lines, expected)
                if kind == "rename":
                    self.assertTrue((fx.base / "cache.moved" / "ok.txt").is_file())
                    self.assertEqual(
                        sorted(
                            path.name
                            for path in (fx.root / "data" / "public_cache").iterdir()
                        ),
                        ["swapped.txt"],
                    )
                elif kind == "link":
                    self.assertEqual(
                        (fx.base / "vault.moved" / "v.txt").read_bytes(), b"x"
                    )
                    self.assertEqual(
                        sorted(path.name for path in (fx.base / "swap").iterdir()),
                        ["swapped.txt"],
                    )
        self.assertEqual(labels, ["rename", "link", "scenario"])


def _open(number: int) -> bool:
    try:
        os.fstat(number)
    except OSError:
        return False
    return True
