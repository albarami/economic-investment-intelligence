"""Planted omissions prove the launcher and discovery assertions themselves."""

import importlib
import shutil
import subprocess
import unittest
from types import ModuleType
from typing import Any

import commands_support
import test_s3_t28_controls as controls_fixture
from s3_t28_discovery import DenyStoreDrivers, require_cases
from s3_t28_support import ROOT, WorkspaceCase


class VerificationControls(WorkspaceCase):
    sensitive = controls_fixture.Controls.sensitive

    def require_red(self, assertion: Any) -> None:
        result = unittest.TestResult()
        unittest.FunctionTestCase(assertion).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("launcher", result.failures[0][1])

    def test_each_launcher_flag_and_product_package_has_a_recorded_argv_plant(
        self,
    ) -> None:
        commands_support.write_fake_uv(self.root)
        launcher = self.root / "eii"
        source = (ROOT / "eii").read_text()
        shell = shutil.which("sh")
        self.assertIsNotNone(shell)
        product = "--locked --offline --package eii-product"
        custodian = "--locked --offline --package eii-custodian --group engine"
        for word, fragment, package in (
            ("up", product, "eii-product"),
            ("build-release", custodian, "eii-custodian"),
        ):

            def assertion(command: str = word, expected: str = package) -> None:
                result = subprocess.run(
                    [str(shell), str(launcher), command],
                    env={"PATH": str(self.root)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 7, "launcher missed fake uv")
                values = result.stdout.splitlines()
                for required in ("--locked", "--offline", "--package", expected):
                    self.assertIn(
                        required, values, "launcher contract admitted omission"
                    )
                if expected == "eii-product":
                    self.assertNotIn(
                        "eii-custodian",
                        values,
                        "launcher admitted Custodian to Product",
                    )
                else:
                    self.assertIn("--group", values, "launcher lost engine group")
                    self.assertIn("engine", values, "launcher lost engine group")

            launcher.write_text(source)
            assertion()
            for token in ("--locked", "--offline", "--package " + package):
                changed = fragment.replace(token, "", 1)
                launcher.write_text(source.replace(fragment, changed, 1))
                with self.subTest(command=word, omitted=token):
                    self.require_red(assertion)
            if word == "up":
                changed = fragment.replace("eii-product", "eii-custodian")
                launcher.write_text(source.replace(fragment, changed, 1))
                with self.subTest(command=word, plant="custodian-package"):
                    self.require_red(assertion)
            else:
                launcher.write_text(
                    source.replace(fragment, fragment.replace("--group engine", ""), 1)
                )
                with self.subTest(command=word, plant="missing-engine-group"):
                    self.require_red(assertion)

    def test_each_task_module_is_nonempty_and_each_driver_import_guard_is_deciding(
        self,
    ) -> None:
        loader = unittest.TestLoader()
        for path in sorted((ROOT / "scripts/tests").glob("test_s3_t28_*.py")):
            module = importlib.import_module(path.stem)
            self.assertGreater(require_cases(loader, module).countTestCases(), 0)
            with self.subTest(module=path.stem, plant="zero-cases"):
                self.sensitive(
                    require_cases,
                    (loader, ModuleType(path.stem)),
                    "INVENTED-empty-test-module",
                    kind=AssertionError,
                )
        finder = DenyStoreDrivers()
        self.assertIsNone(finder.find_spec("INVENTED_allowed"))
        for name in ("duckdb", "duckdb.extension", "psycopg", "psycopg.connection"):
            with self.subTest(driver=name):
                self.sensitive(
                    DenyStoreDrivers.find_spec,
                    (finder, name),
                    "INVENTED-driver-import-tripwire",
                    kind=AssertionError,
                )

    def test_public_build_command_and_closed_operation_refuse_dummy_requests(
        self,
    ) -> None:
        import contextlib
        import io
        from unittest.mock import patch

        from test_s3_t28_promotion import request

        from commands import build_release
        from operations import evidence

        for key, value in (
            ("EII_PARAMETER_SET", "A"),
            ("EII_PARAMETER_SET", "B"),
            ("EII_WINDOW_KEY", "INVENTED-window"),
            ("EII_WORLD_SEED", "INVENTED-seed"),
        ):
            with (
                self.subTest(setting=key, value=value),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
                patch("commands.build_release.build_release") as build,
            ):
                mutant = controls_fixture.without_return(
                    build_release.run,
                    "exits.finish(4, 'build-release', 'public_only_parameter_selection')",
                )
                self.assertEqual(build_release.run(self.root, {}, ()), 0)
                build.reset_mock()
                self.assertEqual(build_release.run(self.root, {key: value}, ()), 4)
                build.assert_not_called()

                def assertion(
                    setting: str = key, choice: str = value, function: Any = mutant
                ) -> None:
                    self.assertEqual(
                        function(self.root, {setting: choice}, ()),
                        4,
                        "Public build admitted a protected request",
                    )

                result = unittest.TestResult()
                unittest.FunctionTestCase(assertion).run(result)
                self.assertEqual(result.errors, [])
                self.assertEqual(len(result.failures), 1)
                self.assertIn("admitted", result.failures[0][1])
                build.assert_called_once_with(self.root)
        raw = request()
        self.assertEqual(evidence.operation(raw), raw)
        for key in ("window_key", "register_append"):
            with self.subTest(operation_property=key):
                self.sensitive(
                    evidence.operation,
                    (dict(raw, **{key: "INVENTED-only"}),),
                    "operation_schema_invalid",
                )
