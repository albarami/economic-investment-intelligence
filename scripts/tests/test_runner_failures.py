"""Failure, time-out, output and interrupt tests for the runner."""

from __future__ import annotations

import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from unittest.mock import patch

import runner_support as support

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests
import run_tests_exec


class RunnerFailures(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="eii-fail-")
        self.root = support.fixture_root(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_crashing_runner_is_a_failed_suite(self) -> None:
        support.put(
            self.root, "fx/crash/test_one.py", "def test_one():\n    assert True\n"
        )
        with self.subTest(row="conftest"):
            (self.root / "conftest.py").write_text(
                "raise RuntimeError('boom')\n", encoding="utf-8"
            )
            self._no_counts("fx-crash", ("fx/crash",), "4")
        (self.root / "conftest.py").write_text(
            (support.ROOT / "conftest.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        with self.subTest(row="sigkill"):
            support.put(
                self.root,
                "fx/crash/test_one.py",
                "import os\nimport signal\n\n"
                "def test_one():\n    os.kill(os.getpid(), signal.SIGKILL)\n",
            )
            self._no_counts("fx-crash", ("fx/crash",), "-9")
        with self.subTest(row="no-pyproject"):
            support.put(
                self.root, "fx/crash/test_one.py", "def test_one():\n    assert True\n"
            )
            (self.root / "pyproject.toml").unlink()
            self._no_counts("fx-crash", ("fx/crash",), "4")
        (self.root / "pyproject.toml").write_text(
            (support.ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        shutil_conftest = (support.ROOT / "conftest.py").read_text(encoding="utf-8")
        (self.root / "conftest.py").write_text(shutil_conftest, encoding="utf-8")
        with self.subTest(row="missing-path"):
            status, out, _err = self._run(
                (support.fx_suite("fx-crash", "pytest", ".", ("fx/missing",)),)
            )
            visible = support.visible(out)
            self.assertEqual(status, 1, visible)
            self.assertIn("suite fx-crash: 0 passed, 0 failed, 0 skipped", visible)
            self.assertIn("FAIL no-tests: fx-crash: the suite ran no tests", visible)
        with self.subTest(row="pytest-exit"):
            support.put(
                self.root,
                "fx/exit1/test_one.py",
                "import pytest\n\n"
                "def test_one():\n    pytest.exit('stop', returncode=0)\n\n"
                "def test_two():\n    assert True\n",
            )
            support.put(
                self.root,
                "fx/exit2/test_one.py",
                "import pytest\n\n"
                "def test_one():\n    assert True\n\n"
                "def test_two():\n    pytest.exit('stop', returncode=0)\n\n"
                "def test_three():\n    assert True\n",
            )
            status, out, _err = self._run(
                (
                    support.fx_suite("fx-exit1", "pytest", ".", ("fx/exit1",)),
                    support.fx_suite("fx-exit2", "pytest", ".", ("fx/exit2",)),
                )
            )
            visible = support.visible(out)
            self.assertEqual(status, 1, visible)
            self.assertNotIn("RESULT: PASSED", visible)
            for name in ("fx-exit1", "fx-exit2"):
                self.assertIn(f"suite {name}: counts unavailable", visible)
                self.assertIn(
                    "FAIL no-counts: "
                    f"{name}: attribute tests is missing or smaller than "
                    "the number of testcase elements",
                    visible,
                )

    def test_garbage_result_is_a_failed_suite(self) -> None:
        original = (self.root / "conftest.py").read_text(encoding="utf-8")
        (self.root / "conftest.py").write_text(
            original
            + "\n"
            + "def pytest_unconfigure(config):\n"
            + "    path = getattr(config.option, 'xmlpath', None)\n"
            + "    if path:\n"
            + "        from pathlib import Path\n"
            + "        Path(path).write_text('garbage', encoding='utf-8')\n",
            encoding="utf-8",
        )
        support.put(
            self.root, "fx/garbage/test_one.py", "def test_one():\n    assert True\n"
        )
        status, out, _err = self._run(
            (support.fx_suite("fx-garbage", "pytest", ".", ("fx/garbage",)),)
        )
        visible = support.visible(out)
        self.assertEqual(status, 1, visible)
        self.assertIn("FAIL no-counts: fx-garbage: not well-formed XML", visible)

    def test_suite_that_cannot_start(self) -> None:
        status, out, err = self._run(
            (support.fx_suite("fx-nowhere", "pytest", "nowhere", ()),)
        )
        self.assertEqual(err, [])
        self.assertEqual(status, 1)
        self.assertEqual(
            out,
            [
                f"seed={support.FIXTURE_SEED}",
                "suite fx-nowhere: counts unavailable",
                "FAIL cannot-start: fx-nowhere: working folder nowhere does not exist",
                "total: 0 passed, 0 failed, 0 skipped in 1 suites, 1 with problems",
                "RESULT: FAILED",
            ],
        )

    def test_timeout_kills_the_process_group(self) -> None:
        pid_path = self.root / "fx" / "slow" / "pid.txt"
        support.put(
            self.root,
            "fx/slow/test_slow.py",
            "import os\nimport time\nfrom pathlib import Path\n\n"
            "def test_slow():\n"
            f"    Path({str(pid_path)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
            "    time.sleep(60)\n",
        )
        started = time.monotonic()
        status, out, _err = self._run(
            (support.fx_suite("fx-slow", "pytest", ".", ("fx/slow",), timeout=10),)
        )
        self.assertLess(
            time.monotonic() - started,
            40.0,
            "the timed-out child was not killed before its 60 s sleep ended",
        )
        self.assertEqual(status, 1, out)
        self.assertIn(
            "FAIL timeout: fx-slow: no result within 10 s; the process group was killed",
            support.visible(out),
        )
        pid = self._await_pid(pid_path, 20)
        self._await_dead(pid, 5)

    def test_hosted_web_checks_timeout_prints_the_selected_limit(self) -> None:
        suite = run_tests.Suite("web-checks", "pytest", "web", (), 1800)
        seen: list[int] = []

        def fake_launch(
            cmd: Sequence[str], cwd: Path, env: Mapping[str, str], timeout: int
        ) -> run_tests_exec.Launched:
            seen.append(timeout)
            return run_tests_exec.Launched(status=None, output="", timed_out=True)

        original = run_tests_exec.launch
        run_tests_exec.launch = fake_launch
        try:
            with patch.dict(
                os.environ,
                {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"},
                clear=True,
            ):
                status, out, _err = support.call(
                    ["--seed", support.FIXTURE_SEED],
                    (suite,),
                    self.root,
                    os.environ,
                )
        finally:
            run_tests_exec.launch = original
        self.assertEqual(seen, [3000])
        self.assertEqual(status, 1, out)
        self.assertIn(
            "FAIL timeout: web-checks: no result within 3000 s; "
            "the process group was killed",
            support.visible(out),
        )

    def test_unknown_kind_is_one_internal_error_line(self) -> None:
        suite = run_tests.Suite("fx-bogus", "bogus", ".", (), 5)
        status, out, _err = self._run((suite,))
        self.assertEqual(status, 1)
        visible = support.visible(out)
        index = visible.index("suite fx-bogus: counts unavailable")
        self.assertEqual(
            visible[index + 1],
            "FAIL internal-error: fx-bogus: ValueError: unknown suite kind: bogus",
        )
        self.assertFalse(any(line.startswith("--- output of ") for line in out))
        self.assertFalse(any(line.startswith("Traceback") for line in out))
        self.assertFalse(any(line.startswith("    File") for line in out))

    def test_unknown_kind_stops_before_any_child_environment(self) -> None:
        seen: list[str] = []
        original = run_tests_exec.child_env

        def spy(
            kind: str,
            parent: Mapping[str, str],
            seed: int,
            tmp: Path,
        ) -> dict[str, str]:
            seen.append(kind)
            return original(kind, parent, seed, tmp)

        run_tests_exec.child_env = spy
        try:
            status, out, _err = self._run(
                (run_tests.Suite("fx-bogus", "bogus", ".", (), 5),)
            )
        finally:
            run_tests_exec.child_env = original
        self.assertEqual(seen, [])
        self.assertEqual(status, 1)
        self.assertIn("unknown suite kind: bogus", "\n".join(out))

    def test_output_block_is_the_last_200_lines(self) -> None:
        prints = "\n".join(f"    print('N {index:04d}')" for index in range(1, 251))
        support.put(
            self.root,
            "fx/tail/test_tail.py",
            "def test_tail():\n" + prints + "\n    assert False\n",
        )
        status, out, _err = self._run(
            (support.fx_suite("fx-tail", "pytest", ".", ("fx/tail",)),)
        )
        self.assertEqual(status, 1, out)
        start = out.index("--- output of fx-tail (last 200 lines) ---")
        end = out.index("--- end of output of fx-tail ---")
        block = out[start + 1 : end]
        self.assertEqual(len(block), 200)
        self.assertNotIn("N 0001", block)
        self.assertTrue(block[-1].strip())

    def test_non_utf8_output_is_replaced(self) -> None:
        body = (
            "import sys\n\n"
            "def test_bytes(capsys):\n"
            "    with capsys.disabled():\n"
            "        sys.stdout.buffer.write(b'\\xff\\xfe raw\\n')\n"
            "        sys.stdout.buffer.flush()\n"
        )
        support.put(self.root, "fx/bytes/test_bytes.py", body + "    assert True\n")
        support.put(
            self.root,
            "fx/bytes-fail/test_bytes.py",
            body + "    assert False\n",
        )
        status, out, _err = self._run(
            (
                support.fx_suite("fx-bytes", "pytest", ".", ("fx/bytes",)),
                support.fx_suite("fx-bytes-fail", "pytest", ".", ("fx/bytes-fail",)),
            )
        )
        visible = support.visible(out)
        self.assertIn("suite fx-bytes: 1 passed, 0 failed, 0 skipped", visible)
        self.assertIn("FAIL tests-failed: fx-bytes-fail: 1 failed", visible)
        self.assertIn("\ufffd", "\n".join(out))
        self.assertFalse(
            any(line.startswith("FAIL internal-error:") for line in visible)
        )
        self.assertEqual(status, 1)

    def test_interrupt_kills_the_process_group(self) -> None:
        pid_path = self.root / "fx" / "intr" / "pid.txt"
        support.put(
            self.root,
            "fx/intr/test_intr.py",
            "import os\nimport time\nfrom pathlib import Path\n\n"
            "def test_intr():\n"
            f"    Path({str(pid_path)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
            "    time.sleep(60)\n",
        )
        suite = support.fx_suite("fx-intr", "pytest", ".", ("fx/intr",), timeout=30)

        def poke() -> None:
            deadline = time.time() + 20
            while time.time() < deadline:
                if pid_path.is_file():
                    time.sleep(0.2)
                    os.kill(os.getpid(), signal.SIGINT)
                    return
                time.sleep(0.05)
            raise AssertionError("pid file never appeared")

        worker = threading.Thread(target=poke)
        worker.start()
        try:
            status, out, _err = self._run((suite,))
        finally:
            worker.join(timeout=5)
        self.assertEqual(status, 1, out)
        self.assertIn("FAIL interrupted", out)
        self.assertFalse(any(line.startswith("Traceback") for line in out))
        pid = self._await_pid(pid_path, 2)
        self._await_dead(pid, 5)

    def _no_counts(self, name: str, args: tuple[str, ...], code: str) -> None:
        status, out, _err = self._run((support.fx_suite(name, "pytest", ".", args),))
        visible = support.visible(out)
        self.assertEqual(status, 1, visible)
        self.assertIn(f"suite {name}: counts unavailable", visible)
        self.assertIn(
            f"FAIL no-counts: {name}: exit status {code}; no result file was written",
            visible,
        )

    def _await_pid(self, path: Path, seconds: float) -> int:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if path.is_file() and path.read_text(encoding="utf-8").strip():
                return int(path.read_text(encoding="utf-8").strip())
            time.sleep(0.05)
        self.fail("pid file never appeared")
        return 0

    def _await_dead(self, pid: int, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)
        self.fail(f"process {pid} still exists")

    def _run(
        self, suites: tuple[run_tests.Suite, ...]
    ) -> tuple[int, list[str], list[str]]:
        return support.call(
            ["--seed", support.FIXTURE_SEED],
            suites,
            self.root,
            support.parent_env(),
        )
