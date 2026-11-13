"""Run the network-free Python and web test suites."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_tests_counts as counts
import run_tests_exec as runner_exec


class UsageError(Exception):
    """The command line is not `./eii test` with an optional seed."""


@dataclass(frozen=True)
class Suite:
    """One row of the suite table."""

    name: str
    kind: str
    cwd: str
    args: tuple[str, ...]
    timeout: int


@dataclass(frozen=True)
class SuiteResult:
    """Counts, failure lines and the optional output block of one suite."""

    name: str
    counts: counts.Counts | None
    fail_lines: tuple[str, ...]
    output_block: tuple[str, ...]


SUITES: tuple[Suite, ...] = (
    Suite("python-guards", "pytest", ".", ("scripts/tests",), 3600),
    Suite("python-core", "pytest", ".", ("core/tests",), 600),
    Suite("python-custodian", "pytest", ".", ("custodian/tests",), 600),
    Suite("python-product", "pytest", ".", ("product/tests",), 600),
    Suite(
        "web-checks",
        "node",
        "web",
        ("scripts/tests/*.node-test.mjs", "spikes/glyphs/tests/*.node-test.mjs"),
        1800,
    ),
    Suite("web-unit", "vitest", "web", (), 600),
)

ROOT = Path(__file__).resolve().parents[1]
_SEED_MIN = 1000000000
_SEED_MAX = 4294967295
_SEED_DETAIL = "seed must be ten decimal digits from 1000000000 to 4294967295"


def parse_arguments(argv: Sequence[str]) -> int | None:
    """Read an optional seed. Raise UsageError at the first fault."""
    seed: int | None = None
    index = 0
    while index < len(argv):
        word = argv[index]
        if word != "--seed":
            raise UsageError(f'unknown flag or argument "{word}"')
        if seed is not None:
            raise UsageError("--seed given twice")
        if index + 1 >= len(argv):
            raise UsageError("--seed needs a value")
        value = argv[index + 1]
        index += 2
        if len(value) != 10 or not value.isascii() or not value.isdigit():
            raise UsageError(_SEED_DETAIL)
        number = int(value)
        if number < _SEED_MIN or number > _SEED_MAX:
            raise UsageError(_SEED_DETAIL)
        seed = number
    return seed


def run_suite(
    suite: Suite,
    seed: int,
    root: Path,
    parent: Mapping[str, str],
    secrets: Mapping[str, str],
) -> SuiteResult:
    """Run one suite and return its counts and failure lines."""
    if suite.kind not in runner_exec.KINDS:
        raise ValueError(f"unknown suite kind: {suite.kind}")
    with tempfile.TemporaryDirectory(prefix="eii-suite-") as raw:
        tmp = Path(raw)
        try:
            env = runner_exec.child_env(suite.kind, parent, seed, tmp)
            cmd = runner_exec.build_command(suite, root, env, tmp, seed)
        except runner_exec.StartError as error:
            return SuiteResult(
                suite.name,
                None,
                (f"FAIL cannot-start: {suite.name}: {error}",),
                (),
            )
        try:
            launched = runner_exec.launch(cmd, root / suite.cwd, env, suite.timeout)
        except runner_exec.StartError as error:
            return SuiteResult(
                suite.name,
                None,
                (f"FAIL cannot-start: {suite.name}: {error}",),
                (),
            )
        redacted, found = runner_exec.redact(launched.output, secrets)
        found_in_skips: set[str] = set()

        def scrub(text: str) -> str:
            cleaned, names = runner_exec.redact(text, secrets)
            found_in_skips.update(names)
            return cleaned

        fail_lines: list[str] = []
        parsed: counts.Counts | None = None
        if launched.timed_out:
            fail_lines.append(
                f"FAIL timeout: {suite.name}: no result within {suite.timeout} s; "
                "the process group was killed"
            )
        else:
            result_path = tmp / runner_exec.RESULT_FILES[suite.kind]
            try:
                payload = result_path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                fail_lines.append(
                    f"FAIL no-counts: {suite.name}: exit status {launched.status}; "
                    "no result file was written"
                )
            else:
                parser = {
                    "pytest": counts.parse_junit,
                    "node": counts.parse_node_records,
                    "vitest": counts.parse_vitest_json,
                }[suite.kind]
                try:
                    parsed = parser(payload)
                except counts.ParseError as error:
                    fail_lines.append(f"FAIL no-counts: {suite.name}: {error}")
                else:
                    fail_lines.extend(
                        counts.judge(suite.name, parsed, launched.status or 0, scrub)
                    )
        for name in sorted(set(found) | found_in_skips):
            fail_lines.append(
                f"FAIL secret-in-output: {suite.name}: "
                f"the output contained the value of {name}"
            )
        lines = runner_exec.tail(redacted)
        if fail_lines and lines:
            header = (
                f"--- output of {suite.name} "
                f"(last {runner_exec.OUTPUT_TAIL_LINES} lines) ---"
            )
            footer = f"--- end of output of {suite.name} ---"
            block = (header, *lines, footer)
        else:
            block = ()
        return SuiteResult(suite.name, parsed, tuple(fail_lines), block)


def main(
    argv: Sequence[str],
    *,
    suites: Sequence[Suite] = SUITES,
    root: Path = ROOT,
    environ: Mapping[str, str] | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
    now: Callable[[], float] = time.time,
) -> int:
    """Print one run and return 0, 1 or 2."""
    stdout = sys.stdout if out is None else out
    stderr = sys.stderr if err is None else err
    try:
        return _main(argv, suites, root, environ, stdout, stderr, now)
    except KeyboardInterrupt:
        stdout.write("FAIL interrupted\n")
        stdout.flush()
        return 1


def _main(
    argv: Sequence[str],
    suites: Sequence[Suite],
    root: Path,
    environ: Mapping[str, str] | None,
    stdout: TextIO,
    stderr: TextIO,
    now: Callable[[], float],
) -> int:
    try:
        parsed_seed = parse_arguments(argv)
    except UsageError as error:
        stderr.write(f"eii: usage error: {error}. Usage: ./eii test [--seed N]\n")
        return 2
    seed = parsed_seed if parsed_seed is not None else int(now())
    stdout.write(f"seed={seed}\n")
    stdout.flush()
    parent = dict(os.environ if environ is None else environ)
    secrets = {
        name: value
        for name, value in parent.items()
        if runner_exec.is_secret_name(name)
        and len(value) >= runner_exec.SECRET_MIN_LENGTH
    }
    results: list[SuiteResult] = []
    for suite in suites:
        try:
            result = run_suite(suite, seed, root, parent, secrets)
        except Exception as error:
            result = _internal(suite.name, error)
        results.append(result)
        _print_suite(stdout, result)
    passed = sum(item.counts.passed for item in results if item.counts is not None)
    failed = sum(item.counts.failed for item in results if item.counts is not None)
    skipped = sum(item.counts.skipped for item in results if item.counts is not None)
    problems = sum(1 for item in results if item.fail_lines)
    stdout.write(
        f"total: {passed} passed, {failed} failed, {skipped} skipped "
        f"in {len(results)} suites, {problems} with problems\n"
    )
    stdout.write("RESULT: FAILED\n" if problems else "RESULT: PASSED\n")
    stdout.flush()
    return 1 if problems else 0


def _internal(name: str, error: Exception) -> SuiteResult:
    message = str(error)
    first = message.splitlines()[0] if message.strip() else ""
    detail = f": {first}" if first else ""
    line = f"FAIL internal-error: {name}: {type(error).__name__}{detail}"
    return SuiteResult(name, None, (line,), ())


def _print_suite(stdout: TextIO, result: SuiteResult) -> None:
    if result.counts is None:
        stdout.write(f"suite {result.name}: counts unavailable\n")
    else:
        stdout.write(
            f"suite {result.name}: {result.counts.passed} passed, "
            f"{result.counts.failed} failed, {result.counts.skipped} skipped\n"
        )
    stdout.flush()
    for line in result.fail_lines:
        stdout.write(f"{line}\n")
        stdout.flush()
    for line in result.output_block:
        stdout.write(f"{line}\n")
        stdout.flush()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
