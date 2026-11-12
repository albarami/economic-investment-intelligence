"""Exact judging of every started program. No sandbox is started."""

from __future__ import annotations

import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import ci_sandbox
import sandbox_check
import sandbox_launch as launch
import sandbox_profiles as tables

INSIDE = "".join(
    f"{name} {want}\n" for name, want in sandbox_check.INSIDE_LINES.items()
)
OUTSIDE = "read_outside ok\ntcp_loopback ok\nunix_abstract ok\n"
VERSION = "bubblewrap 0.11.1\n"
LOAD = "".join(f"{line}\n" for line in sandbox_check.LOAD_LINES)
PACKAGES = "apparmor 4.0.1\napparmor-profiles 4.0.1\nbubblewrap 0.9.0\n"


def _missing(path: Path) -> NoReturn:
    raise FileNotFoundError(path)


def _fault(good: str, kind: str) -> tuple[int, str, str]:
    if kind == "status":
        return 1, good, ""
    if kind == "stderr":
        return 0, good, "x\n"
    if kind == "twice":
        planted = "x" if good == "" else good.splitlines()[-1]
        body = f"{planted}\n{planted}\n" if good == "" else good + planted + "\n"
        return 0, body, ""
    if kind == "extra":
        return 0, good + "extra\n", ""
    raise AssertionError(kind)


class OutputRules(unittest.TestCase):
    def test_output_problems_judge_exactly(self) -> None:
        judge = sandbox_check.output_problems
        pattern = re.compile(r"v[0-9]+")
        plants = [
            judge("x", 0, "a\nb\n", "", ["a", "b"]) == [],
            judge("x", 1, "a\nb\n", "", ["a", "b"]) == ["x: exit status 1, expected 0"],
            judge("x", 0, "a\nb\n", "e\n", ["a", "b"])
            == ["x: standard error is not empty: 'e\\n'"],
            judge("x", 0, "a\nb\nb\n", "", ["a", "b"])
            == ["x: standard output ['a', 'b', 'b'], expected ['a', 'b']"],
            judge("x", 0, "a\nb\nextra\n", "", ["a", "b"])
            == ["x: standard output ['a', 'b', 'extra'], expected ['a', 'b']"],
            judge("x", 0, "a\n", "", ["a", "b"])
            == ["x: standard output ['a'], expected ['a', 'b']"],
            judge("x", 0, "b\na\n", "", ["a", "b"])
            == ["x: standard output ['b', 'a'], expected ['a', 'b']"],
            judge("x", 0, "a\nb", "", ["a", "b"])
            == [
                "x: standard output 'a\\nb' does not end with a newline, expected ['a', 'b']"
            ],
            judge("x", 0, "v12\n", "", [pattern]) == []
            and judge("x", 0, "v12x\n", "", [pattern])
            == ["x: standard output ['v12x'], expected ['v[0-9]+']"],
            judge("x", 2, "z\n", "e\n", ["a", "b"])
            == [
                "x: exit status 2, expected 0",
                "x: standard error is not empty: 'e\\n'",
                "x: standard output ['z'], expected ['a', 'b']",
            ],
            sandbox_check.exit_problems("x", 0, "") == [],
        ]
        self.assertEqual(plants, [True] * 11)

    def test_check_bubblewrap_judges_every_run_exactly(self) -> None:
        runs = ("version", "outside", "build-world", "build-release")
        names = {
            "version": "bwrap --version",
            "outside": "outside the sandbox",
            "build-world": "profile build-world",
            "build-release": "profile build-release",
        }
        goods = {
            "version": VERSION,
            "outside": OUTSIDE,
            "build-world": INSIDE,
            "build-release": INSIDE,
        }
        expected: dict[str, list[sandbox_check.Expected]] = {
            "version": [sandbox_check.VERSION_LINE],
            "outside": ["read_outside ok", "tcp_loopback ok", "unix_abstract ok"],
            "build-world": [
                f"{name} {want}" for name, want in sandbox_check.INSIDE_LINES.items()
            ],
            "build-release": [
                f"{name} {want}" for name, want in sandbox_check.INSIDE_LINES.items()
            ],
        }

        def answer(target: str | None, kind: str | None) -> list[str]:
            def run(
                argv: list[str], **_kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                name = "version" if "--version" in argv else "outside"
                code, out, err = (0, goods[name], "")
                if name == target and kind is not None:
                    code, out, err = _fault(goods[name], kind)
                return subprocess.CompletedProcess(argv, code, out, err)

            def sandbox(
                name: str,
                layout: launch.Layout,
                _command: list[str],
                timeout: float = 0,
            ) -> launch.SandboxResult:
                del timeout
                if name == "build-world":
                    self.assertTrue(
                        layout.scenario is not None and layout.scenario.is_file()
                    )
                    self.assertIsNone(layout.staging)
                else:
                    self.assertEqual(name, "build-release")
                    self.assertTrue(
                        layout.staging is not None and layout.staging.is_dir()
                    )
                    self.assertIsNone(layout.scenario)
                code, out, err = (0, goods[name], "")
                if name == target and kind is not None:
                    code, out, err = _fault(goods[name], kind)
                return launch.SandboxResult(code, out, err)

            with (
                patch.object(support.exposed(sandbox_check, "subprocess"), "run", run),
                patch.object(launch, "run_in_sandbox", sandbox),
            ):
                return sandbox_check.check_bubblewrap()

        self.assertEqual(answer(None, None), [])
        labels = []
        for target in runs:
            for kind in ("status", "stderr", "twice", "extra"):
                labels.append(f"{target}-{kind}")
                code, out, err = _fault(goods[target], kind)
                self.assertEqual(
                    answer(target, kind),
                    sandbox_check.output_problems(
                        names[target], code, out, err, expected[target]
                    ),
                )
        self.assertEqual(len(labels), 16)

    def test_check_extensions_judges_its_run_exactly(self) -> None:
        seen: list[launch.Layout] = []

        def sandbox(
            name: str, layout: launch.Layout, _command: list[str], timeout: float = 0
        ) -> launch.SandboxResult:
            del timeout
            self.assertEqual(name, "build-world")
            self.assertTrue(layout.scenario is not None and layout.scenario.is_file())
            self.assertEqual(layout.extensions, folder)
            seen.append(layout)
            return launch.SandboxResult(*held[0])

        held = [(0, LOAD, "")]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "ext"
            folder.mkdir()
            with patch.object(launch, "run_in_sandbox", sandbox):
                self.assertEqual(sandbox_check.check_extensions(folder), [])
                labels = []
                for kind in ("status", "stderr", "twice", "extra"):
                    labels.append(kind)
                    held[0] = _fault(LOAD, kind)
                    problems = sandbox_check.check_extensions(folder)
                    self.assertEqual(len(problems), 1)
                    self.assertTrue(problems[0].startswith("build-world: "))
                    code, out, err = held[0]
                    self.assertEqual(
                        problems,
                        sandbox_check.output_problems(
                            "build-world",
                            code,
                            out,
                            err,
                            list(sandbox_check.LOAD_LINES),
                        ),
                    )
        self.assertEqual(len(seen), 5)
        self.assertEqual(len(labels), 4)

    def test_runner_steps_judge_every_command_exactly(self) -> None:
        labels: list[str] = []
        for kind in ("status", "stderr", "twice", "extra"):
            labels.append(f"version-{kind}")
            self._facts(
                "bwrap --version",
                VERSION.replace("0.11.1", "0.9.0"),
                kind,
                [sandbox_check.VERSION_LINE],
            )
            labels.append(f"packages-{kind}")
            self._facts("dpkg-query", PACKAGES, kind, list(ci_sandbox.PACKAGE_LINES))
            labels.append(f"probe-{kind}")
            self._install("0\n", "probe", kind, [ci_sandbox.PROBE_ARGV])
            labels.append(f"install-{kind}")
            self._install(
                "1\n", "install", kind, [ci_sandbox.PROBE_ARGV, ci_sandbox.INSTALL_ARGV]
            )
            labels.append(f"parser-{kind}")
            self._install(
                "1\n",
                "apparmor_parser -r",
                kind,
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.INSTALL_ARGV,
                    ci_sandbox.PARSER_ARGV,
                ],
            )
            labels.append(f"after-{kind}")
            self._install(
                "1\n",
                "probe after",
                kind,
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.INSTALL_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.LISTING_ARGV,
                    ci_sandbox.PROBE_ARGV,
                ],
            )
        for kind in ("status", "stderr"):
            labels.append(f"listing-{kind}")
            self._grammar("aa-status --json", kind, support.LISTING_OK.stdout)
            labels.append(f"label-{kind}")
            self._grammar("label read", kind, support.LABEL_OK.stdout)
        self.assertEqual(len(labels), 28)

    def _facts(
        self, what: str, good: str, kind: str, expected: list[sandbox_check.Expected]
    ) -> None:
        code, out, err = _fault(good, kind)
        version = ci_sandbox.CommandResult(0, "bubblewrap 0.9.0\n", "")
        packages = ci_sandbox.CommandResult(0, PACKAGES, "")
        fault = ci_sandbox.CommandResult(code, out, err)
        if what == "bwrap --version":
            version = fault
        else:
            packages = fault
        runner = support.FakeRunner([version, packages])
        text = io.StringIO()
        status = ci_sandbox.facts(runner, _missing, text)
        self.assertEqual(status, 1)
        fails = [
            line for line in text.getvalue().splitlines() if line.startswith("FAIL ")
        ]
        self.assertEqual(
            fails,
            [
                "FAIL " + item
                for item in sandbox_check.output_problems(
                    what, code, out, err, expected
                )
            ],
        )
        self.assertEqual(
            runner.calls, [[tables.BWRAP, "--version"], ci_sandbox.PACKAGES_ARGV]
        )

    def _install(
        self, setting: str, what: str, kind: str, calls: list[list[str]]
    ) -> None:
        code, out, err = _fault("", kind)
        fault = ci_sandbox.CommandResult(code, out, err)
        queued = self._queue(what, fault)
        runner = support.FakeRunner(queued)
        files = support.FakeFiles(
            support.PINNED_BYTES, None, support.PINNED_BYTES, runner
        )
        text = io.StringIO()
        with support.pinned_profile():
            status = ci_sandbox.install_profile(
                ci_sandbox.HOSTED_RUNNER,
                runner,
                files,
                lambda path: setting if path == ci_sandbox.SYSCTL else _missing(path),
                text,
                io.StringIO(),
            )
        self.assertEqual(status, 1)
        fails = [
            line for line in text.getvalue().splitlines() if line.startswith("FAIL ")
        ]
        shown = "probe" if what == "probe" else what
        expected = [
            "FAIL " + item
            for item in sandbox_check.output_problems(shown, code, out, err, [])
        ]
        if setting.strip() != "1":
            expected.append(
                "FAIL namespace creation fails while the restriction reads "
                f"{setting.strip()}; this step handles only the AppArmor restriction"
            )
        self.assertEqual(fails, expected)
        self.assertEqual(runner.calls, calls)

    def _queue(
        self, what: str, fault: ci_sandbox.CommandResult
    ) -> list[ci_sandbox.CommandResult]:
        if what == "probe":
            return [fault]
        if what == "install":
            return [support.OK, fault]
        if what == "apparmor_parser -r":
            return [support.OK, support.OK, fault]
        return [support.OK, support.OK, support.OK, support.LISTING_OK, fault]

    def _grammar(self, what: str, kind: str, good: str) -> None:
        if kind == "status":
            fault = ci_sandbox.CommandResult(1, good, "")
        else:
            fault = ci_sandbox.CommandResult(0, good, "x\n")
        if what == "aa-status --json":
            queued = [support.OK, support.OK, support.OK, fault]
            calls = [
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.INSTALL_ARGV,
                ci_sandbox.PARSER_ARGV,
                ci_sandbox.LISTING_ARGV,
            ]
        else:
            queued = [
                support.OK,
                support.OK,
                support.OK,
                support.LISTING_OK,
                support.OK,
                fault,
            ]
            calls = [
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.INSTALL_ARGV,
                ci_sandbox.PARSER_ARGV,
                ci_sandbox.LISTING_ARGV,
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.LABEL_ARGV,
            ]
        runner = support.FakeRunner(queued)
        files = support.FakeFiles(
            support.PINNED_BYTES, None, support.PINNED_BYTES, runner
        )
        text = io.StringIO()
        with support.pinned_profile():
            status = ci_sandbox.install_profile(
                ci_sandbox.HOSTED_RUNNER,
                runner,
                files,
                lambda path: "1\n" if path == ci_sandbox.SYSCTL else _missing(path),
                text,
                io.StringIO(),
            )
        self.assertEqual(status, 1)
        fails = [
            line for line in text.getvalue().splitlines() if line.startswith("FAIL ")
        ]
        self.assertEqual(len(fails), 1)
        self.assertTrue(fails[0].startswith(f"FAIL {what}: "))
        self.assertEqual(runner.calls, calls)
