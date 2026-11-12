"""Runner steps and workflow rules. No sandbox is started."""

from __future__ import annotations

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

    def test_restriction_on_installs_the_profile_then_probes(self) -> None:
        text, calls = self._success(
            (support.PINNED_BYTES, None, support.PINNED_BYTES),
            [
                ci_sandbox.CommandResult(
                    1, "", "bwrap: setting up uid map: Permission denied\n"
                ),
                support.OK,
                support.OK,
                support.LISTING_OK,
                support.OK,
                support.LABEL_OK,
            ],
        )
        self.assertEqual(
            calls,
            [
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.INSTALL_ARGV,
                ci_sandbox.PARSER_ARGV,
                ci_sandbox.LISTING_ARGV,
                ci_sandbox.PROBE_ARGV,
                ci_sandbox.LABEL_ARGV,
            ],
        )
        self._assert_force(text, calls)

    def test_profile_already_present_is_reloaded_not_copied(self) -> None:
        _text_out, calls = self._success(
            (support.PINNED_BYTES, support.PINNED_BYTES, None),
            [
                ci_sandbox.CommandResult(
                    1, "", "bwrap: setting up uid map: Permission denied\n"
                ),
                support.OK,
                support.LISTING_OK,
                support.OK,
                support.LABEL_OK,
            ],
        )
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

    def test_failures_fail_the_job(self) -> None:
        denied = "bwrap: setting up uid map: Permission denied\n"
        plants = [
            (
                "a",
                "1\n",
                (None, None, None),
                [support.OK],
                [ci_sandbox.PROBE_ARGV],
                [
                    f"FAIL profile file not found: {ci_sandbox.PROFILE_SOURCE}",
                ],
            ),
            (
                "b",
                "1\n",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [support.OK, ci_sandbox.CommandResult(1, "", "denied\n")],
                [ci_sandbox.PROBE_ARGV, ci_sandbox.INSTALL_ARGV],
                [
                    "FAIL install: exit status 1, expected 0",
                    "FAIL install: standard error is not empty: 'denied\\n'",
                ],
            ),
            (
                "c",
                "1\n",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [
                    support.OK,
                    support.OK,
                    ci_sandbox.CommandResult(1, "", "syntax error\n"),
                ],
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
                "d",
                "1\n",
                (support.PINNED_BYTES, None, None),
                [support.OK, support.OK],
                [ci_sandbox.PROBE_ARGV, ci_sandbox.INSTALL_ARGV],
                [
                    f"FAIL profile file not found after the install: {ci_sandbox.PROFILE_TARGET}",
                ],
            ),
            (
                "e",
                "1\n",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [
                    support.OK,
                    support.OK,
                    support.OK,
                    ci_sandbox.CommandResult(
                        4, "", "aa-status: not enough privileges\n"
                    ),
                ],
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.INSTALL_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.LISTING_ARGV,
                ],
                [
                    "FAIL aa-status --json: exit status 4, expected 0",
                    "FAIL aa-status --json: standard error is not empty: 'aa-status: not enough privileges\\n'",
                    "FAIL aa-status --json did not print exactly one line: ''",
                ],
            ),
            (
                "f",
                "1\n",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [
                    support.OK,
                    support.OK,
                    support.OK,
                    support.LISTING_OK,
                    ci_sandbox.CommandResult(1, "", "bwrap: uid map\n"),
                ],
                [
                    ci_sandbox.PROBE_ARGV,
                    ci_sandbox.INSTALL_ARGV,
                    ci_sandbox.PARSER_ARGV,
                    ci_sandbox.LISTING_ARGV,
                    ci_sandbox.PROBE_ARGV,
                ],
                [
                    "FAIL probe after: exit status 1, expected 0",
                    "FAIL probe after: standard error is not empty: 'bwrap: uid map\\n'",
                ],
            ),
            (
                "g",
                "0\n",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [ci_sandbox.CommandResult(1, "", "bwrap: x\n")],
                [ci_sandbox.PROBE_ARGV],
                [
                    "FAIL probe: exit status 1, expected 0",
                    "FAIL probe: standard error is not empty: 'bwrap: x\\n'",
                    "FAIL namespace creation fails while the restriction reads 0; this step handles only the AppArmor restriction",
                ],
            ),
            (
                "h",
                "absent",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [ci_sandbox.CommandResult(1, "", "bwrap: x\n")],
                [ci_sandbox.PROBE_ARGV],
                [
                    "FAIL probe: exit status 1, expected 0",
                    "FAIL probe: standard error is not empty: 'bwrap: x\\n'",
                    "FAIL namespace creation fails while the restriction reads absent; this step handles only the AppArmor restriction",
                ],
            ),
            (
                "i",
                "0\n",
                (support.PINNED_BYTES, None, support.PINNED_BYTES),
                [ci_sandbox.CommandResult(0, "x\n", "")],
                [ci_sandbox.PROBE_ARGV],
                [
                    "FAIL probe: standard output ['x'], expected []",
                    "FAIL namespace creation fails while the restriction reads 0; this step handles only the AppArmor restriction",
                ],
            ),
        ]
        del denied
        labels = []
        with support.pinned_profile():
            for name, setting, files, results, calls, fails in plants:
                labels.append(name)
                runner = support.FakeRunner(results)
                out = io.StringIO()
                read = (
                    _missing
                    if setting == "absent"
                    else (
                        lambda path, setting=setting: (
                            setting if path == ci_sandbox.SYSCTL else _missing(path)
                        )
                    )
                )
                status = ci_sandbox.install_profile(
                    HOSTED,
                    runner,
                    support.FakeFiles(*files, runner),
                    read,
                    out,
                    io.StringIO(),
                )
                self.assertEqual(status, 1, name)
                self.assertEqual(runner.calls, calls, name)
                self.assertEqual(
                    [
                        line
                        for line in out.getvalue().splitlines()
                        if line.startswith("FAIL ")
                    ],
                    fails,
                    name,
                )
                if name == "i":
                    self.assertIn("restriction: 0", out.getvalue().splitlines())
        self.assertEqual(labels, list("abcdefghi"))

    def test_no_system_wide_switch_anywhere(self) -> None:
        ci = _text(ROOT / "scripts/ci_sandbox.py")
        apparmor = _text(ROOT / "scripts/ci_apparmor.py")
        junit = _text(ROOT / "scripts/ci_junit.py")
        job = _text(ROOT / ".github/workflows/sandbox.yml")
        self.assertEqual(workflow.check_ci_module(ci), [])
        self.assertEqual(workflow.check_ci_module(apparmor), [])
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
        self.assertNotIn(workflow.SETTING_WORD, apparmor)
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
        with support.pinned_profile():
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
        self.assertEqual(
            lines[2:8],
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
            lines[-1], "namespace creation works with the per-binary profile in force"
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
