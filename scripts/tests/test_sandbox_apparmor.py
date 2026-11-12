"""AppArmor proof on synthetic input. No AppArmor and no sandbox are needed."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import ci_apparmor
import ci_sandbox

GOOD = support.LISTING_OK.stdout
PROBE = ci_sandbox.CommandResult(
    1, "", "bwrap: setting up uid map: Permission denied\n"
)
HOSTED = ci_sandbox.HOSTED_RUNNER


def _listing(profiles: dict[str, str]) -> str:
    return json.dumps({"version": "2", "profiles": profiles, "processes": {}}) + "\n"


def _read_setting(_path: Path) -> str:
    return "1\n"


class AppArmorRules(unittest.TestCase):
    def test_profile_file_is_the_pinned_file(self) -> None:
        self.assertEqual(
            ci_apparmor.PROFILE_SHA256,
            "11d39094f044f0cda0febb3ad517b830301da6b2ce929664af09ee9e4dd264f9",
        )
        self.assertEqual(ci_apparmor.PROFILE_SIZE, 1936)
        self.assertEqual(
            ci_apparmor.PROFILE_PACKAGE,
            "apparmor-profiles 4.0.1really4.0.1-0ubuntu0.24.04.9",
        )
        labels = []
        with support.pinned_profile():
            labels.append(1)
            self.assertEqual(
                ci_apparmor.profile_file_problems("pinned", support.PINNED_BYTES), []
            )
            changed = bytearray(support.PINNED_BYTES)
            changed[0] ^= 1
            samples = [bytes(changed), b"", b"x" * len(support.PINNED_BYTES)]
            for data in samples:
                labels.append(len(labels) + 1)
                problems = ci_apparmor.profile_file_problems("sample", data)
                digest = hashlib.sha256(data).hexdigest()
                self.assertEqual(
                    problems,
                    [
                        f"sample has {len(data)} bytes and SHA-256 {digest}; the pinned file of "
                        f"{ci_apparmor.PROFILE_PACKAGE} has {len(support.PINNED_BYTES)} bytes and "
                        f"SHA-256 {hashlib.sha256(support.PINNED_BYTES).hexdigest()}: a person reviews "
                        "the new file and updates the pin"
                    ],
                )
        self.assertEqual(labels, [1, 2, 3, 4])

    def test_aa_status_listing_grammar(self) -> None:
        # Hosted runner: a valid status object whose closing brace stands
        # alone on the last line, and the output ends with a line feed.
        hosted = json.dumps(json.loads(GOOD), indent=2) + "\n"
        self.assertEqual(hosted.splitlines()[-1], "}", "hosted runner shape")
        self.assertTrue(hosted.endswith("}\n"), "hosted runner shape")
        self.assertEqual(ci_apparmor.status_problems(hosted), [], "hosted runner shape")
        other = _listing(
            {
                "/usr/bin/man": "enforce",
                "bwrap-other": "enforce",
                "unpriv_bwrap": "enforce",
            }
        )
        complain = _listing(
            {"/usr/bin/man": "enforce", "bwrap": "complain", "unpriv_bwrap": "enforce"}
        )
        neither = _listing({"/usr/bin/man": "enforce"})
        kill = _listing(
            {"/usr/bin/man": "enforce", "bwrap": "enforce", "unpriv_bwrap": "kill"}
        )
        duplicate = (
            '{"version": "2", "profiles": {"bwrap": "enforce", "bwrap": "enforce", '
            '"unpriv_bwrap": "enforce"}, "processes": {}}\n'
        )
        version3 = _listing({}).replace('"version": "2"', '"version": "3"', 1)
        profiles_list = '{"version": "2", "profiles": [], "processes": {}}\n'
        plants = [
            (GOOD, []),
            (other, ["profile bwrap is not loaded, expected enforce"]),
            (complain, ["profile bwrap is complain, expected enforce"]),
            (
                neither,
                [
                    "profile bwrap is not loaded, expected enforce",
                    "profile unpriv_bwrap is not loaded, expected enforce",
                ],
            ),
            (kill, ["profile unpriv_bwrap is kill, expected enforce"]),
            (
                duplicate,
                [
                    "aa-status --json printed no JSON object with unique keys (repeated key bwrap)"
                ],
            ),
            (
                "x\n",
                [
                    "aa-status --json printed no JSON object with unique keys (Expecting value: line 1 column 1 (char 0))"
                ],
            ),
            (
                version3,
                ["aa-status --json is not format version 2 with a profiles object"],
            ),
            (
                profiles_list,
                ["aa-status --json is not format version 2 with a profiles object"],
            ),
            (
                "[]\n",
                ["aa-status --json is not format version 2 with a profiles object"],
            ),
            (
                GOOD + GOOD,
                [
                    "aa-status --json printed no JSON object with unique keys "
                    "(Extra data: line 2 column 1 (char 122))"
                ],
            ),
            (
                "",
                [
                    "aa-status --json printed no JSON object with unique keys "
                    "(Expecting value: line 1 column 1 (char 0))"
                ],
            ),
            (
                GOOD.replace("{}", '{"x": NaN}', 1)
                if False
                else GOOD[:-2] + ', "x": NaN}\n',
                [
                    "aa-status --json printed no JSON object with unique keys (constant NaN is not JSON)"
                ],
            ),
        ]
        # The last plant rebuilds the object with a NaN member rather than the false branch.
        body = GOOD[:-1]
        plants[12] = (body[:-1] + ', "x": NaN}\n', plants[12][1])
        self.assertEqual(len(plants), 13)
        for index, (text, want) in enumerate(plants, start=1):
            self.assertEqual(ci_apparmor.status_problems(text), want, index)

    def test_label_grammar(self) -> None:
        def rejected(line: str) -> list[str]:
            return [
                "a program started by bubblewrap runs under "
                f"{line!r}, expected 'bwrap//&unpriv_bwrap (enforce)'"
            ]

        simple = "bwrap (enforce)"
        plants = [
            ("bwrap//&unpriv_bwrap (enforce)\n", []),
            (simple + "\n", rejected(simple)),
            ("unconfined\n", rejected("unconfined")),
            (
                "bwrap//&unpriv_bwrap (complain)\n",
                rejected("bwrap//&unpriv_bwrap (complain)"),
            ),
            (
                "bwrap//&unpriv_bwrap (mixed)\n",
                rejected("bwrap//&unpriv_bwrap (mixed)"),
            ),
            (
                "unprivileged_userns (enforce)\n",
                rejected("unprivileged_userns (enforce)"),
            ),
            (
                "unpriv_bwrap//&bwrap (enforce)\n",
                rejected("unpriv_bwrap//&bwrap (enforce)"),
            ),
            (
                ":ns:bwrap//&unpriv_bwrap (enforce)\n",
                rejected(":ns:bwrap//&unpriv_bwrap (enforce)"),
            ),
            (
                "bwrap//& (enforce)\n",
                ["the label 'bwrap//& (enforce)' cannot be parsed"],
            ),
            (
                "bwrap//&unpriv_bwrap (enforce)\0\n",
                ["the label 'bwrap//&unpriv_bwrap (enforce)\\x00' cannot be parsed"],
            ),
            (
                "bwrap//&unpriv_bwrap (Enforce)\n",
                ["the label 'bwrap//&unpriv_bwrap (Enforce)' cannot be parsed"],
            ),
            ("", ["the label read did not print exactly one line: ''"]),
            ("a\nb\n", ["the label read did not print exactly one line: 'a\\nb\\n'"]),
        ]
        self.assertEqual(
            [ci_apparmor.label_problems(text) for text, _want in plants],
            [want for _text, want in plants],
        )
        self.assertEqual(
            ci_apparmor.parse_label("bwrap (enforce)"), (("bwrap",), "enforce")
        )
        self.assertEqual(
            ci_apparmor.parse_label("bwrap//&unpriv_bwrap (enforce)"),
            (("bwrap", "unpriv_bwrap"), "enforce"),
        )
        self.assertEqual(ci_apparmor.parse_label("unconfined"), (("unconfined",), None))
        self.assertEqual(len(plants) + 3, 16)

    def test_install_profile_fails_unless_the_profile_is_in_force(self) -> None:
        other = b"other\n"
        target = str(ci_sandbox.PROFILE_TARGET)
        source = str(ci_sandbox.PROFILE_SOURCE)
        listing_other = _listing(
            {
                "/usr/bin/man": "enforce",
                "bwrap-other": "enforce",
                "unpriv_bwrap": "enforce",
            }
        )
        listing_complain = _listing(
            {"/usr/bin/man": "enforce", "bwrap": "complain", "unpriv_bwrap": "enforce"}
        )
        cases = [
            (
                "a",
                (support.PINNED_BYTES, other, None),
                [PROBE],
                [ci_sandbox.PROBE_ARGV],
                target,
                other,
            ),
            ("b", (other, None, None), [PROBE], [ci_sandbox.PROBE_ARGV], source, other),
            (
                "c",
                (support.PINNED_BYTES, None, other),
                [PROBE, support.OK],
                [ci_sandbox.PROBE_ARGV, ci_sandbox.INSTALL_ARGV],
                target,
                other,
            ),
            (
                "d",
                (support.PINNED_BYTES, support.PINNED_BYTES, None),
                [PROBE, ci_sandbox.CommandResult(0, "", "Warning: x\n")],
                [ci_sandbox.PROBE_ARGV, ci_sandbox.PARSER_ARGV],
                "",
                b"",
            ),
            (
                "e",
                (support.PINNED_BYTES, support.PINNED_BYTES, None),
                [PROBE, support.OK, ci_sandbox.CommandResult(0, listing_other, "")],
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.LISTING_ARGV,
                ],
                "",
                b"",
            ),
            (
                "f",
                (support.PINNED_BYTES, support.PINNED_BYTES, None),
                [PROBE, support.OK, ci_sandbox.CommandResult(0, listing_complain, "")],
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.LISTING_ARGV,
                ],
                "",
                b"",
            ),
        ]
        labels = [name for name, *_rest in cases]
        with support.pinned_profile():
            for name, file_args, results, calls, path, data in cases:
                text, got_calls = self._run(file_args, results)
                self.assertEqual(got_calls, calls, name)
                self.assertEqual(text.splitlines()[-1].startswith("FAIL "), True, name)
                if path:
                    self.assertIn(path, text.splitlines()[-1])
                    self.assertEqual(
                        text.splitlines()[-1],
                        "FAIL " + ci_apparmor.profile_file_problems(path, data)[0],
                    )
            self._label("g", "unprivileged_userns (enforce)\n", labels)
            self._label("h", "unconfined\n", labels)
            self._label("i", "bwrap (enforce)\n", labels)
            stderr = "cat: /proc/self/attr/apparmor/current: Invalid argument\n"
            text, calls = self._run(
                (support.PINNED_BYTES, support.PINNED_BYTES, None),
                [
                    PROBE,
                    support.OK,
                    support.LISTING_OK,
                    support.OK,
                    ci_sandbox.CommandResult(1, "", stderr),
                ],
            )
            labels.append("j")
            self.assertEqual(calls[-1], ci_sandbox.LABEL_ARGV)
            self.assertEqual(
                [line for line in text.splitlines() if line.startswith("FAIL ")],
                [
                    "FAIL label read: exit status 1, expected 0",
                    f"FAIL label read: standard error is not empty: {stderr!r}",
                    "FAIL the label read did not print exactly one line: ''",
                ],
            )
            denied = "aa-status: not enough privileges\n"
            text, calls = self._run(
                (support.PINNED_BYTES, support.PINNED_BYTES, None),
                [PROBE, support.OK, ci_sandbox.CommandResult(4, "", denied)],
            )
            labels.append("k")
            self.assertEqual(
                calls,
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.LISTING_ARGV,
                ],
            )
            self.assertEqual(
                [line for line in text.splitlines() if line.startswith("FAIL ")],
                [
                    "FAIL aa-status --json: exit status 4, expected 0",
                    f"FAIL aa-status --json: standard error is not empty: {denied!r}",
                    "FAIL aa-status --json printed no JSON object with unique keys "
                    "(Expecting value: line 1 column 1 (char 0))",
                ],
            )
        self.assertEqual(labels, list("abcdefghijk"))

    def _run(
        self,
        file_args: tuple[bytes | None, bytes | None, bytes | None],
        results: list[ci_sandbox.CommandResult],
    ) -> tuple[str, list[list[str]]]:
        runner = support.FakeRunner(results)
        files = support.FakeFiles(*file_args, runner)
        text = io.StringIO()
        status = ci_sandbox.install_profile(
            HOSTED, runner, files, _read_setting, text, io.StringIO()
        )
        self.assertEqual(status, 1)
        body = text.getvalue()
        if any(
            call == ci_sandbox.LISTING_ARGV or call == ci_sandbox.LABEL_ARGV
            for call in runner.calls
        ):
            self.assertLess(body.find("raw:"), body.find("FAIL "))
        return body, runner.calls

    def _label(self, name: str, line: str, labels: list[str]) -> None:
        text, calls = self._run(
            (support.PINNED_BYTES, support.PINNED_BYTES, None),
            [
                PROBE,
                support.OK,
                support.LISTING_OK,
                support.OK,
                ci_sandbox.CommandResult(0, line, ""),
            ],
        )
        labels.append(name)
        self.assertEqual(
            calls,
            [
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.PARSER_ARGV,
                ci_sandbox.LISTING_ARGV,
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.LABEL_ARGV,
            ],
        )
        self.assertEqual(
            text.splitlines()[-1], "FAIL " + ci_apparmor.label_problems(line)[0]
        )
