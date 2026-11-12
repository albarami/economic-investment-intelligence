"""Parsers, skip rules and child environments, without subprocesses."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import run_tests_counts as counts
import run_tests_exec as runner_exec


def _case(
    name: str | None,
    kind: str | None = None,
    message: str | None = None,
) -> ET.Element:
    element = ET.Element("testcase")
    if name is not None:
        element.set("name", name)
    if kind is not None:
        child = ET.SubElement(element, kind)
        if message is not None:
            child.set("message", message)
    return element


def _junit(cases: list[ET.Element], tests: int | None, wrap: bool = False) -> str:
    suite = ET.Element("testsuite")
    if tests is not None:
        suite.set("tests", str(tests))
    for case in cases:
        suite.append(case)
    root = suite
    if wrap:
        root = ET.Element("testsuites")
        root.append(suite)
    return ET.tostring(root, encoding="unicode")


def _vitest(
    entries: list[object],
    passed: object = 0,
    failed: object = 0,
    pending: object = 0,
    todo: object = 0,
    success: object = True,
) -> str:
    return json.dumps(
        {
            "numPassedTests": passed,
            "numFailedTests": failed,
            "numPendingTests": pending,
            "numTodoTests": todo,
            "success": success,
            "testResults": entries,
        }
    )


def _entry(status: str, assertions: list[dict[str, str]]) -> dict[str, object]:
    return {"status": status, "assertionResults": assertions}


def _assert(status: str, full_name: str) -> dict[str, str]:
    return {"status": status, "fullName": full_name}


class CountParsers(unittest.TestCase):
    def test_junit_examples(self) -> None:
        clean = counts.parse_junit(_junit([_case("a"), _case("b"), _case("c")], 3))
        self.assertEqual((clean.passed, clean.failed, clean.skipped), (3, 0, 0))
        failed = counts.parse_junit(_junit([_case("a", "failure", "no")], 1))
        self.assertEqual(failed.failed, 1)
        errored = counts.parse_junit(_junit([_case("a", "error", "no")], 1))
        self.assertEqual(errored.failed, 1)
        skipped = counts.parse_junit(_junit([_case("a", "skipped", "OI-10 x")], 1))
        self.assertEqual(skipped.skips, (("a", "OI-10 x"),))
        xfail = counts.parse_junit(_junit([_case("a", "skipped", "later")], 1))
        self.assertEqual(xfail.skips, (("a", "later"),))
        wrapped = counts.parse_junit(_junit([_case("a")], 1, wrap=True))
        self.assertEqual(wrapped.passed, 1)
        foreign = counts.parse_junit(_junit([_case("a", "skipped", "caf\u00e9")], 1))
        self.assertEqual(foreign.skips[0][1], "caf\u00e9")
        missing = counts.parse_junit(_junit([_case("a", "skipped")], 1))
        self.assertEqual(missing.skips, (("a", None),))
        unnamed = ET.Element("testcase")
        ET.SubElement(unnamed, "skipped")
        parsed = counts.parse_junit(_junit([unnamed], 1))
        self.assertEqual(parsed.skips, (("", None),))
        larger = counts.parse_junit(_junit([_case("a"), _case("b")], 5))
        self.assertEqual((larger.passed, larger.failed, larger.skipped), (2, 0, 0))

    @settings(derandomize=True, database=None)
    @given(
        st.integers(min_value=0, max_value=30),
        st.integers(min_value=0, max_value=30),
        st.integers(min_value=0, max_value=30),
        st.lists(
            st.text(alphabet="abcXYZ ", min_size=0, max_size=12),
            max_size=30,
        ),
    )
    def test_junit_round_trip_property(
        self, passed: int, failed: int, errors: int, reasons: list[str]
    ) -> None:
        cases = [_case(f"p{index}") for index in range(passed)]
        cases += [_case(f"f{index}", "failure", "no") for index in range(failed)]
        cases += [_case(f"e{index}", "error", "no") for index in range(errors)]
        cases += [
            _case(f"s{index}", "skipped", reason)
            for index, reason in enumerate(reasons)
        ]
        text = _junit(cases, len(cases))
        parsed = counts.parse_junit(text)
        self.assertEqual(parsed.passed, passed)
        self.assertEqual(parsed.failed, failed + errors)
        self.assertEqual(parsed.skipped, len(reasons))
        self.assertEqual([item[1] for item in parsed.skips], reasons)

    def test_junit_garbage(self) -> None:
        rows: tuple[tuple[str, str], ...] = (
            ("", "not well-formed XML"),
            ("garbage", "not well-formed XML"),
            ("<a/>", "no testsuite element"),
            (
                "<testsuites><testsuite tests='0'/><testsuite tests='0'/></testsuites>",
                "more than one testsuite element",
            ),
            (
                "<testsuite><testcase name='a'/></testsuite>",
                "attribute tests is missing or smaller than the number of testcase elements",
            ),
            (
                "<testsuite tests='x'><testcase name='a'/></testsuite>",
                "attribute tests is missing or smaller than the number of testcase elements",
            ),
            (
                "<testsuite tests='-1'><testcase name='a'/></testsuite>",
                "attribute tests is missing or smaller than the number of testcase elements",
            ),
            (
                "<testsuite tests='0'><testcase name='a'/></testsuite>",
                "attribute tests is missing or smaller than the number of testcase elements",
            ),
        )
        for text, message in rows:
            with self.subTest(text=text):
                with self.assertRaises(counts.ParseError) as caught:
                    counts.parse_junit(text)
                self.assertEqual(str(caught.exception), message)

    def test_node_records(self) -> None:
        end = '{"end": true}\n'
        clean = json.dumps({"s": "pass", "n": "a", "r": ""}) + "\n" + end
        parsed = counts.parse_node_records(clean)
        self.assertEqual((parsed.passed, parsed.failed, parsed.skipped), (1, 0, 0))
        failed = json.dumps({"s": "fail", "n": "a", "r": ""}) + "\n" + end
        self.assertEqual(counts.parse_node_records(failed).failed, 1)
        skipped = json.dumps({"s": "skip", "n": "a", "r": "later"}) + "\n" + end
        self.assertEqual(counts.parse_node_records(skipped).skips, (("a", "later"),))
        empty_reason = json.dumps({"s": "skip", "n": "a", "r": ""}) + "\n" + end
        self.assertEqual(counts.parse_node_records(empty_reason).skips, (("a", ""),))
        faults = (
            (
                json.dumps({"s": "pass", "n": "a", "r": ""}),
                "result file ends without the end record",
            ),
            (
                json.dumps({"s": "pass", "n": "a", "r": ""})
                + "\n"
                + end
                + json.dumps({"s": "pass", "n": "b", "r": ""})
                + "\n",
                "records after the end record",
            ),
            (end + end, "records after the end record"),
            ("{}\n" + end, "line 1 is not a known record"),
            ('{"end": 1}\n' + end, "line 1 is not a known record"),
            ('{"end": true, "x": 1}\n' + end, "line 1 is not a known record"),
            (
                json.dumps({"s": "pass", "n": 1, "r": ""}) + "\n" + end,
                "line 1 is not a known record",
            ),
            (
                json.dumps({"s": ["pass"], "n": "a", "r": ""}) + "\n" + end,
                "line 1 is not a known record",
            ),
            (
                json.dumps({"s": "pass", "n": "a"}) + "\n" + end,
                "line 1 is not a known record",
            ),
            ("{]\n" + end, "line 1 is not valid JSON"),
            ("", "result file is empty"),
            (" \n\t\n", "result file is empty"),
        )
        for text, message in faults:
            with self.subTest(message=message, text=text):
                with self.assertRaises(counts.ParseError) as caught:
                    counts.parse_node_records(text)
                self.assertEqual(str(caught.exception), message)
        second = '{"s": "pass", "n": "a", "r": ""}\n{]\n'
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_node_records(second)
        self.assertEqual(str(caught.exception), "line 2 is not valid JSON")
        name = "a" + chr(0x2028) + "b" + chr(0x85) + "c"
        line = json.dumps({"s": "pass", "n": name, "r": ""}, ensure_ascii=False) + "\n"
        parsed = counts.parse_node_records(line + end)
        self.assertEqual(parsed.passed, 1)
        self.assertEqual(parsed.skips, ())

    def test_vitest_json(self) -> None:
        clean = counts.parse_vitest_json(
            _vitest(
                [_entry("passed", [_assert("passed", "a"), _assert("passed", "b")])],
                2,
                0,
                0,
                0,
                True,
            )
        )
        self.assertEqual(
            (clean.passed, clean.failed, clean.skipped, clean.success), (2, 0, 0, True)
        )
        one = counts.parse_vitest_json(
            _vitest([_entry("failed", [_assert("failed", "a")])], 0, 1, 0, 0, False)
        )
        self.assertEqual(one.failed, 1)
        file_level = counts.parse_vitest_json(
            _vitest([_entry("failed", [])], 0, 0, 0, 0, False)
        )
        self.assertEqual(file_level.failed, 1)
        hook = counts.parse_vitest_json(
            _vitest(
                [
                    _entry(
                        "failed",
                        [
                            _assert("skipped", "g a"),
                            _assert("skipped", "g b"),
                            _assert("passed", "top"),
                        ],
                    )
                ],
                1,
                0,
                2,
                0,
                False,
            )
        )
        self.assertEqual((hook.passed, hook.failed, hook.skipped), (1, 1, 2))
        self.assertEqual(hook.skips, (("g a", None), ("g b", None)))
        mixed = counts.parse_vitest_json(
            _vitest(
                [_entry("passed", [_assert("skipped", "s"), _assert("todo", "t")])],
                0,
                0,
                1,
                1,
                True,
            )
        )
        self.assertEqual(mixed.skipped, 2)
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(
                _vitest([_entry("failed", [_assert("failed", "a")])], 0, 0, 0, 0, False)
            )
        self.assertEqual(str(caught.exception), "totals disagree with testResults")
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(
                _vitest([_entry("passed", [_assert("pending", "a")])], 0, 0, 0, 0, True)
            )
        self.assertEqual(
            str(caught.exception), 'assertion status "pending" is not known'
        )
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(_vitest(["nope"], 0, 0, 0, 0, True))
        self.assertEqual(str(caught.exception), "testResults entry 0 is malformed")
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(
                _vitest([_entry("passed", []), "nope"], 0, 0, 0, 0, True)
            )
        self.assertEqual(str(caught.exception), "testResults entry 1 is malformed")
        bad_assert = _entry("passed", [{"status": "passed"}])
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(
                _vitest([_entry("passed", []), bad_assert], 0, 0, 0, 0, True)
            )
        self.assertEqual(str(caught.exception), "testResults entry 1 is malformed")
        without = {"status": "passed"}
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(_vitest([without], 0, 0, 0, 0, True))
        self.assertEqual(str(caught.exception), "testResults entry 0 is malformed")
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(
                _vitest(
                    [
                        _entry("passed", [_assert("nope", "a")]),
                        "bad",
                    ],
                    0,
                    0,
                    0,
                    0,
                    True,
                )
            )
        self.assertEqual(str(caught.exception), "testResults entry 1 is malformed")
        payload = json.loads(_vitest([_entry("passed", [])], 0, 0, 0, 0, True))
        for field in (
            "numPassedTests",
            "numFailedTests",
            "numPendingTests",
            "numTodoTests",
        ):
            broken = dict(payload)
            del broken[field]
            with self.subTest(field=field):
                with self.assertRaises(counts.ParseError) as caught:
                    counts.parse_vitest_json(json.dumps(broken))
                self.assertEqual(
                    str(caught.exception),
                    f"field {field} is missing or not a non-negative integer",
                )
        broken = dict(payload)
        broken["numPassedTests"] = "1"
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(json.dumps(broken))
        self.assertIn("numPassedTests", str(caught.exception))
        broken = dict(payload)
        broken["numPassedTests"] = True
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(json.dumps(broken))
        self.assertEqual(
            str(caught.exception),
            "field numPassedTests is missing or not a non-negative integer",
        )
        broken = dict(payload)
        broken["numFailedTests"] = -1
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(json.dumps(broken))
        self.assertIn("numFailedTests", str(caught.exception))
        for value in (None, "yes"):
            body = dict(payload)
            if value is None:
                del body["success"]
            else:
                body["success"] = value
            with self.assertRaises(counts.ParseError) as caught:
                counts.parse_vitest_json(json.dumps(body))
            self.assertEqual(
                str(caught.exception), "field success is missing or not a boolean"
            )
        body = dict(payload)
        body["testResults"] = {}
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json(json.dumps(body))
        self.assertEqual(
            str(caught.exception), "field testResults is missing or not a list"
        )
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json("[]")
        self.assertEqual(str(caught.exception), "top level is not an object")
        with self.assertRaises(counts.ParseError) as caught:
            counts.parse_vitest_json("{")
        self.assertEqual(str(caught.exception), "not valid JSON")

    def test_secret_names(self) -> None:
        for name in (
            "ANTHROPIC_API_KEY",
            "JEV_PRO_API_KEY",
            "FOO_KEY",
            "x_token",
            "Y_SECRET",
            "_KEY",
        ):
            self.assertTrue(runner_exec.is_secret_name(name), name)
        for name in ("PATH", "MONKEY", "KEYBOARD", "SECRET", "TOKEN_FILE", "HOME"):
            self.assertFalse(runner_exec.is_secret_name(name), name)

    def test_standing_skip_rule(self) -> None:
        expected = (
            ("OI-01", True),
            ("OI-10 x", True),
            ("a OI-10", True),
            ("OI-100", False),
            ("OI-1", False),
            ("oi-10", False),
            ("", False),
            (None, False),
        )
        for reason, want in expected:
            self.assertEqual(counts.standing_skip(reason), want, reason)

    def test_child_env_is_an_allow_list(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="eii-child-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        parent = {name: f"v-{name}" for name in runner_exec.PYTHON_PASS_THROUGH}
        for name in (
            "ANTHROPIC_API_KEY",
            "JEV_PRO_API_KEY",
            "FOO_KEY",
            "BAR_TOKEN",
            "BAZ_SECRET",
            "my_secret",
            "PYTHONPATH",
            "NODE_OPTIONS",
            "CI",
            "HYPOTHESIS_STORAGE_DIRECTORY",
        ):
            parent[name] = "x" * 9
        pytest_env = runner_exec.child_env("pytest", parent, 1794000000, folder)
        expected = set(runner_exec.PYTHON_PASS_THROUGH) | {
            "PYTHONHASHSEED",
            "PYTHONDONTWRITEBYTECODE",
            "EII_DECISION_PROVIDER",
            "NO_COLOR",
            "HYPOTHESIS_STORAGE_DIRECTORY",
        }
        self.assertEqual(set(pytest_env), expected)
        for name in runner_exec.PYTHON_PASS_THROUGH:
            self.assertEqual(pytest_env[name], parent[name])
        self.assertEqual(
            pytest_env["HYPOTHESIS_STORAGE_DIRECTORY"], str(folder / "hypothesis")
        )
        self.assertEqual(pytest_env["PYTHONHASHSEED"], "1794000000")
        node_env = runner_exec.child_env("node", parent, 1794000000, folder)
        self.assertEqual(
            set(node_env),
            {"PATH", "HOME", "TMPDIR", "LANG", "NO_COLOR", "EII_DECISION_PROVIDER"},
        )
        self.assertEqual(node_env["HOME"], str(folder))
        self.assertEqual(node_env["TMPDIR"], str(folder))
        self.assertEqual(node_env["LANG"], "C")
        self.assertEqual(node_env["EII_DECISION_PROVIDER"], "none")
        for env in (pytest_env, node_env):
            self.assertFalse(any(runner_exec.is_secret_name(name) for name in env))
        with self.assertRaises(ValueError):
            runner_exec.child_env("bogus", parent, 1794000000, folder)

    def test_judge_rules(self) -> None:
        def counts_of(
            passed: int,
            failed: int,
            skipped: int = 0,
            skips: tuple[tuple[str, str | None], ...] = (),
            success: bool | None = None,
        ) -> counts.Counts:
            return counts.Counts(passed, failed, skipped, skips, success)

        first = counts.judge("s", counts_of(0, 2), 0)
        self.assertTrue(any(line.startswith("FAIL exit-mismatch:") for line in first))
        second = counts.judge("s", counts_of(3, 0), 1)
        self.assertEqual(
            second,
            ["FAIL exit-mismatch: s: exit status 1 disagrees with 0 failed tests"],
        )
        third = counts.judge("s", counts_of(0, 0), 5)
        self.assertEqual(third, ["FAIL no-tests: s: the suite ran no tests"])
        fourth = counts.judge("s", counts_of(1, 0, success=False), 0)
        self.assertTrue(any(line.startswith("FAIL exit-mismatch:") for line in fourth))
        self.assertEqual(counts.judge("s", counts_of(1, 0), 0), [])
        shown = counts.judge("s", counts_of(1, 0, 1, (("a\nb", "r\x00s"),)), 0)
        self.assertEqual(shown, ["FAIL unexplained-skip: s: a b: r s"])

        def scrub(text: str) -> str:
            return text.replace("sekrit", "[redacted]")

        redacted = counts.judge("s", counts_of(1, 0, 1, (("n", "sekrit"),)), 0, scrub)
        self.assertEqual(redacted, ["FAIL unexplained-skip: s: n: [redacted]"])
