"""Judge a gitleaks scan of the full history of the current branch."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

import hooks_gitleaks as wrapper

ROOT = Path(__file__).resolve().parents[1]
LOG_OPTS = "--log-opts=--full-history HEAD"
SCAN_ARGS = (
    "git",
    "--redact",
    "--verbose",
    "--no-banner",
    "--no-color",
    "--exit-code",
    "2",
    "--ignore-gitleaks-allow",
    "--config",
    wrapper.CONFIG,
    LOG_OPTS,
)
# S0-T05 evidence command with two dummy probe values in the environment.
KNOWN_LINES: tuple[tuple[str, str, str], ...] = (
    (
        "PROGRESS.md",
        "generic-api-key",
        "a194c613ce842796bbb78c5e5311c561e470fe579dfcb63735917e4d945f99f7",
    ),
)
SCAN_TIMEOUT_SECONDS = 600
GIT_TIMEOUT_SECONDS = 120
COMMIT_FORMAT = "--format=%x00commit"
COMMIT_MARK = "\x00commit"
TEXT_ADDED_RE = re.compile(r"(?m)^[1-9][0-9]*\t")
SCANNED_RE = re.compile(r"(?m)^\S+ INF ([0-9]+) commits scanned")
ERROR_RE = re.compile(r"(?m)^\S+ (?:ERR|FTL)\b.*$")
FINDINGS_RE = re.compile(r"(?m)^\S+ [A-Z]{3} leaks found: [1-9][0-9]*")
LEAKS_COUNT_RE = re.compile(r"(?m)^\S+ \w+ leaks found: (\d+)\s*$")
USAGE = "usage: ci_history_scan.py scan"


def run_git(root: Path, environ: Mapping[str, str], *args: str) -> str:
    """Run one read-only git command and return standard output."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env=dict(environ),
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise wrapper.Failure(
            f"git {args[0]} did not run ({type(error).__name__})"
        ) from error
    if done.returncode != 0:
        raise wrapper.Failure(f"git {args[0]} failed (exit {done.returncode})")
    return done.stdout.removesuffix("\n")


def read_blob(root: Path, environ: Mapping[str, str], commit: str, file: str) -> bytes:
    """Read one git blob without translating line endings."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{file}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=dict(environ),
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise wrapper.Failure(
            f"git show did not run ({type(error).__name__})"
        ) from error
    if done.returncode != 0:
        raise wrapper.Failure(f"git show failed (exit {done.returncode})")
    return done.stdout


def commit_bounds(root: Path, environ: Mapping[str, str]) -> tuple[int, int]:
    """Return the minimum listed-commit count and total reachable commits."""
    if run_git(root, environ, "rev-parse", "--is-shallow-repository") != "false":
        raise wrapper.Failure(
            "the checkout is shallow or not a repository; fetch the full history"
        )
    total = int(run_git(root, environ, "rev-list", "--count", "HEAD"))
    if total < 1:
        raise wrapper.Failure("HEAD has no commit")
    listing = run_git(
        root,
        environ,
        "log",
        "--no-merges",
        "-M",
        "--diff-filter=AM",
        "--numstat",
        COMMIT_FORMAT,
        "HEAD",
    )
    lower = sum(
        1 for block in listing.split(COMMIT_MARK)[1:] if TEXT_ADDED_RE.search(block)
    )
    return lower, total


def line_digest(text: str) -> str:
    """Return the UTF-8 SHA-256 of one line with no line ending."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def known_ledger_entry(file: str, rule: str, digest: str) -> bool:
    """Return whether the table lists this file, rule and line digest."""
    return any(
        listed_file == file and listed_rule == rule and listed_digest == digest
        for listed_file, listed_rule, listed_digest in KNOWN_LINES
    )


def leak_count_from_log(output: str) -> int | None:
    """Return the finding count from the scanner log when exactly one line names it."""
    matches = LEAKS_COUNT_RE.findall(output)
    if len(matches) != 1:
        return None
    return int(matches[0])


def read_report(path: Path) -> list[object] | None:
    """Read a JSON report list when the path exists and parses."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list):
        return None
    return payload


def finding_is_known(
    root: Path,
    environ: Mapping[str, str],
    entry: object,
) -> bool:
    """Return whether one report entry matches a known ledger line."""
    if not isinstance(entry, dict):
        return False
    for key in ("File", "RuleID", "Commit", "StartLine", "EndLine"):
        if key not in entry:
            return False
    start = entry["StartLine"]
    end = entry["EndLine"]
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    if start != end:
        return False
    file = entry["File"]
    rule = entry["RuleID"]
    commit = entry["Commit"]
    if (
        not isinstance(file, str)
        or not isinstance(rule, str)
        or not isinstance(commit, str)
    ):
        return False
    try:
        blob = read_blob(root, environ, commit, file)
    except wrapper.Failure:
        return False
    lines = blob.split(b"\n")
    if start < 1 or start > len(lines):
        return False
    try:
        line = lines[start - 1].decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    return known_ledger_entry(file, rule, line_digest(line))


def classify_findings(
    root: Path,
    environ: Mapping[str, str],
    output: str,
    report_path: Path | None,
) -> tuple[bool, str | None]:
    """Return whether every finding is known and the left-out summary when it is."""
    expected = leak_count_from_log(output)
    if expected is None or report_path is None:
        return False, None
    report = read_report(report_path)
    if report is None or len(report) == 0:
        return False, None
    if len(report) != expected:
        return False, None
    known_positions: set[tuple[str, int]] = set()
    for entry in report:
        if not finding_is_known(root, environ, entry):
            return False, None
        if isinstance(entry, dict) and isinstance(entry.get("StartLine"), int):
            file = entry.get("File")
            if isinstance(file, str):
                known_positions.add((file, entry["StartLine"]))
    count = len(report)
    lines = len(known_positions)
    summary = (
        f"history scan: {count} finding(s) on known ledger lines left out "
        f"({lines} line(s))"
    )
    return True, summary


def judge(
    status: int,
    output: str,
    lower: int,
    total: int,
    *,
    root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    report_path: Path | None = None,
) -> tuple[list[str], str | None]:
    """Return one problem per failed scanner-result rule and an optional left-out line."""
    problems: list[str] = []
    left_out: str | None = None
    if status == wrapper.FINDING_STATUS:
        if root is not None and environ is not None:
            all_known, left_out = classify_findings(root, environ, output, report_path)
            if not all_known:
                problems.append("FAIL secret: the scanner reported findings")
        else:
            problems.append("FAIL secret: the scanner reported findings")
    elif status != 0:
        problems.append(f"FAIL scanner: exited with status {status}")
    if ERROR_RE.search(output):
        problems.append("FAIL scanner: an error was logged")
    if status == 0 and FINDINGS_RE.search(output):
        problems.append("FAIL scanner: findings were printed with exit status zero")
    counts = [int(value) for value in SCANNED_RE.findall(output)]
    if len(counts) != 1:
        problems.append(
            f'FAIL count: expected one "commits scanned" line, found {len(counts)}'
        )
    elif counts[0] == 0:
        problems.append("FAIL count: zero commits scanned on a non-empty range")
    elif counts[0] < lower:
        problems.append(
            f"FAIL count: {counts[0]} commits scanned, fewer than the required {lower}"
        )
    elif counts[0] > total:
        problems.append(
            f"FAIL count: {counts[0]} commits scanned, more than the range total {total}"
        )
    return problems, left_out


def scan(
    root: Path,
    environ: Mapping[str, str],
    out: TextIO,
    err: TextIO,
) -> int:
    """Run and judge the full-history scan."""
    try:
        binary = wrapper.verify_binary(root, wrapper.read_version(root))
        lower, total = commit_bounds(root, environ)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            scan_args = (
                *SCAN_ARGS,
                "--report-format",
                "json",
                "--report-path",
                str(report),
            )
            done = subprocess.run(
                [str(binary), *scan_args],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=dict(environ),
                timeout=SCAN_TIMEOUT_SECONDS,
                check=False,
            )
            out.write(done.stdout)
            problems, left_out = judge(
                done.returncode,
                done.stdout,
                lower,
                total,
                root=root,
                environ=environ,
                report_path=report if report.is_file() else None,
            )
    except (wrapper.Failure, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL history-scan: {error}", file=err)
        return 1
    if left_out is not None:
        print(left_out, file=out)
    for problem in problems:
        print(problem, file=err)
    result = "FAILED" if problems else "PASSED"
    print(
        f"history scan: range HEAD, {total} commits, "
        f"at least {lower} to list, RESULT: {result}",
        file=out,
    )
    return 1 if problems else 0


def main(argv: Sequence[str]) -> int:
    """Run the `scan` command."""
    if list(argv) != ["scan"]:
        print(USAGE, file=sys.stderr)
        return 2
    return scan(ROOT, os.environ, sys.stdout, sys.stderr)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
