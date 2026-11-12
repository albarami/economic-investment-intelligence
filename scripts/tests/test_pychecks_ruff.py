"""Planted ruff lint and format violation tests."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import pychecks_support as support


class PychecksRuff(unittest.TestCase):
    """Prove ruff rule families and formatter settings bite."""

    def _env(self) -> tuple[Path, dict[str, str]]:
        home = Path(tempfile.mkdtemp(dir=support.home_tmpdir()))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        return home, support.clean_env(home)

    def test_ruff_check_rules_have_teeth(self) -> None:
        _home, env = self._env()
        noqa = "# no" + "qa: F401"
        copy = support.fresh_copy(self)
        support.write_files(
            copy,
            {
                "scripts/planted_e402.py": "x = 1\nimport os\n\nprint(x, os.name)\n",
                "scripts/planted_e711.py": "x = None\nif x == None:\n    pass\n",
                "scripts/planted_f401.py": "import os\n",
                "scripts/planted_b006.py": "def f(x: list[int] = []) -> None:\n    x.append(1)\n",
                "scripts/planted_i001.py": (
                    "import eii_core\nimport mypy\n\n"
                    "print(eii_core.__version__, mypy.__file__)\n"
                ),
                "scripts/planted_up006.py": "import typing\n\nx: typing.List[int] = []\n",
                "scripts/planted_ruf012.py": "class A:\n    x: list[int] = []\n",
                "scripts/planted_ruf100.py": f"x = 1  {noqa}\n",
            },
        )
        proc = support.run(
            [support.tool("ruff"), "check", ".", "--output-format", "concise"],
            copy,
            env,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout)
        expected = [
            ("scripts/planted_b006.py", 1, "B006"),
            ("scripts/planted_e402.py", 2, "E402"),
            ("scripts/planted_e711.py", 2, "E711"),
            ("scripts/planted_f401.py", 1, "F401"),
            ("scripts/planted_i001.py", 1, "I001"),
            ("scripts/planted_ruf012.py", 2, "RUF012"),
            ("scripts/planted_ruf100.py", 1, "RUF100"),
            ("scripts/planted_up006.py", 3, "UP006"),
        ]
        self.assertEqual(support.ruff_findings(proc.stdout + proc.stderr), expected)

        text = (copy / "pyproject.toml").read_text(encoding="utf-8")
        text, n = re.subn(r"^\s*src\s*=\s*\[.*\]\s*$", "", text, count=1, flags=re.M)
        self.assertEqual(n, 1)
        (copy / "pyproject.toml").write_text(text, encoding="utf-8")
        proc2 = support.run(
            [support.tool("ruff"), "check", ".", "--output-format", "concise"],
            copy,
            env,
        )
        findings = support.ruff_findings(proc2.stdout + proc2.stderr)
        self.assertFalse(any(p.endswith("planted_i001.py") for p, _, _ in findings))

    def test_ruff_check_does_not_fix(self) -> None:
        _home, env = self._env()
        copy = support.fresh_copy(self)
        rel = "scripts/planted_f401.py"
        support.write_files(copy, {rel: "import os\n"})
        path = copy / rel
        before = path.read_bytes()
        proc = support.run([support.tool("ruff"), "check", "."], copy, env)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(path.read_bytes(), before)
        proc_fix = support.run(
            [support.tool("ruff"), "check", rel, "--fix"],
            copy,
            env,
        )
        self.assertEqual(proc_fix.returncode, 0)
        self.assertEqual(path.read_bytes(), b"")

    def test_ruff_format_has_teeth(self) -> None:
        _home, env = self._env()
        copy = support.fresh_copy(self)
        support.write_files(
            copy,
            {
                "scripts/planted_fmt_spaces.py": 'x  =  {"a":1}\n',
                "scripts/planted_fmt_quotes.py": "x = 'a'\n",
                "scripts/planted_paren_except.py": (
                    "try:\n    pass\nexcept (OSError, ValueError):\n    pass\n"
                ),
            },
        )
        proc = support.run(
            [
                support.tool("ruff"),
                "format",
                "--check",
                ".",
                "--output-format",
                "concise",
            ],
            copy,
            env,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(
            support.format_paths(proc.stdout + proc.stderr),
            ["scripts/planted_fmt_quotes.py", "scripts/planted_fmt_spaces.py"],
        )

    def test_ruff_format_write_mode(self) -> None:
        _home, env = self._env()
        copy = support.fresh_copy(self)
        support.write_files(
            copy,
            {
                "scripts/planted_fmt_spaces.py": 'x  =  {"a":1}\n',
                "scripts/planted_fmt_quotes.py": "x = 'a'\n",
                "docs_planted.md": "```python\nx  =  1\n```\n",
            },
        )
        proc = support.run([support.tool("ruff"), "format", "."], copy, env)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            (copy / "scripts/planted_fmt_spaces.py").read_text(encoding="utf-8"),
            'x = {"a": 1}\n',
        )
        self.assertEqual(
            (copy / "scripts/planted_fmt_quotes.py").read_text(encoding="utf-8"),
            'x = "a"\n',
        )
        md_before = (copy / "docs_planted.md").read_bytes()
        proc2 = support.run([support.tool("ruff"), "format", "--check", "."], copy, env)
        self.assertEqual(proc2.returncode, 0)
        self.assertEqual((copy / "docs_planted.md").read_bytes(), md_before)

    def test_markdown_is_not_judged(self) -> None:
        _home, env = self._env()
        copy = support.fresh_copy(self)
        support.write_files(copy, {"docs_planted.md": "```python\nx  =  1\n```\n"})
        for args in (["check", "."], ["format", "--check", "."]):
            proc = support.run([support.tool("ruff"), *args], copy, env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (copy / "pyproject.toml").read_text(encoding="utf-8")
        text, n = re.subn(
            r"^\s*extend-exclude\s*=\s*\[.*\]\s*$", "", text, count=1, flags=re.M
        )
        self.assertEqual(n, 1)
        (copy / "pyproject.toml").write_text(text, encoding="utf-8")
        proc = support.run(
            [
                support.tool("ruff"),
                "format",
                "--check",
                ".",
                "--output-format",
                "concise",
            ],
            copy,
            env,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(
            support.format_paths(proc.stdout + proc.stderr), ["docs_planted.md"]
        )

    def test_ruff_target_version_is_read(self) -> None:
        _home, env = self._env()
        copy = support.fresh_copy(self)
        support.write_files(
            copy,
            {
                "scripts/planted_paren_except.py": (
                    "try:\n    pass\nexcept (OSError, ValueError):\n    pass\n"
                ),
                "scripts/planted_unparen_except.py": (
                    "try:\n    pass\nexcept OSError, ValueError:\n    pass\n"
                ),
            },
        )
        proc_fmt = support.run(
            [support.tool("ruff"), "format", "--check", "."], copy, env
        )
        self.assertEqual(proc_fmt.returncode, 0)
        proc = support.run(
            [support.tool("ruff"), "check", ".", "--output-format", "concise"],
            copy,
            env,
        )
        self.assertEqual(proc.returncode, 1)
        findings = support.ruff_findings(proc.stdout + proc.stderr)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][:2], ("scripts/planted_unparen_except.py", 3))

        text = (copy / "pyproject.toml").read_text(encoding="utf-8")
        text = re.sub(
            r'^target-version\s*=\s*"py312"\s*$',
            'target-version = "py314"',
            text,
            count=1,
            flags=re.M,
        )
        (copy / "pyproject.toml").write_text(text, encoding="utf-8")
        proc_check = support.run([support.tool("ruff"), "check", "."], copy, env)
        self.assertEqual(proc_check.returncode, 0)
        proc_fmt2 = support.run(
            [
                support.tool("ruff"),
                "format",
                "--check",
                "scripts/planted_paren_except.py",
                "--output-format",
                "concise",
            ],
            copy,
            env,
        )
        self.assertEqual(proc_fmt2.returncode, 1)
        self.assertEqual(
            support.format_paths(proc_fmt2.stdout + proc_fmt2.stderr),
            ["scripts/planted_paren_except.py"],
        )


if __name__ == "__main__":
    unittest.main()
