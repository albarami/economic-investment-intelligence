"""Hosted-runner steps for the sandbox proof (TST-62, task S0-T11).

Commands: ``facts`` (report of the runner; fails when bubblewrap or a package
is missing), ``install-profile`` (GitHub-hosted runner only), ``prove`` (run the
sandbox-marked tests and judge each required test case by name).

The restriction of unprivileged user namespaces is handled only by the AppArmor
profile of the bubblewrap binary. This module never writes a kernel setting and
never starts another sandbox tool. Installation, loading and namespace probes
are judged exactly (exit status, standard error, standard output). Profile file
sizes and hashes, the status listing and the label are printed for the record
only. The judges of the test result are in ``ci_junit``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import ci_junit as junit
import sandbox_check
import sandbox_profiles as tables

ROOT = Path(__file__).resolve().parents[1]
SYSCTL = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
APPARMOR_ENABLED = Path("/sys/module/apparmor/parameters/enabled")
OS_RELEASE = Path("/etc/os-release")
PROFILE_SOURCE = Path("/usr/share/apparmor/extra-profiles/bwrap-userns-restrict")
PROFILE_TARGET = Path("/etc/apparmor.d/bwrap-userns-restrict")
PROBE_ARGV = [
    tables.BWRAP,
    "--unshare-user",
    "--unshare-net",
    "--ro-bind",
    "/",
    "/",
    "true",
]
# The AppArmor attribute file of the reading process (libapparmor's interface
# that holds even when several security modules are stacked).
LABEL_FILE = "/proc/self/attr/apparmor/current"
LABEL_ARGV = [*PROBE_ARGV[:-1], "/usr/bin/cat", LABEL_FILE]
INSTALL_ARGV = [
    "sudo",
    "install",
    "-m",
    "0644",
    str(PROFILE_SOURCE),
    str(PROFILE_TARGET),
]
PARSER_ARGV = ["sudo", "apparmor_parser", "-r", str(PROFILE_TARGET)]
LISTING_ARGV = ["sudo", "aa-status", "--json"]
PACKAGES_ARGV = [
    "dpkg-query",
    "-W",
    "-f=${Package} ${Version}\n",
    "apparmor",
    "apparmor-profiles",
    "bubblewrap",
]
# dpkg-query prints the packages sorted by name, one line each.
PACKAGE_LINES = tuple(
    re.compile(re.escape(name) + r" \S+")
    for name in ("apparmor", "apparmor-profiles", "bubblewrap")
)
HOSTED_RUNNER = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}
COMMAND_TIMEOUT = 120.0
PROVE_TIMEOUT = 1500.0
EXIT_USAGE = 2
OUTPUT_TAIL = 4000


@dataclass(frozen=True)
class CommandResult:
    """What a command printed and how it ended."""

    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str]], CommandResult]
ReadText = Callable[[Path], str]
ReadBytes = Callable[[Path], bytes]


def run_command(argv: Sequence[str]) -> CommandResult:
    """Run a command with a small environment and return what it printed.

    Args:
        argv: The program and its arguments.

    Returns:
        The exit status (127 when the program does not exist, 124 on a time-out)
        and the two outputs.
    """
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C"}
    try:
        done = subprocess.run(
            list(argv),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(127, "", f"{argv[0]}: not found\n")
    except subprocess.TimeoutExpired:
        return CommandResult(
            124, "", f"{argv[0]}: timed out after {COMMAND_TIMEOUT:g} s\n"
        )
    return CommandResult(done.returncode, done.stdout, done.stderr)


def judge(
    what: str, result: CommandResult, expected: Sequence[sandbox_check.Expected]
) -> list[str]:
    """Judge a command exactly: status 0, empty standard error, the lines given."""
    return sandbox_check.output_problems(
        what, result.returncode, result.stdout, result.stderr, expected
    )


def report(problems: Sequence[str], out: TextIO) -> int:
    """Print one ``FAIL`` line per problem and return the exit status."""
    for problem in problems:
        print(f"FAIL {problem}", file=out)
    return 1 if problems else 0


def restriction_value(read_text: ReadText) -> str:
    """Read the AppArmor restriction setting without changing it.

    Returns:
        The trimmed text of the setting, or ``absent`` when the file does not exist.
    """
    try:
        return read_text(SYSCTL).strip()
    except FileNotFoundError:
        return "absent"


def _try(read_text: ReadText, path: Path) -> str:
    """Read a file, or return an empty string when it does not exist."""
    try:
        return read_text(path)
    except FileNotFoundError:
        return ""


def facts(runner: Runner, read_text: ReadText, out: TextIO) -> int:
    """Print what the runner is, changing nothing.

    Args:
        runner: Runs a command.
        read_text: Reads a file as text; raises FileNotFoundError when absent.
        out: Where the lines go.

    Returns:
        0 when ``bwrap --version`` and ``dpkg-query`` printed exactly the
        expected lines, 1 otherwise (a missing package or bubblewrap).
    """
    name = "unknown"
    for line in _try(read_text, OS_RELEASE).splitlines():
        if line.startswith("PRETTY_NAME="):
            name = line.split("=", 1)[1].strip('"')
    print(f"os: {name}", file=out)
    print(f"kernel: {platform.release()}", file=out)
    print(f"restriction setting: {restriction_value(read_text)}", file=out)
    print(
        f"apparmor enabled: {_try(read_text, APPARMOR_ENABLED).strip() or 'unknown'}",
        file=out,
    )
    version = runner([tables.BWRAP, "--version"])
    print(f"bubblewrap: {version.stdout.strip()}", file=out)
    packages = runner(PACKAGES_ARGV)
    for line in packages.stdout.splitlines():
        print(f"package: {line}", file=out)
    problems = judge("bwrap --version", version, [sandbox_check.VERSION_LINE])
    problems += judge("dpkg-query", packages, PACKAGE_LINES)
    return report(problems, out)


def _read(read_bytes: ReadBytes, path: Path) -> bytes | None:
    """Read a file's bytes, or None when it does not exist."""
    try:
        return read_bytes(path)
    except FileNotFoundError:
        return None


def _profile_record(path: Path, data: bytes, out: TextIO) -> None:
    """Print the file size and hash without comparing them with a pin."""
    print(
        f"profile file {path}: {len(data)} bytes, SHA-256 "
        f"{hashlib.sha256(data).hexdigest()}",
        file=out,
    )


def _place_and_load(runner: Runner, read_bytes: ReadBytes, out: TextIO) -> list[str]:
    """Install the distribution profile when absent, record its bytes, and load."""
    source = _read(read_bytes, PROFILE_SOURCE)
    if source is None:
        return [f"profile file not found: {PROFILE_SOURCE}"]
    _profile_record(PROFILE_SOURCE, source, out)
    target = _read(read_bytes, PROFILE_TARGET)
    if target is None:
        problems = judge("install", runner(INSTALL_ARGV), [])
        if problems:
            return problems
        target = _read(read_bytes, PROFILE_TARGET)
        if target is None:
            return [f"profile file not found after the install: {PROFILE_TARGET}"]
    # An existing file that differs is never replaced.
    _profile_record(PROFILE_TARGET, target, out)
    return judge("apparmor_parser -r", runner(PARSER_ARGV), [])


def _record_state(runner: Runner, out: TextIO) -> None:
    """Print raw listing and label results; neither decides the proof."""
    for name, argv in (("aa-status --json", LISTING_ARGV), ("label", LABEL_ARGV)):
        result = runner(argv)
        print(f"{name} raw: exit {result.returncode}", file=out)
        print(f"{name} raw stdout: {result.stdout!r}", file=out)
        print(f"{name} raw stderr: {result.stderr!r}", file=out)


def install_profile(
    environ: Mapping[str, str],
    runner: Runner,
    read_bytes: ReadBytes,
    read_text: ReadText,
    out: TextIO,
    err: TextIO,
) -> int:
    """Make namespace creation work for bubblewrap, or fail.

    Only on a GitHub-hosted runner. A passing first probe installs nothing.
    When it fails and the restriction reads 1, the distribution profile must
    exist. Its size and hash are recorded, it is installed only when absent,
    and the target is recorded and loaded. The same probe must then pass.
    Status and label commands print records only. No kernel setting is written.

    Args:
        environ: The process environment.
        runner: Runs a command.
        read_bytes: Reads a file as bytes; raises FileNotFoundError when absent.
        read_text: Reads a file as text.
        out: Where the report goes.
        err: Where the refusal goes.

    Returns:
        0 when namespace creation works, 1 when setup or the probe fails,
        2 when this is not a
        GitHub-hosted runner (nothing is run then).
    """
    if any(environ.get(key) != value for key, value in HOSTED_RUNNER.items()):
        print(
            "ci_sandbox: install-profile runs only on a GitHub-hosted runner; nothing was changed",
            file=err,
        )
        return EXIT_USAGE
    value = restriction_value(read_text)
    print(f"restriction: {value}", file=out)
    before = runner(PROBE_ARGV)
    print(
        f"probe before: exit {before.returncode}, standard error {before.stderr!r}",
        file=out,
    )
    problems = judge("probe", before, [])
    if not problems:
        print("namespace creation works; nothing to install", file=out)
        return 0
    if value != "1":
        problems.append(
            f"namespace creation fails while the restriction reads {value}; this step handles only the AppArmor restriction"
        )
        return report(problems, out)
    problems = _place_and_load(runner, read_bytes, out)
    if problems:
        return report(problems, out)
    problems = judge("probe after", runner(PROBE_ARGV), [])
    if problems:
        return report(problems, out)
    _record_state(runner, out)
    print("namespace creation works after loading the per-binary profile", file=out)
    return 0


def pytest_environment(parent: Mapping[str, str], tmp: Path) -> dict[str, str]:
    """Build the environment of the pytest child from an empty dictionary."""
    env = {
        "LANG": "C",
        "NO_COLOR": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HYPOTHESIS_STORAGE_DIRECTORY": str(tmp / "hypothesis"),
    }
    if "PATH" in parent:
        env["PATH"] = parent["PATH"]
    return env


def prove(root: Path, parent: Mapping[str, str], out: TextIO) -> int:
    """Run the sandbox-marked tests and judge each required test case by name.

    Args:
        root: The repository root.
        parent: The process environment (only ``PATH`` is passed on).
        out: Where the report goes.

    Returns:
        0 when the run is proof, 1 otherwise.
    """
    print(sandbox_check.bubblewrap_version(), file=out)
    with tempfile.TemporaryDirectory() as tmp:
        result_file = Path(tmp) / "sandbox.xml"
        command = [
            sys.executable,
            "-P",
            "-s",
            "-m",
            "pytest",
            "-c",
            "pyproject.toml",
            "--rootdir",
            ".",
            "-m",
            "sandbox",
            "--junit-xml",
            str(result_file),
        ]
        try:
            done = subprocess.run(
                command,
                cwd=root,
                env=pytest_environment(parent, Path(tmp)),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=PROVE_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(f"FAIL sandbox-tests: timed out after {PROVE_TIMEOUT:g} s", file=out)
            print("RESULT: FAILED", file=out)
            return 1
        try:
            cases = junit.read_cases(result_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(done.stdout[-OUTPUT_TAIL:], file=out)
            print(f"FAIL sandbox-tests: no usable result file ({error})", file=out)
            print("RESULT: FAILED", file=out)
            return 1
    problems = junit.case_problems(cases, done.returncode)
    if done.stderr:
        problems.append(
            f"FAIL sandbox-tests: standard error is not empty: {done.stderr[-OUTPUT_TAIL:]!r}"
        )
    if problems:
        print(done.stdout[-OUTPUT_TAIL:], file=out)
    for owner, name, status in sorted(cases):
        print(f"case {status} {owner}::{name}", file=out)
    for line in problems:
        print(line, file=out)
    print("RESULT: FAILED" if problems else "RESULT: PASSED", file=out)
    return 1 if problems else 0


def main(argv: Sequence[str]) -> int:
    """Run one command.

    Args:
        argv: ``facts``, ``install-profile`` or ``prove``.

    Returns:
        The exit status of the command; 2 for a usage error.
    """
    if list(argv) == ["facts"]:
        return facts(
            run_command, lambda path: path.read_text(encoding="utf-8"), sys.stdout
        )
    if list(argv) == ["install-profile"]:
        return install_profile(
            os.environ,
            run_command,
            lambda path: path.read_bytes(),
            lambda path: path.read_text(encoding="utf-8"),
            sys.stdout,
            sys.stderr,
        )
    if list(argv) == ["prove"]:
        return prove(ROOT, os.environ, sys.stdout)
    print("ci_sandbox: usage: facts | install-profile | prove", file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
