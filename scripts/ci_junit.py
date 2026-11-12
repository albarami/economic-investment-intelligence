"""Judges of the result of the sandbox-marked tests (TST-62, task S0-T11).

Pure functions over the text of the JUnit file that pytest writes for
``ci_sandbox prove``; nothing here starts a program or reads a file. The proof
names its test cases: every case of ``REQUIRED`` must be reported exactly once
and passed, and no other case may be reported. A number of passed tests alone
would accept unrelated tests that carry the marker in place of required ones.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Sequence

# pytest writes the class name of a unittest case as the dotted path of its
# module below the root folder, then the class (observed with pytest 9.2.0).
MODULE_PREFIX = "scripts.tests."
# The marker modules, their classes and test methods; test_sandbox_prove.py
# compares this table with the methods that the marker modules really hold.
REQUIRED = {
    "test_sandbox_sentinel.SentinelRules": (
        "test_both_profiles_block_read_and_network",
        "test_repository_secrets_are_not_mounted",
        "test_planted_leaks_are_seen",
        "test_network_attempts_table",
        "test_scenario_and_staging_mounts",
    ),
    "test_sandbox_mounts.MountRules": (
        "test_filesystem_modes_in_both_profiles",
        "test_environment_names_and_values",
        "test_hostile_surroundings_do_not_reach_the_sandbox",
        "test_exit_statuses_and_setup_failure",
        "test_timeout_kills_the_process_group",
        "test_die_with_parent",
        "test_check_commands_have_teeth",
        "test_swapped_source_is_not_mounted",
    ),
    "test_sandbox_loading.LoadingRules": (
        "test_load_offline_read_only_in_both_profiles",
        "test_signature_check_stays_on",
        "test_empty_folder_and_read_only_install",
        "test_automatic_loading_is_off",
        "test_namespace_creation_refused_is_reported",
        "test_extension_files_are_the_checked_objects",
    ),
}
PASSED, FAILED, SKIPPED = "passed", "failed", "skipped"
Case = tuple[str, str, str]


def required_cases() -> frozenset[tuple[str, str]]:
    """Return the required test cases as ``(class name, test name)`` pairs."""
    return frozenset(
        (MODULE_PREFIX + owner, name)
        for owner, names in REQUIRED.items()
        for name in names
    )


def read_cases(text: str) -> list[Case]:
    """Read the test cases of the one test suite of a JUnit file.

    Returns:
        ``(class name, test name, status)`` per ``testcase`` element, in file
        order; the status is ``failed`` when the case has a ``failure`` or
        ``error`` child, else ``skipped`` when it has a ``skipped`` child, else
        ``passed``.

    Raises:
        ValueError: The text is not well-formed XML, holds not exactly one
            ``testsuite``, or a case lacks its class name or name.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError("result file is not well-formed XML") from error
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if len(suites) != 1:
        raise ValueError("result file does not hold exactly one testsuite")
    cases = []
    for case in suites[0].iter("testcase"):
        owner, name = case.get("classname"), case.get("name")
        if not owner or not name:
            raise ValueError("a testcase has no classname or no name")
        tags = {child.tag for child in case}
        status = (
            FAILED
            if tags & {"failure", "error"}
            else SKIPPED
            if "skipped" in tags
            else PASSED
        )
        cases.append((owner, name, status))
    return cases


def case_problems(cases: Sequence[Case], exit_status: int) -> list[str]:
    """List the reasons the test cases do not count as proof.

    Args:
        cases: The cases of ``read_cases``.
        exit_status: Exit status of pytest.

    Returns:
        ``FAIL`` lines; empty when every required case was reported exactly
        once and passed, no other case was reported, and pytest exited 0.
    """
    if not cases:
        return ["FAIL sandbox-tests: no sandbox test ran"]
    required = required_cases()
    seen = Counter((owner, name) for owner, name, _ in cases)
    lines = [
        f"FAIL sandbox-tests: required test case missing: {owner}::{name}"
        for owner, name in sorted(required - seen.keys())
    ]
    lines += [
        f"FAIL sandbox-tests: test case not in the required list: {owner}::{name}"
        for owner, name in sorted(seen.keys() - required)
    ]
    lines += [
        f"FAIL sandbox-tests: test case reported {count} times: {owner}::{name}"
        for (owner, name), count in sorted(seen.items())
        if count > 1
    ]
    lines += [
        f"FAIL sandbox-tests: {status} (a sandbox test must pass and is never "
        f"skipped): {owner}::{name}"
        for owner, name, status in sorted(cases)
        if status != PASSED
    ]
    failed = sum(1 for case in cases if case[2] == FAILED)
    if (exit_status == 0) != (failed == 0):
        lines.append(
            f"FAIL sandbox-tests: exit status {exit_status} disagrees with "
            f"{failed} failed test cases"
        )
    return lines
