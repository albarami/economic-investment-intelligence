"""Black-box tests for the eii launcher."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import runner_support as support

ROOT = support.ROOT
LAUNCHER = ROOT / "eii"


class Launcher(unittest.TestCase):
    def test_file_form(self) -> None:
        if not LAUNCHER.is_file():
            self.fail("FAIL launcher: eii: missing")
        first = LAUNCHER.read_text(encoding="utf-8").splitlines()[0]
        if not first.startswith("#!"):
            self.fail("FAIL launcher: eii: shebang missing")
        if not os.access(LAUNCHER, os.X_OK):
            self.fail("FAIL launcher: eii: not executable")

    def test_launcher_usage_errors(self) -> None:
        rows: tuple[tuple[str, ...], ...] = (
            ("bogus",),
            ("TEST",),
            ("test2",),
            ("",),
            (),
        )
        for args in rows:
            with self.subTest(args=args):
                proc = self._run(args, {"PATH": os.environ.get("PATH", "")})
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(proc.stdout, "")
                lines = proc.stderr.splitlines()
                self.assertEqual(len(lines), 1, proc.stderr)
                self.assertTrue(lines[0].startswith("eii: usage error:"), lines[0])

    def test_missing_uv(self) -> None:
        empty = self._temp()
        proc = self._run(("test",), {"PATH": str(empty)})
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(
            proc.stderr,
            "FAIL tools: uv: not found on PATH; install uv, then run ./eii test again\n",
        )

    def test_forwarding(self) -> None:
        bindir = self._temp()
        fake = bindir / "uv"
        fake.write_text(
            '#!/bin/sh\nfor arg in "$@"; do\n  printf \'%s\\n\' "$arg"\ndone\npwd\nexit 7\n',
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        other = self._temp()
        proc = self._run(
            ("test", "--seed", support.FIXTURE_SEED),
            {"PATH": str(bindir)},
            cwd=other,
        )
        self.assertEqual(proc.returncode, 7, proc.stdout + proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertIn("--locked", lines)
        self.assertEqual(lines[-3], "--seed")
        self.assertEqual(lines[-2], support.FIXTURE_SEED)
        self.assertEqual(lines[-1], str(ROOT.resolve()))

    def test_started_from_its_own_folder_by_a_bare_name(self) -> None:
        bindir = self._temp()
        fake = bindir / "uv"
        fake.write_text(
            '#!/bin/sh\nfor arg in "$@"; do\n  printf \'%s\\n\' "$arg"\ndone\npwd\nexit 7\n',
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        shell = bindir / "sh"
        shell.symlink_to("/bin/sh")
        proc = subprocess.run(
            ["sh", "eii", "test", "--seed", support.FIXTURE_SEED],
            cwd=ROOT,
            env={"PATH": str(bindir)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(proc.returncode, 7, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.splitlines()[-1], str(ROOT.resolve()))

    def _temp(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="eii-launcher-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(path, ignore_errors=True))
        return path

    def _run(
        self,
        args: tuple[str, ...],
        env: dict[str, str],
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LAUNCHER), *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
