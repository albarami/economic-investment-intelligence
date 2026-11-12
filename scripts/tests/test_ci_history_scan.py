"""History-scan tests for S0-T07."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ci_support as support

import ci_history_scan as history
import ci_plant_cases as plant_cases
import hooks_gitleaks


class HistoryScan(unittest.TestCase):
    def test_missing_scanner_fails_and_is_not_skipped(self) -> None:
        home, _env = support.temp_home(self)
        shutil.copy2(support.ROOT / "pins.toml", home / "pins.toml")
        probe = home / "history"
        probe.mkdir(parents=True)
        with patch.object(support, "ROOT", home):
            try:
                support.place_scanner(probe)
            except unittest.SkipTest:
                self.fail("a missing scanner skipped the test instead of failing it")
            except AssertionError as error:
                self.assertIn(
                    "uv run --locked python scripts/hooks_gitleaks.py fetch",
                    str(error),
                )
            else:
                self.fail("a missing scanner was accepted")

    def test_progress_has_known_ledger_line(self) -> None:
        line = support.known_ledger_line()
        digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
        self.assertEqual(digest, history.KNOWN_LINES[0][2])

    def test_clean_result_passes(self) -> None:
        problems, _left = history.judge(
            0, support.scanner_output(status=0, commits=2), lower=1, total=2
        )
        self.assertEqual(problems, [])

    def test_one_plant_per_rule(self) -> None:
        lower, total = 2, 3
        plants = [
            (
                hooks_gitleaks.FINDING_STATUS,
                support.scanner_output(status=hooks_gitleaks.FINDING_STATUS, commits=2),
                "FAIL secret",
            ),
            (
                1,
                support.scanner_output(status=1, commits=2),
                "FAIL scanner: exited with status 1",
            ),
            (
                0,
                support.scanner_output(
                    status=0, commits=2, err_line="gitleaks ERR broken"
                ),
                "FAIL scanner: an error was logged",
            ),
            (
                0,
                support.scanner_output(
                    status=0,
                    commits=2,
                    finding_line="gitleaks WRN leaks found: 1",
                ),
                "findings were printed with exit status zero",
            ),
            (
                0,
                support.scanner_output(status=0, commits=None),
                'expected one "commits scanned"',
            ),
            (
                0,
                support.scanner_output(status=0, commits=0),
                "zero commits scanned",
            ),
            (
                0,
                support.scanner_output(status=0, commits=1),
                "fewer than the required",
            ),
        ]
        for status, output, needle in plants:
            with self.subTest(status=status, needle=needle):
                problems, _left = history.judge(status, output, lower, total)
                self.assertTrue(problems)
                hit = [item for item in problems if needle in item]
                self.assertEqual(len(hit), 1, problems)
        high, _left = history.judge(
            0, support.scanner_output(status=0, commits=total + 1), lower, total
        )
        self.assertTrue(any("more than the range total" in item for item in high))

    def test_full_history_arguments(self) -> None:
        joined = " ".join(history.SCAN_ARGS)
        self.assertIn(history.LOG_OPTS, joined)
        self.assertIn("--full-history", joined)
        self.assertIn(hooks_gitleaks.CONFIG, joined)

    def test_shallow_checkout_refusal(self) -> None:
        home, env = support.temp_home(self)
        repo = support.history_repo(home, env)
        with patch.object(
            history,
            "run_git",
            side_effect=lambda _root, _env, *args: (
                "true" if args[:2] == ("rev-parse", "--is-shallow-repository") else "1"
            ),
        ):
            with self.assertRaises(hooks_gitleaks.Failure) as caught:
                history.commit_bounds(repo, env)
        self.assertIn("shallow", str(caught.exception))

    def test_real_scratch_history_with_clean_commits(self) -> None:
        home, env = support.temp_home(self)
        repo = support.history_repo(home, env)
        support.place_scanner(repo)
        out = io.StringIO()
        err = io.StringIO()
        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 0, err.getvalue())
        self.assertIn("RESULT: PASSED", out.getvalue())

    def test_runtime_token_gives_finding(self) -> None:
        home, env = support.temp_home(self)
        repo = support.history_repo(home, env)
        support.place_scanner(repo)
        support.token_in_history(repo, env)
        out = io.StringIO()
        err = io.StringIO()
        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 1)
        self.assertIn("FAIL secret", err.getvalue())

    def test_bad_revision_that_exits_zero_still_fails(self) -> None:
        home, env = support.temp_home(self)
        repo = support.history_repo(home, env)
        binary = home / "gitleaks"
        binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        binary.chmod(0o755)
        fake = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=support.scanner_output(status=0, commits=None),
        )
        with patch.object(hooks_gitleaks, "verify_binary", return_value=binary):
            with patch.object(hooks_gitleaks, "read_version", return_value="8.30.1"):
                with patch.object(history, "commit_bounds", return_value=(1, 2)):
                    with patch.object(subprocess, "run", return_value=fake):
                        out = io.StringIO()
                        err = io.StringIO()
                        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 1)
        self.assertIn('expected one "commits scanned"', err.getvalue())

    def test_usage(self) -> None:
        status, _stdout, stderr = support.run_module("ci_history_scan.py", ["wrong"])
        self.assertEqual(status, 2)
        self.assertIn("usage: ci_history_scan.py scan", stderr)

    def test_known_ledger_line_is_left_out(self) -> None:
        home, env = support.temp_home(self)
        line = support.known_ledger_line()
        repo = support.history_with_ledger_line(home, env, line)
        support.place_scanner(repo)
        out = io.StringIO()
        err = io.StringIO()
        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 0, err.getvalue())
        left = "history scan: 2 finding(s) on known ledger lines left out (1 line(s))"
        self.assertIn(left, out.getvalue())
        self.assertIn("RESULT: PASSED", out.getvalue())
        self.assertNotIn("FAIL secret", err.getvalue())

    def test_known_text_after_a_carriage_return_is_not_left_out(self) -> None:
        home, env = support.temp_home(self)
        repo = support.history_repo(home, env)
        line = support.known_ledger_line()
        (repo / "PROGRESS.md").write_bytes(
            ("x\r" + line + "\nsecond line\n").encode("utf-8")
        )
        support.git(env, repo, "add", "PROGRESS.md")
        support.git(env, repo, "commit", "-q", "-m", "chore: carriage return")
        commit = history.run_git(repo, env, "rev-parse", "HEAD")
        for number in (2, 1):
            with self.subTest(number=number):
                entry = {
                    "File": "PROGRESS.md",
                    "RuleID": "generic-api-key",
                    "Commit": commit,
                    "StartLine": number,
                    "EndLine": number,
                }
                self.assertFalse(history.finding_is_known(repo, env, entry))

    def test_known_line_in_other_file_fails(self) -> None:
        home, env = support.temp_home(self)
        line = support.known_ledger_line()
        repo = support.history_repo(home, env)
        other = repo / "ledger_copy.txt"
        other.write_text(line + "\n", encoding="utf-8")
        support.git(env, repo, "add", "ledger_copy.txt")
        support.git(env, repo, "commit", "-q", "-m", "chore: other file")
        support.place_scanner(repo)
        out = io.StringIO()
        err = io.StringIO()
        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 1)
        self.assertIn("FAIL secret", err.getvalue())

    def test_shaped_line_in_progress_fails(self) -> None:
        home, env = support.temp_home(self)
        repo = support.history_repo(home, env)
        probe = support.shaped_probe_line()
        (repo / "PROGRESS.md").write_text(probe + "\n", encoding="utf-8")
        support.git(env, repo, "add", "PROGRESS.md")
        support.git(env, repo, "commit", "-q", "-m", "chore: probe")
        support.place_scanner(repo)
        out = io.StringIO()
        err = io.StringIO()
        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 1)
        self.assertIn("FAIL secret", err.getvalue())

    def test_known_line_with_unknown_finding_fails(self) -> None:
        home, env = support.temp_home(self)
        line = support.known_ledger_line()
        repo = support.history_with_ledger_line(home, env, line)
        plant_cases.plant_token_history(repo, env)
        support.place_scanner(repo)
        out = io.StringIO()
        err = io.StringIO()
        status = history.scan(repo, env, out, err)
        self.assertEqual(status, 1)
        self.assertIn("FAIL secret", err.getvalue())

    def test_missing_report_with_finding_status_fails(self) -> None:
        output = support.scanner_output(
            status=hooks_gitleaks.FINDING_STATUS,
            commits=2,
            leak_count=1,
        )
        problems, left = history.judge(
            hooks_gitleaks.FINDING_STATUS,
            output,
            1,
            2,
            root=Path("/"),
            environ=os.environ,
            report_path=Path("/no/such/report.json"),
        )
        self.assertIn("FAIL secret", "\n".join(problems))
        self.assertIsNone(left)

    def test_empty_report_with_finding_status_fails(self) -> None:
        home, env = support.temp_home(self)
        report = home / "empty.json"
        report.write_text("[]\n", encoding="utf-8")
        output = support.scanner_output(
            status=hooks_gitleaks.FINDING_STATUS,
            commits=2,
            leak_count=1,
        )
        problems, left = history.judge(
            hooks_gitleaks.FINDING_STATUS,
            output,
            1,
            2,
            root=home,
            environ=env,
            report_path=report,
        )
        self.assertIn("FAIL secret", "\n".join(problems))
        self.assertIsNone(left)
