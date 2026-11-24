"""Sandbox/cleanup/process/launcher boundary plants on invented local inputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from s3_t28_support import IDENTITY, ROOT, WorkspaceCase

import sandbox_launch
import sandbox_profiles
from operations.build import build_release
from operations.common import Refusal
from operations.policy import require_sources
from operations.process import identity, require_command, require_owned, wait_ready


class Boundaries(WorkspaceCase):
    def test_owned_child_each_readiness_failure_without_fallback(self) -> None:
        record = dict(port=18088, release_id=IDENTITY)
        for value in (
            dict(status="degraded", release_id=IDENTITY, release_hash=IDENTITY),
            dict(status="ok", release_id="cd" * 32, release_hash="cd" * 32),
            dict(status="ok", release_id=IDENTITY, release_hash="cd" * 32),
        ):
            with (
                self.subTest(value=value),
                patch("operations.process.require_owned"),
                self.assertRaisesRegex(Refusal, "startup_not_ready"),
            ):
                wait_ready(record, "live", Mock(return_value=value))
        with (
            patch("operations.process.require_owned"),
            patch("operations.process.time.monotonic", side_effect=[0.0, 6.0]),
            self.assertRaisesRegex(Refusal, "startup_not_ready"),
        ):
            wait_ready(record, "live", Mock())

    def test_static_operation_policy_has_each_database_control_plant(self) -> None:
        sources = {
            path.name: path.read_text()
            for path in (ROOT / "scripts/operations").glob("*.py")
        }
        require_sources(sources)
        for name in (
            "up_cmd.py",
            "down_cmd.py",
            "deploy.py",
            "process.py",
            "package.py",
            "install.py",
        ):
            for executable in ("docker", "compose", "pg_ctl", "postgres", "systemctl"):
                planted = {
                    name: "import subprocess\nsubprocess.run(["
                    + repr(executable)
                    + ", 'start'])\n"
                }
                with (
                    self.subTest(name=name, executable=executable),
                    self.assertRaisesRegex(Refusal, "operation_command_refused"),
                ):
                    require_sources(planted)

    def test_all_new_tests_run_with_both_store_drivers_denied(self) -> None:
        if any(getattr(finder, "s3_t28_tripwire", False) for finder in sys.meta_path):
            self.assertNotIn("duckdb", sys.modules)
            self.assertNotIn("psycopg", sys.modules)
            return
        program = """
import importlib
import sys
import unittest
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root / name) for name in ("scripts/tests", "scripts", "core/src", "product/src")]
from s3_t28_discovery import DenyStoreDrivers, require_cases
sys.meta_path.insert(0, DenyStoreDrivers())
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for path in sorted((root / "scripts/tests").glob("test_s3_t28_*.py")):
    suite.addTests(require_cases(loader, importlib.import_module(path.stem)))
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=0).run(suite)
print("driver-free cases:", result.testsRun)
raise SystemExit(0 if result.wasSuccessful() else 1)
"""
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", program, str(ROOT)],
            env={
                key: value
                for key, value in os.environ.items()
                if key in {"PATH", "HOME", "LANG", "LC_ALL"}
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("driver-free cases:", result.stdout)

    def sandbox(self, profile: str, layout: Any, command: Any) -> Any:
        self.assertEqual(profile, "build-release")
        self.assertIn("--unshare-net", sandbox_profiles.ISOLATION)
        self.assertEqual(
            sandbox_profiles.CODE_FOLDERS,
            ("core/src", "custodian/src", "scripts/sandbox_inside"),
        )
        self.assertNotIn("product", repr(command))
        (layout.vault / "INVENTED-record").write_bytes(b"INVENTED-only")
        (layout.staging / "manifest.json").write_text(
            json.dumps(dict(release_kind="public_only", release_id=IDENTITY))
        )
        self.vault = layout.vault
        return SimpleNamespace(returncode=0)

    def test_build_deletes_owned_vault_before_publication(self) -> None:
        def validate(stage: Any) -> None:
            self.assertFalse(self.vault.exists())
            self.assertTrue((stage / "manifest.json").is_file())

        result = build_release(self.root, sandbox=self.sandbox, validate=validate)
        self.assertEqual(result.name, IDENTITY)
        self.assertFalse(self.vault.exists())

    def test_failed_build_still_deletes_vault(self) -> None:
        def fail(*args: Any) -> Any:
            self.sandbox(*args)
            return SimpleNamespace(returncode=4)

        with self.assertRaisesRegex(Refusal, "operation_failed"):
            build_release(self.root, sandbox=fail, validate=Mock())
        self.assertFalse(self.vault.exists())
        self.assertFalse((self.root / "data/releases").exists())

    def test_cleanup_leftover_and_error_each_block_publication(self) -> None:
        for cleanup in (lambda _: None, Mock(side_effect=OSError("INVENTED-error"))):
            with (
                self.subTest(cleanup=type(cleanup).__name__),
                self.assertRaisesRegex(Refusal, "vault_cleanup_failed"),
            ):
                build_release(
                    self.root, sandbox=self.sandbox, cleanup=cleanup, validate=Mock()
                )
            self.assertFalse((self.root / "data/releases").exists())

    def test_no_sandbox_fallback(self) -> None:
        validate = Mock()
        with self.assertRaisesRegex(Refusal, "sandbox_enforcement_failed"):
            build_release(
                self.root,
                sandbox=Mock(
                    side_effect=sandbox_launch.SandboxError("INVENTED-unavailable")
                ),
                validate=validate,
            )
        validate.assert_not_called()
        self.assertFalse((self.root / "data/releases").exists())

    def test_database_control_executables_never_admitted(self) -> None:
        for command in (
            "docker",
            "compose",
            "pg_ctl",
            "postgres",
            "systemctl",
            "sh",
            "python",
        ):
            with (
                self.subTest(command=command),
                self.assertRaisesRegex(Refusal, "operation_command_refused"),
            ):
                require_command((command, "up"))
        require_command(
            (sys.executable, "-I", "-B", "-S", "scripts/operations/serve.py")
        )

    def test_process_identity_each_field_and_foreign_environment(self) -> None:
        pid = 17
        proc = self.root / str(pid)
        proc.mkdir()
        # state is item three; starttime is item twenty two, after comm.
        (proc / "stat").write_text(
            "17 (INVENTED worker) " + " ".join(["S"] + ["0"] * 18 + ["123"])
        )
        (proc / "cmdline").write_bytes(
            b"\0".join(
                [
                    b"python",
                    b"-I",
                    b"--nonce",
                    b"INVENTED-nonce",
                    b"--environment",
                    b"staging",
                    b"--port",
                    b"8089",
                    b"",
                ]
            )
        )
        ticks, command = identity(pid, proc_root=self.root)
        valid = dict(
            pid=pid,
            environment="staging",
            start_ticks=ticks,
            cmdline_sha256=command,
            nonce="INVENTED-nonce",
            port=8089,
        )
        require_owned(valid, "staging", proc_root=self.root)
        for key, value in (
            ("start_ticks", "124"),
            ("cmdline_sha256", "ab" * 32),
            ("nonce", "INVENTED-other"),
            ("environment", "live"),
        ):
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(Refusal, "process_identity_mismatch"),
            ):
                require_owned(
                    dict(valid, **{key: value}), "staging", proc_root=self.root
                )

    def test_launcher_is_offline_and_command_scoped(self) -> None:
        launcher = (ROOT / "eii").read_text()
        self.assertIn("--locked --offline --package eii-product", launcher)
        self.assertIn(
            "--locked --offline --package eii-custodian --group engine", launcher
        )
        self.assertNotIn("PYTHONPATH", launcher)
        with patch("operations.process.subprocess.Popen") as spawn:
            with self.assertRaisesRegex(Refusal, "operation_command_refused"):
                from operations.process import launch

                launch(
                    self.root,
                    self.root / "state",
                    ("docker", "up"),
                    {},
                    environment="live",
                    nonce="INVENTED",
                    port=8088,
                    release_id=IDENTITY,
                    application_sha256="ef" * 32,
                )
            spawn.assert_not_called()
