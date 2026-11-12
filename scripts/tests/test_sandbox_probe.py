"""Probe and loader rules. The programs run as modules; no sandbox is started."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import sandbox_check

PROBE = support.ROOT / support.PROBE_REL
LOADER = support.ROOT / support.CHECK_REL


def _probe(
    arguments: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(PROBE), *arguments],
        env={} if env is None else env,
        capture_output=True,
        text=True,
        check=False,
    )


class ProbeRules(unittest.TestCase):
    def test_probe_prints_one_line_per_attempt_outside(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            config = support.probe_config(fx, port, abstract, hidden=[])
            done = _probe(
                [
                    config,
                    "read_outside",
                    "tcp_loopback",
                    "unix_abstract",
                    "profile",
                    "fds",
                ]
            )
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stderr, "")
            self.assertEqual(
                done.stdout.splitlines(),
                [
                    "read_outside ok",
                    "tcp_loopback ok",
                    "unix_abstract ok",
                    "profile unset",
                    "fds none",
                ],
            )
            self.assertEqual(
                (fx.outside / "sentinel.txt").read_text(encoding="utf-8"), "sentinel\n"
            )

    def test_probe_usage_errors(self) -> None:
        cases = [
            ([], "sentinel_probe: usage: CONFIG_JSON ATTEMPT [ATTEMPT ...]\n"),
            (["{}"], "sentinel_probe: usage: CONFIG_JSON ATTEMPT [ATTEMPT ...]\n"),
            (
                ["not json", "read_outside"],
                "sentinel_probe: config is not valid JSON\n",
            ),
            (
                ["[]", "read_outside"],
                "sentinel_probe: unknown attempt: config is not an object\n",
            ),
            (["{}", "nonsense"], "sentinel_probe: unknown attempt: nonsense\n"),
            (
                ["{}", "write_tmp"],
                "sentinel_probe: write attempts run only inside a sandbox profile\n",
            ),
            (
                ["{}", "write_root"],
                "sentinel_probe: write attempts run only inside a sandbox profile\n",
            ),
            (["{}", "read_outside"], "sentinel_probe: config key missing: sentinel\n"),
            (["{}", "tcp_loopback"], "sentinel_probe: config key missing: port\n"),
        ]
        labels = []
        for index, (arguments, error) in enumerate(cases, start=1):
            labels.append(index)
            done = _probe(arguments)
            self.assertEqual(done.returncode, 2)
            self.assertEqual(done.stdout, "")
            self.assertEqual(done.stderr, error)
        self.assertEqual(labels, list(range(1, 10)))

    def test_probe_outcome_formats(self) -> None:
        probe = support.load_module("sentinel_probe", PROBE)
        samples = [
            (FileNotFoundError(2, "x"), "error FileNotFoundError ENOENT"),
            (PermissionError(13, "x"), "error PermissionError EACCES"),
            (OSError(), "error OSError none"),
            (OSError(9999, "x"), "error OSError 9999"),
            (__import__("socket").gaierror(-3, "x"), "error gaierror -3"),
            (ImportError("x"), "error ImportError none"),
            (ModuleNotFoundError("x"), "error ModuleNotFoundError none"),
        ]
        labels = []
        for index, (error, text) in enumerate(samples, start=1):
            labels.append(index)

            def action(error: BaseException = error) -> None:
                raise error

            self.assertEqual(probe.outcome(action), text)
        labels.append(8)

        def quiet() -> None:
            return None

        self.assertEqual(probe.outcome(quiet), "ok")
        labels.append(9)

        def boom() -> None:
            raise ValueError("x")

        with self.assertRaises(ValueError):
            probe.outcome(boom)
        self.assertEqual(
            probe.WRITES,
            (
                "write_root",
                "write_usr",
                "write_tmp",
                "write_scenario",
                "write_venv",
                "write_code",
                "write_interpreter",
                "write_inside",
                "write_extensions",
            ),
        )
        self.assertEqual(probe.FD_RANGE, range(3, 1024))
        child = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, str(Path(sys.argv[1]))); "
                "import sentinel_probe; print(sentinel_probe.open_descriptors())",
                str(PROBE.parent),
            ],
            close_fds=True,
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(child.returncode, 0)
        self.assertEqual(child.stdout, "none\n")
        before = {number for number in probe.FD_RANGE if _open(number)}
        handle = open(PROBE, "rb")
        try:
            after = {number for number in probe.FD_RANGE if _open(number)}
            self.assertEqual(after - before, {handle.fileno()})
        finally:
            handle.close()
        self.assertEqual(labels, list(range(1, 10)))

    def test_probe_hidden_list_and_profile_line(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            present = fx.outside / "sentinel.txt"
            missing = fx.base / "missing.txt"
            config = support.probe_config(
                fx, port, abstract, hidden=[str(present), str(missing)]
            )
            done = _probe(
                [config, "hidden", "profile", "env"],
                env={"EII_SANDBOX_PROFILE": "probe-x"},
            )
        self.assertEqual(done.returncode, 0)
        self.assertEqual(
            done.stdout.splitlines(),
            [
                "hidden 0 ok",
                "hidden 1 error FileNotFoundError ENOENT",
                "profile probe-x",
                "env EII_SANDBOX_PROFILE,LC_CTYPE",
            ],
        )

    def test_extension_check_logic_with_a_fake_engine(self) -> None:
        loader = support.load_module("extension_check", LOADER)
        labels = []
        labels.append(1)
        fake = support.FakeDuckdb()
        fake.version = "v9.9.9"
        lines = loader.run_load(fake, "/extensions")
        self.assertEqual(
            lines,
            [
                "engine duckdb v9.9.9",
                "settings autoinstall_known_extensions=False autoload_known_extensions=False "
                "allow_unsigned_extensions=False",
                "LOAD spatial ok",
                "LOAD h3 ok",
                "PATH h3 inside",
                "PATH spatial inside",
                "USE POINT (1 2) abc",
                "LOCK autoinstall error InvalidInputException locked",
            ],
        )
        labels.append(2)
        fake = support.FakeDuckdb()
        fake.allow_lock_change = True
        self.assertEqual(
            loader.run_load(fake, "/extensions")[-1], "LOCK autoinstall changed"
        )
        labels.append(3)
        fake = support.FakeDuckdb()
        fake.loaded = ["spatial"]
        fake.fail_on.append(
            ("LOAD h3", support.FakeError("signature is either missing or invalid"))
        )
        lines = loader.run_load(fake, "/extensions")
        self.assertIn("LOAD h3 error FakeError bad-signature", lines)
        self.assertNotIn("USE POINT (1 2) abc", lines)
        self.assertEqual(
            [line for line in lines if line.startswith("PATH ")],
            ["PATH spatial inside"],
        )
        labels.append(4)
        samples = [
            ("not found", "not-found"),
            ("signature is either missing or invalid", "bad-signature"),
            ("Read-only file system", "read-only"),
            ("Could not establish connection", "no-network"),
            ("is not in the catalog", "not-in-catalog"),
            ("has been locked", "locked"),
            ("anything else", "other"),
        ]
        for text, label in samples:
            self.assertEqual(loader.classify(support.FakeError(text)), label)
        labels.append(5)
        for argv in ([], ["x"], ["x", "bogus"]):
            status, out, err = _main(loader.main, argv)
            self.assertEqual(status, 2)
            self.assertEqual(out, "")
            self.assertEqual(
                err, "extension_check: usage: FOLDER load|install|autoload|files\n"
            )
        fake = support.FakeDuckdb()
        fake.fail_on.append(("INSTALL h3", support.FakeError("Read-only file system")))
        fake.fail_on.append(
            ("FORCE INSTALL", support.FakeError("Could not establish connection"))
        )
        self.assertEqual(
            loader.run_install(fake, "/extensions"),
            [
                "INSTALL h3 error FakeError read-only",
                "FORCE spatial error FakeError no-network",
            ],
        )
        fake = support.FakeDuckdb()
        self.assertEqual(
            loader.run_autoload(fake, "/extensions"),
            ["QUERY st_point error FakeError not-in-catalog"],
        )
        labels.append(6)
        with patch.object(
            support.exposed(support, "importlib"),
            "import_module",
            side_effect=ImportError,
        ):
            with self.assertRaises(AssertionError) as caught:
                support.require_engine(self)
        self.assertEqual(
            str(caught.exception),
            "duckdb is not installed: run uv sync --managed-python --all-packages --locked --group engine",
        )
        labels.append(7)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "a").mkdir()
            (folder / "a" / "f").write_bytes(b"x\n")
            (folder / "a" / "dangling").symlink_to(folder / "missing")
            (folder / "l").symlink_to(folder / "a")
            digest = hashlib.sha256(b"x\n").hexdigest()
            self.assertEqual(
                digest,
                "73cb3858a687a8494ca3323053016282f3dad39d42cf62ca4e79dda2aac7d9ac",
            )
            self.assertEqual(
                loader.run_files(None, str(folder)),
                ["DIR a", "OTHER a/dangling", f"FILE a/f {digest}", "OTHER l"],
            )
            (folder / "a").chmod(0)
            try:
                with self.assertRaises(PermissionError):
                    loader.run_files(None, str(folder))
            finally:
                (folder / "a").chmod(stat.S_IRWXU)
        self.assertEqual(labels, list(range(1, 8)))


def _open(number: int) -> bool:
    try:
        os.fstat(number)
    except OSError:
        return False
    return True


def _main(main: Callable[[list[str]], int], argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
        status = main(argv)
    return status, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
