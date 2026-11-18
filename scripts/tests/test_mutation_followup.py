"""Invented plants for PO-S2-25/26; no mutation campaign or source access."""

import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

mutation = importlib.import_module("scripts.mutation")
ROOT = Path(__file__).resolve().parents[2]


class GitEnvironmentTests(unittest.TestCase):
    def test_ordinary_configuration_keeps_ignore_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            ignore = folder / "ignore"
            ignore.write_text("synthetic-global-ignore\n")
            config = folder / "config"
            config.write_text(
                "[core]\n excludesFile = " + os.path.relpath(ignore, ROOT) + "\n"
            )
            clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            for settings in (
                {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_SYSTEM": os.devnull},
                {"GIT_CONFIG_SYSTEM": str(config), "GIT_CONFIG_GLOBAL": os.devnull},
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.excludesFile",
                    "GIT_CONFIG_VALUE_0": str(ignore),
                },
            ):
                ordinary = {
                    **clean,
                    **settings,
                    "GIT_CEILING_DIRECTORIES": str(ROOT.parent),
                    "GIT_DISCOVERY_ACROSS_FILESYSTEM": "0",
                    "GIT_NAMESPACE": "synthetic",
                }
                with (
                    self.subTest(settings=tuple(settings)),
                    patch.dict(os.environ, ordinary, clear=True),
                ):
                    environment = mutation.package_environment()
                    self.assertTrue(mutation.repository_matches(ROOT, environment))
                    self.assertFalse(
                        mutation.repository_matches(
                            ROOT, {**environment, "GIT_WORK_TREE": str(folder)}
                        )
                    )
                    for key, value in ordinary.items():
                        self.assertEqual(environment[key], value)
                    for name, expected in (
                        ("synthetic-global-ignore", 0),
                        ("synthetic-kept", 1),
                    ):
                        result = subprocess.run(
                            ["git", "check-ignore", "--no-index", "-q", "--", name],
                            cwd=ROOT,
                            env=environment,
                            capture_output=True,
                            check=False,
                        )
                        self.assertEqual(result.returncode, expected, result.stderr)

    def test_redirected_listing_refused_even_with_overlapping_module(self) -> None:
        module = "core/src/synthetic.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "core/src").mkdir(parents=True)
            (root / module).write_text("def value(): return 1\n")

            def git(
                arguments: list[str], **kwargs: Any
            ) -> subprocess.CompletedProcess[bytes]:
                self.assertEqual(kwargs["cwd"], root)
                answer = (
                    str(root / "other") + "\n"
                    if "rev-parse" in arguments
                    else module + "\0"
                )
                return subprocess.CompletedProcess(arguments, 0, answer.encode(), b"")

            with (
                patch.object(mutation, "ROOT", root),
                patch.object(mutation.subprocess, "run", side_effect=git),
                patch.object(sys, "argv", ["mutation.py", module]),
                patch.object(
                    mutation,
                    "TemporaryDirectory",
                    side_effect=AssertionError("copy began before repository check"),
                ),
                contextlib.redirect_stderr(io.StringIO()) as output,
            ):
                with self.assertRaises(SystemExit) as refused:
                    mutation.main()
            self.assertEqual(refused.exception.code, 2)
            self.assertIn("outside the workspace", output.getvalue())
            self.assertEqual(list(root.rglob("*.py")), [root / module])

    def test_configuration_cannot_redirect_package_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sentinel = root / "sentinel"
            sentinel.mkdir()
            (sentinel / "kept.txt").write_text("invented sentinel")
            copy = root / "copy"
            copy.mkdir()
            with (
                patch.dict(
                    os.environ,
                    {
                        "GIT_CONFIG_COUNT": "1",
                        "GIT_CONFIG_KEY_0": "core.worktree",
                        "GIT_CONFIG_VALUE_0": str(sentinel),
                    },
                ),
                patch.object(
                    mutation.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        ["git"], 0, (str(sentinel) + "\n").encode(), b""
                    ),
                ),
                patch.object(mutation, "run_copy") as campaign,
                contextlib.redirect_stderr(io.StringIO()) as output,
            ):
                code = mutation.run_packages(
                    copy, ["core/src/synthetic.py"], root / "ledger"
                )
            self.assertEqual(code, 2)
            campaign.assert_not_called()
            self.assertIn("outside the mutation copy", output.getvalue())
            self.assertEqual([p.name for p in sentinel.iterdir()], ["kept.txt"])
            self.assertEqual((sentinel / "kept.txt").read_text(), "invented sentinel")


class PackagePytestTests(unittest.TestCase):
    def test_copied_settings_bootstrap_and_planted_unknown_marker(self) -> None:
        settings = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"][
            "pytest"
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text((ROOT / "pyproject.toml").read_text())
            (root / "conftest.py").write_text((ROOT / "conftest.py").read_text())
            package = root / "core"
            (package / "tests").mkdir(parents=True)
            config = package / "pyproject.toml"
            config.write_text("")
            (package / "tests/test_invented.py").write_text(
                "import pytest\nfrom hypothesis import settings\n"
                "@pytest.mark.public_data\ndef test_profile():\n"
                " assert settings.default.max_examples == 100\n"
                " assert settings.default.database is None\n"
                "@pytest.mark.nightly\ndef test_nightly():\n"
                " raise AssertionError('nightly must be deselected')\n"
            )

            def run_copy(
                work: Path, *args: Any, **kwargs: Any
            ) -> tuple[int, list[dict[str, str]]]:
                copied = tomllib.loads(config.read_text())["tool"]["pytest"]
                self.assertEqual(
                    {k: v for k, v in copied.items() if k != "pythonpath"},
                    {k: v for k, v in settings.items() if k != "pythonpath"},
                )
                self.assertEqual(
                    copied["pythonpath"],
                    ["src", "../..", "../../scripts", "../../scripts/tests"],
                )
                self.assertEqual(
                    (work / "conftest.py").read_text(),
                    (root / "conftest.py").read_text(),
                )
                # Simulate mutmut's extra directory level, retaining its config/bootstrap.
                mutants = work / "mutants"
                import shutil

                shutil.copytree(work, mutants, ignore=shutil.ignore_patterns("mutants"))
                command = [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "tests/",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp",
                    str(root / "pytest-tmp"),
                ]
                result = subprocess.run(
                    command, cwd=mutants, capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("1 passed, 1 deselected", result.stdout)
                # A misspelled marker must fail collection under copied strict settings.
                (mutants / "tests/test_bad.py").write_text(
                    "import pytest\n"
                    "@pytest.mark.synthetic_unknown\ndef test_bad(): pass\n"
                )
                result = subprocess.run(
                    command, cwd=mutants, capture_output=True, text=True
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("synthetic_unknown", result.stdout)
                return 0, []

            with patch.object(mutation, "run_copy", side_effect=run_copy):
                self.assertEqual(
                    mutation.run_packages(
                        root, ["core/src/synthetic.py"], root / "ledger"
                    ),
                    0,
                )
            self.assertEqual(config.read_text(), "")
