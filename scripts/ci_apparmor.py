"""Judges of the AppArmor proof on the hosted runner (TST-62, task S0-T11).

Pure functions over bytes and text that ``ci_sandbox`` reads or receives from
the commands it runs; nothing here starts a program or reads a file, so every
failure can be planted with synthetic input. Three facts make the per-binary
profile "in force": the profile file is the pinned file of the distribution
package, ``aa-status --json`` lists both of its profiles in enforce mode, and a
program started by ``/usr/bin/bwrap`` carries the stacked label that only the
rule of profile ``bwrap`` gives it.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# The file usr/share/apparmor/extra-profiles/bwrap-userns-restrict of the noble
# package apparmor-profiles 4.0.1really4.0.1-0ubuntu0.24.04.9, read 2026-11-12.
PROFILE_PACKAGE = "apparmor-profiles 4.0.1really4.0.1-0ubuntu0.24.04.9"
PROFILE_SIZE = 1936
PROFILE_SHA256 = "11d39094f044f0cda0febb3ad517b830301da6b2ce929664af09ee9e4dd264f9"
# aa-status --json of AppArmor 4.0.1 prints one line: an object with the keys
# version ("2"), profiles (name -> mode) and processes.
STATUS_VERSION = "2"
PROFILE_NAMES = ("bwrap", "unpriv_bwrap")
ENFORCE = "enforce"
# A label line: profile names joined by //& (a stack), then " (<mode>)"; a
# label without a mode has no parenthesis. Names hold no space or parenthesis.
LABEL_LINE = re.compile(r"(?P<stack>[^ ()]+)(?: \((?P<mode>[a-z]+)\))?")
STACK_SEPARATOR = "//&"
# The rule "allow px /** -> bwrap//&unpriv_bwrap" of profile bwrap.
EXPECTED_STACK = ("bwrap", "unpriv_bwrap")


def profile_file_problems(what: str, data: bytes) -> list[str]:
    """Compare a profile file with the pinned file of the package.

    Args:
        what: The path, used in the problem text.
        data: The bytes of the file.

    Returns:
        One problem text when size or SHA-256 differ from the pin; else empty.
    """
    digest = hashlib.sha256(data).hexdigest()
    if len(data) == PROFILE_SIZE and digest == PROFILE_SHA256:
        return []
    return [
        f"{what} has {len(data)} bytes and SHA-256 {digest}; the pinned file of "
        f"{PROFILE_PACKAGE} has {PROFILE_SIZE} bytes and SHA-256 {PROFILE_SHA256}: "
        "a person reviews the new file and updates the pin"
    ]


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object, refusing a repeated key.

    Raises:
        ValueError: A key occurs twice.
    """
    found: dict[str, Any] = {}
    for key, value in pairs:
        if key in found:
            raise ValueError(f"repeated key {key}")
        found[key] = value
    return found


def _no_constant(name: str) -> Any:
    """Refuse the constants NaN, Infinity and -Infinity, which JSON does not have.

    Raises:
        ValueError: Always.
    """
    raise ValueError(f"constant {name} is not JSON")


def one_line(what: str, stdout: str) -> tuple[str | None, list[str]]:
    """Return the single line of an output, or a problem when there is not one.

    Returns:
        The line without its newline and no problem, or None and one problem.
    """
    lines = stdout.split("\n")
    if len(lines) != 2 or lines[1] != "":
        return None, [f"{what} did not print exactly one line: {stdout!r}"]
    if lines[0] != lines[0].strip():
        return None, [f"{what} line has leading or trailing white space: {stdout!r}"]
    return lines[0], []


def status_problems(stdout: str) -> list[str]:
    """Judge the output of ``aa-status --json``.

    Args:
        stdout: Its standard output.

    Returns:
        Problem texts; empty when the output is one JSON object of format
        ``STATUS_VERSION`` without a repeated key, whose ``profiles`` object
        lists each name of ``PROFILE_NAMES`` exactly, in enforce mode.
    """
    line, problems = one_line("aa-status --json", stdout)
    if line is None:
        return problems
    try:
        data = json.loads(
            line, object_pairs_hook=_unique_keys, parse_constant=_no_constant
        )
    except ValueError as error:
        return [f"aa-status --json printed no JSON object with unique keys ({error})"]
    if (
        not isinstance(data, dict)
        or data.get("version") != STATUS_VERSION
        or not isinstance(data.get("profiles"), dict)
    ):
        return [
            f"aa-status --json is not format version {STATUS_VERSION} with a profiles object"
        ]
    profiles = data["profiles"]
    return [
        f"profile {name} is {profiles.get(name, 'not loaded')!s}, expected {ENFORCE}"
        for name in PROFILE_NAMES
        if profiles.get(name) != ENFORCE
    ]


def parse_label(line: str) -> tuple[tuple[str, ...], str | None] | None:
    """Split a label line into its profile names and its mode.

    Returns:
        The names in printed order and the mode (None when the label has no
        mode), or None when the line does not follow the grammar.
    """
    match = LABEL_LINE.fullmatch(line)
    if match is None:
        return None
    names = tuple(match["stack"].split(STACK_SEPARATOR))
    if any(not name for name in names):
        return None
    return names, match["mode"]


def label_problems(stdout: str) -> list[str]:
    """Judge the label that a program started by ``/usr/bin/bwrap`` read for itself.

    Args:
        stdout: The output of ``cat /proc/self/attr/apparmor/current`` run by
            bubblewrap.

    Returns:
        Problem texts; empty when the one line is the stack ``EXPECTED_STACK``
        in enforce mode.
    """
    line, problems = one_line("the label read", stdout)
    if line is None:
        return problems
    parsed = parse_label(line)
    if parsed is None:
        return [f"the label {line!r} cannot be parsed"]
    expected = f"{STACK_SEPARATOR.join(EXPECTED_STACK)} ({ENFORCE})"
    if parsed != (EXPECTED_STACK, ENFORCE):
        return [
            f"a program started by bubblewrap runs under {line!r}, expected {expected!r}"
        ]
    return []
