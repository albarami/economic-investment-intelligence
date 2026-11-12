"""Count parsers and verdict rules for the test runner."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

STANDING_SKIP_PATTERN = r"OI-(?:01|10)(?![0-9])"
MIN_TESTS = 1
NAME_CUT = 120
CONTROL_PATTERN = r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+"
_ATTRIBUTE = (
    "attribute tests is missing or smaller than the number of testcase elements"
)


class ParseError(Exception):
    """A result file could not be turned into counts."""


@dataclass(frozen=True)
class Counts:
    """Passed, failed and skipped totals, with skip reasons and tool success."""

    passed: int
    failed: int
    skipped: int
    skips: tuple[tuple[str, str | None], ...]
    success: bool | None


def standing_skip(reason: str | None) -> bool:
    """Return whether a raw skip reason names OI-01 or OI-10."""
    if reason is None:
        return False
    return re.search(STANDING_SKIP_PATTERN, reason) is not None


def sanitise(text: str) -> str:
    """Replace control characters and line breaks with one space, then strip."""
    return re.sub(CONTROL_PATTERN, " ", text).strip()


def parse_junit(text: str) -> Counts:
    """Count testcase elements in one JUnit testsuite document."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ParseError("not well-formed XML") from error
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = [child for child in list(root) if child.tag == "testsuite"]
    else:
        suites = []
    if not suites:
        raise ParseError("no testsuite element")
    if len(suites) > 1:
        raise ParseError("more than one testsuite element")
    suite = suites[0]
    cases = [element for element in suite.iter("testcase")]
    passed = 0
    failed = 0
    skipped = 0
    skips: list[tuple[str, str | None]] = []
    for case in cases:
        children = list(case)
        if any(child.tag in {"failure", "error"} for child in children):
            failed += 1
            continue
        skipped_child = next(
            (child for child in children if child.tag == "skipped"), None
        )
        if skipped_child is not None:
            skipped += 1
            if "name" not in case.attrib:
                name = ""
            else:
                name = case.attrib["name"]
            message = (
                skipped_child.attrib["message"]
                if "message" in skipped_child.attrib
                else None
            )
            skips.append((name, message))
            continue
        passed += 1
    raw = suite.get("tests")
    try:
        declared = int(raw) if raw is not None else None
    except ValueError:
        declared = None
    if declared is None or declared < 0 or declared < len(cases):
        raise ParseError(_ATTRIBUTE)
    return Counts(passed, failed, skipped, tuple(skips), None)


def parse_node_records(text: str) -> Counts:
    """Count JSON lines written by the Node counting reporter."""
    if text.strip() == "":
        raise ParseError("result file is empty")
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    passed = 0
    failed = 0
    skipped = 0
    skips: list[tuple[str, str | None]] = []
    seen_end = False
    for number, line in enumerate(lines, start=1):
        try:
            item = json.loads(line)
        except ValueError as error:
            raise ParseError(f"line {number} is not valid JSON") from error
        is_end = isinstance(item, dict) and set(item) == {"end"} and item["end"] is True
        is_test = (
            isinstance(item, dict)
            and set(item) == {"s", "n", "r"}
            and isinstance(item["s"], str)
            and item["s"] in {"pass", "fail", "skip"}
            and isinstance(item["n"], str)
            and isinstance(item["r"], str)
        )
        if not is_end and not is_test:
            raise ParseError(f"line {number} is not a known record")
        if seen_end:
            raise ParseError("records after the end record")
        if is_end:
            seen_end = True
            continue
        assert isinstance(item, dict)
        if item["s"] == "pass":
            passed += 1
        elif item["s"] == "fail":
            failed += 1
        else:
            skipped += 1
            skips.append((item["n"], item["r"]))
    if not seen_end:
        raise ParseError("result file ends without the end record")
    return Counts(passed, failed, skipped, tuple(skips), None)


def parse_vitest_json(text: str) -> Counts:
    """Count Vitest assertion results and file-level failures."""
    try:
        payload = json.loads(text)
    except ValueError as error:
        raise ParseError("not valid JSON") from error
    if not isinstance(payload, dict):
        raise ParseError("top level is not an object")
    numbers: dict[str, int] = {}
    for name in (
        "numPassedTests",
        "numFailedTests",
        "numPendingTests",
        "numTodoTests",
    ):
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ParseError(f"field {name} is missing or not a non-negative integer")
        numbers[name] = value
    success = payload.get("success")
    if not isinstance(success, bool):
        raise ParseError("field success is missing or not a boolean")
    entries = payload.get("testResults")
    if not isinstance(entries, list):
        raise ParseError("field testResults is missing or not a list")
    for index, entry in enumerate(entries):
        if not _vitest_entry_ok(entry):
            raise ParseError(f"testResults entry {index} is malformed")
    passed = 0
    failed_assertions = 0
    skipped = 0
    file_failures = 0
    skips: list[tuple[str, str | None]] = []
    for entry in entries:
        assert isinstance(entry, dict)
        assertions = entry["assertionResults"]
        assert isinstance(assertions, list)
        entry_failed = False
        for assertion in assertions:
            assert isinstance(assertion, dict)
            status = assertion["status"]
            if status == "passed":
                passed += 1
            elif status == "failed":
                failed_assertions += 1
                entry_failed = True
            elif status in {"skipped", "todo"}:
                skipped += 1
                skips.append((str(assertion["fullName"]), None))
            else:
                raise ParseError(f'assertion status "{status}" is not known')
        if entry["status"] == "failed" and not entry_failed:
            file_failures += 1
    if (
        numbers["numPassedTests"] != passed
        or numbers["numFailedTests"] != failed_assertions
        or numbers["numPendingTests"] + numbers["numTodoTests"] != skipped
    ):
        raise ParseError("totals disagree with testResults")
    return Counts(
        passed,
        failed_assertions + file_failures,
        skipped,
        tuple(skips),
        success,
    )


def judge(
    suite: str,
    counts: Counts,
    exit_status: int,
    scrub: Callable[[str], str] = str,
) -> list[str]:
    """Return the count-rule lines for one suite, in rule order."""
    if counts.passed + counts.failed + counts.skipped < MIN_TESTS:
        return [f"FAIL no-tests: {suite}: the suite ran no tests"]
    lines: list[str] = []
    if counts.failed > 0:
        lines.append(f"FAIL tests-failed: {suite}: {counts.failed} failed")
    for name, reason in counts.skips:
        if standing_skip(reason):
            continue
        shown_name = scrub(sanitise(name))[:NAME_CUT]
        if reason is None:
            shown_reason = "reason not readable from this runner"
        else:
            shown_reason = scrub(sanitise(reason))[:NAME_CUT]
            if shown_reason == "":
                shown_reason = "no reason given"
        lines.append(f"FAIL unexplained-skip: {suite}: {shown_name}: {shown_reason}")
    agrees = counts.failed == 0 and counts.success is not False
    if (exit_status == 0) != agrees:
        lines.append(
            f"FAIL exit-mismatch: {suite}: exit status {exit_status} "
            f"disagrees with {counts.failed} failed tests"
        )
    return lines


def _vitest_entry_ok(entry: object) -> bool:
    if not isinstance(entry, dict) or not isinstance(entry.get("status"), str):
        return False
    assertions = entry.get("assertionResults")
    if not isinstance(assertions, list):
        return False
    return all(
        isinstance(assertion, dict)
        and isinstance(assertion.get("status"), str)
        and isinstance(assertion.get("fullName"), str)
        for assertion in assertions
    )
