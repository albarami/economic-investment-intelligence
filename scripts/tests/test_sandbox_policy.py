"""Mount policy and the blocking enforcement command."""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_golden as golden
import sandbox_support as support
from test_sandbox_argv import COMMAND, golden_layout

import sandbox_check
import sandbox_launch as launch
import sandbox_policy
import sandbox_profiles as tables


def _streams(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
        status = sandbox_check.main(argv)
    return status, out.getvalue(), err.getvalue()


class EnforcementRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        support.require_environment(cls)
        support.require_engine(cls)

    def test_check_enforcement_reports_policy_and_blocks_failure(self) -> None:
        seen: list[tuple[str, launch.SandboxResult]] = []
        commands: list[list[str]] = []
        real = launch.run_in_sandbox
        real_run = subprocess.run

        def wrapped_run(
            argv: Sequence[str],
            *,
            env: Mapping[str, str],
            capture_output: bool,
            text: Literal[True],
            check: bool,
        ) -> subprocess.CompletedProcess[str]:
            commands.append([str(part) for part in argv])
            return real_run(
                list(argv),
                env=dict(env),
                capture_output=capture_output,
                text=text,
                check=check,
            )

        def wrapped(
            name: str,
            layout: launch.Layout,
            command: Sequence[str],
            *,
            timeout: float = tables.TIMEOUT_SECONDS,
            venv: Path | None = None,
        ) -> launch.SandboxResult:
            result = real(name, layout, command, timeout=timeout, venv=venv)
            seen.append((name, result))
            return result

        with (
            patch.object(launch, "run_in_sandbox", wrapped),
            patch.object(
                support.exposed(sandbox_check, "subprocess"), "run", wrapped_run
            ),
        ):
            status, out, err = _streams(["check-enforcement"])
        self.assertEqual((status, err), (0, ""))
        lines = out.splitlines()
        self.assertRegex(lines[0], r"version: bubblewrap [0-9]+\.[0-9]+\.[0-9]+")
        self.assertEqual(
            lines[1:],
            [
                "outside: OK",
                "profile build-world sentinel: OK",
                "profile build-world mounts: OK",
                "profile build-release sentinel: OK",
                "profile build-release mounts: OK",
                "extensions: OK",
                "sandbox enforcement: OK",
            ],
        )
        self.assertNotIn("FAIL", out)
        self.assertTrue(any("--version" in command for command in commands))
        self.assertTrue(
            any(
                "read_outside" in command and "tcp_loopback" in command
                for command in commands
            )
        )
        self.assertEqual(
            [name for name, _result in seen],
            ["build-world", "build-release", "build-world"],
        )
        for _name, result in seen[:2]:
            self.assertIn("read_outside error FileNotFoundError ENOENT", result.stdout)
            self.assertIn(
                "tcp_loopback error ConnectionRefusedError ECONNREFUSED", result.stdout
            )
            self.assertIn(
                "unix_abstract error ConnectionRefusedError ECONNREFUSED",
                result.stdout,
            )
        self.assertIn("LOAD spatial ok", seen[2][1].stdout)

        real_argv = launch.build_argv

        def drop_net(
            profile: tables.Profile,
            layout: launch.Layout,
            interpreter: launch.Interpreter,
            command: Sequence[str],
            descriptors: Mapping[Path, int],
        ) -> list[str]:
            built = real_argv(profile, layout, interpreter, command, descriptors)
            return [token for token in built if token != "--unshare-net"]

        with patch.object(launch, "build_argv", drop_net):
            failed, failed_out, failed_err = _streams(["check-enforcement"])
        self.assertEqual(failed_err, "")
        self.assertEqual(failed, 1)
        failed_lines = failed_out.splitlines()
        self.assertEqual(failed_lines[-1], "sandbox enforcement: FAILED")
        self.assertIn(
            "FAIL profile build-world mounts: network: missing, expected unshared",
            failed_lines,
        )
        self.assertIn(
            "FAIL profile build-release mounts: network: missing, expected unshared",
            failed_lines,
        )


def _item(
    profile_name: str, argv: list[str] | None = None
) -> sandbox_policy.PolicyInput:
    profile, layout, interpreter, descriptors = golden_layout(profile_name)
    if argv is None:
        argv = launch.build_argv(profile, layout, interpreter, COMMAND, descriptors)
    return sandbox_policy.PolicyInput(profile, layout, interpreter, argv)


def _replace(argv: list[str], destination: str, option: str) -> list[str]:
    index = argv.index(destination)
    found = list(argv)
    found[index - 2] = option
    return found


def _drop_option(argv: list[str], option: str, destination: str) -> list[str]:
    index = 0
    found = list(argv)
    while index < len(found) - 1:
        if found[index] == option and found[index + 1] == destination:
            del found[index : index + 2]
            return found
        index += 1
    raise AssertionError(option)


class PolicyRules(unittest.TestCase):
    def test_both_profiles_match_the_normalized_sequence(self) -> None:
        for name, golden_argv in (
            ("build-world", golden.GOLDEN_WORLD),
            ("build-release", golden.GOLDEN_RELEASE),
        ):
            item = _item(name)
            self.assertEqual(item.argv, golden_argv)
            self.assertEqual(
                sandbox_policy.normalize(item), sandbox_policy.expected_mounts(item)
            )
            self.assertEqual(sandbox_policy.judge(item).problems, ())
            for record in sandbox_policy.normalize(item):
                self.assertNotIn("/", record.role)
                self.assertNotIn("/", record.mode)

    def test_descriptors_and_temporary_paths_are_roles(self) -> None:
        profile, layout, interpreter, descriptors = golden_layout("build-world")
        renumbered = {path: 3 for path in descriptors}
        argv = launch.build_argv(profile, layout, interpreter, COMMAND, renumbered)
        item = sandbox_policy.PolicyInput(profile, layout, interpreter, argv)
        self.assertEqual(sandbox_policy.judge(item).problems, ())
        cache = Path("/tmp/eii-cache")
        vault = Path("/tmp/eii-vault")
        moved = launch.Layout(
            layout.code_root,
            cache,
            vault,
            layout.extensions,
            None,
            layout.scenario,
        )
        paths = launch.bound_paths(profile, moved, interpreter)
        numbers = {path: 10 + index for index, path in enumerate(paths)}
        moved_argv = launch.build_argv(profile, moved, interpreter, COMMAND, numbers)
        moved_item = sandbox_policy.PolicyInput(profile, moved, interpreter, moved_argv)
        self.assertEqual(sandbox_policy.judge(moved_item).problems, ())
        shown = " ".join(
            f"{record.role} {record.mode}"
            for record in sandbox_policy.normalize(moved_item)
        )
        self.assertNotIn("/tmp", shown)
        self.assertIn("public cache read-only", shown)
        self.assertIn("vault writable", shown)
        release, release_layout, release_interpreter, _descriptors = golden_layout(
            "build-release"
        )
        staged = launch.Layout(
            release_layout.code_root,
            cache,
            vault,
            release_layout.extensions,
            Path("/tmp/eii-staging"),
            None,
        )
        staged_paths = launch.bound_paths(release, staged, release_interpreter)
        staged_numbers = {path: 10 + index for index, path in enumerate(staged_paths)}
        staged_argv = launch.build_argv(
            release, staged, release_interpreter, COMMAND, staged_numbers
        )
        staged_item = sandbox_policy.PolicyInput(
            release, staged, release_interpreter, staged_argv
        )
        self.assertEqual(sandbox_policy.judge(staged_item).problems, ())
        staged_shown = " ".join(
            f"{record.role} {record.mode}"
            for record in sandbox_policy.normalize(staged_item)
        )
        self.assertNotIn("/tmp", staged_shown)
        self.assertIn("release staging writable", staged_shown)

    def test_planted_mount_mismatches_name_the_role(self) -> None:
        world = _item("build-world")
        release = _item("build-release")
        cache = str(world.layout.cache)
        extensions = str(world.layout.extensions)
        plants = [
            (
                _replace(list(world.argv), cache, "--bind-fd"),
                world,
                ["public cache: mode writable, expected read-only"],
            ),
            (
                _drop_bind(list(world.argv), cache),
                world,
                ["public cache: missing, expected read-only"],
            ),
            (
                _insert(list(world.argv), ["--ro-bind", "/w/repo", "/w/repo"]),
                world,
                ["checkout: extra path-read-only mount, expected absent"],
            ),
            (
                _drop_option(list(world.argv), "--remount-ro", extensions),
                world,
                ["extension sealing: missing, expected sealed"],
            ),
            (
                _insert(
                    list(release.argv),
                    ["--ro-bind-fd", "30", "/scenario/scenario.bin"],
                ),
                release,
                ["scenario: extra read-only mount, expected absent"],
            ),
            (
                _insert(
                    list(world.argv),
                    ["--bind-fd", "30", "/w/repo/data/releases/.staging/b1"],
                ),
                world,
                ["release staging: extra writable mount, expected absent"],
            ),
            (
                _without(list(world.argv), "--unshare-net"),
                world,
                ["network: missing, expected unshared"],
            ),
        ]
        for argv, item, want in plants:
            judged = sandbox_policy.judge(
                sandbox_policy.PolicyInput(
                    item.profile, item.layout, item.interpreter, argv
                )
            )
            self.assertEqual(list(judged.problems), want)

    def test_profile_flags_are_not_the_policy(self) -> None:
        item = _item("build-world")
        flipped = tables.Profile("build-world", staging=False, scenario=False)
        problems = sandbox_policy.judge(
            sandbox_policy.PolicyInput(
                flipped, item.layout, item.interpreter, list(item.argv)
            )
        ).problems
        self.assertEqual(
            list(problems), ["scenario: declared absent, expected present"]
        )

    def test_mount_order_is_part_of_the_policy(self) -> None:
        item = _item("build-world")
        argv = _swap_env(list(item.argv), "HOME", "PYTHONDONTWRITEBYTECODE")
        problems = sandbox_policy.judge(
            sandbox_policy.PolicyInput(
                item.profile, item.layout, item.interpreter, argv
            )
        ).problems
        self.assertEqual(
            list(problems), ["mount order: differs, expected the policy order"]
        )

    def test_parse_edges_name_the_role(self) -> None:
        item = _item("build-world")
        argv = list(item.argv)
        program = "/w/repo/.venv/bin/python"
        command_at = argv.index(program)
        home_at = argv.index("/tmp")
        wrong_home = list(argv)
        wrong_home[home_at] = "/elsewhere"
        bytecode_at = argv.index("1")
        wrong_bytecode = list(argv)
        wrong_bytecode[bytecode_at] = "0"
        path_at = argv.index("/w/repo/.venv/bin")
        wrong_path = list(argv)
        wrong_path[path_at] = "/elsewhere/bin"
        profile_at = argv.index("build-world")
        wrong_profile = list(argv)
        wrong_profile[profile_at] = "build-other"
        cache = str(item.layout.cache)
        cache_at = argv.index(cache)
        bad_fd = list(argv)
        bad_fd[cache_at - 1] = "nope"
        plants = [
            ([], ["bubblewrap: missing, expected present"]),
            (
                ["/usr/bin/other", *argv[1:]],
                ["bubblewrap: missing, expected present"],
            ),
            (argv[:command_at], ["program: missing, expected present"]),
            (
                [*argv[:command_at], "--setenv"],
                ["argument list: truncated, expected a complete operation"],
            ),
            (wrong_home, ["home: mode other, expected scratch"]),
            (wrong_bytecode, ["bytecode: mode other, expected off"]),
            (
                wrong_path,
                ["interpreter path: mode other, expected virtual environment"],
            ),
            (wrong_profile, ["profile name: mode other, expected build-world"]),
            (
                _insert(argv, ["--setenv", "EXTRA", "1"]),
                ["environment: extra set mount, expected absent"],
            ),
            (
                _replace_after(argv, "--chdir", "/elsewhere"),
                ["working directory: mode other, expected scratch"],
            ),
            (
                _drop_option(argv, "--remount-ro", "/"),
                ["root sealing: missing, expected sealed"],
            ),
            (bad_fd, ["public cache: mode other, expected read-only"]),
            (
                _insert(argv, ["--proc", "/proc"]),
                ["proc: extra mounted mount, expected absent"],
            ),
            (
                _insert(argv, ["--perms", "755"]),
                ["unrecognised operation: extra --perms mount, expected absent"],
            ),
            (
                _insert(argv, ["--not-a-real-option"]),
                [
                    "unrecognised operation: extra --not-a-real-option mount, expected absent"
                ],
            ),
            (
                _insert(
                    argv, ["--ro-bind", "/w/repo/product/src", "/w/repo/product/src"]
                ),
                ["checkout: extra path-read-only mount, expected absent"],
            ),
            (
                _insert(argv, ["--ro-bind-fd", "30", cache]),
                ["public cache: extra read-only mount, expected absent"],
            ),
            (
                _replace_after(argv, "--symlink", "elsewhere"),
                ["loader link: mode other, expected symlink"],
            ),
            (
                _replace_before(
                    argv, "/w/py/cpython-3.14-linux-x86_64-gnu", "elsewhere"
                ),
                ["interpreter alias: mode other, expected symlink"],
            ),
            (
                _insert(
                    argv,
                    [
                        "--ro-bind-fd",
                        "30",
                        "/w/repo/data/engine_extensions/v2.0.0/linux_amd64/nested/h3.duckdb_extension",
                    ],
                ),
                ["unrecognised: extra read-only mount, expected absent"],
            ),
        ]
        for planted, want in plants:
            judged = sandbox_policy.judge(
                sandbox_policy.PolicyInput(
                    item.profile, item.layout, item.interpreter, planted
                )
            )
            self.assertEqual(list(judged.problems), want, planted[:4])
        kept = [*argv[:command_at], "--", *argv[command_at:]]
        self.assertEqual(
            sandbox_policy.judge(
                sandbox_policy.PolicyInput(
                    item.profile, item.layout, item.interpreter, kept
                )
            ).problems,
            (),
        )
        release = _item("build-release")
        declared = tables.Profile("build-release", staging=True, scenario=True)
        problems = sandbox_policy.judge(
            sandbox_policy.PolicyInput(
                declared, release.layout, release.interpreter, list(release.argv)
            )
        ).problems
        self.assertEqual(
            list(problems), ["scenario: declared present, expected absent"]
        )
        unknown = tables.Profile("build-other", staging=False, scenario=False)
        unknown_problems = sandbox_policy.judge(
            sandbox_policy.PolicyInput(unknown, item.layout, item.interpreter, argv)
        ).problems
        self.assertEqual(
            list(unknown_problems)[:1],
            ["profile: extra build-other mount, expected absent"],
        )

    def test_unopenable_layout_is_a_mount_failure(self) -> None:
        layout = launch.Layout(
            Path("/missing/code"),
            Path("/missing/cache"),
            Path("/missing/vault"),
            Path("/missing/extensions"),
            None,
            Path("/missing/scenario"),
        )
        component = sandbox_check.mount_component("build-world", layout)
        self.assertTrue(component.problems)
        item = _item("build-world")

        def boom(*_args: object, **_kwargs: object) -> list[str]:
            raise launch.SandboxError("boom")

        with (
            patch.object(launch, "open_sources", lambda *_args, **_kwargs: {}),
            patch.object(launch, "build_argv", boom),
        ):
            failed = sandbox_check.mount_component(
                "build-world",
                launch.Layout(
                    item.layout.code_root,
                    item.layout.cache,
                    item.layout.vault,
                    item.layout.extensions,
                    None,
                    item.layout.scenario,
                ),
            )
        self.assertEqual(failed.problems, ("boom",))

    def test_policy_starts_no_process(self) -> None:
        text = Path(sandbox_policy.__file__).read_text(encoding="utf-8")
        self.assertNotIn("subprocess", text)
        self.assertNotIn("run_in_sandbox", text)
        self.assertNotIn("Popen", text)
        item = _item("build-release")
        self.assertEqual(sandbox_policy.judge(item).problems, ())


def _drop_bind(argv: list[str], destination: str) -> list[str]:
    index = argv.index(destination)
    found = list(argv)
    del found[index - 2 : index + 1]
    return found


def _insert(argv: list[str], tokens: list[str]) -> list[str]:
    index = argv.index("--chdir")
    return [*argv[:index], *tokens, *argv[index:]]


def _without(argv: list[str], token: str) -> list[str]:
    found = list(argv)
    found.remove(token)
    return found


def _replace_before(argv: list[str], destination: str, value: str) -> list[str]:
    found = list(argv)
    found[found.index(destination) - 1] = value
    return found


def _replace_after(argv: list[str], option: str, value: str) -> list[str]:
    found = list(argv)
    found[found.index(option) + 1] = value
    return found


def _swap_env(argv: list[str], left: str, right: str) -> list[str]:
    found = list(argv)
    left_at = found.index(left) - 1
    right_at = found.index(right) - 1
    left_tokens = found[left_at : left_at + 3]
    right_tokens = found[right_at : right_at + 3]
    found[left_at : left_at + 3] = right_tokens
    found[right_at : right_at + 3] = left_tokens
    return found
