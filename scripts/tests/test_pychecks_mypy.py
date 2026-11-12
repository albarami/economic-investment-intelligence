"""Planted mypy strict violation tests."""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

import pychecks_support as support


class PychecksMypy(unittest.TestCase):
    """Prove mypy strict mode bites across workspace roots."""

    def test_mypy_strict_has_teeth(self) -> None:

        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: shutil.rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        ignore = "# type" + ": ignore"
        copy = support.fresh_copy(self)
        support.write_files(
            copy,
            {
                "scripts/planted_untyped.py": "def f(x):\n    return x\n",
                "scripts/tests/planted_untyped_tests.py": "def f(x):\n    return x\n",
                "core/src/eii_core/planted_untyped.py": "def f(x):\n    return x\n",
                "custodian/src/eii_custodian/planted_untyped.py": "def f(x):\n    return x\n",
                "product/src/eii_product/planted_untyped.py": "def f(x):\n    return x\n",
                "core/src/eii_core/planted_type_arg.py": "def g(x: list) -> None:\n    return None\n",
                "core/src/eii_core/planted_unused_ignore.py": f"x: int = 1  {ignore}\n",
                "core/src/eii_core/planted_any_return.py": (
                    "import json\n\n\ndef h(s: str) -> str:\n    return json.loads(s)\n"
                ),
                "custodian/src/eii_custodian/planted_cross.py": (
                    "from eii_core import __version__\n\nx: int = __version__\n"
                ),
                "product/src/eii_product/planted_missing_import.py": (
                    "import no_such_module_for_planting\n"
                ),
            },
        )
        proc = support.run([support.tool("mypy")], copy, env)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        expected = [
            ("core/src/eii_core/planted_any_return.py", 5, "no-any-return"),
            ("core/src/eii_core/planted_type_arg.py", 1, "type-arg"),
            ("core/src/eii_core/planted_untyped.py", 1, "no-untyped-def"),
            ("core/src/eii_core/planted_unused_ignore.py", 1, "unused-ignore"),
            ("custodian/src/eii_custodian/planted_cross.py", 3, "assignment"),
            ("custodian/src/eii_custodian/planted_untyped.py", 1, "no-untyped-def"),
            (
                "product/src/eii_product/planted_missing_import.py",
                1,
                "import-not-found",
            ),
            ("product/src/eii_product/planted_untyped.py", 1, "no-untyped-def"),
            ("scripts/planted_untyped.py", 1, "no-untyped-def"),
            ("scripts/tests/planted_untyped_tests.py", 1, "no-untyped-def"),
        ]
        self.assertEqual(support.mypy_findings(proc.stdout + proc.stderr), expected)

    def test_mypy_python_version_is_read(self) -> None:
        import tempfile
        from pathlib import Path

        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: shutil.rmtree(home, ignore_errors=True))
        env = support.clean_env(home)
        copy = support.fresh_copy(self)
        support.write_files(
            copy,
            {
                "scripts/planted_unparen_except.py": (
                    "try:\n    pass\nexcept OSError, ValueError:\n    pass\n"
                ),
            },
        )
        proc = support.run([support.tool("mypy")], copy, env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        text = (copy / "pyproject.toml").read_text(encoding="utf-8")
        text, n = re.subn(
            r'^python_version\s*=\s*"3\.14"\s*$',
            'python_version = "3.13"',
            text,
            count=1,
            flags=re.M,
        )
        self.assertEqual(n, 1)
        (copy / "pyproject.toml").write_text(text, encoding="utf-8")
        proc2 = support.run([support.tool("mypy")], copy, env)
        self.assertEqual(proc2.returncode, 1)
        self.assertEqual(
            support.mypy_findings(proc2.stdout + proc.stderr),
            [("scripts/planted_unparen_except.py", 3, "syntax")],
        )


if __name__ == "__main__":
    unittest.main()
