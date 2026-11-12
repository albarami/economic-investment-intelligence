"""Environment, secret and import-mode tests for the runner."""

from __future__ import annotations

import secrets
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import runner_support as support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests

HOSTILE = (
    "ANTHROPIC_API_KEY",
    "JEV_PRO_API_KEY",
    "FOO_KEY",
    "BAR_TOKEN",
    "BAZ_SECRET",
    "my_secret",
)


class RunnerEnvironment(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="eii-env-")
        self.root = support.fixture_root(Path(self._tmp.name))
        self.assertTrue(run_tests.SUITES)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_secrets_never_reach_a_suite(self) -> None:
        names = ", ".join(repr(name) for name in HOSTILE)
        support.put(
            self.root,
            "fx/env/test_env.py",
            "import os\n\n"
            "def test_env(request):\n"
            f"    banned = [{names}]\n"
            "    for name in banned:\n"
            "        assert name not in os.environ\n"
            "    assert 'PYTHONPATH' not in os.environ\n"
            "    assert 'PYTEST_ADDOPTS' not in os.environ\n"
            "    assert os.environ['EII_DECISION_PROVIDER'] == 'none'\n"
            f"    assert os.environ['PYTHONHASHSEED'] == '{support.FIXTURE_SEED}'\n"
            "    assert request.config.getoption('hypothesis_seed') == "
            f"'{support.FIXTURE_SEED}'\n",
        )
        extra = {name: "dummy-" + secrets.token_hex(8) for name in HOSTILE}
        extra["PYTHONPATH"] = "leak"
        extra["PYTEST_ADDOPTS"] = "-q"
        extra["EII_DECISION_PROVIDER"] = "jev"
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-env", "pytest", ".", ("fx/env",)),),
            self.root,
            support.parent_env(extra),
        )
        self.assertEqual(status, 0, out)
        self.assertIn("suite fx-env: 1 passed, 0 failed, 0 skipped", out)
        control = subprocess.run(
            [
                sys.executable,
                "-P",
                "-s",
                "-m",
                "pytest",
                "-c",
                "pyproject.toml",
                "--rootdir",
                ".",
                "fx/env",
            ],
            cwd=self.root,
            env=extra,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(control.returncode, 1, control.stdout + control.stderr)

    def test_secret_value_in_output_is_redacted_and_fails(self) -> None:
        value = "dummy-" + secrets.token_hex(8)
        support.put(
            self.root,
            "fx/leak/test_leak.py",
            "import pytest\n\n"
            "def test_print():\n"
            f"    print({value!r})\n"
            "    assert False\n\n"
            f"@pytest.mark.skip(reason={value!r})\n"
            "def test_hidden():\n"
            "    assert True\n",
        )
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-leak", "pytest", ".", ("fx/leak",)),),
            self.root,
            support.parent_env({"ANTHROPIC_API_KEY": value}),
        )
        text = "\n".join(out)
        self.assertEqual(status, 1, out)
        self.assertIn(
            "FAIL secret-in-output: fx-leak: the output contained the value of ANTHROPIC_API_KEY",
            out,
        )
        self.assertNotIn(value, text)
        self.assertIn("[redacted]", text)
        self.assertTrue(
            any(
                line.startswith("FAIL unexplained-skip: fx-leak:")
                and line.endswith(": [redacted]")
                for line in out
            ),
            out,
        )

    def test_children_write_no_cache_and_no_bytecode_and_no_hypothesis_folder(
        self,
    ) -> None:
        support.put(
            self.root,
            "fx/cache/test_cache.py",
            "from hypothesis import given\n"
            "from hypothesis import strategies as st\n\n"
            "@given(st.integers())\n"
            "def test_one(number):\n"
            "    assert isinstance(number, int)\n",
        )
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-cache", "pytest", ".", ("fx/cache",)),),
            self.root,
            support.parent_env(),
        )
        self.assertEqual(status, 0, out)
        self.assertFalse((self.root / ".pytest_cache").exists())
        self.assertFalse(any(self.root.rglob("__pycache__")))
        self.assertFalse((self.root / ".hypothesis").exists())
        control_root = Path(tempfile.mkdtemp(prefix="eii-cache-control-"))
        self.addCleanup(
            lambda: __import__("shutil").rmtree(control_root, ignore_errors=True)
        )
        support.fixture_root(control_root)
        support.put(
            control_root,
            "fx/cache/test_cache.py",
            (self.root / "fx" / "cache" / "test_cache.py").read_text(encoding="utf-8"),
        )
        env = support.parent_env()
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        proc = subprocess.run(
            [
                sys.executable,
                "-P",
                "-m",
                "pytest",
                "-c",
                "pyproject.toml",
                "--rootdir",
                ".",
                "--hypothesis-seed",
                support.FIXTURE_SEED,
                "-o",
                "addopts=",
                "fx/cache",
            ],
            cwd=control_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((control_root / ".pytest_cache").is_dir())
        self.assertTrue(any(control_root.rglob("__pycache__")))
        self.assertTrue((control_root / ".hypothesis" / "constants").exists())

    def test_same_named_test_files_in_two_folders(self) -> None:
        body = "def test_one():\n    assert True\n"
        support.put(self.root, "fx/names/a/test_same.py", body)
        support.put(self.root, "fx/names/b/test_same.py", body)
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-names", "pytest", ".", ("fx/names",)),),
            self.root,
            support.parent_env(),
        )
        self.assertEqual(status, 0, out)
        self.assertIn("suite fx-names: 2 passed, 0 failed, 0 skipped", out)
        proc = subprocess.run(
            [
                sys.executable,
                "-P",
                "-s",
                "-m",
                "pytest",
                "-c",
                "pyproject.toml",
                "--rootdir",
                ".",
                "--import-mode=prepend",
                "-o",
                "addopts=",
                "fx/names",
            ],
            cwd=self.root,
            env=support.parent_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_secret_values_are_one_line_per_name_sorted_and_have_a_minimum_length(
        self,
    ) -> None:
        long_a = "dummy-" + secrets.token_hex(8)
        long_b = "dummy-" + secrets.token_hex(8)
        zed = "z" * 8
        short = "tinykey"
        twin = "dummy-" + secrets.token_hex(8)
        prefix = "dummy-" + secrets.token_hex(4)
        longer = prefix + secrets.token_hex(4)
        tail = longer[-8:]
        support.put(
            self.root,
            "fx/multi/test_multi.py",
            "def test_print():\n"
            f"    print({long_a!r})\n"
            f"    print({long_b!r})\n"
            f"    print({zed!r})\n"
            f"    print({short!r})\n"
            f"    print({twin!r})\n"
            f"    print({longer!r})\n"
            "    assert False\n",
        )
        environ = support.parent_env(
            {
                "JEV_PRO_API_KEY": long_b,
                "ANTHROPIC_API_KEY": long_a,
                "ZED_KEY": zed,
                "SHORT_KEY": short,
                "TWIN_A_KEY": twin,
                "TWIN_B_KEY": twin,
                "PFX_A_KEY": prefix,
                "PFX_B_KEY": longer,
            }
        )
        status, out, _err = support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-multi", "pytest", ".", ("fx/multi",)),),
            self.root,
            environ,
        )
        self.assertEqual(status, 1, out)
        secret_lines = [
            line for line in out if line.startswith("FAIL secret-in-output:")
        ]
        self.assertEqual(
            secret_lines,
            [
                "FAIL secret-in-output: fx-multi: the output contained the value of ANTHROPIC_API_KEY",
                "FAIL secret-in-output: fx-multi: the output contained the value of JEV_PRO_API_KEY",
                "FAIL secret-in-output: fx-multi: the output contained the value of PFX_A_KEY",
                "FAIL secret-in-output: fx-multi: the output contained the value of PFX_B_KEY",
                "FAIL secret-in-output: fx-multi: the output contained the value of TWIN_A_KEY",
                "FAIL secret-in-output: fx-multi: the output contained the value of TWIN_B_KEY",
                "FAIL secret-in-output: fx-multi: the output contained the value of ZED_KEY",
            ],
        )
        text = "\n".join(out)
        for hidden in (long_a, long_b, zed, twin, prefix, tail):
            self.assertNotIn(hidden, text)
        self.assertIn(short, text)
        self.assertIn("[redacted]", text)
        for character in set(tail):
            self.assertNotIn("[redacted]" + character, text)
