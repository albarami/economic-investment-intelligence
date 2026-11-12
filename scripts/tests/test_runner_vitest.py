"""Vitest suite tests for the runner."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import runner_support as support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests

PASS = (
    "import { expect, it } from 'vitest';\n"
    "it('a', () => { expect(1).toBe(1); });\n"
    "it('b', () => { expect(1).toBe(1); });\n"
)


class RunnerVitest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="eii-vitest-")
        self.root = support.fixture_root(Path(self._tmp.name))
        self.assertTrue(hasattr(run_tests, "SUITES"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_vitest_suites(self) -> None:
        cases: list[tuple[str, dict[str, str], str, int, tuple[str, ...]]] = [
            (
                "clean",
                {"web/tests/unit/a.test.ts": PASS},
                "2 passed, 0 failed, 0 skipped",
                0,
                (),
            ),
            (
                "one-fail",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { expect, it } from 'vitest';\n"
                        "it('bad', () => { expect(1).toBe(2); });\n"
                        "it('good', () => { expect(1).toBe(1); });\n"
                    )
                },
                "1 passed, 1 failed, 0 skipped",
                1,
                ("FAIL tests-failed: fx-vitest: 1 failed",),
            ),
            (
                "describe-fail",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { describe, expect, it } from 'vitest';\n"
                        "describe('g', () => {\n"
                        "  it('a', () => { expect(1).toBe(2); });\n"
                        "  it('b', () => { expect(1).toBe(2); });\n"
                        "  it('c', () => { expect(1).toBe(1); });\n"
                        "});\n"
                    )
                },
                "1 passed, 2 failed, 0 skipped",
                1,
                ("FAIL tests-failed: fx-vitest: 2 failed",),
            ),
            (
                "deep",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { describe, expect, it } from 'vitest';\n"
                        "describe('outer', () => {\n"
                        "  describe('inner', () => {\n"
                        "    it('bad', () => { expect(1).toBe(2); });\n"
                        "  });\n"
                        "});\n"
                    )
                },
                "0 passed, 1 failed, 0 skipped",
                1,
                (),
            ),
            (
                "skip",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { it } from 'vitest';\nit.skip('hidden', () => {});\n"
                    )
                },
                "0 passed, 0 failed, 1 skipped",
                1,
                (
                    "FAIL unexplained-skip: fx-vitest: hidden: reason not readable from this runner",
                ),
            ),
            (
                "todo",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { it } from 'vitest';\nit.todo('hidden');\n"
                    )
                },
                "0 passed, 0 failed, 1 skipped",
                1,
                (
                    "FAIL unexplained-skip: fx-vitest: hidden: reason not readable from this runner",
                ),
            ),
            (
                "before-all",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { beforeAll, describe, expect, it } from 'vitest';\n"
                        "describe('g', () => {\n"
                        "  beforeAll(() => { throw new Error('boom'); });\n"
                        "  it('a', () => { expect(1).toBe(1); });\n"
                        "  it('b', () => { expect(1).toBe(1); });\n"
                        "});\n"
                        "it('top', () => { expect(1).toBe(1); });\n"
                    )
                },
                "1 passed, 1 failed, 2 skipped",
                1,
                (
                    "FAIL tests-failed: fx-vitest: 1 failed",
                    "FAIL unexplained-skip: fx-vitest: g a: reason not readable from this runner",
                    "FAIL unexplained-skip: fx-vitest: g b: reason not readable from this runner",
                ),
            ),
            (
                "file-before",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { beforeAll, expect, it } from 'vitest';\n"
                        "beforeAll(() => { throw new Error('boom'); });\n"
                        "it('a', () => { expect(1).toBe(1); });\n"
                        "it('b', () => { expect(1).toBe(1); });\n"
                    )
                },
                "0 passed, 1 failed, 2 skipped",
                1,
                (),
            ),
            (
                "after-all",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { afterAll, describe, expect, it } from 'vitest';\n"
                        "describe('g', () => {\n"
                        "  afterAll(() => { throw new Error('boom'); });\n"
                        "  it('a', () => { expect(1).toBe(1); });\n"
                        "});\n"
                    )
                },
                "1 passed, 1 failed, 0 skipped",
                1,
                (),
            ),
            (
                "missing-import",
                {
                    "web/tests/unit/bad.test.ts": "import './no-such-module';\n",
                    "web/tests/unit/ok.test.ts": (
                        "import { expect, it } from 'vitest';\n"
                        "it('ok', () => { expect(1).toBe(1); });\n"
                    ),
                },
                "1 passed, 1 failed, 0 skipped",
                1,
                (),
            ),
            (
                "throw",
                {"web/tests/unit/a.test.ts": "throw new Error('boom');\n"},
                "0 passed, 1 failed, 0 skipped",
                1,
                (),
            ),
            (
                "empty",
                {"web/tests/unit/a.test.ts": "export {};\n"},
                "0 passed, 1 failed, 0 skipped",
                1,
                (),
            ),
            (
                "fails-pass",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { expect, it } from 'vitest';\n"
                        "it.fails('odd', () => { expect(1).toBe(1); });\n"
                    )
                },
                "0 passed, 1 failed, 0 skipped",
                1,
                (),
            ),
            (
                "none",
                {},
                "0 passed, 0 failed, 0 skipped",
                1,
                ("FAIL no-tests: fx-vitest: the suite ran no tests",),
            ),
            (
                "include",
                {
                    "web/tests/unit/x.node-test.mjs": "throw new Error('no');\n",
                    "web/src/y.test.ts": "throw new Error('no');\n",
                    "web/tests/unit/z.test.ts": (
                        "import { expect, it } from 'vitest';\n"
                        "it('ok', () => { expect(1).toBe(1); });\n"
                    ),
                },
                "1 passed, 0 failed, 0 skipped",
                0,
                (),
            ),
            (
                "bad-config",
                {"web/vitest.config.ts": "export default [;\n"},
                "counts unavailable",
                1,
                (
                    "FAIL no-counts: fx-vitest: exit status 1; no result file was written",
                ),
            ),
            (
                "fails-fail",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { expect, it } from 'vitest';\n"
                        "it.fails('expected', () => { expect(1).toBe(2); });\n"
                        "it('ok', () => { expect(1).toBe(1); });\n"
                    )
                },
                "2 passed, 0 failed, 0 skipped",
                0,
                (),
            ),
            (
                "todo-describe",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { describe, expect, it } from 'vitest';\n"
                        "describe.todo('g');\n"
                        "it('ok', () => { expect(1).toBe(1); });\n"
                    )
                },
                "1 passed, 0 failed, 0 skipped",
                0,
                (),
            ),
            (
                "todo-body",
                {
                    "web/tests/unit/a.test.ts": (
                        "import { describe, it } from 'vitest';\n"
                        "describe.todo('h', () => { it('t', () => {}); });\n"
                    )
                },
                "0 passed, 0 failed, 1 skipped",
                1,
                (
                    "FAIL unexplained-skip: fx-vitest: h t: reason not readable from this runner",
                ),
            ),
        ]
        for name, files, counts, expect, lines in cases:
            with self.subTest(name=name):
                self._reset()
                for rel, text in files.items():
                    support.put(self.root, rel, text)
                status, out, _err = self._run()
                visible = support.visible(out)
                self.assertEqual(status, expect, visible)
                if counts == "counts unavailable":
                    self.assertIn("suite fx-vitest: counts unavailable", visible)
                else:
                    self.assertIn(f"suite fx-vitest: {counts}", visible)
                for line in lines:
                    self.assertIn(line, visible)
                if name in {"fails-fail", "todo-describe"}:
                    self.assertFalse(any(item.startswith("FAIL ") for item in visible))
                if name == "none":
                    fails = [item for item in visible if item.startswith("FAIL ")]
                    self.assertEqual(
                        fails, ["FAIL no-tests: fx-vitest: the suite ran no tests"]
                    )

    def test_vitest_install_problems(self) -> None:
        support.put(self.root, "web/tests/unit/a.test.ts", PASS)
        rows = (
            ("missing", "vitest is not installed (run npm ci in web/)"),
            ("json", "node_modules/vitest/package.json is not valid JSON"),
            ("bin", "node_modules/vitest/package.json has no bin entry named vitest"),
            ("absent", "vitest binary not found:"),
        )
        for name, detail in rows:
            with self.subTest(name=name):
                self._install(name)
                status, out, _err = self._run()
                self.assertEqual(status, 1, out)
                joined = "\n".join(out)
                self.assertIn(f"FAIL cannot-start: fx-vitest: {detail}", joined)

    def test_vitest_receives_the_seed(self) -> None:
        lines = [
            "import { expect, it } from 'vitest';",
        ]
        for number in range(1, 13):
            lines.append(
                f"it('t{number}', () => {{ console.log('ORDER {number}'); "
                f"expect({number}).toBe({0 if number == 12 else number}); }});"
            )
        support.put(self.root, "web/tests/unit/order.test.ts", "\n".join(lines) + "\n")
        first = self._order("1794000000")
        again = self._order("1794000000")
        other = self._order("1794000007")
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertTrue(first != list(range(1, 13)) or other != list(range(1, 13)))

    def _order(self, seed: str) -> list[int]:
        status, out, _err = support.call(
            ["--seed", seed],
            (support.fx_suite("fx-vitest", "vitest", "web", ()),),
            self.root,
            support.parent_env(),
        )
        self.assertEqual(status, 1, out)
        found = []
        for line in out:
            match = re.search(r"ORDER (\d+)\s*$", line)
            if match:
                found.append(int(match.group(1)))
        self.assertEqual(len(found), 12, out)
        return found

    def _reset(self) -> None:
        for rel in ("web/tests/unit", "web/src"):
            folder = self.root / rel
            if folder.exists():
                for child in folder.rglob("*"):
                    if child.is_file():
                        child.unlink()
        source = support.ROOT / "web" / "vitest.config.ts"
        if source.is_file():
            support.put(
                self.root,
                "web/vitest.config.ts",
                source.read_text(encoding="utf-8"),
            )
        link = self.root / "web" / "node_modules"
        if not link.is_symlink() and not link.exists():
            link.symlink_to(
                support.ROOT / "web" / "node_modules", target_is_directory=True
            )

    def _install(self, kind: str) -> None:
        link = self.root / "web" / "node_modules"
        if link.is_symlink() or link.exists():
            if link.is_symlink() or link.is_file():
                link.unlink()
            else:
                __import__("shutil").rmtree(link)
        if kind == "missing":
            return
        folder = self.root / "web" / "node_modules" / "vitest"
        folder.mkdir(parents=True)
        if kind == "json":
            (folder / "package.json").write_text("{", encoding="utf-8")
            return
        if kind == "bin":
            (folder / "package.json").write_text(
                json.dumps({"bin": {"other": "./missing.mjs"}}), encoding="utf-8"
            )
            return
        (folder / "package.json").write_text(
            json.dumps({"bin": {"vitest": "./missing.mjs"}}), encoding="utf-8"
        )

    def _run(self) -> tuple[int, list[str], list[str]]:
        return support.call(
            ["--seed", support.FIXTURE_SEED],
            (support.fx_suite("fx-vitest", "vitest", "web", ()),),
            self.root,
            support.parent_env(),
        )
