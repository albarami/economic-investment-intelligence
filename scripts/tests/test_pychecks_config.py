"""Configuration and smoke tests for Python lint, format and type checks."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pychecks_support as support

ROOT = support.ROOT


class PychecksConfig(unittest.TestCase):
    """Read configuration and run tools against the repository or copies."""

    def test_tools_run(self) -> None:
        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        for args in (["--version"],):
            proc = support.run([support.tool("ruff"), *args], ROOT, env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = support.run([support.tool("mypy"), *args], ROOT, env)
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_config_sections_present(self) -> None:
        import tomllib

        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        select = data["tool"]["ruff"]["lint"]["select"]
        for family in ("E4", "E7", "F", "B", "I", "UP", "RUF"):
            self.assertIn(
                family, select, f"FAIL config: tool.ruff.lint.select: missing {family}"
            )
        self.assertFalse(
            data["tool"]["ruff"]["fix"], "FAIL config: tool.ruff.fix: not false"
        )
        self.assertTrue(
            data["tool"]["mypy"]["strict"], "FAIL config: tool.mypy.strict: not true"
        )
        tv = data["tool"]["ruff"]["target-version"]
        pv = data["tool"]["mypy"]["python_version"]
        self.assertRegex(
            tv, r"^py3\d+$", f"FAIL config: tool.ruff.target-version: {tv}"
        )
        self.assertRegex(
            pv, r"^3\.\d+$", f"FAIL config: tool.mypy.python_version: {pv}"
        )
        dev = data["dependency-groups"]["dev"]
        pins = {line.split("==")[0]: line for line in dev}
        for name in ("mypy", "ruff"):
            line = pins.get(name)
            self.assertIsNotNone(
                line, f"FAIL config: dependency-groups.dev: missing {name}"
            )
            pin = cast(str, line)
            self.assertRegex(
                pin, rf"^{name}==\d+\.\d+\.\d+$", f"FAIL config: dev pin: {pin}"
            )

    def test_real_repository_passes(self) -> None:
        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        for cmd in (
            [support.tool("ruff"), "check", "."],
            [support.tool("ruff"), "format", "--check", "."],
            [support.tool("mypy")],
        ):
            proc = support.run(cast(Sequence[str | Path], cmd), ROOT, env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_clean_copy_passes(self) -> None:
        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        copy = support.fresh_copy(self)
        for cmd in (
            [support.tool("ruff"), "check", ".", "--output-format", "concise"],
            [
                support.tool("ruff"),
                "format",
                "--check",
                ".",
                "--output-format",
                "concise",
            ],
            [support.tool("mypy")],
        ):
            proc = support.run(cast(Sequence[str | Path], cmd), copy, env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            if "ruff" in str(cmd[0]):
                self.assertEqual(support.ruff_findings(proc.stdout + proc.stderr), [])
            elif cmd[0] == support.tool("mypy"):
                self.assertEqual(support.mypy_findings(proc.stdout + proc.stderr), [])

    def test_home_tmpdir_is_the_system_temp(self) -> None:
        self.assertEqual(support.home_tmpdir(), Path(tempfile.gettempdir()))
        source = inspect.getsource(support.home_tmpdir)
        self.assertNotIn("ROOT", source)
        self.assertNotIn("mkdir", source)

    def test_support_module_contract(self) -> None:
        """Guard helper constants and error paths used by planted-violation tests."""
        self.assertEqual(support.TIMEOUT_SECONDS, 600)
        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        self.assertEqual(env["TMPDIR"], str(home))
        with self.assertRaises(AssertionError, msg="FAIL tool-missing"):
            support.tool("no-such-binary-xyz")

    def test_malformed_config_fails(self) -> None:
        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        copy = support.fresh_copy(self)
        (copy / "pyproject.toml").write_text("[tool.ruff\n", encoding="utf-8")
        for args in (["check", "."], ["format", "--check", "."]):
            proc = support.run([support.tool("ruff"), *args], copy, env)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("Failed to parse", proc.stderr)
        proc = support.run([support.tool("mypy")], copy, env)
        combined = proc.stdout + proc.stderr
        self.assertIn("Expected ']' at the end of a table declaration", combined)

        import re

        copy2 = support.fresh_copy(self)
        text = (copy2 / "pyproject.toml").read_text(encoding="utf-8")
        text, n = re.subn(
            r"(select = \[)(\s*[^\]]+)(\])",
            r'\1\2, "ZZZ999"\3',
            text,
            count=1,
            flags=re.S,
        )
        self.assertEqual(n, 1)
        (copy2 / "pyproject.toml").write_text(text, encoding="utf-8")
        proc = support.run([support.tool("ruff"), "check", "."], copy2, env)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("Unknown rule selector", proc.stderr)


if __name__ == "__main__":
    unittest.main()
