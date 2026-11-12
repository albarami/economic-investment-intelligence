#!/usr/bin/env python3
"""Harness and environment isolation for the fresh-interpreter guard."""

from __future__ import annotations

import os
import site
import subprocess
import sysconfig
import tempfile
import unittest
import venv
from pathlib import Path
from typing import Any
from unittest import mock

import import_boundary_cases as cases
import import_boundary_child as child


class _StoreEnvBuilder(venv.EnvBuilder):
    """Record the venv context after ``post_setup``."""

    context: Any = None

    def post_setup(self, context: Any) -> None:
        type(self).context = context


class ImportBoundarySurroundingsTest(unittest.TestCase):
    """Child harness failures and hostile parent environments."""

    def test_fresh_harness_failures(self) -> None:
        """The child harness reports timeouts, exits and missing JSON."""
        count = 0
        scenarios: tuple[tuple[str, str, list[str], int | None], ...] = (
            (
                "timeout",
                "import time\ntime.sleep(30)\n",
                [cases.expected_fresh_timeout("eii_product", 3)],
                3,
            ),
            (
                "exit_five",
                "import os\nos._exit(5)\n",
                [cases.expected_fresh_harness_exit("eii_product", 5)],
                None,
            ),
            (
                "noise_before",
                'print("noise")\n',
                [],
                None,
            ),
            (
                "exit_zero",
                "import os\nos._exit(0)\n",
                [cases.expected_fresh_harness_no_result("eii_product")],
                None,
            ),
            (
                "noise_after",
                "import atexit\natexit.register(print, 'noise')\n",
                [cases.expected_fresh_harness_no_result("eii_product")],
                None,
            ),
        )
        for label, source, expected, timeout in scenarios:
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    cases.make_tree(root)
                    cases.write_planted(root, "eii_product", source)
                    if timeout is None:
                        result = child.run_fresh(root, "eii_product")
                    else:
                        result = child.run_fresh(root, "eii_product", timeout=timeout)
                    self.assertEqual(result, expected)
            count += 1
        with self.subTest(case="json_not_object"):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cases.make_tree(root)
                cases.write_planted(root, "eii_product", "pass\n")
                with mock.patch.object(
                    subprocess,
                    "run",
                    return_value=mock.Mock(returncode=0, stdout="[1, 2]\n"),
                ):
                    result = child.run_fresh(root, "eii_product")
                self.assertEqual(
                    result,
                    [cases.expected_fresh_harness_no_result("eii_product")],
                )
            count += 1
        self.assertEqual(count, 6)

    def test_fresh_hostile_surroundings(self) -> None:
        """Parent environment tricks must not change an isolated child."""
        count = 0
        already = cases.expected_fresh_already_loaded("eii_product", "eii_custodian")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            path_dir = Path(folder) / "path_inject"
            path_dir.mkdir()
            (path_dir / "sitecustomize.py").write_text(
                "import sys, types\n"
                'sys.modules["eii_custodian"] = types.ModuleType("eii_custodian")\n',
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ, {"PYTHONPATH": str(path_dir)}, clear=False
            ):
                with self.subTest(case="pythonpath_isolated"):
                    self.assertEqual(child.run_fresh(root, "eii_product"), [])
                    count += 1
                with self.subTest(case="pythonpath_tooth"):
                    result = child.run_fresh(
                        root,
                        "eii_product",
                        flags=("-B",),
                        env=dict(os.environ),
                    )
                    self.assertIn(already, result)
                    count += 1

            venv_root = Path(folder) / "venv"
            builder = _StoreEnvBuilder(with_pip=False)
            builder.create(str(venv_root))
            assert builder.context is not None
            purelib = sysconfig.get_path(
                "purelib",
                scheme="venv",
                vars={
                    "base": str(venv_root),
                    "platbase": str(venv_root),
                },
            )
            Path(purelib).mkdir(parents=True, exist_ok=True)
            (Path(purelib) / "startup.pth").write_text(
                'import sys, types; sys.modules["eii_custodian"] = types.ModuleType("eii_custodian")\n',
                encoding="utf-8",
            )
            with self.subTest(case="venv_site_default"):
                self.assertEqual(
                    child.run_fresh(
                        root,
                        "eii_product",
                        python=builder.context.env_exe,
                    ),
                    [],
                )
                count += 1
            with self.subTest(case="venv_site_tooth"):
                result = child.run_fresh(
                    root,
                    "eii_product",
                    flags=("-I", "-B"),
                    python=builder.context.env_exe,
                )
                self.assertIn(already, result)
                count += 1

            shadow = Path(folder) / "shadow"
            shadow.mkdir()
            (shadow / "json.py").write_text(
                'raise ImportError("planted")\n',
                encoding="utf-8",
            )
            shadow_env = {"PYTHONPATH": str(shadow)}
            with self.subTest(case="shadow_without_I"):
                result = child.run_fresh(
                    root,
                    "eii_product",
                    flags=("-S", "-B"),
                    env=shadow_env,
                )
                self.assertEqual(
                    result,
                    [cases.expected_fresh_harness_exit("eii_product", 1)],
                )
                count += 1
            with self.subTest(case="shadow_isolated"):
                self.assertEqual(
                    child.run_fresh(root, "eii_product", env=shadow_env),
                    [],
                )
                count += 1

        self.assertEqual(count, 6)

    def test_fresh_third_party_in_parent_environment(self) -> None:
        """Site paths and parent variables reach the child only by design."""
        count = 0
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases.make_tree(root)
            fake_site = Path(folder) / "fake_site"
            fake_site.mkdir()
            (fake_site / "thirdparty_zz.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

            with self.subTest(case="site_packages_default"):
                cases.write_planted(root, "eii_product", "import thirdparty_zz\n")
                with mock.patch.object(
                    site, "getsitepackages", return_value=[str(fake_site)]
                ):
                    self.assertEqual(child.run_fresh(root, "eii_product"), [])
                count += 1

            with self.subTest(case="site_packages_tooth"):
                with mock.patch.object(
                    site, "getsitepackages", return_value=[str(fake_site)]
                ):
                    result = child.run_fresh(root, "eii_product", site_paths=())
                expected = cases.expected_fresh_import_error(
                    "eii_product", "eii_product.planted", "ModuleNotFoundError"
                )
                self.assertEqual(result, [expected])
                count += 1

            with self.subTest(case="parent_env_var"):
                cases.write_planted(
                    root,
                    "eii_product",
                    'import os\nos.environ["EII_PLANTED_ZZ"]\n',
                )
                with mock.patch.dict(os.environ, {"EII_PLANTED_ZZ": "1"}, clear=False):
                    result = child.run_fresh(root, "eii_product")
                expected = cases.expected_fresh_import_error(
                    "eii_product", "eii_product.planted", "KeyError"
                )
                self.assertEqual(result, [expected])
                count += 1

            fake_user = Path(folder) / "fake_user"
            fake_user.mkdir()
            (fake_user / "dummyzz.py").write_text("VALUE = 1\n", encoding="utf-8")
            cases.write_planted(root, "eii_product", "import dummyzz\n")
            with self.subTest(case="user_site_ignored"):
                with (
                    mock.patch.object(site, "getsitepackages", return_value=[]),
                    mock.patch.object(
                        site, "getusersitepackages", return_value=str(fake_user)
                    ),
                ):
                    result = child.run_fresh(root, "eii_product")
                expected = cases.expected_fresh_import_error(
                    "eii_product", "eii_product.planted", "ModuleNotFoundError"
                )
                self.assertEqual(result, [expected])
                count += 1

        self.assertEqual(count, 4)

    def test_child_env(self) -> None:
        """The child environment keeps only documented keys."""
        count = 0
        base = {
            "PYTHONPATH": "/x",
            "HOME": "/home/x",
            "EII_DECISION_PROVIDER": "none",
        }
        with self.subTest(case="empty_without_systemroot"):
            with mock.patch.dict(os.environ, base, clear=True):
                self.assertEqual(child.child_env(), {})
            count += 1
        with self.subTest(case="systemroot_preserved"):
            with mock.patch.dict(os.environ, {**base, "SYSTEMROOT": "q"}, clear=True):
                self.assertEqual(child.child_env(), {"SYSTEMROOT": "q"})
            count += 1
        self.assertEqual(count, 2)
