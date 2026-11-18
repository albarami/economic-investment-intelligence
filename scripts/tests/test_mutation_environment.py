"""PO-S2-61: caller-supplied options cannot narrow a mutation run."""

import contextlib
import importlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

mutation = importlib.import_module("scripts.mutation")


class MutationEnvironment(unittest.TestCase):
    def test_passed_addopts_refused_before_copy_or_tool_access(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(mutation.os.environ, {}, clear=True):
                with contextlib.redirect_stderr(io.StringIO()) as output:
                    result = mutation.run_copy(
                        Path(folder),
                        [],
                        [],
                        Path(folder) / "absent.toml",
                        environment={"PYTEST_ADDOPTS": "-k nothing"},
                    )
            self.assertEqual(result, (2, []))
            self.assertIn("Refusing PYTEST_ADDOPTS", output.getvalue())
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_process_namespace_is_required(self) -> None:
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as folder:
            result = mutation.isolated_command(
                Path(folder), [sys.executable, "-c", "print('invented-child')"], None
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "invented-child")
            # Plant a launcher that executes in the caller's namespace.
            with patch.object(mutation, "ISOLATION_PREFIX", ()):
                refused = mutation.isolated_command(
                    Path(folder), [sys.executable, "-c", "print('must-not-run')"], None
                )
            self.assertNotEqual(refused.returncode, 0)
            self.assertNotIn("must-not-run", refused.stdout)
            self.assertIn("process namespace", refused.stderr)
            with patch.object(
                mutation.subprocess, "run", side_effect=FileNotFoundError
            ):
                missing = mutation.isolated_command(
                    Path(folder), [sys.executable], None
                )
            self.assertEqual(missing.returncode, 2)
            self.assertIsInstance(missing, subprocess.CompletedProcess)
