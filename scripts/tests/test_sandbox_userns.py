"""Runner steps and workflow rules. No sandbox is started."""

from __future__ import annotations

import hashlib
import io
import sys
import unittest
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support
import sandbox_workflow as workflow

import ci_sandbox
import sandbox_check
import sandbox_profiles as tables

ROOT = support.ROOT
HOSTED = dict(ci_sandbox.HOSTED_RUNNER)
USAGE = "ci_sandbox: usage: facts | install-profile | prove\n"
DENIED = ci_sandbox.CommandResult(
    1, "", "bwrap: setting up uid map: Permission denied\n"
)
REFUSAL = "ci_sandbox: install-profile runs only on a GitHub-hosted runner; nothing was changed\n"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _missing(path: Path) -> NoReturn:
    raise FileNotFoundError(path)


class RunnerRules(unittest.TestCase):
    def test_facts_lines(self) -> None:
        version = ci_sandbox.CommandResult(0, "bubblewrap 0.9.0\n", "")
        packages = ci_sandbox.CommandResult(
            0,
            "apparmor 4.0.1\napparmor-profiles 4.0.1\nbubblewrap 0.9.0-1ubuntu0.3\n",
            "",
        )
        present = {
            ci_sandbox.OS_RELEASE: 'PRETTY_NAME="Ubuntu 24.04.5 LTS"\n',
            ci_sandbox.SYSCTL: "1\n",
            ci_sandbox.APPARMOR_ENABLED: "Y\n",
        }
        with patch.object(
            support.exposed(ci_sandbox, "platform"),
            "release",
            return_value="7.0.0-test",
        ):
            runner = support.FakeRunner([version, packages])
            out = io.StringIO()
            status = ci_sandbox.facts(runner, lambda path: present[path], out)
            self.assertEqual(status, 0)
            self.assertEqual(
                out.getvalue().splitlines(),
                [
                    "os: Ubuntu 24.04.5 LTS",
                    "kernel: 7.0.0-test",
                    "restriction setting: 1",
                    "apparmor enabled: Y",
                    "bubblewrap: bubblewrap 0.9.0",
                    "package: apparmor 4.0.1",
                    "package: apparmor-profiles 4.0.1",
                    "package: bubblewrap 0.9.0-1ubuntu0.3",
                ],
            )
            denied = ci_sandbox.CommandResult(
                1,
                "apparmor 4.0.1\nbubblewrap 0.9.0\n",
                "dpkg-query: no packages found matching apparmor-profiles\n",
            )
            runner = support.FakeRunner([version, denied])
            out = io.StringIO()
            status = ci_sandbox.facts(runner, _missing, out)
            self.assertEqual(status, 1)
            problems = sandbox_check.output_problems(
                "dpkg-query",
                denied.returncode,
                denied.stdout,
                denied.stderr,
                list(ci_sandbox.PACKAGE_LINES),
            )
            self.assertEqual(
                out.getvalue().splitlines(),
                [
                    "os: unknown",
                    "kernel: 7.0.0-test",
                    "restriction setting: absent",
                    "apparmor enabled: unknown",
                    "bubblewrap: bubblewrap 0.9.0",
                    "package: apparmor 4.0.1",
                    "package: bubblewrap 0.9.0",
                    *[f"FAIL {problem}" for problem in problems],
                ],
            )
            self.assertEqual(
                runner.calls, [[tables.BWRAP, "--version"], ci_sandbox.PACKAGES_ARGV]
            )

    def test_install_profile_refuses_outside_a_hosted_runner(self) -> None:
        environments = [
            {},
            {"GITHUB_ACTIONS": "true"},
            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"},
            {"GITHUB_ACTIONS": "True", "RUNNER_ENVIRONMENT": "github-hosted"},
            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "GitHub-hosted"},
            {"RUNNER_ENVIRONMENT": "github-hosted"},
        ]
        for index, environ in enumerate(environments, start=1):
            runner = support.FakeRunner([])
            out, err = io.StringIO(), io.StringIO()
            status = ci_sandbox.install_profile(
                environ, runner, _missing, _missing, out, err
            )
            self.assertEqual(status, 2, index)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(err.getvalue(), REFUSAL)
            self.assertEqual(runner.calls, [])
        self.assertEqual(index, 6)
        runner = support.FakeRunner([support.OK])
        out, err = io.StringIO(), io.StringIO()
        status = ci_sandbox.install_profile(
            HOSTED, runner, _missing, _missing, out, err
        )
        self.assertEqual(status, 0)
        captured = io.StringIO()
        with patch.object(sys, "stderr", captured):
            self.assertEqual(ci_sandbox.main([]), 2)
            self.assertEqual(ci_sandbox.main(["x"]), 2)
        self.assertEqual(captured.getvalue(), USAGE + USAGE)

    def test_restriction_absent_or_zero_installs_nothing(self) -> None:
        for value, label in (("absent", "absent"), ("0\n", "0")):
            runner = support.FakeRunner([support.OK])
            out = io.StringIO()
            read = (
                _missing
                if value == "absent"
                else (
                    lambda path, value=value: (
                        value if path == ci_sandbox.SYSCTL else _missing(path)
                    )
                )
            )
            status = ci_sandbox.install_profile(
                HOSTED, runner, _missing, read, out, io.StringIO()
            )
            self.assertEqual(status, 0)
            self.assertEqual(runner.calls, [ci_sandbox.PROBE_ARGV])
            self.assertEqual(
                out.getvalue().splitlines(),
                [
                    f"restriction: {label}",
                    "probe before: exit 0, standard error ''",
                    "namespace creation works; nothing to install",
                ],
            )

    def test_restriction_on_with_passing_probe_installs_nothing(self) -> None:
        runner = support.FakeRunner([support.OK])
        out = io.StringIO()
        status = ci_sandbox.install_profile(
            HOSTED, runner, _missing, lambda _path: "1\n", out, io.StringIO()
        )
        self.assertEqual(status, 0)
        self.assertEqual(runner.calls, [ci_sandbox.PROBE_ARGV])
        self.assertEqual(
            out.getvalue().splitlines(),
            [
                "restriction: 1",
                "probe before: exit 0, standard error ''",
                "namespace creation works; nothing to install",
            ],
        )

    def test_restriction_on_installs_the_profile_then_probes(self) -> None:
        text, calls = self._success(
            (support.PROFILE_BYTES, None, support.PROFILE_BYTES),
            [
                DENIED,
                support.OK,
                support.OK,
                support.OK,
                support.LISTING_OK,
                support.LABEL_OK,
            ],
        )
        self.assertEqual(
            calls,
            [
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.INSTALL_ARGV,
                ci_sandbox.PARSER_ARGV,
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.LISTING_ARGV,
                ci_sandbox.LABEL_ARGV,
            ],
        )
        self._assert_force(text, calls)

    def test_profile_already_present_is_reloaded_not_copied(self) -> None:
        source, target = b"new distribution profile\n", b"existing different profile\n"
        text, calls = self._success(
            (source, target, None),
            [DENIED, support.OK, support.OK, support.LISTING_OK, support.LABEL_OK],
        )
        self.assertEqual(
            calls,
            [
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.PARSER_ARGV,
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.LISTING_ARGV,
                ci_sandbox.LABEL_ARGV,
            ],
        )
        for path, data in (
            (ci_sandbox.PROFILE_SOURCE, source),
            (ci_sandbox.PROFILE_TARGET, target),
        ):
            self.assertIn(
                f"profile file {path}: {len(data)} bytes, SHA-256 "
                f"{hashlib.sha256(data).hexdigest()}",
                text,
            )

    def test_record_commands_never_decide_the_result(self) -> None:
        for record in ("listing", "label"):
            for fault in (
                ci_sandbox.CommandResult(4, "", "record denied\n"),
                ci_sandbox.CommandResult(0, "not parseable\nextra\n", ""),
                ci_sandbox.CommandResult(0, "", "warning\n"),
            ):
                with self.subTest(record=record, fault=fault):
                    listing = fault if record == "listing" else support.LISTING_OK
                    label = fault if record == "label" else support.LABEL_OK
                    text, calls = self._success(
                        (support.PROFILE_BYTES, None, support.PROFILE_BYTES),
                        [DENIED, support.OK, support.OK, support.OK, listing, label],
                    )
                    self.assertEqual(
                        calls,
                        [
                            ci_sandbox.PROBE_ARGV,
                            ci_sandbox.INSTALL_ARGV,
                            ci_sandbox.PARSER_ARGV,
                            ci_sandbox.PROBE_ARGV,
                            ci_sandbox.LISTING_ARGV,
                            ci_sandbox.LABEL_ARGV,
                        ],
                    )
                    name = "aa-status --json" if record == "listing" else "label"
                    self.assertIn(f"{name} raw: exit {fault.returncode}", text)
                    self.assertIn(f"{name} raw stdout: {fault.stdout!r}", text)
                    self.assertIn(f"{name} raw stderr: {fault.stderr!r}", text)
                    self.assertNotIn("FAIL ", text)

    def test_failures_fail_the_job(self) -> None:
        files = (support.PROFILE_BYTES, None, support.PROFILE_BYTES)
        plants = [
            (
                "source missing",
                "1",
                (None, None, None),
                [DENIED],
                [ci_sandbox.PROBE_ARGV],
                [f"FAIL profile file not found: {ci_sandbox.PROFILE_SOURCE}"],
            ),
            (
                "install fails",
                "1",
                files,
                [DENIED, ci_sandbox.CommandResult(1, "", "denied\n")],
                [ci_sandbox.PROBE_ARGV, ci_sandbox.INSTALL_ARGV],
                [
                    "FAIL install: exit status 1, expected 0",
                    "FAIL install: standard error is not empty: 'denied\\n'",
                ],
            ),
            (
                "parser fails",
                "1",
                files,
                [DENIED, support.OK, ci_sandbox.CommandResult(1, "", "syntax error\n")],
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.INSTALL_ARGV,
                    ci_sandbox.PARSER_ARGV,
                ],
                [
                    "FAIL apparmor_parser -r: exit status 1, expected 0",
                    "FAIL apparmor_parser -r: standard error is not empty: 'syntax error\\n'",
                ],
            ),
            (
                "installed file missing",
                "1",
                (support.PROFILE_BYTES, None, None),
                [DENIED, support.OK],
                [ci_sandbox.PROBE_ARGV, ci_sandbox.INSTALL_ARGV],
                [
                    f"FAIL profile file not found after the install: {ci_sandbox.PROFILE_TARGET}"
                ],
            ),
            (
                "probe after fails",
                "1",
                files,
                [DENIED, support.OK, support.OK, DENIED],
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.INSTALL_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.PROBE_ARGV,
                ],
                [
                    "FAIL probe after: exit status 1, expected 0",
                    f"FAIL probe after: standard error is not empty: {DENIED.stderr!r}",
                ],
            ),
        ]
        for setting, result in (
            ("0", DENIED),
            ("absent", DENIED),
            ("0", ci_sandbox.CommandResult(0, "x\n", "")),
        ):
            problems = sandbox_check.output_problems(
                "probe", result.returncode, result.stdout, result.stderr, []
            )
            plants.append(
                (
                    f"probe fails with {setting}",
                    setting,
                    files,
                    [result],
                    [ci_sandbox.PROBE_ARGV],
                    [
                        *[f"FAIL {problem}" for problem in problems],
                        "FAIL namespace creation fails while the restriction reads "
                        f"{setting}; this step handles only the AppArmor restriction",
                    ],
                )
            )
        for name, setting, data, results, calls, fails in plants:
            with self.subTest(rule=name):
                runner = support.FakeRunner(results)
                out = io.StringIO()
                read = (
                    _missing
                    if setting == "absent"
                    else lambda _path, setting=setting: setting
                )
                status = ci_sandbox.install_profile(
                    HOSTED,
                    runner,
                    support.FakeFiles(*data, runner),
                    read,
                    out,
                    io.StringIO(),
                )
                self.assertEqual(status, 1)
                self.assertEqual(runner.calls, calls)
                self.assertEqual(
                    [
                        line
                        for line in out.getvalue().splitlines()
                        if line.startswith("FAIL ")
                    ],
                    fails,
                )

    def test_first_probe_requires_exact_success(self) -> None:
        for result in (
            ci_sandbox.CommandResult(0, "unexpected\n", ""),
            ci_sandbox.CommandResult(0, "", "warning\n"),
        ):
            with self.subTest(result=result):
                _text_out, calls = self._success(
                    (support.PROFILE_BYTES, None, support.PROFILE_BYTES),
                    [
                        result,
                        support.OK,
                        support.OK,
                        support.OK,
                        support.LISTING_OK,
                        support.LABEL_OK,
                    ],
                )
                self.assertIn(ci_sandbox.INSTALL_ARGV, calls)

    def test_no_system_wide_switch_anywhere(self) -> None:
        ci = _text(ROOT / "scripts/ci_sandbox.py")
        junit = _text(ROOT / "scripts/ci_junit.py")
        job = _text(ROOT / ".github/workflows/sandbox.yml")
        self.assertEqual(workflow.check_ci_module(ci), [])
        self.assertEqual(workflow.check_ci_module(junit), [])
        self.assertEqual(workflow.check_no_switch(job), [])
        labels = []
        for word in workflow.FORBIDDEN_WORDS:
            labels.append(word)
            plant = f"\n# {word}\n"
            self.assertEqual(
                workflow.check_ci_module(ci + plant), [f"forbidden: {word}"]
            )
            self.assertEqual(
                workflow.check_no_switch(job + plant), [f"forbidden: {word}"]
            )
        labels.append("setting")
        setting = "\n# kernel.apparmor_restrict_unprivileged_userns\n"
        self.assertEqual(
            workflow.check_ci_module(ci + setting),
            ["forbidden: apparmor_restrict_unprivileged_userns"],
        )
        structural = {
            "a": (
                '\n\ndef planted() -> None:\n    SYSCTL.write_text("0")\n',
                [
                    "forbidden: SYSCTL used in planted",
                    "forbidden: write_text in planted",
                ],
            ),
            "b": (
                '\nOFF = ["sudo", "systemctl", "stop", "apparmor"]\n',
                [
                    "forbidden: sudo outside INSTALL_ARGV, PARSER_ARGV, LISTING_ARGV",
                    "forbidden: systemctl",
                ],
            ),
            "c": (
                '\nEXTRA_ARGV = ["sudo", "true"]\n',
                [
                    "forbidden: sudo outside INSTALL_ARGV, PARSER_ARGV, LISTING_ARGV",
                ],
            ),
            "d": (
                '\n\ndef planted() -> None:\n    subprocess.run("true", shell=True)\n',
                [
                    "forbidden: shell=True in planted",
                    "forbidden: subprocess.run in planted",
                ],
            ),
            "e": (
                '\n\ndef planted() -> None:\n    os.system("true")\n',
                ["forbidden: os.system in planted"],
            ),
            "f": (
                '\n\ndef planted() -> None:\n    open("/x", "w")\n',
                ["forbidden: open in planted"],
            ),
            "g": (
                '\n\ndef planted() -> None:\n    Path("/x").write_bytes(b"")\n',
                ["forbidden: write_bytes in planted"],
            ),
            "h": (
                "\n\ndef planted() -> None:\n    return str(SYSCTL)\n",
                ["forbidden: SYSCTL used in planted"],
            ),
        }
        for name, (plant, want) in structural.items():
            labels.append(name)
            self.assertEqual(workflow.check_ci_module(ci + plant), want, name)
        self.assertEqual(len(labels), 22)
        self.assertEqual(ci.count(workflow.SETTING_WORD), 1)
        self.assertTrue(
            any(
                line.startswith(workflow.SETTING_LINE_START) for line in ci.splitlines()
            )
        )
        self.assertNotIn(workflow.SETTING_WORD, junit)

    def test_workflow_rules(self) -> None:
        job = _text(ROOT / ".github/workflows/sandbox.yml")
        version = (
            _text(ROOT / "pyproject.toml")
            .split('required-version = "==', 1)[1]
            .split('"', 1)[0]
        )
        series = _text(ROOT / ".python-version").strip()
        self.assertEqual(workflow.check_workflow(job, version, series), [])
        bars = "||"
        plants = [
            (
                job.replace("ubuntu-24.04", "ubuntu-latest", 1),
                [
                    "workflow: runs-on is not ubuntu-24.04",
                    "workflow: forbidden: ubuntu-latest",
                ],
            ),
            (
                job.replace(
                    "timeout-minutes: 30\n",
                    "timeout-minutes: 30\n      continue-on-error: true\n",
                    1,
                ),
                [
                    "workflow: forbidden: continue-on-error",
                ],
            ),
            (
                job.replace(
                    "timeout-minutes: 30\n",
                    "timeout-minutes: 30\n      if: always()\n",
                    1,
                ),
                ["workflow: forbidden: if:"],
            ),
            (
                job.replace(
                    "timeout-minutes: 30\n", "timeout-minutes: 30\n    needs: x\n", 1
                ),
                ["workflow: forbidden: needs:"],
            ),
            (
                job.replace(
                    "timeout-minutes: 30\n", "timeout-minutes: 30\n    paths:\n", 1
                ),
                ["workflow: forbidden: paths:"],
            ),
            (
                job.replace(
                    "uv python install 3.14",
                    "uv python install 3.14 " + bars + " true",
                    1,
                ),
                [
                    "workflow: forbidden: " + bars,
                    "workflow: run steps differ",
                ],
            ),
            (
                job.replace(
                    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                    "actions/checkout@v4",
                    1,
                ),
                [
                    "workflow: action not pinned by commit: actions/checkout@v4",
                ],
            ),
            (
                job.replace("contents: read", "contents: write", 1),
                ["workflow: permissions are not exactly contents read"],
            ),
            (
                job.replace("    timeout-minutes: 30\n", "", 1),
                ["workflow: no timeout-minutes"],
            ),
            (
                job.replace("      - main", "      - dev", 1),
                ["workflow: missing trigger push to main"],
            ),
            (
                job.replace(
                    "        run: uv run --locked python scripts/ci_sandbox.py prove\n",
                    "",
                    1,
                ),
                [
                    "workflow: run steps differ",
                ],
            ),
            (
                job.replace('version: "0.11.31"', 'version: "0.11.32"', 1),
                [
                    "workflow: uv version differs from required-version",
                ],
            ),
            (job + "  other:\n    steps: []\n", ["workflow: expected exactly one job"]),
            (
                job.replace(
                    "        run: uv python install 3.14\n",
                    "        run: uv python install 3.14\n        env:\n          X: y\n",
                    1,
                ),
                [
                    "workflow: forbidden: env:",
                ],
            ),
            (
                job.replace(
                    "        run: uv python install 3.14\n",
                    "        run: uv python install 3.14\n        shell: bash\n",
                    1,
                ),
                [
                    "workflow: forbidden: shell:",
                ],
            ),
            (
                job.replace(
                    "        run: uv python install 3.14\n",
                    "        run: uv python install 3.14\n        working-directory: web\n",
                    1,
                ),
                [
                    "workflow: forbidden: working-directory:",
                ],
            ),
            (
                job.replace(
                    "    timeout-minutes: 30\n",
                    "    timeout-minutes: 30\n    permissions:\n      contents: write\n",
                    1,
                ),
                [
                    "workflow: expected exactly one permissions block",
                ],
            ),
        ]
        self.assertEqual(len(plants), 17)
        for index, (text, want) in enumerate(plants, start=1):
            self.assertEqual(
                workflow.check_workflow(text, version, series), want, index
            )

    def _success(
        self,
        files: tuple[bytes | None, bytes | None, bytes | None],
        results: list[ci_sandbox.CommandResult],
    ) -> tuple[str, list[list[str]]]:
        runner = support.FakeRunner(results)
        out = io.StringIO()
        status = ci_sandbox.install_profile(
            HOSTED,
            runner,
            support.FakeFiles(*files, runner),
            lambda path: "1\n" if path == ci_sandbox.SYSCTL else _missing(path),
            out,
            io.StringIO(),
        )
        self.assertEqual(status, 0)
        return out.getvalue(), runner.calls

    def _assert_force(self, text: str, calls: list[list[str]]) -> None:
        lines = text.splitlines()
        self.assertEqual(lines[0], "restriction: 1")
        self.assertEqual(
            lines[1],
            "probe before: exit 1, standard error 'bwrap: setting up uid map: Permission denied\\n'",
        )
        for index, path in enumerate(
            (ci_sandbox.PROFILE_SOURCE, ci_sandbox.PROFILE_TARGET), start=2
        ):
            self.assertEqual(
                lines[index],
                f"profile file {path}: {len(support.PROFILE_BYTES)} bytes, SHA-256 "
                f"{hashlib.sha256(support.PROFILE_BYTES).hexdigest()}",
            )
        self.assertEqual(
            lines[4:10],
            [
                "aa-status --json raw: exit 0",
                f"aa-status --json raw stdout: {support.LISTING_OK.stdout!r}",
                "aa-status --json raw stderr: ''",
                "label raw: exit 0",
                f"label raw stdout: {support.LABEL_OK.stdout!r}",
                "label raw stderr: ''",
            ],
        )
        self.assertEqual(
            lines[-1], "namespace creation works after loading the per-binary profile"
        )
        sudo = [call for call in calls if call and call[0] == "sudo"]
        allowed = [
            ci_sandbox.INSTALL_ARGV,
            ci_sandbox.PARSER_ARGV,
            ci_sandbox.LISTING_ARGV,
        ]
        self.assertTrue(all(call in allowed for call in sudo))
        banned = ("sysctl", "tee", "aa-disable", "aa-complain")
        for call in calls:
            joined = " ".join(call)
            for word in banned:
                self.assertNotIn(word, joined)
